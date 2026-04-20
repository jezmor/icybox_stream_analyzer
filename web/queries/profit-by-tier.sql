-- Profit breakdown per box tier (time-aware pricing)
SELECT
  e.box_tier,
  bp.cost AS box_cost,
  COUNT(*) AS opens,
  COUNT(*) * bp.cost AS total_in,
  SUM(e.item_value) AS total_out,
  COUNT(*) * bp.cost - SUM(e.item_value) AS net_gain,
  ROUND(SUM(e.item_value) * 100.0 / (COUNT(*) * bp.cost), 2) AS return_pct
FROM events e
JOIN box_pricing bp
  ON bp.box_tier = e.box_tier
  AND REPLACE(e.acquired_at, 'Z', '+00:00') >= COALESCE(
    (SELECT MAX(bp2.effective_until) FROM box_pricing bp2
     WHERE bp2.box_tier = bp.box_tier AND bp2.effective_from < bp.effective_from),
    '1970-01-01T00:00:00+00:00')
  AND (bp.effective_until IS NULL OR REPLACE(e.acquired_at, 'Z', '+00:00') < bp.effective_until)
GROUP BY e.box_tier, bp.effective_from
ORDER BY bp.cost ASC, bp.effective_from;
