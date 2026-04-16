Welcome to my vibecoded, overengineered solution to a simple question: What is the EV (Expected Value) of Wristwatch LootBox I got an ad for.

# IcyBox Stream Analyzer

A CLI tool that connects to the [IcyBox](https://www.icybox.io) activity stream, collects box-opening events in real time, and runs statistical analysis to evaluate the fairness and value proposition of each box tier.

## What it does

- **Collects** live box-opening events via SSE (Server-Sent Events) or polling
- **Persists** events to a local JSONL file with deduplication
- **Analyzes** collected data to produce:
  - Box tier distribution (Bronze, Silver, Gold, Icy)
  - Rarity odds per box (quartz, automatic, chronograph, tourbillon)
  - Value vs cost breakdown showing total money in, total money out, and IcyBox's profit margin
  - Rarity cross-tabulation across all tiers
  - Value statistics (min, max, mean, median, std dev) per tier and rarity

## Box Prices

| Tier   | Cost     |
|--------|----------|
| Bronze | $50.00   |
| Silver | $100.00  |
| Gold   | $500.00  |
| Icy    | $1,000.00|

## Setup

```bash
npm install
npm run build
```

## Usage

### Collect events

Start the collector to stream live events into a local file:

```bash
# SSE mode (default) — holds a persistent connection open
node dist/cli.js collect

# Polling mode — fetches every N seconds
node dist/cli.js collect --mode polling --interval 30

# Custom data file
node dist/cli.js collect --data-file ./my-data.jsonl
```

Press `Ctrl+C` to stop collecting. The collector handles reconnection with exponential backoff and respects rate limits (HTTP 429).

### Analyze collected data

```bash
# Console report
node dist/cli.js analyze

# With CSV export
node dist/cli.js analyze --export-csv report.csv

# Analyze a specific data file
node dist/cli.js analyze --data-file ./my-data.jsonl
```

### CLI options

```
Usage: icybox [options] [command]

Commands:
  collect   Start collecting box-opening events
  analyze   Run statistical analysis on collected data

collect options:
  --data-file <path>     Path to JSONL data file (default: ./icybox-data.jsonl)
  --mode <mode>          Connection mode: sse or polling (default: sse)
  --interval <seconds>   Polling interval in seconds (default: 30)

analyze options:
  --data-file <path>     Path to JSONL data file (default: ./icybox-data.jsonl)
  --export-csv <path>    Export report as CSV
```

## Data format

Events are stored as JSON Lines (`.jsonl`), one event per line:

```json
{
  "id": "abc123",
  "username": "player1",
  "platform": "web",
  "boxName": "Gold Box",
  "boxSlug": "gold-box",
  "itemName": "Diamond Watch",
  "itemValue": 150.50,
  "rarity": "chronograph",
  "rarityColor": "#FFD700",
  "itemImageUrl": "https://example.com/watch.png",
  "acquiredAt": "2024-01-15T10:30:00.000Z",
  "collectedAt": "2024-01-15T10:30:05.123Z"
}
```

## Development

```bash
npm run build    # Compile TypeScript
npm test         # Run tests
```

## Architecture

```
src/
├── cli.ts                    # CLI entry point (commander.js)
├── types.ts                  # Shared types and interfaces
├── collector/
│   ├── sse-client.ts         # SSE connection with backoff
│   ├── polling-client.ts     # Polling alternative
│   ├── event-parser.ts       # Event validation and parsing
│   ├── deduplicator.ts       # In-memory ID deduplication
│   ├── data-writer.ts        # JSONL append writer
│   └── backoff.ts            # Exponential backoff calculator
└── analyzer/
    ├── data-reader.ts        # JSONL line-by-line reader
    ├── stats-engine.ts       # Single-pass data accumulator
    ├── tier-analysis.ts      # Box tier distribution
    ├── rarity-analysis.ts    # Rarity distribution + cross-tab
    ├── value-analysis.ts     # Value statistics
    ├── user-analysis.ts      # User activity patterns
    └── report-generator.ts   # Console + CSV report formatting
```

## License

GPL-3.0

## Disclaimer

*This project is not affiliated with, endorsed by, or associated with IcyBox or Infinite Edgers. It uses publicly available data for independent analysis.*
