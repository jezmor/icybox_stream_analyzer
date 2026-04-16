import { describe, it, expect } from 'vitest';
import { Deduplicator } from './deduplicator.js';

describe('Deduplicator', () => {
  it('reports new IDs as not duplicate', () => {
    const dedup = new Deduplicator();
    expect(dedup.isDuplicate('abc')).toBe(false);
    expect(dedup.isDuplicate('def')).toBe(false);
  });

  it('detects previously added IDs as duplicates', () => {
    const dedup = new Deduplicator();
    dedup.add('abc');
    expect(dedup.isDuplicate('abc')).toBe(true);
    expect(dedup.isDuplicate('def')).toBe(false);
  });

  it('pre-populates from an iterable of existing IDs', () => {
    const existing = ['id-1', 'id-2', 'id-3'];
    const dedup = new Deduplicator(existing);

    expect(dedup.isDuplicate('id-1')).toBe(true);
    expect(dedup.isDuplicate('id-2')).toBe(true);
    expect(dedup.isDuplicate('id-3')).toBe(true);
    expect(dedup.isDuplicate('id-4')).toBe(false);
  });

  it('pre-populates from a Set', () => {
    const existing = new Set(['x', 'y']);
    const dedup = new Deduplicator(existing);

    expect(dedup.isDuplicate('x')).toBe(true);
    expect(dedup.isDuplicate('y')).toBe(true);
    expect(dedup.isDuplicate('z')).toBe(false);
  });

  it('tracks size accurately', () => {
    const dedup = new Deduplicator();
    expect(dedup.size()).toBe(0);

    dedup.add('a');
    expect(dedup.size()).toBe(1);

    dedup.add('b');
    expect(dedup.size()).toBe(2);

    // Adding a duplicate should not increase size
    dedup.add('a');
    expect(dedup.size()).toBe(2);
  });

  it('counts pre-populated IDs in size', () => {
    const dedup = new Deduplicator(['one', 'two', 'three']);
    expect(dedup.size()).toBe(3);

    dedup.add('four');
    expect(dedup.size()).toBe(4);
  });

  it('starts empty when no existing IDs are provided', () => {
    const dedup = new Deduplicator();
    expect(dedup.size()).toBe(0);
  });

  it('handles an empty iterable', () => {
    const dedup = new Deduplicator([]);
    expect(dedup.size()).toBe(0);
    expect(dedup.isDuplicate('anything')).toBe(false);
  });
});
