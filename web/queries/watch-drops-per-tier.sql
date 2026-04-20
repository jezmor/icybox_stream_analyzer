-- Complete watch catalog with rarity and drop counts per tier (includes unseen grails)
SELECT
  item_name,
  item_value,
  MAX(bronze_rarity) AS bronze_rarity,
  MAX(silver_rarity) AS silver_rarity,
  MAX(gold_rarity) AS gold_rarity,
  MAX(icy_rarity) AS icy_rarity,
  MIN(first_seen) AS first_seen,
  MAX(last_seen) AS last_seen,
  SUM(times_dropped) AS times_dropped,
  SUM(bronze_count) AS bronze_count,
  SUM(silver_count) AS silver_count,
  SUM(gold_count) AS gold_count,
  SUM(icy_count) AS icy_count
FROM (
  SELECT
    e.item_name,
    e.item_value,
    MAX(CASE WHEN e.box_tier = 'Bronze' THEN e.rarity END) AS bronze_rarity,
    MAX(CASE WHEN e.box_tier = 'Silver' THEN e.rarity END) AS silver_rarity,
    MAX(CASE WHEN e.box_tier = 'Gold' THEN e.rarity END) AS gold_rarity,
    MAX(CASE WHEN e.box_tier = 'Icy' THEN e.rarity END) AS icy_rarity,
    MIN(e.acquired_at) AS first_seen,
    MAX(e.acquired_at) AS last_seen,
    COUNT(*) AS times_dropped,
    SUM(CASE WHEN e.box_tier = 'Bronze' THEN 1 ELSE 0 END) AS bronze_count,
    SUM(CASE WHEN e.box_tier = 'Silver' THEN 1 ELSE 0 END) AS silver_count,
    SUM(CASE WHEN e.box_tier = 'Gold' THEN 1 ELSE 0 END) AS gold_count,
    SUM(CASE WHEN e.box_tier = 'Icy' THEN 1 ELSE 0 END) AS icy_count
  FROM events e
  GROUP BY e.item_name

  UNION ALL

  SELECT
    lw.item_name,
    lw.item_value,
    CASE WHEN lw.box_tier = 'Bronze' THEN 'grail' END,
    CASE WHEN lw.box_tier = 'Silver' THEN 'grail' END,
    CASE WHEN lw.box_tier = 'Gold' THEN 'grail' END,
    CASE WHEN lw.box_tier = 'Icy' THEN 'grail' END,
    NULL,
    NULL,
    0,
    0, 0, 0, 0
  FROM listed_watches lw
  WHERE lw.listed = 1
    AND lw.item_name NOT IN (SELECT DISTINCT item_name FROM events)
)
GROUP BY item_name
ORDER BY times_dropped DESC;
