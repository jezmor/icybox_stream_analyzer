#!/usr/bin/env node

import { Command } from 'commander';
import { createReadStream, existsSync } from 'node:fs';
import { writeFile } from 'node:fs/promises';
import { createInterface } from 'node:readline';

import type { CollectOptions, AnalyzeOptions, IcyBoxEvent, StoredEvent, ReportData } from './types.js';
import { validateEvent } from './collector/event-parser.js';
import { Deduplicator } from './collector/deduplicator.js';
import { DataWriter } from './collector/data-writer.js';
import { SSEClient } from './collector/sse-client.js';
import { PollingClient } from './collector/polling-client.js';
import { DataReader } from './analyzer/data-reader.js';
import { accumulate } from './analyzer/stats-engine.js';
import { analyzeTiers } from './analyzer/tier-analysis.js';
import { analyzeRarities } from './analyzer/rarity-analysis.js';
import { analyzeValues } from './analyzer/value-analysis.js';
import { analyzeUserActivity } from './analyzer/user-analysis.js';
import { formatConsoleReport, formatCSVReport } from './analyzer/report-generator.js';

// ── CLI Setup ──

const program = new Command();

program
  .name('icybox')
  .version('1.0.0')
  .description('IcyBox Stream Analyzer — Collect and analyze IcyBox box-opening events');

// ── collect subcommand ──

program
  .command('collect')
  .description('Start collecting box-opening events from the IcyBox activity stream')
  .option('--data-file <path>', 'Path to the JSONL data file', './icybox-data.jsonl')
  .option('--mode <mode>', 'Connection mode: sse or polling', 'sse')
  .option('--interval <seconds>', 'Polling interval in seconds (polling mode only)', '30')
  .action(async (opts) => {
    const options: CollectOptions = {
      dataFile: opts.dataFile,
      mode: opts.mode as 'sse' | 'polling',
      interval: parseInt(opts.interval, 10),
    };

    if (options.mode !== 'sse' && options.mode !== 'polling') {
      console.error(`Invalid mode "${options.mode}". Must be "sse" or "polling".`);
      process.exit(1);
    }

    if (isNaN(options.interval) || options.interval <= 0) {
      console.error(`Invalid interval "${opts.interval}". Must be a positive number.`);
      process.exit(1);
    }

    await runCollect(options);
  });

// ── analyze subcommand ──

program
  .command('analyze')
  .description('Run statistical analysis on collected event data')
  .option('--data-file <path>', 'Path to the JSONL data file', './icybox-data.jsonl')
  .option('--export-csv <path>', 'Export analysis report as CSV to the given path')
  .action(async (opts) => {
    const options: AnalyzeOptions = {
      dataFile: opts.dataFile,
      exportCsv: opts.exportCsv,
    };

    await runAnalyze(options);
  });

program.parse();

// ── collect implementation ──

async function runCollect(options: CollectOptions): Promise<void> {
  console.log(`[icybox] Starting collector in ${options.mode} mode`);
  console.log(`[icybox] Data file: ${options.dataFile}`);

  // 1. Load existing event IDs from the data file into the Deduplicator
  const existingIds = await loadExistingIds(options.dataFile);
  const deduplicator = new Deduplicator(existingIds);
  console.log(`[icybox] Loaded ${deduplicator.size()} existing event IDs`);

  // 2. Set up the data writer
  const writer = new DataWriter(options.dataFile);

  // 3. Track new events for periodic logging
  let newEventCount = 0;
  let lastLogTime = Date.now();
  const LOG_INTERVAL_MS = 10_000; // Log every 10 seconds

  // 4. Build the event processing pipeline
  const processEvents = async (rawEvents: unknown[]): Promise<void> => {
    for (const raw of rawEvents) {
      const event: IcyBoxEvent | null = validateEvent(raw);
      if (event === null) {
        continue;
      }

      if (deduplicator.isDuplicate(event.id)) {
        continue;
      }

      // Add collectedAt timestamp and persist
      const stored: StoredEvent = {
        ...event,
        collectedAt: new Date(),
      };

      await writer.append(stored);
      deduplicator.add(event.id);
      newEventCount++;
    }

    // Periodic logging
    const now = Date.now();
    if (now - lastLogTime >= LOG_INTERVAL_MS) {
      console.log(`[icybox] ${newEventCount} new events persisted (${deduplicator.size()} total tracked)`);
      lastLogTime = now;
    }
  };

  // 5. Instantiate the appropriate client
  let disconnect: () => void;

  if (options.mode === 'sse') {
    const client = new SSEClient({
      onEvents: processEvents,
      onError: (err) => console.error('[icybox] SSE error:', err.message),
    });
    await client.connect();
    disconnect = () => client.disconnect();
    console.log('[icybox] SSE client connected');
  } else {
    const client = new PollingClient({
      interval: options.interval * 1000,
      onEvents: processEvents,
      onError: (err) => console.error('[icybox] Polling error:', err.message),
    });
    client.start();
    disconnect = () => client.stop();
    console.log(`[icybox] Polling client started (interval: ${options.interval}s)`);
  }

  // 6. Graceful shutdown on SIGINT / SIGTERM
  const shutdown = async () => {
    console.log('\n[icybox] Shutting down...');
    disconnect();
    await writer.close();
    console.log(`[icybox] Final count: ${newEventCount} new events persisted this session`);
    process.exit(0);
  };

  process.on('SIGINT', () => void shutdown());
  process.on('SIGTERM', () => void shutdown());
}

// ── analyze implementation ──

async function runAnalyze(options: AnalyzeOptions): Promise<void> {
  // 1. Check that the data file exists
  if (!existsSync(options.dataFile)) {
    console.error(`[icybox] Data file not found: ${options.dataFile}`);
    console.error('[icybox] Run "icybox collect" first to gather event data.');
    process.exit(1);
  }

  console.log(`[icybox] Analyzing data from: ${options.dataFile}`);

  // 2. Read all events via DataReader
  const reader = new DataReader(options.dataFile);

  // 3. Run the Stats Engine accumulator over all events
  const data = await accumulate(reader.readAll());

  if (data.totalCount === 0) {
    console.error('[icybox] No events found in the data file.');
    console.error('[icybox] Run "icybox collect" first to gather event data.');
    process.exit(1);
  }

  console.log(`[icybox] Loaded ${data.totalCount} events`);

  // 4. Run all four analysis modules
  const tierStats = analyzeTiers(data);
  const rarityStats = analyzeRarities(data);
  const valueAnalysis = analyzeValues(data);
  const userActivity = analyzeUserActivity(data);

  // 5. Compute the duration string from the date range
  const duration = formatDuration(data.dateRange.min, data.dateRange.max);

  // 6. Build the ReportData object
  const reportData: ReportData = {
    summary: {
      totalEvents: data.totalCount,
      dateRange: { start: data.dateRange.min, end: data.dateRange.max },
      duration,
    },
    tierStats,
    rarityStats,
    valueAnalysis,
    userActivity,
  };

  // 7. Output the console report to stdout
  const consoleReport = formatConsoleReport(reportData);
  console.log(consoleReport);

  // 8. If --export-csv is specified, write the CSV report
  if (options.exportCsv) {
    const csvReport = formatCSVReport(reportData);
    await writeFile(options.exportCsv, csvReport, 'utf-8');
    console.log(`[icybox] CSV report exported to: ${options.exportCsv}`);
  }
}

/**
 * Formats the duration between two dates as a human-readable string.
 * Examples: "2 hours 15 minutes", "3 days 5 hours", "45 minutes"
 */
function formatDuration(start: Date, end: Date): string {
  const diffMs = Math.abs(end.getTime() - start.getTime());
  const totalMinutes = Math.floor(diffMs / 60_000);
  const totalHours = Math.floor(totalMinutes / 60);
  const days = Math.floor(totalHours / 24);
  const hours = totalHours % 24;
  const minutes = totalMinutes % 60;

  const parts: string[] = [];
  if (days > 0) {
    parts.push(`${days} ${days === 1 ? 'day' : 'days'}`);
  }
  if (hours > 0) {
    parts.push(`${hours} ${hours === 1 ? 'hour' : 'hours'}`);
  }
  if (minutes > 0 || parts.length === 0) {
    parts.push(`${minutes} ${minutes === 1 ? 'minute' : 'minutes'}`);
  }

  return parts.join(' ');
}

// ── helpers ──

/**
 * Reads the JSONL data file line by line and extracts event IDs
 * for pre-populating the deduplicator.
 */
async function loadExistingIds(filePath: string): Promise<string[]> {
  if (!existsSync(filePath)) {
    return [];
  }

  const ids: string[] = [];
  const fileStream = createReadStream(filePath, { encoding: 'utf-8' });
  const rl = createInterface({
    input: fileStream,
    crlfDelay: Infinity,
  });

  try {
    for await (const line of rl) {
      const trimmed = line.trim();
      if (trimmed.length === 0) {
        continue;
      }

      try {
        const parsed = JSON.parse(trimmed) as { id?: string };
        if (parsed.id) {
          ids.push(parsed.id);
        }
      } catch {
        // Skip malformed lines
      }
    }
  } finally {
    rl.close();
    fileStream.destroy();
  }

  return ids;
}
