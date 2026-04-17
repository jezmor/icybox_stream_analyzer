-- Observed rarity odds per box tier
SELECT
  e.box_tier,
  e.rarity,
  COUNT(*) AS drops,
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY e.box_tier), 2) AS odds_pct
FROM events e
GROUP BY e.box_tier, e.rarity
ORDER BY e.box_tier, odds_pct DESC;
