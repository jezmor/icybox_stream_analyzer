import { createReadStream } from 'node:fs';
import { createInterface } from 'node:readline';
import type { StoredEvent } from '../types.js';

/**
 * Streams and parses a JSONL file line by line, yielding StoredEvent objects.
 * Date fields (acquiredAt, collectedAt) are revived from ISO 8601 strings.
 */
export class DataReader {
  private readonly filePath: string;

  constructor(filePath: string) {
    this.filePath = filePath;
  }

  /**
   * Streams the JSONL file line by line, parsing each line into a StoredEvent.
   * Skips empty lines. Date fields are converted from ISO strings back to Date objects.
   */
  async *readAll(): AsyncIterable<StoredEvent> {
    const fileStream = createReadStream(this.filePath, { encoding: 'utf-8' });
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

        const parsed = JSON.parse(trimmed) as Record<string, unknown>;

        // Revive Date fields from ISO 8601 strings
        if (typeof parsed.acquiredAt === 'string') {
          parsed.acquiredAt = new Date(parsed.acquiredAt);
        }
        if (typeof parsed.collectedAt === 'string') {
          parsed.collectedAt = new Date(parsed.collectedAt);
        }

        yield parsed as unknown as StoredEvent;
      }
    } finally {
      rl.close();
      fileStream.destroy();
    }
  }

  /**
   * Returns the total number of events in the JSONL file.
   * Counts non-empty lines.
   */
  async count(): Promise<number> {
    const fileStream = createReadStream(this.filePath, { encoding: 'utf-8' });
    const rl = createInterface({
      input: fileStream,
      crlfDelay: Infinity,
    });

    let total = 0;

    try {
      for await (const line of rl) {
        if (line.trim().length > 0) {
          total++;
        }
      }
    } finally {
      rl.close();
      fileStream.destroy();
    }

    return total;
  }
}
