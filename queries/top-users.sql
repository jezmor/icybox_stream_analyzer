-- Top users by opens with per-tier breakdown (time-aware pricing)
SELECT
  username,
  COUNT(*) AS opens,
  SUM(CASE WHEN e.box_tier = 'Bronze' THEN 1 ELSE 0 END) AS bronze,
  SUM(CASE WHEN e.box_tier = 'Silver' THEN 1 ELSE 0 END) AS silver,
  SUM(CASE WHEN e.box_tier = 'Gold' THEN 1 ELSE 0 END) AS gold,
  SUM(CASE WHEN e.box_tier = 'Icy' THEN 1 ELSE 0 END) AS icy,
  SUM(bp.cost) AS total_spent,
  SUM(e.item_value) AS total_received,
  SUM(bp.cost) - SUM(e.item_value) AS net_loss
FROM events e
JOIN box_pricing bp
  ON bp.box_tier = e.box_tier
  AND REPLACE(e.acquired_at, 'Z', '+00:00') >= COALESCE(
    (SELECT MAX(bp2.effective_until) FROM box_pricing bp2
     WHERE bp2.box_tier = bp.box_tier AND bp2.effective_from < bp.effective_from),
    '1970-01-01T00:00:00+00:00')
  AND (bp.effective_until IS NULL OR REPLACE(e.acquired_at, 'Z', '+00:00') < bp.effective_until)
GROUP BY username
ORDER BY opens DESC;
