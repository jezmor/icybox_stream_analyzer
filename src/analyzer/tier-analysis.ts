import type { AccumulatedData, TierStats } from '../types.js';

/**
 * Computes the distribution of events across box tiers.
 *
 * Derives tiers dynamically from the data — no hardcoded list.
 * Percentages are rounded to 2 decimal places.
 * Results are sorted by count in descending order.
 */
export function analyzeTiers(data: AccumulatedData): TierStats[] {
  const total = data.totalCount;

  const stats: TierStats[] = [...data.byTier.entries()].map(([tier, events]) => {
    const count = events.length;
    const percentage = total > 0
      ? Math.round((count / total) * 100 * 100) / 100
      : 0;
    return { tier, count, percentage };
  });

  stats.sort((a, b) => b.count - a.count);

  return stats;
}
