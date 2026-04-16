import { createWriteStream, type WriteStream } from 'node:fs';
import { open } from 'node:fs/promises';
import type { StoredEvent } from '../types.js';

/**
 * Appends StoredEvent objects as JSON Lines to a file.
 * Creates the file if it does not exist.
 */
export class DataWriter {
  private stream: WriteStream | null = null;
  private readonly filePath: string;

  constructor(filePath: string) {
    this.filePath = filePath;
  }

  /**
   * Ensures the write stream is open, creating the file if needed.
   */
  private async ensureStream(): Promise<WriteStream> {
    if (this.stream) {
      return this.stream;
    }

    // Open with 'a' flag to append, creating the file if it doesn't exist
    const handle = await open(this.filePath, 'a');
    await handle.close();

    this.stream = createWriteStream(this.filePath, { flags: 'a' });

    return this.stream;
  }

  /**
   * Appends a StoredEvent as a single JSON line to the file.
   * Date fields are serialized as ISO 8601 strings.
   */
  async append(event: StoredEvent): Promise<void> {
    const stream = await this.ensureStream();
    const line = JSON.stringify(event) + '\n';

    return new Promise<void>((resolve, reject) => {
      const ok = stream.write(line, 'utf-8', (err) => {
        if (err) {
          reject(err);
        } else {
          resolve();
        }
      });

      if (!ok) {
        stream.once('drain', () => {
          // Already resolved/rejected via the write callback
        });
      }
    });
  }

  /**
   * Closes the underlying write stream.
   */
  async close(): Promise<void> {
    if (!this.stream) {
      return;
    }

    const stream = this.stream;
    this.stream = null;

    return new Promise<void>((resolve, reject) => {
      stream.on('error', reject);
      stream.end(() => {
        resolve();
      });
    });
  }
}
