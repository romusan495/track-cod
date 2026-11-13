// D1 access for the players table (schema.sql). `data` is stored as JSON text; times are epoch ms.

const parse = (row) => (row ? { ...row, data: JSON.parse(row.data || "{}") } : null);

export function makeStore(db) {
  return {
    async create({ id, pseudo, pseudoKey, keyHash, now }) {
      await db.prepare(
        "INSERT INTO players (id, pseudo, pseudo_key, key_hash, created_at, updated_at, data) VALUES (?, ?, ?, ?, ?, ?, '{}')",
      ).bind(id, pseudo, pseudoKey, keyHash, now, now).run();
      return id;
    },
    async get(id) {
      return parse(await db.prepare("SELECT * FROM players WHERE id = ?").bind(id).first());
    },
    async byKey(pseudoKey) {
      return parse(await db.prepare("SELECT * FROM players WHERE pseudo_key = ?").bind(pseudoKey).first());
    },
    async update(id, data, now) {
      await db.prepare("UPDATE players SET data = ?, updated_at = ? WHERE id = ?")
        .bind(JSON.stringify(data), now, id).run();
    },
    async remove(id) {
      const r = await db.prepare("DELETE FROM players WHERE id = ?").bind(id).run();
      await db.prepare("DELETE FROM league_members WHERE player_id = ?").bind(id).run();
      await dropEmptyLeagues();
      return r.meta.changes > 0;
    },
    async all() {
      const { results } = await db.prepare("SELECT id, pseudo, updated_at, data FROM players").all();
      return results.map(parse);
    },
    async purge(before) {
      const r = await db.prepare("DELETE FROM players WHERE updated_at < ?").bind(before).run();
      await db.prepare("DELETE FROM league_members WHERE player_id NOT IN (SELECT id FROM players)").run();
      await dropEmptyLeagues();
      return r.meta.changes;
    },

    // ----- leagues -----
    async createLeague({ code, name, ownerId, now }) {
      await db.prepare("INSERT INTO leagues (code, name, owner_id, created_at) VALUES (?, ?, ?, ?)")
        .bind(code, name, ownerId, now).run();
    },
    async league(code) {
      return db.prepare("SELECT * FROM leagues WHERE code = ?").bind(code).first();
    },
    async leaguesOf(playerId) {
      const { results } = await db.prepare("SELECT code FROM league_members WHERE player_id = ?").bind(playerId).all();
      return results.map((r) => r.code);
    },
    async addMember(code, playerId, now) {
      await db.prepare("INSERT OR IGNORE INTO league_members (code, player_id, joined_at) VALUES (?, ?, ?)")
        .bind(code, playerId, now).run();
    },
    async removeMember(code, playerId) {
      await db.prepare("DELETE FROM league_members WHERE code = ? AND player_id = ?").bind(code, playerId).run();
      await dropEmptyLeagues();
    },
    async deleteLeague(code) {
      await db.prepare("DELETE FROM league_members WHERE code = ?").bind(code).run();
      const r = await db.prepare("DELETE FROM leagues WHERE code = ?").bind(code).run();
      return r.meta.changes > 0;
    },
    async leaguePlayers(code) {
      const { results } = await db.prepare(
        "SELECT p.id, p.pseudo, p.updated_at, p.data FROM players p JOIN league_members m ON m.player_id = p.id WHERE m.code = ?",
      ).bind(code).all();
      return results.map(parse);
    },
  };

  async function dropEmptyLeagues() {
    await db.prepare("DELETE FROM leagues WHERE code NOT IN (SELECT DISTINCT code FROM league_members)").run();
  }
}
