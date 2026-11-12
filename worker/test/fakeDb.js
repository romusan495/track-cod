// D1-shaped wrapper over Node's built-in SQLite, so the real SQL of src/store.js runs in tests.
import { DatabaseSync } from "node:sqlite";
import { readFileSync } from "node:fs";

export function fakeDb() {
  const db = new DatabaseSync(":memory:");
  db.exec(readFileSync(new URL("../schema.sql", import.meta.url), "utf8"));
  return {
    prepare(sql) {
      const st = db.prepare(sql);
      let args = [];
      const stmt = {
        bind(...a) { args = a; return stmt; },
        async first() { return st.get(...args) ?? null; },
        async all() { return { results: st.all(...args) }; },
        async run() { const r = st.run(...args); return { meta: { changes: Number(r.changes) } }; },
      };
      return stmt;
    },
  };
}
