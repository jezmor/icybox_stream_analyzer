#!/usr/bin/env node

import { Command } from 'commander';
import { createReadStream, existsSync } from 'node:fs';
import { createInterface } from 'node:readline';

import type { CollectOptions, IcyBoxEvent, StoredEvent } from './types.js';
import { validateEvent } from './collector/event-parser.js';
import { Deduplicator } from './collector/deduplicator.js';
import { DataWriter } from './collector/data-writer.js';
import { SSEClient } from './collector/sse-client.js';
import { PollingClient } from './collector/polling-client.js';

// ── CLI Setup ──

const program = new Command();

program
  .name('icybox')
  .version('3.0.0')
  .description('IcyBox Stream Collector — Collect box-opening events from the IcyBox activity stream');

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

  // 2b. Set up the bad event writer — rejected events go here so nothing is lost
  const badEventFile = options.dataFile.replace(/\.jsonl$/, '-rejected.jsonl');
  const badWriter = new DataWriter(badEventFile);
  let badEventCount = 0;

  // 3. Track new events for periodic logging
  let newEventCount = 0;
  let lastLogTime = Date.now();
  const LOG_INTERVAL_MS = 10_000; // Log every 10 seconds

  // 4. Build the event processing pipeline
  const processEvents = async (rawEvents: unknown[]): Promise<void> => {
    for (const raw of rawEvents) {
      const event: IcyBoxEvent | null = validateEvent(raw);
      if (event === null) {
        // Persist rejected event so nothing is lost
        const rejected = { raw, rejectedAt: new Date().toISOString(), reason: 'failed validation' };
        await badWriter.append(rejected as unknown as StoredEvent);
        badEventCount++;
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
    await badWriter.close();
    console.log(`[icybox] Final count: ${newEventCount} new events persisted this session`);
    if (badEventCount > 0) {
      console.log(`[icybox] ${badEventCount} rejected events saved to ${badEventFile}`);
    }
    process.exit(0);
  };

  process.on('SIGINT', () => void shutdown());
  process.on('SIGTERM', () => void shutdown());
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
