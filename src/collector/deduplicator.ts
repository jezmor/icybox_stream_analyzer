/**
 * Tracks seen event IDs to prevent duplicate writes.
 * Uses an in-memory Set<string> for O(1) lookup.
 */
export class Deduplicator {
  private readonly seen: Set<string>;

  /**
   * Create a new Deduplicator, optionally pre-populated with existing IDs.
   * @param existingIds - An iterable of IDs already persisted in the data store.
   */
  constructor(existingIds?: Iterable<string>) {
    this.seen = new Set(existingIds);
  }

  /**
   * Check whether the given ID has already been seen.
   */
  isDuplicate(id: string): boolean {
    return this.seen.has(id);
  }

  /**
   * Record an ID as seen so future calls to `isDuplicate` return true.
   */
  add(id: string): void {
    this.seen.add(id);
  }

  /**
   * Return the number of unique IDs currently tracked.
   */
  size(): number {
    return this.seen.size;
  }
}
