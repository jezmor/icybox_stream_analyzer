-- Grand total profit across all boxes
SELECT
  COUNT(*) AS opens,
  SUM(b.cost) AS total_in,
  SUM(e.item_value) AS total_out,
  SUM(b.cost) - SUM(e.item_value) AS profit,
  ROUND(SUM(e.item_value) * 100.0 / SUM(b.cost), 2) AS return_pct
FROM events e
JOIN boxes b ON e.box_tier = b.box_tier;
