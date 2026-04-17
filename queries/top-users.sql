-- Top users by opens with per-tier breakdown
SELECT
  username,
  COUNT(*) AS opens,
  SUM(CASE WHEN e.box_tier = 'Bronze' THEN 1 ELSE 0 END) AS bronze,
  SUM(CASE WHEN e.box_tier = 'Silver' THEN 1 ELSE 0 END) AS silver,
  SUM(CASE WHEN e.box_tier = 'Gold' THEN 1 ELSE 0 END) AS gold,
  SUM(CASE WHEN e.box_tier = 'Icy' THEN 1 ELSE 0 END) AS icy,
  SUM(b.cost) AS total_spent,
  SUM(e.item_value) AS total_received,
  SUM(b.cost) - SUM(e.item_value) AS net_loss
FROM events e
JOIN boxes b ON e.box_tier = b.box_tier
GROUP BY username
ORDER BY opens DESC;
