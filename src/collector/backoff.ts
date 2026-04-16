/**
 * Backoff Calculator
 *
 * Pure function for computing exponential backoff delays.
 * Backoff doubles on each consecutive failure, capped at a maximum delay.
 *
 * Example with initialDelay=5000, maxDelay=60000:
 *   attempt 0 → 5000ms
 *   attempt 1 → 10000ms
 *   attempt 2 → 20000ms
 *   attempt 3 → 40000ms
 *   attempt 4 → 60000ms (capped)
 */

/**
 * Calculates the backoff delay for a given retry attempt using
 * exponential backoff with a configurable cap.
 *
 * @param attempt - Zero-based retry attempt number (0 = first retry)
 * @param initialDelay - Base delay in milliseconds (e.g. 5000)
 * @param maxDelay - Maximum delay cap in milliseconds (e.g. 60000)
 * @returns The backoff delay in milliseconds
 *
 * Validates: Requirements 1.3, 1.5, 3.1
 */
export function calculateBackoff(
  attempt: number,
  initialDelay: number,
  maxDelay: number
): number {
  const delay = initialDelay * Math.pow(2, attempt);
  return Math.min(delay, maxDelay);
}
