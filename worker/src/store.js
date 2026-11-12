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
      return r.meta.changes > 0;
    },
    async all() {
      const { results } = await db.prepare("SELECT id, pseudo, updated_at, data FROM players").all();
      return results.map(parse);
    },
    async purge(before) {
      const r = await db.prepare("DELETE FROM players WHERE updated_at < ?").bind(before).run();
      return r.meta.changes;
    },
  };
}
