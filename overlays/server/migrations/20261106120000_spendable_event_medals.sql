-- +goose Up
-- Coffin of Repose (event chapter 508) drops medals 53 and 54 and Rhythm's
-- Citadel (chapter 513) drops 63, 64 and 65, but their shops take 22 and 29.
-- New drops now arrive as 22 and 29 (questflow/bunker_medals.go); this turns
-- the ones already held into them, one for one.
INSERT INTO user_consumable_items (user_id, consumable_item_id, count)
SELECT user_id,
       CASE WHEN consumable_item_id IN (53, 54) THEN 22 ELSE 29 END,
       SUM(count)
FROM user_consumable_items
WHERE consumable_item_id IN (53, 54, 63, 64, 65) AND count > 0
GROUP BY user_id, CASE WHEN consumable_item_id IN (53, 54) THEN 22 ELSE 29 END
ON CONFLICT (user_id, consumable_item_id) DO UPDATE SET count = count + excluded.count;

DELETE FROM user_consumable_items WHERE consumable_item_id IN (53, 54, 63, 64, 65);

-- +goose Down
SELECT 1;
