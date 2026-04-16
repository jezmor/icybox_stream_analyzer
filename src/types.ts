// ── Enumerations ──

export type BoxTier = 'Bronze' | 'Silver' | 'Gold' | 'Icy';

export type Rarity = 'quartz' | 'automatic' | 'chronograph' | 'tourbillon';

// ── Core Event Models ──

export interface IcyBoxEvent {
  id: string;
  username: string;
  platform: string;
  boxName: string;
  boxSlug: string;
  itemName: string;
  itemValue: number;
  rarity: Rarity;
  rarityColor: string;
  itemImageUrl: string;
  acquiredAt: Date;
}

export interface StoredEvent extends IcyBoxEvent {
  collectedAt: Date;
}

// ── CLI Option Types ──

export interface CLIOptions {
  dataFile: string;
}

export interface CollectOptions extends CLIOptions {
  mode: 'sse' | 'polling';
  interval: number;
}

export interface AnalyzeOptions extends CLIOptions {
  exportCsv?: string;
}

// ── Analysis Types ──

export interface AccumulatedData {
  events: StoredEvent[];
  byTier: Map<BoxTier, StoredEvent[]>;
  byRarity: Map<Rarity, StoredEvent[]>;
  byUser: Map<string, number>;
  byHour: Map<string, number>;
  dateRange: { min: Date; max: Date };
  totalCount: number;
}

export interface TierStats {
  tier: BoxTier;
  count: number;
  percentage: number;
}

export interface RarityStats {
  rarity: Rarity;
  totalCount: number;
  totalPercentage: number;
  byTier: Map<BoxTier, { count: number; percentage: number }>;
}

export interface ValueStats {
  min: number;
  max: number;
  mean: number;
  median: number;
  stdDev: number;
}

export interface TopItem {
  itemName: string;
  count: number;
  rarity: Rarity;
  itemValue: number;
}

export interface UserActivityStats {
  uniqueUsers: number;
  openingsPerUser: { min: number; max: number; mean: number; median: number };
  topUsers: { username: string; count: number }[];
  eventsPerHour: { hour: string; count: number }[];
}

export interface ParseResult {
  valid: IcyBoxEvent[];
  invalid: { raw: unknown; reason: string }[];
}

export interface ReportData {
  summary: {
    totalEvents: number;
    dateRange: { start: Date; end: Date };
    duration: string;
  };
  tierStats: TierStats[];
  rarityStats: RarityStats[];
  valueAnalysis: {
    byTier: Map<BoxTier, ValueStats>;
    byRarity: Map<Rarity, Omit<ValueStats, 'stdDev'>>;
    overall: { expectedValue: number };
    topItems: TopItem[];
  };
  userActivity: UserActivityStats;
}
