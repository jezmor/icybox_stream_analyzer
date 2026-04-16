import { describe, it, expect } from 'vitest';
import type {
  BoxTier,
  Rarity,
  IcyBoxEvent,
  StoredEvent,
  CLIOptions,
  CollectOptions,
  AnalyzeOptions,
  AccumulatedData,
  TierStats,
  RarityStats,
  ValueStats,
  TopItem,
  UserActivityStats,
  ParseResult,
  ReportData,
} from './types.js';

describe('types', () => {
  it('should allow valid BoxTier values', () => {
    const tiers: BoxTier[] = ['Bronze', 'Silver', 'Gold', 'Icy'];
    expect(tiers).toHaveLength(4);
  });

  it('should allow valid Rarity values', () => {
    const rarities: Rarity[] = ['quartz', 'automatic', 'chronograph', 'tourbillon'];
    expect(rarities).toHaveLength(4);
  });

  it('should construct a valid IcyBoxEvent', () => {
    const event: IcyBoxEvent = {
      id: 'abc123',
      username: 'player1',
      platform: 'web',
      boxName: 'Gold Box',
      boxSlug: 'gold-box',
      itemName: 'Diamond Watch',
      itemValue: 150.5,
      rarity: 'chronograph',
      rarityColor: '#FFD700',
      itemImageUrl: 'https://example.com/watch.png',
      acquiredAt: new Date('2024-01-15T10:30:00.000Z'),
    };
    expect(event.id).toBe('abc123');
    expect(event.itemValue).toBe(150.5);
    expect(event.rarity).toBe('chronograph');
  });

  it('should construct a valid StoredEvent extending IcyBoxEvent', () => {
    const event: StoredEvent = {
      id: 'abc123',
      username: 'player1',
      platform: 'web',
      boxName: 'Gold Box',
      boxSlug: 'gold-box',
      itemName: 'Diamond Watch',
      itemValue: 150.5,
      rarity: 'chronograph',
      rarityColor: '#FFD700',
      itemImageUrl: 'https://example.com/watch.png',
      acquiredAt: new Date('2024-01-15T10:30:00.000Z'),
      collectedAt: new Date('2024-01-15T10:30:05.123Z'),
    };
    expect(event.collectedAt).toBeInstanceOf(Date);
  });

  it('should construct valid CLIOptions', () => {
    const opts: CLIOptions = { dataFile: './icybox-data.jsonl' };
    expect(opts.dataFile).toBe('./icybox-data.jsonl');
  });

  it('should construct valid CollectOptions', () => {
    const opts: CollectOptions = {
      dataFile: './icybox-data.jsonl',
      mode: 'sse',
      interval: 30,
    };
    expect(opts.mode).toBe('sse');
    expect(opts.interval).toBe(30);
  });

  it('should construct valid AnalyzeOptions', () => {
    const opts: AnalyzeOptions = {
      dataFile: './icybox-data.jsonl',
      exportCsv: './report.csv',
    };
    expect(opts.exportCsv).toBe('./report.csv');
  });

  it('should allow AnalyzeOptions without exportCsv', () => {
    const opts: AnalyzeOptions = { dataFile: './icybox-data.jsonl' };
    expect(opts.exportCsv).toBeUndefined();
  });
});
