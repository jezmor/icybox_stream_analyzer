import type { AccumulatedData, BoxTier, TierStats } from '../types.js';

const ALL_TIERS: readonly BoxTier[] = ['Bronze', 'Silver', 'Gold', 'Icy'] as const;

/**
 * Computes the distribution of events across box tiers.
 *
 * For each tier, calculates the count and percentage of total events.
 * Percentages are rounded to 2 decimal places.
 * Results are sorted by count in descending order.
 *
 * Validates: Requirements 4.1, 4.2, 4.3
 */
export function analyzeTiers(data: AccumulatedData): TierStats[] {
  const total = data.totalCount;

  const stats: TierStats[] = ALL_TIERS.map((tier) => {
    const events = data.byTier.get(tier);
    const count = events?.length ?? 0;
    const percentage = total > 0
      ? Math.round((count / total) * 100 * 100) / 100
      : 0;

    return { tier, count, percentage };
  });

  // Sort by count descending
  stats.sort((a, b) => b.count - a.count);

  return stats;
}
