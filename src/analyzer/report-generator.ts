import type { ReportData, TierStats, RarityStats } from '../types.js';

const BOX_COST: Record<string, number> = {
  Bronze: 50,
  Silver: 100,
  Gold: 500,
  Icy: 1000,
};

// ── Formatting helpers ──

function fmtDollars(value: number): string {
  return value.toFixed(2);
}

function fmtMoney(value: number): string {
  return '$' + value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function pct(value: number): string {
  return value.toFixed(2) + '%';
}

function pad(text: string, width: number): string {
  return text.padEnd(width);
}

function padLeft(text: string, width: number): string {
  return text.padStart(width);
}

function separator(char: string, length: number): string {
  return char.repeat(length);
}

function sectionHeader(title: string): string {
  const line = separator('═', 60);
  return line + '\n  ' + title + '\n' + line;
}

function formatDate(date: Date): string {
  return date.toISOString().replace('T', ' ').replace(/\.\d{3}Z$/, ' UTC');
}

// ── Console Report ──

export function formatConsoleReport(data: ReportData): string {
  const sections: string[] = [];
  sections.push(formatSummarySection(data));
  sections.push(formatTierSection(data.tierStats));
  sections.push(formatOddsPerBoxSection(data.tierStats, data.rarityStats));
  sections.push(formatValueVsCostSection(data));
  sections.push(formatRaritySection(data.tierStats, data.rarityStats));
  sections.push(formatValueSection(data));
  return sections.join('\n\n');
}

function formatSummarySection(data: ReportData): string {
  const lines: string[] = [];
  lines.push(sectionHeader('Collection Summary'));
  lines.push('  Total Events:  ' + data.summary.totalEvents.toLocaleString());
  lines.push('  Date Range:    ' + formatDate(data.summary.dateRange.start) + ' → ' + formatDate(data.summary.dateRange.end));
  lines.push('  Duration:      ' + data.summary.duration);
  return lines.join('\n');
}

function formatTierSection(tierStats: TierStats[]): string {
  const lines: string[] = [];
  lines.push(sectionHeader('Box Tier Distribution'));
  const nameW = 10; const countW = 10; const pctW = 10;
  lines.push('  ' + pad('Tier', nameW) + padLeft('Count', countW) + padLeft('Pct', pctW));
  lines.push('  ' + separator('─', nameW + countW + pctW));
  for (const ts of tierStats) {
    lines.push('  ' + pad(ts.tier, nameW) + padLeft(ts.count.toLocaleString(), countW) + padLeft(pct(ts.percentage), pctW));
  }
  return lines.join('\n');
}

function formatValueVsCostSection(data: ReportData): string {
  const lines: string[] = [];
  lines.push(sectionHeader('Value vs Cost per Box'));
  const tierW = 10; const colW = 16;
  lines.push('  ' + pad('Tier', tierW) + padLeft('Count', colW) + padLeft('Cost/Box', colW) + padLeft('Total In', colW) + padLeft('Total Out', colW) + padLeft('Profit', colW) + padLeft('Return', colW));
  lines.push('  ' + separator('─', tierW + colW * 6));

  let grandCount = 0;
  let grandIn = 0;
  let grandOut = 0;

  for (const ts of data.tierStats) {
    const cost = BOX_COST[ts.tier];
    const vs = data.valueAnalysis.byTier.get(ts.tier);
    if (cost !== undefined && vs && ts.count > 0) {
      const totalIn = cost * ts.count;
      const totalOut = vs.mean * ts.count;
      const profit = totalIn - totalOut;
      const returnPct = (vs.mean / cost) * 100;
      grandCount += ts.count;
      grandIn += totalIn;
      grandOut += totalOut;
      lines.push('  ' + pad(ts.tier, tierW) + padLeft(ts.count.toLocaleString(), colW) + padLeft(fmtMoney(cost), colW) + padLeft(fmtMoney(totalIn), colW) + padLeft(fmtMoney(totalOut), colW) + padLeft(fmtMoney(profit), colW) + padLeft(pct(returnPct), colW));
    } else if (vs && ts.count > 0) {
      // Unknown tier cost — show what we can
      lines.push('  ' + pad(ts.tier, tierW) + padLeft(ts.count.toLocaleString(), colW) + padLeft('???', colW) + padLeft('???', colW) + padLeft(fmtMoney(vs.mean * ts.count), colW) + padLeft('???', colW) + padLeft('???', colW));
    }
  }

  if (grandCount > 0) {
    const grandProfit = grandIn - grandOut;
    const grandReturn = (grandOut / grandIn) * 100;
    lines.push('  ' + separator('─', tierW + colW * 6));
    lines.push('  ' + pad('TOTAL', tierW) + padLeft(grandCount.toLocaleString(), colW) + padLeft('', colW) + padLeft(fmtMoney(grandIn), colW) + padLeft(fmtMoney(grandOut), colW) + padLeft(fmtMoney(grandProfit), colW) + padLeft(pct(grandReturn), colW));
  }

  lines.push('');
  lines.push('  Total In  = what users paid (count × cost/box)');
  lines.push('  Total Out = what users received (count × avg item value)');
  lines.push('  Profit    = IcyBox take (Total In - Total Out)');
  lines.push('  Return    = avg item value / box cost (>100% = user wins)');
  return lines.join('\n');
}

function formatOddsPerBoxSection(tierStats: TierStats[], rarityStats: RarityStats[]): string {
  const lines: string[] = [];
  lines.push(sectionHeader('Rarity Odds per Box'));
  const rarityW = 18; const oddsW = 12;
  for (const ts of tierStats) {
    lines.push('\n  ' + ts.tier + ' Box:');
    lines.push('  ' + pad('Rarity', rarityW) + padLeft('Odds', oddsW));
    lines.push('  ' + separator('─', rarityW + oddsW));
    for (const rs of rarityStats) {
      const tierData = rs.byTier.get(ts.tier);
      const percentage = tierData?.percentage ?? 0;
      lines.push('  ' + pad(rs.rarity, rarityW) + padLeft(pct(percentage), oddsW));
    }
  }
  return lines.join('\n');
}

function formatRaritySection(tierStats: TierStats[], rarityStats: RarityStats[]): string {
  const lines: string[] = [];
  lines.push(sectionHeader('Rarity Distribution (Cross-Tabulation)'));
  const tiers = tierStats.map(t => t.tier);
  const rarityW = 18; const totalW = 10; const pctColW = 10; const tierW = 14;
  let header = '  ' + pad('Rarity', rarityW) + padLeft('Total', totalW) + padLeft('Pct', pctColW);
  for (const tier of tiers) { header += padLeft(tier, tierW); }
  lines.push(header);
  lines.push('  ' + separator('─', rarityW + totalW + pctColW + tiers.length * tierW));
  for (const rs of rarityStats) {
    let row = '  ' + pad(rs.rarity, rarityW) + padLeft(rs.totalCount.toLocaleString(), totalW) + padLeft(pct(rs.totalPercentage), pctColW);
    for (const tier of tiers) {
      const tierData = rs.byTier.get(tier);
      const cellText = tierData ? tierData.count + ' (' + pct(tierData.percentage) + ')' : '0 (0.00%)';
      row += padLeft(cellText, tierW);
    }
    lines.push(row);
  }
  return lines.join('\n');
}

function formatValueSection(data: ReportData): string {
  const lines: string[] = [];
  lines.push(sectionHeader('Value Analysis'));
  lines.push('  Overall Expected Value: ' + fmtDollars(data.valueAnalysis.overall.expectedValue));
  lines.push('');

  lines.push('  Value by Tier:');
  const tierW = 10; const statW = 12;
  lines.push('  ' + pad('Tier', tierW) + padLeft('Min', statW) + padLeft('Max', statW) + padLeft('Mean', statW) + padLeft('Median', statW) + padLeft('StdDev', statW));
  lines.push('  ' + separator('─', tierW + statW * 5));
  for (const [tier, vs] of data.valueAnalysis.byTier) {
    lines.push('  ' + pad(tier, tierW) + padLeft(fmtDollars(vs.min), statW) + padLeft(fmtDollars(vs.max), statW) + padLeft(fmtDollars(vs.mean), statW) + padLeft(fmtDollars(vs.median), statW) + padLeft(fmtDollars(vs.stdDev), statW));
  }
  lines.push('');

  lines.push('  Value by Rarity:');
  lines.push('  ' + pad('Rarity', 18) + padLeft('Min', statW) + padLeft('Max', statW) + padLeft('Mean', statW) + padLeft('Median', statW));
  lines.push('  ' + separator('─', 18 + statW * 4));
  for (const [rarity, vs] of data.valueAnalysis.byRarity) {
    lines.push('  ' + pad(rarity, 18) + padLeft(fmtDollars(vs.min), statW) + padLeft(fmtDollars(vs.max), statW) + padLeft(fmtDollars(vs.mean), statW) + padLeft(fmtDollars(vs.median), statW));
  }
  return lines.join('\n');
}

// ── CSV Report ──

export function formatCSVReport(data: ReportData): string {
  const tiers = data.tierStats.map(t => t.tier);
  const rows: string[] = [];

  rows.push('Section,Metric,Value');
  rows.push('Summary,Total Events,' + data.summary.totalEvents);
  rows.push('Summary,Date Range Start,' + data.summary.dateRange.start.toISOString());
  rows.push('Summary,Date Range End,' + data.summary.dateRange.end.toISOString());
  rows.push('Summary,Duration,' + csvEscape(data.summary.duration));
  rows.push('');

  rows.push('Tier,Count,Percentage');
  for (const ts of data.tierStats) {
    rows.push(ts.tier + ',' + ts.count + ',' + ts.percentage);
  }
  rows.push('');

  const rarityHeader = ['Rarity', 'Total Count', 'Total Percentage'];
  for (const tier of tiers) { rarityHeader.push(tier + ' Count', tier + ' Percentage'); }
  rows.push(rarityHeader.join(','));
  for (const rs of data.rarityStats) {
    const cells: (string | number)[] = [rs.rarity, rs.totalCount, rs.totalPercentage];
    for (const tier of tiers) {
      const tierData = rs.byTier.get(tier);
      cells.push(tierData?.count ?? 0, tierData?.percentage ?? 0);
    }
    rows.push(cells.join(','));
  }
  rows.push('');

  rows.push('Tier,Min,Max,Mean,Median,StdDev');
  for (const [tier, vs] of data.valueAnalysis.byTier) {
    rows.push(tier + ',' + vs.min + ',' + vs.max + ',' + vs.mean + ',' + vs.median + ',' + vs.stdDev);
  }
  rows.push('');

  rows.push('Rarity,Min,Max,Mean,Median');
  for (const [rarity, vs] of data.valueAnalysis.byRarity) {
    rows.push(rarity + ',' + vs.min + ',' + vs.max + ',' + vs.mean + ',' + vs.median);
  }
  rows.push('');

  rows.push('Metric,Value');
  rows.push('Overall Expected Value,' + data.valueAnalysis.overall.expectedValue);

  return rows.join('\n');
}

function csvEscape(value: string): string {
  if (value.includes(',') || value.includes('"') || value.includes('\n')) {
    return '"' + value.replace(/"/g, '""') + '"';
  }
  return value;
}
