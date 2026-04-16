import type { AccumulatedData, BoxTier, StoredEvent } from '../types.js';

/**
 * Extracts the BoxTier from a box name string.
 * Strips " Box" suffix if present (e.g., "Gold Box" → "Gold", "Ice Box" → "Ice").
 * Maps known aliases (e.g., "Ice" → "Icy").
 */
function extractTier(boxName: string): BoxTier {
  let tier = boxName.replace(/\s*Box$/i, '').trim();
  // API sends "Ice Box" for the Icy tier
  if (tier === 'Ice') {
    tier = 'Icy';
  }
  return tier;
}

/**
 * Formats a Date into an ISO hour string for hourly grouping.
 * Example: 2024-01-15T10:30:00Z → "2024-01-15T10"
 */
function toHourKey(date: Date): string {
  const iso = date.toISOString();
  // "2024-01-15T10:30:00.000Z" → "2024-01-15T10"
  return iso.slice(0, 13);
}

/**
 * Single-pass accumulator that builds all aggregation structures from an
 * async iterable of StoredEvent objects.
 *
 * Validates: Requirements 4.1, 5.1, 6.1, 7.1
 */
export async function accumulate(
  events: AsyncIterable<StoredEvent>,
): Promise<AccumulatedData> {
  const allEvents: StoredEvent[] = [];
  const byTier = new Map<BoxTier, StoredEvent[]>();
  const byRarity = new Map<StoredEvent['rarity'], StoredEvent[]>();
  const byUser = new Map<string, number>();
  const byHour = new Map<string, number>();

  let minDate: Date | undefined;
  let maxDate: Date | undefined;
  let totalCount = 0;

  for await (const event of events) {
    totalCount++;
    allEvents.push(event);

    // --- byTier ---
    const tier = extractTier(event.boxName);
    const tierEvents = byTier.get(tier);
    if (tierEvents !== undefined) {
      tierEvents.push(event);
    } else {
      byTier.set(tier, [event]);
    }

    // --- byRarity ---
    const rarityEvents = byRarity.get(event.rarity);
    if (rarityEvents !== undefined) {
      rarityEvents.push(event);
    } else {
      byRarity.set(event.rarity, [event]);
    }

    // --- byUser ---
    byUser.set(event.username, (byUser.get(event.username) ?? 0) + 1);

    // --- byHour ---
    const hourKey = toHourKey(event.acquiredAt);
    byHour.set(hourKey, (byHour.get(hourKey) ?? 0) + 1);

    // --- dateRange ---
    const eventDate = event.acquiredAt;
    if (minDate === undefined || eventDate < minDate) {
      minDate = eventDate;
    }
    if (maxDate === undefined || eventDate > maxDate) {
      maxDate = eventDate;
    }
  }

  return {
    events: allEvents,
    byTier,
    byRarity,
    byUser,
    byHour,
    dateRange: {
      min: minDate ?? new Date(0),
      max: maxDate ?? new Date(0),
    },
    totalCount,
  };
}
