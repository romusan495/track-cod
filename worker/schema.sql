-- One row per player who chose to publish from Track COD. data = validated JSON (see src/validate.js).
CREATE TABLE IF NOT EXISTS players (
  id TEXT PRIMARY KEY,
  pseudo TEXT NOT NULL,
  pseudo_key TEXT NOT NULL UNIQUE,   -- lowercased NFC pseudo: uniqueness ignores case
  key_hash TEXT NOT NULL,            -- SHA-256 hex of the player's secret key (the key itself is never stored)
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  data TEXT NOT NULL DEFAULT '{}'
);
