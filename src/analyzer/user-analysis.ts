import type { AccumulatedData, UserActivityStats } from '../types.js';

/**
 * Computes the median of a sorted array of numbers.
 * For even-length arrays, returns the average of the two middle elements.
 */
function median(sorted: number[]): number {
  const len = sorted.length;
  if (len === 0) return 0;
  const mid = Math.floor(len / 2);
  if (len % 2 === 1) {
    return sorted[mid]!;
  }
  return (sorted[mid - 1]! + sorted[mid]!) / 2;
}

/**
 * Analyzes user activity patterns from accumulated event data.
 *
 * - uniqueUsers: total number of distinct usernames
 * - openingsPerUser: min, max, mean, median of openings per unique user
 * - topUsers: top 10 most active users by opening count (descending)
 * - eventsPerHour: event counts per hour, sorted chronologically
 *
 * Validates: Requirements 7.1, 7.2, 7.3, 7.4
 */
export function analyzeUserActivity(data: AccumulatedData): UserActivityStats {
  // --- Unique users (Req 7.1) ---
  const uniqueUsers = data.byUser.size;

  // --- Openings per user distribution (Req 7.2) ---
  const counts = [...data.byUser.values()];
  let openingsPerUser: { min: number; max: number; mean: number; median: number };

  if (counts.length === 0) {
    openingsPerUser = { min: 0, max: 0, mean: 0, median: 0 };
  } else {
    const sorted = [...counts].sort((a, b) => a - b);
    const min = sorted[0]!;
    const max = sorted[sorted.length - 1]!;
    const sum = counts.reduce((acc, v) => acc + v, 0);
    const mean = sum / counts.length;
    const med = median(sorted);
    openingsPerUser = { min, max, mean, median: med };
  }

  // --- Top 10 most active users (Req 7.3) ---
  const userEntries = [...data.byUser.entries()].map(([username, count]) => ({
    username,
    count,
  }));
  userEntries.sort((a, b) => b.count - a.count);
  const topUsers = userEntries.slice(0, 10);

  // --- Events per hour (Req 7.4) ---
  const eventsPerHour = [...data.byHour.entries()]
    .map(([hour, count]) => ({ hour, count }))
    .sort((a, b) => a.hour.localeCompare(b.hour));

  return { uniqueUsers, openingsPerUser, topUsers, eventsPerHour };
}
