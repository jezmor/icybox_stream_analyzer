-- Profit breakdown per box tier
SELECT
  e.box_tier,
  b.cost AS box_cost,
  COUNT(*) AS opens,
  COUNT(*) * b.cost AS total_in,
  SUM(e.item_value) AS total_out,
  COUNT(*) * b.cost - SUM(e.item_value) AS profit,
  ROUND(SUM(e.item_value) * 100.0 / (COUNT(*) * b.cost), 2) AS return_pct
FROM events e
JOIN boxes b ON e.box_tier = b.box_tier
GROUP BY e.box_tier
ORDER BY opens DESC;
