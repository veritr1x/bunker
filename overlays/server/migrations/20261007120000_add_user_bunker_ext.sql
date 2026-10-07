-- +goose Up
-- Bunker's additions to the save, one JSON document per user (store.ExtState).
CREATE TABLE user_bunker_ext (
    user_id INTEGER NOT NULL PRIMARY KEY REFERENCES users(user_id),
    data    TEXT    NOT NULL DEFAULT '{}'
);

-- +goose Down
DROP TABLE IF EXISTS user_bunker_ext;
