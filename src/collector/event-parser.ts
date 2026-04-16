import type { IcyBoxEvent, ParseResult } from '../types.js';

const REQUIRED_FIELDS = [
  'id',
  'username',
  'boxName',
  'itemName',
  'itemValue',
  'rarity',
  'acquiredAt',
] as const;

/**
 * Parse a string value (or number) into a numeric decimal.
 * Strips leading currency symbols like "$" before parsing.
 * Returns NaN if the value cannot be parsed.
 */
export function parseItemValue(value: string | number): number {
  if (typeof value === 'number') {
    return value;
  }

  const cleaned = value.replace(/^\$/, '').trim();
  if (cleaned === '') {
    return NaN;
  }
  return Number(cleaned);
}

/**
 * Validate an ISO 8601 timestamp string and return a Date, or null if invalid.
 */
export function parseTimestamp(value: string): Date | null {
  if (typeof value !== 'string' || value.trim() === '') {
    return null;
  }

  const date = new Date(value);

  // Check that the Date constructor produced a valid date
  if (isNaN(date.getTime())) {
    return null;
  }

  // Basic ISO 8601 format check: must contain date separators and T or be a valid date string
  // Accept formats like: 2024-01-15T10:30:00.000Z, 2024-01-15T10:30:00Z, 2024-01-15
  const iso8601Pattern = /^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?)?$/;
  if (!iso8601Pattern.test(value.trim())) {
    return null;
  }

  return date;
}

/**
 * Validate a raw event object and return a typed IcyBoxEvent, or null if invalid.
 * Checks for all required fields and correct types.
 */
export function validateEvent(raw: unknown): IcyBoxEvent | null {
  if (raw === null || typeof raw !== 'object') {
    return null;
  }

  const obj = raw as Record<string, unknown>;

  // Check all required fields are present
  for (const field of REQUIRED_FIELDS) {
    if (obj[field] === undefined || obj[field] === null) {
      return null;
    }
  }

  // Validate id is a string
  if (typeof obj.id !== 'string' || obj.id.trim() === '') {
    return null;
  }

  // Validate username is a string
  if (typeof obj.username !== 'string') {
    return null;
  }

  // Validate boxName is a string
  if (typeof obj.boxName !== 'string') {
    return null;
  }

  // Validate itemName is a string
  if (typeof obj.itemName !== 'string') {
    return null;
  }

  // Validate and parse itemValue
  if (typeof obj.itemValue !== 'string' && typeof obj.itemValue !== 'number') {
    return null;
  }
  const itemValue = parseItemValue(obj.itemValue as string | number);
  if (isNaN(itemValue)) {
    return null;
  }

  // Validate rarity is a non-empty string
  if (typeof obj.rarity !== 'string' || obj.rarity.trim() === '') {
    return null;
  }

  // Validate and parse acquiredAt
  if (typeof obj.acquiredAt !== 'string') {
    return null;
  }
  const acquiredAt = parseTimestamp(obj.acquiredAt as string);
  if (acquiredAt === null) {
    return null;
  }

  return {
    id: obj.id as string,
    username: obj.username as string,
    platform: typeof obj.platform === 'string' ? obj.platform as string : '',
    boxName: obj.boxName as string,
    boxSlug: typeof obj.boxSlug === 'string' ? obj.boxSlug as string : '',
    itemName: obj.itemName as string,
    itemValue,
    rarity: obj.rarity as string,
    rarityColor: typeof obj.rarityColor === 'string' ? obj.rarityColor as string : '',
    itemImageUrl: typeof obj.itemImageUrl === 'string' ? obj.itemImageUrl as string : '',
    acquiredAt,
  };
}

/**
 * Parse a JSON array payload string into validated IcyBoxEvent objects.
 * Returns both valid events and invalid entries with reasons.
 */
export function parseEventPayload(payload: string): ParseResult {
  const result: ParseResult = {
    valid: [],
    invalid: [],
  };

  let parsed: unknown;
  try {
    parsed = JSON.parse(payload);
  } catch {
    console.warn('[event-parser] Failed to parse JSON payload:', payload);
    result.invalid.push({ raw: payload, reason: 'Invalid JSON' });
    return result;
  }

  if (!Array.isArray(parsed)) {
    console.warn('[event-parser] Payload is not an array:', parsed);
    result.invalid.push({ raw: parsed, reason: 'Payload is not an array' });
    return result;
  }

  for (const rawEvent of parsed) {
    const event = validateEvent(rawEvent);
    if (event !== null) {
      result.valid.push(event);
    } else {
      const reason = getMalformedReason(rawEvent);
      console.warn('[event-parser] Malformed event skipped:', JSON.stringify(rawEvent), '- Reason:', reason);
      result.invalid.push({ raw: rawEvent, reason });
    }
  }

  return result;
}

/**
 * Determine a human-readable reason why an event is invalid.
 */
function getMalformedReason(raw: unknown): string {
  if (raw === null || typeof raw !== 'object') {
    return 'Event is not an object';
  }

  const obj = raw as Record<string, unknown>;

  for (const field of REQUIRED_FIELDS) {
    if (obj[field] === undefined || obj[field] === null) {
      return `Missing required field: ${field}`;
    }
  }

  if (typeof obj.itemValue === 'string' || typeof obj.itemValue === 'number') {
    const val = parseItemValue(obj.itemValue as string | number);
    if (isNaN(val)) {
      return `Invalid itemValue: ${String(obj.itemValue)}`;
    }
  } else {
    return `Invalid itemValue type: ${typeof obj.itemValue}`;
  }

  if (typeof obj.rarity === 'string' && obj.rarity.trim() === '') {
    return 'Empty rarity';
  }

  if (typeof obj.acquiredAt === 'string') {
    const ts = parseTimestamp(obj.acquiredAt as string);
    if (ts === null) {
      return `Invalid acquiredAt timestamp: ${obj.acquiredAt}`;
    }
  }

  return 'Unknown validation error';
}
