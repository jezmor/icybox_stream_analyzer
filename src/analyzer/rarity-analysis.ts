import type { AccumulatedData, BoxTier, Rarity, RarityStats } from '../types.js';

const ALL_RARITIES: readonly Rarity[] = ['quartz', 'automatic', 'chronograph', 'tourbillon'] as const;
const ALL_TIERS: readonly BoxTier[] = ['Bronze', 'Silver', 'Gold', 'Icy'] as const;

/**
 * Computes the distribution of events across rarities, both overall and
 * broken down by box tier.
 *
 * For each rarity:
 * - totalCount / totalPercentage: count and percentage across all events
 * - byTier: count and percentage of that rarity within each individual tier
 *   (percentage is relative to the tier's total, not the overall total)
 *
 * Percentages are rounded to 2 decimal places.
 *
 * Validates: Requirements 5.1, 5.2, 5.3
 */
export function analyzeRarities(data: AccumulatedData): RarityStats[] {
  const total = data.totalCount;

  return ALL_RARITIES.map((rarity) => {
    const rarityEvents = data.byRarity.get(rarity);
    const totalCount = rarityEvents?.length ?? 0;
    const totalPercentage = total > 0
      ? Math.round((totalCount / total) * 100 * 100) / 100
      : 0;

    const byTier = new Map<BoxTier, { count: number; percentage: number }>();

    for (const tier of ALL_TIERS) {
      const tierEvents = data.byTier.get(tier);
      const tierTotal = tierEvents?.length ?? 0;

      // Count events in this tier that match the current rarity
      const count = tierEvents?.filter((e) => e.rarity === rarity).length ?? 0;

      const percentage = tierTotal > 0
        ? Math.round((count / tierTotal) * 100 * 100) / 100
        : 0;

      byTier.set(tier, { count, percentage });
    }

    return { rarity, totalCount, totalPercentage, byTier };
  });
}
