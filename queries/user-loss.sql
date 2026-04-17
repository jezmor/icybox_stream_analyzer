-- How much a specific user has lost (change username)
SELECT
  COUNT(*) AS opens,
  SUM(b.cost) AS total_spent,
  SUM(e.item_value) AS total_received,
  SUM(b.cost) - SUM(e.item_value) AS net_loss
FROM events e
JOIN boxes b ON e.box_tier = b.box_tier
WHERE e.username = 'username';
