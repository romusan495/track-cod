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

-- Private leagues: a short code shared between friends or a Discord server.
CREATE TABLE IF NOT EXISTS leagues (
  code TEXT PRIMARY KEY,             -- 6 characters, no O/0 or I/1
  name TEXT NOT NULL,
  owner_id TEXT NOT NULL,
  created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS league_members (
  code TEXT NOT NULL,
  player_id TEXT NOT NULL,
  joined_at INTEGER NOT NULL,
  PRIMARY KEY (code, player_id)
);
