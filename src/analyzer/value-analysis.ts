import type {
  AccumulatedData,
  BoxTier,
  Rarity,
  StoredEvent,
  TopItem,
  ValueStats,
} from '../types.js';


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
 * Computes full value statistics (min, max, mean, median, stdDev) for a list
 * of numeric values. Returns undefined when the list is empty.
 */
function computeValueStats(values: number[]): ValueStats | undefined {
  if (values.length === 0) return undefined;

  const sorted = [...values].sort((a, b) => a - b);
  const min = sorted[0]!;
  const max = sorted[sorted.length - 1]!;
  const sum = values.reduce((acc, v) => acc + v, 0);
  const mean = sum / values.length;
  const med = median(sorted);

  // Population standard deviation: sqrt(sum((x - mean)^2) / count)
  const squaredDiffs = values.reduce((acc, v) => acc + (v - mean) ** 2, 0);
  const stdDev = Math.sqrt(squaredDiffs / values.length);

  return { min, max, mean, median: med, stdDev };
}

/**
 * Computes value statistics without standard deviation, used for per-rarity
 * breakdowns. Returns undefined when the list is empty.
 */
function computeBasicValueStats(
  values: number[],
): Omit<ValueStats, 'stdDev'> | undefined {
  if (values.length === 0) return undefined;

  const sorted = [...values].sort((a, b) => a - b);
  const min = sorted[0]!;
  const max = sorted[sorted.length - 1]!;
  const sum = values.reduce((acc, v) => acc + v, 0);
  const mean = sum / values.length;
  const med = median(sorted);

  return { min, max, mean, median: med };
}

/**
 * Extracts itemValue numbers from an array of StoredEvents.
 */
function extractValues(events: StoredEvent[]): number[] {
  return events.map((e) => e.itemValue);
}

/**
 * Identifies the top 10 most frequently awarded items across all events.
 * Items are grouped by name. For each item, the rarity and value are taken
 * from the first occurrence (they should be consistent across events).
 *
 * Results are sorted by count descending, then by item name ascending for
 * stable ordering among ties.
 */
function findTopItems(events: StoredEvent[]): TopItem[] {
  const itemMap = new Map<string, { count: number; rarity: Rarity; itemValue: number }>();

  for (const event of events) {
    const existing = itemMap.get(event.itemName);
    if (existing !== undefined) {
      existing.count++;
    } else {
      itemMap.set(event.itemName, {
        count: 1,
        rarity: event.rarity,
        itemValue: event.itemValue,
      });
    }
  }

  const items: TopItem[] = [];
  for (const [itemName, info] of itemMap) {
    items.push({
      itemName,
      count: info.count,
      rarity: info.rarity,
      itemValue: info.itemValue,
    });
  }

  // Sort by count descending, then by name ascending for stable ordering
  items.sort((a, b) => b.count - a.count || a.itemName.localeCompare(b.itemName));

  return items.slice(0, 10);
}

/**
 * Analyzes item values across box tiers, rarities, and overall.
 *
 * - byTier: min, max, mean, median, stdDev of itemValue per Box Tier
 * - byRarity: min, max, mean, median of itemValue per Rarity (no stdDev)
 * - overall: expected value (mean itemValue) across all events
 * - topItems: top 10 most frequently awarded items with count, rarity, value
 *
 * Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5
 */
export function analyzeValues(data: AccumulatedData): {
  byTier: Map<BoxTier, ValueStats>;
  byRarity: Map<Rarity, Omit<ValueStats, 'stdDev'>>;
  overall: { expectedValue: number };
  topItems: TopItem[];
} {
  // --- Per-tier value stats (Req 6.1, 6.4) ---
  const byTier = new Map<BoxTier, ValueStats>();
  for (const [tier, tierEvents] of data.byTier) {
    if (tierEvents.length > 0) {
      const stats = computeValueStats(extractValues(tierEvents));
      if (stats !== undefined) {
        byTier.set(tier, stats);
      }
    }
  }

  // --- Per-rarity value stats (Req 6.2) ---
  const byRarity = new Map<Rarity, Omit<ValueStats, 'stdDev'>>();
  for (const [rarity, rarityEvents] of data.byRarity) {
    if (rarityEvents.length > 0) {
      const stats = computeBasicValueStats(extractValues(rarityEvents));
      if (stats !== undefined) {
        byRarity.set(rarity, stats);
      }
    }
  }

  // --- Overall expected value (Req 6.3) ---
  const allValues = extractValues(data.events);
  const expectedValue = allValues.length > 0
    ? allValues.reduce((acc, v) => acc + v, 0) / allValues.length
    : 0;

  // --- Top 10 items (Req 6.5) ---
  const topItems = findTopItems(data.events);

  return { byTier, byRarity, overall: { expectedValue }, topItems };
}
