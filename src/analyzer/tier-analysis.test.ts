import { describe, it, expect } from 'vitest';
import { analyzeTiers } from './tier-analysis.js';
import type { AccumulatedData, BoxTier, StoredEvent, Rarity } from '../types.js';

function makeEvent(overrides: Partial<StoredEvent> = {}): StoredEvent {
  return {
    id: 'test-id',
    username: 'user1',
    platform: 'web',
    boxName: 'Bronze Box',
    boxSlug: 'bronze-box',
    itemName: 'Test Item',
    itemValue: 10,
    rarity: 'quartz' as Rarity,
    rarityColor: '#aaa',
    itemImageUrl: 'https://example.com/img.png',
    acquiredAt: new Date('2024-01-15T10:00:00Z'),
    collectedAt: new Date('2024-01-15T10:00:01Z'),
    ...overrides,
  };
}

function makeAccumulatedData(tierCounts: Partial<Record<BoxTier, number>>): AccumulatedData {
  const byTier = new Map<BoxTier, StoredEvent[]>();
  const allEvents: StoredEvent[] = [];
  let total = 0;

  for (const [tier, count] of Object.entries(tierCounts) as [BoxTier, number][]) {
    const events: StoredEvent[] = [];
    for (let i = 0; i < count; i++) {
      const event = makeEvent({ id: `${tier}-${i}`, boxName: `${tier} Box` });
      events.push(event);
      allEvents.push(event);
    }
    byTier.set(tier, events);
    total += count;
  }

  return {
    events: allEvents,
    byTier,
    byRarity: new Map(),
    byUser: new Map(),
    byHour: new Map(),
    dateRange: { min: new Date(0), max: new Date(0) },
    totalCount: total,
  };
}

describe('analyzeTiers', () => {
  it('computes count and percentage for each tier', () => {
    const data = makeAccumulatedData({ Bronze: 50, Silver: 30, Gold: 15, Icy: 5 });
    const result = analyzeTiers(data);

    expect(result).toHaveLength(4);

    const bronze = result.find((s) => s.tier === 'Bronze')!;
    expect(bronze.count).toBe(50);
    expect(bronze.percentage).toBe(50);

    const silver = result.find((s) => s.tier === 'Silver')!;
    expect(silver.count).toBe(30);
    expect(silver.percentage).toBe(30);

    const gold = result.find((s) => s.tier === 'Gold')!;
    expect(gold.count).toBe(15);
    expect(gold.percentage).toBe(15);

    const icy = result.find((s) => s.tier === 'Icy')!;
    expect(icy.count).toBe(5);
    expect(icy.percentage).toBe(5);
  });

  it('sorts results by count in descending order', () => {
    const data = makeAccumulatedData({ Bronze: 10, Silver: 50, Gold: 5, Icy: 35 });
    const result = analyzeTiers(data);

    expect(result[0].tier).toBe('Silver');
    expect(result[1].tier).toBe('Icy');
    expect(result[2].tier).toBe('Bronze');
    expect(result[3].tier).toBe('Gold');
  });

  it('rounds percentages to 2 decimal places', () => {
    // 3 events total: 1 Bronze, 1 Silver, 1 Gold → each 33.33%
    const data = makeAccumulatedData({ Bronze: 1, Silver: 1, Gold: 1 });
    const result = analyzeTiers(data);

    const bronze = result.find((s) => s.tier === 'Bronze')!;
    expect(bronze.percentage).toBe(33.33);

    const icy = result.find((s) => s.tier === 'Icy')!;
    expect(icy.count).toBe(0);
    expect(icy.percentage).toBe(0);
  });

  it('includes tiers with zero events', () => {
    const data = makeAccumulatedData({ Gold: 10 });
    const result = analyzeTiers(data);

    expect(result).toHaveLength(4);

    const bronze = result.find((s) => s.tier === 'Bronze')!;
    expect(bronze.count).toBe(0);
    expect(bronze.percentage).toBe(0);
  });

  it('handles empty data with no events', () => {
    const data = makeAccumulatedData({});
    const result = analyzeTiers(data);

    expect(result).toHaveLength(4);
    for (const stat of result) {
      expect(stat.count).toBe(0);
      expect(stat.percentage).toBe(0);
    }
  });

  it('percentages sum to approximately 100 when all tiers have events', () => {
    const data = makeAccumulatedData({ Bronze: 47, Silver: 23, Gold: 19, Icy: 11 });
    const result = analyzeTiers(data);

    const totalPercentage = result.reduce((sum, s) => sum + s.percentage, 0);
    expect(totalPercentage).toBeCloseTo(100, 0);
  });
});
