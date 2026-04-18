-- Stated vs observed odds per rarity, per box, per stated-odds time period
-- Events before the first scrape are included in the earliest period
-- observed_pct and drift are NULL when sample size is too small to expect even 1 drop
SELECT
  box_tier,
  rarity_key,
  stated_pct,
  effective_from,
  effective_until,
  drops AS rarity_total,
  CASE
    WHEN drops = 0 AND (stated_pct / 100.0) * tier_total < 1 THEN NULL
    WHEN tier_total = 0 THEN NULL
    ELSE ROUND(drops * 100.0 / tier_total, 2)
  END AS observed_pct,
  CASE
    WHEN drops = 0 AND (stated_pct / 100.0) * tier_total < 1 THEN NULL
    WHEN tier_total = 0 THEN NULL
    ELSE ROUND(drops * 100.0 / tier_total - stated_pct, 2)
  END AS drift
FROM (
  SELECT
    s.box_tier,
    s.rarity_key,
    s.odds_pct AS stated_pct,
    s.effective_from,
    s.effective_until,
    COUNT(e.id) AS drops,
    SUM(COUNT(e.id)) OVER (PARTITION BY s.box_tier, s.effective_from) AS tier_total
  FROM stated_odds s
  LEFT JOIN events e
    ON e.box_tier = s.box_tier
    AND e.rarity = s.rarity_key
    AND (s.effective_until IS NULL OR e.acquired_at < REPLACE(s.effective_until, '+00:00', 'Z'))
    AND e.acquired_at >= COALESCE(
      (SELECT MAX(REPLACE(s2.effective_until, '+00:00', 'Z'))
       FROM stated_odds s2
       WHERE s2.box_tier = s.box_tier AND s2.rarity_key = s.rarity_key
         AND s2.effective_from < s.effective_from),
      '1970-01-01T00:00:00Z'
    )
  GROUP BY s.box_tier, s.rarity_key, s.effective_from
)
ORDER BY box_tier, effective_from, stated_pct DESC;
