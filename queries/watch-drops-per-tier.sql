-- Watch drop counts per box tier
SELECT
  item_name,
  box_tier,
  COUNT(*) AS drops
FROM events
GROUP BY item_name, box_tier
ORDER BY item_name, drops DESC;
