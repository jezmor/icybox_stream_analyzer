import { describe, it, expect, vi } from 'vitest';
import {
  parseEventPayload,
  validateEvent,
  parseItemValue,
  parseTimestamp,
} from './event-parser.js';

describe('parseItemValue', () => {
  it('returns a number as-is', () => {
    expect(parseItemValue(150.5)).toBe(150.5);
    expect(parseItemValue(0)).toBe(0);
    expect(parseItemValue(-10)).toBe(-10);
  });

  it('parses a numeric string', () => {
    expect(parseItemValue('150.50')).toBe(150.5);
    expect(parseItemValue('0')).toBe(0);
    expect(parseItemValue('99')).toBe(99);
  });

  it('strips leading $ sign', () => {
    expect(parseItemValue('$1.50')).toBe(1.5);
    expect(parseItemValue('$100')).toBe(100);
  });

  it('returns NaN for non-numeric strings', () => {
    expect(parseItemValue('abc')).toBeNaN();
    expect(parseItemValue('')).toBeNaN();
  });
});

describe('parseTimestamp', () => {
  it('parses valid ISO 8601 timestamps', () => {
    const date = parseTimestamp('2024-01-15T10:30:00.000Z');
    expect(date).toBeInstanceOf(Date);
    expect(date!.toISOString()).toBe('2024-01-15T10:30:00.000Z');
  });

  it('parses ISO 8601 without milliseconds', () => {
    const date = parseTimestamp('2024-01-15T10:30:00Z');
    expect(date).toBeInstanceOf(Date);
  });

  it('parses date-only ISO 8601', () => {
    const date = parseTimestamp('2024-01-15');
    expect(date).toBeInstanceOf(Date);
  });

  it('parses ISO 8601 with timezone offset', () => {
    const date = parseTimestamp('2024-01-15T10:30:00+05:30');
    expect(date).toBeInstanceOf(Date);
  });

  it('returns null for invalid timestamps', () => {
    expect(parseTimestamp('not-a-date')).toBeNull();
    expect(parseTimestamp('')).toBeNull();
    expect(parseTimestamp('Jan 15, 2024')).toBeNull();
  });
});

describe('validateEvent', () => {
  const validRaw = {
    id: 'abc123',
    username: 'player1',
    platform: 'web',
    boxName: 'Gold Box',
    boxSlug: 'gold-box',
    itemName: 'Diamond Watch',
    itemValue: '150.50',
    rarity: 'chronograph',
    rarityColor: '#FFD700',
    itemImageUrl: 'https://example.com/watch.png',
    acquiredAt: '2024-01-15T10:30:00.000Z',
  };

  it('returns a valid IcyBoxEvent for complete data', () => {
    const event = validateEvent(validRaw);
    expect(event).not.toBeNull();
    expect(event!.id).toBe('abc123');
    expect(event!.username).toBe('player1');
    expect(event!.itemValue).toBe(150.5);
    expect(event!.rarity).toBe('chronograph');
    expect(event!.acquiredAt).toBeInstanceOf(Date);
  });

  it('returns null for null input', () => {
    expect(validateEvent(null)).toBeNull();
  });

  it('returns null for non-object input', () => {
    expect(validateEvent('string')).toBeNull();
    expect(validateEvent(42)).toBeNull();
  });

  it('returns null when required fields are missing', () => {
    for (const field of ['id', 'username', 'boxName', 'itemName', 'itemValue', 'rarity', 'acquiredAt']) {
      const incomplete = { ...validRaw, [field]: undefined };
      expect(validateEvent(incomplete)).toBeNull();
    }
  });

  it('returns null for invalid rarity', () => {
    expect(validateEvent({ ...validRaw, rarity: 'legendary' })).toBeNull();
  });

  it('returns null for invalid acquiredAt', () => {
    expect(validateEvent({ ...validRaw, acquiredAt: 'not-a-date' })).toBeNull();
  });

  it('returns null for non-parseable itemValue', () => {
    expect(validateEvent({ ...validRaw, itemValue: 'abc' })).toBeNull();
  });

  it('defaults optional fields to empty strings', () => {
    const minimal = {
      id: 'abc123',
      username: 'player1',
      boxName: 'Gold Box',
      itemName: 'Diamond Watch',
      itemValue: 100,
      rarity: 'quartz',
      acquiredAt: '2024-01-15T10:30:00.000Z',
    };
    const event = validateEvent(minimal);
    expect(event).not.toBeNull();
    expect(event!.platform).toBe('');
    expect(event!.boxSlug).toBe('');
    expect(event!.rarityColor).toBe('');
    expect(event!.itemImageUrl).toBe('');
  });
});

describe('parseEventPayload', () => {
  const validEventJson = JSON.stringify([
    {
      id: 'abc123',
      username: 'player1',
      platform: 'web',
      boxName: 'Gold Box',
      boxSlug: 'gold-box',
      itemName: 'Diamond Watch',
      itemValue: '150.50',
      rarity: 'chronograph',
      rarityColor: '#FFD700',
      itemImageUrl: 'https://example.com/watch.png',
      acquiredAt: '2024-01-15T10:30:00.000Z',
    },
  ]);

  it('parses a valid JSON array payload', () => {
    const result = parseEventPayload(validEventJson);
    expect(result.valid).toHaveLength(1);
    expect(result.invalid).toHaveLength(0);
    expect(result.valid[0].id).toBe('abc123');
  });

  it('separates valid and invalid events', () => {
    const payload = JSON.stringify([
      {
        id: 'abc123',
        username: 'player1',
        boxName: 'Gold Box',
        itemName: 'Diamond Watch',
        itemValue: 100,
        rarity: 'quartz',
        acquiredAt: '2024-01-15T10:30:00.000Z',
      },
      { id: 'bad', username: 'player2' }, // missing fields
    ]);
    const result = parseEventPayload(payload);
    expect(result.valid).toHaveLength(1);
    expect(result.invalid).toHaveLength(1);
    expect(result.invalid[0].reason).toContain('Missing required field');
  });

  it('returns invalid result for non-JSON input', () => {
    const result = parseEventPayload('not json');
    expect(result.valid).toHaveLength(0);
    expect(result.invalid).toHaveLength(1);
    expect(result.invalid[0].reason).toBe('Invalid JSON');
  });

  it('returns invalid result for non-array JSON', () => {
    const result = parseEventPayload('{"key": "value"}');
    expect(result.valid).toHaveLength(0);
    expect(result.invalid).toHaveLength(1);
    expect(result.invalid[0].reason).toBe('Payload is not an array');
  });

  it('handles empty array', () => {
    const result = parseEventPayload('[]');
    expect(result.valid).toHaveLength(0);
    expect(result.invalid).toHaveLength(0);
  });

  it('logs warnings for malformed events', () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const payload = JSON.stringify([{ id: 'bad' }]);
    parseEventPayload(payload);
    expect(warnSpy).toHaveBeenCalled();
    warnSpy.mockRestore();
  });
});
