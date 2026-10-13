-- +goose Up
-- Enhanced companions (m_companion_enhanced: 49, 50, 51, 53, all Level 50)
-- only come from possession type 9 grants, which Bunker used to give at Lv1.
-- They cannot be levelled, so raise existing ones to the table's level.
UPDATE user_companions SET level = 50
WHERE companion_id IN (49, 50, 51, 53) AND level < 50;

-- +goose Down
SELECT 1;
