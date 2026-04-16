/**
 * Polling Client
 *
 * Alternative to the SSE client that fetches the Activity Stream endpoint
 * at a configurable interval. Each request is a standard HTTP GET that
 * reads the response body, parses the JSON, and closes the connection
 * immediately — it does NOT hold an SSE stream open.
 *
 * Validates: Requirements 3.2, 3.3, 3.4, 3.5, 1.1
 */

export type RawEvent = unknown;

export interface PollingClientConfig {
  url: string;
  headers: Record<string, string>;
  interval: number; // Polling interval in ms
  onEvents: (events: RawEvent[]) => Promise<void>;
  onError: (error: Error) => void;
}

const DEFAULT_URL =
  'https://icybox.api.infiniteedgers.com/api/activity/stream?limit=20';

const DEFAULT_HEADERS: Record<string, string> = {
  Accept: 'text/event-stream',
  'Cache-Control': 'no-cache',
  Origin: 'https://www.icybox.io',
  Referer: 'https://www.icybox.io/',
  'User-Agent':
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
};

const DEFAULT_INTERVAL_MS = 30_000;
const DEFAULT_RETRY_AFTER_MS = 120_000;
const LOG_EVERY_N_REQUESTS = 100;

/**
 * Polling client that fetches the IcyBox activity stream at a configurable
 * interval. Handles HTTP 429 rate-limit responses by pausing for the
 * Retry-After duration (or 120s default). Logs request statistics every
 * 100 requests.
 */
export class PollingClient {
  private readonly config: PollingClientConfig;
  private running = false;
  private pollTimer: ReturnType<typeof setTimeout> | null = null;
  private abortController: AbortController | null = null;

  // Statistics tracking
  private requestCount = 0;
  private firstRequestTime: number | null = null;

  constructor(
    config: Partial<PollingClientConfig> &
      Pick<PollingClientConfig, 'onEvents' | 'onError'>
  ) {
    this.config = {
      url: config.url ?? DEFAULT_URL,
      headers: config.headers ?? DEFAULT_HEADERS,
      interval: config.interval ?? DEFAULT_INTERVAL_MS,
      onEvents: config.onEvents,
      onError: config.onError,
    };
  }

  /**
   * Starts the polling loop. The first poll fires immediately, then
   * subsequent polls fire at the configured interval.
   */
  start(): void {
    if (this.running) {
      return;
    }

    this.running = true;
    this.abortController = new AbortController();

    // Fire the first poll immediately
    void this.poll();
  }

  /**
   * Stops the polling loop and cancels any in-flight request.
   */
  stop(): void {
    this.running = false;

    if (this.pollTimer !== null) {
      clearTimeout(this.pollTimer);
      this.pollTimer = null;
    }

    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }
  }

  /**
   * Returns whether the polling loop is currently active.
   */
  isRunning(): boolean {
    return this.running;
  }

  /**
   * Executes a single poll: fetches the endpoint, reads the full response
   * body as text, parses JSON, delivers events, then schedules the next poll.
   */
  private async poll(): Promise<void> {
    if (!this.running) {
      return;
    }

    const now = Date.now();
    if (this.firstRequestTime === null) {
      this.firstRequestTime = now;
    }

    this.requestCount++;

    // Log statistics every LOG_EVERY_N_REQUESTS requests
    if (this.requestCount % LOG_EVERY_N_REQUESTS === 0) {
      this.logStats(now);
    }

    try {
      const response = await fetch(this.config.url, {
        method: 'GET',
        headers: this.config.headers,
        signal: this.abortController?.signal,
      });

      // Handle HTTP 429 rate limiting
      if (response.status === 429) {
        const retryAfter = this.parseRetryAfter(
          response.headers.get('Retry-After')
        );
        console.warn(
          `[polling-client] Rate limited (429). Pausing for ${retryAfter}ms`
        );
        this.config.onError(
          new Error(`HTTP 429: Too Many Requests`)
        );
        this.scheduleNext(retryAfter);
        return;
      }

      if (!response.ok) {
        let body = '';
        try {
          body = await response.text();
        } catch {
          // ignore read errors
        }
        console.error(
          `[polling-client] HTTP error ${response.status}: ${body}`
        );
        this.config.onError(
          new Error(`HTTP ${response.status}: ${body}`)
        );
        this.scheduleNext(this.config.interval);
        return;
      }

      // Read the full response body and close the connection (Req 3.3)
      const text = await response.text();

      let parsed: unknown;
      try {
        parsed = JSON.parse(text);
      } catch {
        console.warn(
          '[polling-client] Failed to parse response as JSON:',
          text.slice(0, 200)
        );
        this.scheduleNext(this.config.interval);
        return;
      }

      const events: RawEvent[] = Array.isArray(parsed) ? parsed : [parsed];

      await this.config.onEvents(events);
    } catch (err: unknown) {
      if (this.isAbortError(err)) {
        return;
      }
      const error = err instanceof Error ? err : new Error(String(err));
      console.error('[polling-client] Request failed:', error.message);
      this.config.onError(error);
    }

    this.scheduleNext(this.config.interval);
  }

  /**
   * Schedules the next poll after the given delay, respecting the running state.
   */
  private scheduleNext(delayMs: number): void {
    if (!this.running) {
      return;
    }

    this.pollTimer = setTimeout(() => {
      this.pollTimer = null;
      void this.poll();
    }, delayMs);
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
   * Logs total request count and average interval every 100 requests.
   */
  private logStats(now: number): void {
    const elapsed = now - (this.firstRequestTime ?? now);
    const avgInterval =
      this.requestCount > 1
        ? Math.round(elapsed / (this.requestCount - 1))
        : 0;

    console.log(
      `[polling-client] Stats: ${this.requestCount} requests, avg interval ${avgInterval}ms`
    );
  }

  /**
   * Checks whether an error is an AbortError (from AbortController).
   */
  private isAbortError(err: unknown): boolean {
    return err instanceof DOMException && err.name === 'AbortError';
  }
}
