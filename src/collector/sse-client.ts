import { createParser, type EventSourceParser } from 'eventsource-parser';
import { calculateBackoff } from './backoff.js';

/**
 * Raw event object as received from the SSE stream before validation.
 */
export type RawEvent = unknown;

export interface SSEClientConfig {
  url: string;
  headers: Record<string, string>;
  onEvents: (events: RawEvent[]) => Promise<void>;
  onError: (error: Error) => void;
  initialBackoff: number;
  maxBackoff: number;
}

const DEFAULT_URL = 'https://icybox.api.infiniteedgers.com/api/activity/stream?limit=20';

const DEFAULT_HEADERS: Record<string, string> = {
  'Accept': 'text/event-stream',
  'Cache-Control': 'no-cache',
  'Origin': 'https://www.icybox.io',
  'Referer': 'https://www.icybox.io/',
  'User-Agent':
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
};

const DEFAULT_RETRY_AFTER_MS = 120_000;

/**
 * SSE client that connects to the IcyBox activity stream using fetch and
 * eventsource-parser. Handles reconnection with exponential backoff and
 * HTTP 429 rate-limit responses.
 */
export class SSEClient {
  private readonly config: SSEClientConfig;
  private abortController: AbortController | null = null;
  private connected = false;
  private reconnecting = false;
  private attempt = 0;

  constructor(config: Partial<SSEClientConfig> & Pick<SSEClientConfig, 'onEvents' | 'onError'>) {
    this.config = {
      url: config.url ?? DEFAULT_URL,
      headers: config.headers ?? DEFAULT_HEADERS,
      onEvents: config.onEvents,
      onError: config.onError,
      initialBackoff: config.initialBackoff ?? 5000,
      maxBackoff: config.maxBackoff ?? 60000,
    };
  }

  /**
   * Opens the SSE connection and begins piping data through the parser.
   * Resolves once the initial connection is established (response received).
   * The connection stays open and events arrive continuously.
   */
  async connect(): Promise<void> {
    if (this.connected) {
      return;
    }

    this.abortController = new AbortController();
    await this.startConnection();
  }

  /**
   * Aborts the active connection and stops any pending reconnection.
   */
  disconnect(): void {
    this.connected = false;
    this.reconnecting = false;
    this.attempt = 0;

    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }
  }

  /**
   * Returns whether the client currently has an active connection.
   */
  isConnected(): boolean {
    return this.connected;
  }

  /**
   * Internal: opens a fetch-based SSE connection and reads the stream.
   */
  private async startConnection(): Promise<void> {
    const { url, headers, onEvents, onError } = this.config;

    const parser: EventSourceParser = createParser({
      onEvent: (event) => {
        // Each SSE event's data field should be a JSON array of raw events
        let parsed: unknown;
        try {
          parsed = JSON.parse(event.data);
        } catch {
          console.warn('[sse-client] Failed to parse event data as JSON:', event.data);
          return;
        }

        const events: RawEvent[] = Array.isArray(parsed) ? parsed : [parsed];
        onEvents(events).catch((err: unknown) => {
          console.error('[sse-client] onEvents callback error:', err);
        });
      },
      onError: (parseError) => {
        console.warn('[sse-client] SSE parse error:', parseError.message);
      },
    });

    let response: Response;
    try {
      response = await fetch(url, {
        method: 'GET',
        headers,
        signal: this.abortController?.signal,
      });
    } catch (err: unknown) {
      if (this.isAbortError(err)) {
        return;
      }
      const error = err instanceof Error ? err : new Error(String(err));
      console.error('[sse-client] Connection failed:', error.message);
      onError(error);
      await this.scheduleReconnect();
      return;
    }

    // Handle HTTP errors
    if (!response.ok) {
      const status = response.status;
      let body = '';
      try {
        body = await response.text();
      } catch {
        // ignore read errors
      }

      console.error(`[sse-client] HTTP error ${status}: ${body}`);
      onError(new Error(`HTTP ${status}: ${body}`));

      // Handle 429 rate limiting
      if (status === 429) {
        const retryAfter = this.parseRetryAfter(response.headers.get('Retry-After'));
        console.warn(`[sse-client] Rate limited (429). Pausing for ${retryAfter}ms`);
        await this.sleep(retryAfter);
      }

      await this.scheduleReconnect();
      return;
    }

    // Connection established successfully — reset backoff
    this.connected = true;
    this.attempt = 0;

    if (!response.body) {
      console.error('[sse-client] Response has no body');
      onError(new Error('Response has no body'));
      this.connected = false;
      await this.scheduleReconnect();
      return;
    }

    // Read the stream
    try {
      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          break;
        }
        const text = decoder.decode(value, { stream: true });
        parser.feed(text);
      }
    } catch (err: unknown) {
      if (this.isAbortError(err)) {
        return;
      }
      const error = err instanceof Error ? err : new Error(String(err));
      console.error('[sse-client] Stream read error:', error.message);
      onError(error);
    }

    // Stream ended or errored — reconnect if still supposed to be connected
    this.connected = false;
    parser.reset();
    await this.scheduleReconnect();
  }

  /**
   * Schedules a reconnection attempt using exponential backoff.
   */
  private async scheduleReconnect(): Promise<void> {
    // Don't reconnect if we've been explicitly disconnected
    if (!this.abortController || this.abortController.signal.aborted) {
      return;
    }

    this.reconnecting = true;
    const delay = calculateBackoff(this.attempt, this.config.initialBackoff, this.config.maxBackoff);
    this.attempt++;

    console.log(`[sse-client] Reconnecting in ${delay}ms (attempt ${this.attempt})`);
    await this.sleep(delay);

    // Check again after sleeping — user may have called disconnect()
    if (!this.abortController || this.abortController.signal.aborted) {
      this.reconnecting = false;
      return;
    }

    this.reconnecting = false;
    await this.startConnection();
  }

  /**
   * Parses the Retry-After header value into milliseconds.
   * Falls back to DEFAULT_RETRY_AFTER_MS (120s) if absent or unparseable.
   */
  private parseRetryAfter(headerValue: string | null): number {
    if (!headerValue) {
      return DEFAULT_RETRY_AFTER_MS;
    }

    // Try parsing as seconds (integer)
    const seconds = parseInt(headerValue, 10);
    if (!isNaN(seconds) && seconds > 0) {
      return seconds * 1000;
    }

    // Try parsing as HTTP-date
    const date = new Date(headerValue);
    if (!isNaN(date.getTime())) {
      const delayMs = date.getTime() - Date.now();
      return delayMs > 0 ? delayMs : DEFAULT_RETRY_AFTER_MS;
    }

    return DEFAULT_RETRY_AFTER_MS;
  }

  /**
   * Sleeps for the given duration, respecting abort signals.
   */
  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => {
      const timer = setTimeout(resolve, ms);

      // If the abort controller fires while we're sleeping, resolve early
      const onAbort = () => {
        clearTimeout(timer);
        resolve();
      };

      if (this.abortController) {
        this.abortController.signal.addEventListener('abort', onAbort, { once: true });
      }
    });
  }

  /**
   * Checks whether an error is an AbortError (from AbortController).
   */
  private isAbortError(err: unknown): boolean {
    return err instanceof DOMException && err.name === 'AbortError';
  }
}
