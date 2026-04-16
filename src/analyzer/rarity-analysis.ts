import type { AccumulatedData, BoxTier, RarityStats } from '../types.js';

/**
 * Computes the distribution of events across rarities, both overall and
 * broken down by box tier. Derives all tiers and rarities from the data.
 */
export function analyzeRarities(data: AccumulatedData): RarityStats[] {
  const total = data.totalCount;
  const tiers = [...data.byTier.keys()];

  return [...data.byRarity.keys()].map((rarity) => {
    const rarityEvents = data.byRarity.get(rarity);
    const totalCount = rarityEvents?.length ?? 0;
    const totalPercentage = total > 0
      ? Math.round((totalCount / total) * 100 * 100) / 100
      : 0;

    const byTier = new Map<BoxTier, { count: number; percentage: number }>();

    for (const tier of tiers) {
      const tierEvents = data.byTier.get(tier);
      const tierTotal = tierEvents?.length ?? 0;
      const count = tierEvents?.filter((e) => e.rarity === rarity).length ?? 0;
      const percentage = tierTotal > 0
        ? Math.round((count / tierTotal) * 100 * 100) / 100
        : 0;
      byTier.set(tier, { count, percentage });
    }

    return { rarity, totalCount, totalPercentage, byTier };
  });
}
