-- Per-event P&L with running total per user (time-aware pricing)
-- Uncomment the WHERE clause to filter to a specific user
SELECT
  e.acquired_at,
  e.username,
  e.box_tier,
  bp.cost AS paid,
  e.item_value AS received,
  e.item_value - bp.cost AS pnl,
  SUM(e.item_value - bp.cost) OVER (PARTITION BY e.username ORDER BY e.acquired_at) AS running_pnl,
  e.item_name,
  e.rarity
FROM events e
JOIN box_pricing bp
  ON bp.box_tier = e.box_tier
  AND REPLACE(e.acquired_at, 'Z', '+00:00') >= COALESCE(
    (SELECT MAX(bp2.effective_until) FROM box_pricing bp2
     WHERE bp2.box_tier = bp.box_tier AND bp2.effective_from < bp.effective_from),
    '1970-01-01T00:00:00+00:00')
  AND (bp.effective_until IS NULL OR REPLACE(e.acquired_at, 'Z', '+00:00') < bp.effective_until)
-- WHERE e.username = 'username'
ORDER BY e.acquired_at, e.username;
