import { test } from "node:test";
import assert from "node:assert/strict";
import worker from "../src/index.js";
import { fakeDb } from "./fakeDb.js";

const DAY = 86400000;
const T0 = 1_800_000_000_000;

function env(now = T0) { return { DB: fakeDb(), ADMIN_KEY: "admin-secret", NOW: now }; }

async function call(e, method, path, body, key) {
  const headers = {};
  if (body !== undefined) headers["content-type"] = "application/json";
  if (key) headers.authorization = `Bearer ${key}`;
  const res = await worker.fetch(new Request(`https://x${path}`, {
    method, headers, body: body === undefined ? undefined : JSON.stringify(body),
  }), e, {});
  const text = await res.text();
  return { status: res.status, body: text ? JSON.parse(text) : null };
}

const stats = (games = 128) => ({
  global: { kills: 2134, deaths: 2372, wins: 70, losses: 58, games, calibrated: true },
  matches: [1, 2, 3, 4, 5].map((i) => ({ at: 1794500000 + i, mode: "Domination", map: "Port", kills: 20, deaths: 10, score: 3000, result: "win" })),
  level: 54, prestige: 1, mastery: null,
});

test("register, update, read, rank", async () => {
  const e = env();
  const reg = await call(e, "POST", "/api/players", { pseudo: "Romusan" });
  assert.equal(reg.status, 201);
  assert.match(reg.body.key, /^[0-9a-f]{64}$/);
  assert.equal((await call(e, "PUT", `/api/players/${reg.body.id}`, stats(), reg.body.key)).status, 204);
  const got = await call(e, "GET", `/api/players/${reg.body.id}`);
  assert.equal(got.status, 200);
  assert.equal(got.body.pseudo, "Romusan");
  assert.equal(got.body.data.level, 54);
  assert.equal("key_hash" in got.body, false);
  const board = await call(e, "GET", "/api/leaderboard?sort=kd");
  assert.deepEqual(board.body.entries.map((x) => x.pseudo), ["Romusan"]);
});

test("unknown sort falls back to kd", async () => {
  const board = await call(env(), "GET", "/api/leaderboard?sort=nimporte");
  assert.equal(board.status, 200);
  assert.equal(board.body.sort, "kd");
});

test("pseudo taken ignores case", async () => {
  const e = env();
  await call(e, "POST", "/api/players", { pseudo: "Romusan" });
  const again = await call(e, "POST", "/api/players", { pseudo: "romusan" });
  assert.equal(again.status, 409);
  assert.equal(again.body.error, "pseudo déjà pris");
});

test("bad pseudo is 400", async () => {
  assert.equal((await call(env(), "POST", "/api/players", { pseudo: "<b>" })).status, 400);
});

test("update needs the right key", async () => {
  const e = env();
  const reg = await call(e, "POST", "/api/players", { pseudo: "Romusan" });
  assert.equal((await call(e, "PUT", `/api/players/${reg.body.id}`, stats())).status, 401);
  const wrong = await call(e, "PUT", `/api/players/${reg.body.id}`, stats(), "0".repeat(64));
  assert.equal(wrong.status, 401);
  assert.equal(wrong.body.error, "clé invalide");
});

test("two updates within 30 s", async () => {
  const e = env();
  const reg = await call(e, "POST", "/api/players", { pseudo: "Romusan" });
  assert.equal((await call(e, "PUT", `/api/players/${reg.body.id}`, stats(), reg.body.key)).status, 204);
  e.NOW = T0 + 10_000;
  const fast = await call(e, "PUT", `/api/players/${reg.body.id}`, stats(), reg.body.key);
  assert.equal(fast.status, 429);
  assert.equal(fast.body.error, "trop rapide");
  e.NOW = T0 + 31_000;
  assert.equal((await call(e, "PUT", `/api/players/${reg.body.id}`, stats(), reg.body.key)).status, 204);
});

test("invalid stats are 400 with a message", async () => {
  const e = env();
  const reg = await call(e, "POST", "/api/players", { pseudo: "Romusan" });
  const r = await call(e, "PUT", `/api/players/${reg.body.id}`, { ...stats(), level: 100 }, reg.body.key);
  assert.equal(r.status, 400);
  assert.match(r.body.error, /niveau/);
});

test("delete by owner and by admin", async () => {
  const e = env();
  const a = await call(e, "POST", "/api/players", { pseudo: "Alpha" });
  const b = await call(e, "POST", "/api/players", { pseudo: "Bravo" });
  assert.equal((await call(e, "DELETE", `/api/players/${a.body.id}`, undefined, a.body.key)).status, 204);
  assert.equal((await call(e, "DELETE", `/api/players/${b.body.id}`, undefined, "admin-secret")).status, 204);
  assert.equal((await call(e, "GET", `/api/players/${a.body.id}`)).status, 404);
  assert.equal((await call(e, "GET", `/api/players/${b.body.id}`)).status, 404);
  assert.equal((await call(e, "POST", "/api/players", { pseudo: "Alpha" })).status, 201);  // free again
});

test("admin key cannot write stats", async () => {
  const e = env();
  const a = await call(e, "POST", "/api/players", { pseudo: "Alpha" });
  assert.equal((await call(e, "PUT", `/api/players/${a.body.id}`, stats(), "admin-secret")).status, 401);
});

test("cron removes profiles idle for 90 days", async () => {
  const e = env();
  const a = await call(e, "POST", "/api/players", { pseudo: "Alpha" });
  await call(e, "PUT", `/api/players/${a.body.id}`, stats(), a.body.key);
  e.NOW = T0 + 89 * DAY;
  await worker.scheduled({}, e, {});
  assert.equal((await call(e, "GET", `/api/players/${a.body.id}`)).status, 200);
  e.NOW = T0 + 91 * DAY;
  await worker.scheduled({}, e, {});
  assert.equal((await call(e, "GET", `/api/players/${a.body.id}`)).status, 404);
});
