import { test } from "node:test";
import assert from "node:assert/strict";
import worker from "../src/index.js";
import { fakeDb } from "./fakeDb.js";

const T0 = 1_800_000_000_000;
const env = () => ({ DB: fakeDb(), ADMIN_KEY: "admin-secret", NOW: T0 });

async function call(e, method, path, body, key) {
  const headers = {};
  if (body !== undefined) headers["content-type"] = "application/json";
  if (key) headers.authorization = `Bearer ${key}`;
  const res = await worker.fetch(new Request(`https://x${path}`, {
    method, headers, body: body === undefined ? undefined : JSON.stringify(body),
  }), e, {});
  const text = await res.text();
  let parsed = null;
  try { parsed = text ? JSON.parse(text) : null; } catch { parsed = text; }
  return { status: res.status, body: parsed, headers: res.headers };
}

const stats = (kills) => ({
  global: { kills, deaths: 1000, wins: 60, losses: 40, games: 100, calibrated: true },
  matches: [], level: 50, prestige: 1, mastery: null,
});

async function player(e, pseudo, kills = 1000) {
  const r = await call(e, "POST", "/api/players", { pseudo });
  await call(e, "PUT", `/api/players/${r.body.id}`, stats(kills), r.body.key);
  return r.body;
}

test("create a league: short code, the creator is a member", async () => {
  const e = env();
  const a = await player(e, "Romusan");
  const r = await call(e, "POST", "/api/leagues", { name: "CoDQG France", player_id: a.id }, a.key);
  assert.equal(r.status, 201);
  assert.match(r.body.code, /^[A-HJ-NP-Z2-9]{6}$/);  // no O/0, I/1 to avoid typos
  const board = await call(e, "GET", `/api/leagues/${r.body.code}?sort=kd`);
  assert.equal(board.body.name, "CoDQG France");
  assert.deepEqual(board.body.entries.map((x) => x.pseudo), ["Romusan"]);
});

test("join with the code, ranked among members only", async () => {
  const e = env();
  const a = await player(e, "Romusan", 900);
  const b = await player(e, "Alpha", 1500);
  await player(e, "Pas dans la ligue", 3000);
  const { code } = (await call(e, "POST", "/api/leagues", { name: "Les potes", player_id: a.id }, a.key)).body;
  assert.equal((await call(e, "POST", `/api/leagues/${code.toLowerCase()}/members`, { player_id: b.id }, b.key)).status, 204);
  const board = await call(e, "GET", `/api/leagues/${code}?sort=kd`);
  assert.deepEqual(board.body.entries.map((x) => x.pseudo), ["Alpha", "Romusan"]);
});

test("joining needs the player's own key and a real code", async () => {
  const e = env();
  const a = await player(e, "Romusan");
  const b = await player(e, "Alpha");
  const { code } = (await call(e, "POST", "/api/leagues", { name: "Les potes", player_id: a.id }, a.key)).body;
  assert.equal((await call(e, "POST", `/api/leagues/${code}/members`, { player_id: b.id }, a.key)).status, 401);
  assert.equal((await call(e, "POST", "/api/leagues/ZZZZZZ/members", { player_id: b.id }, b.key)).status, 404);
  assert.equal((await call(e, "POST", "/api/leagues", { name: "Les potes", player_id: a.id }, b.key)).status, 401);
});

test("at most 5 leagues per player", async () => {
  const e = env();
  const a = await player(e, "Romusan");
  for (let i = 1; i <= 5; i++) {
    assert.equal((await call(e, "POST", "/api/leagues", { name: `Ligue ${i}`, player_id: a.id }, a.key)).status, 201);
  }
  const sixth = await call(e, "POST", "/api/leagues", { name: "Ligue 6", player_id: a.id }, a.key);
  assert.equal(sixth.status, 400);
  assert.match(sixth.body.error, /5 ligues/);
});

test("bad league names are refused", async () => {
  const e = env();
  const a = await player(e, "Romusan");
  for (const name of ["ab", "x".repeat(31), "<script>"]) {
    assert.equal((await call(e, "POST", "/api/leagues", { name, player_id: a.id }, a.key)).status, 400, name);
  }
});

test("leaving; the last one out removes the league", async () => {
  const e = env();
  const a = await player(e, "Romusan");
  const b = await player(e, "Alpha");
  const { code } = (await call(e, "POST", "/api/leagues", { name: "Les potes", player_id: a.id }, a.key)).body;
  await call(e, "POST", `/api/leagues/${code}/members`, { player_id: b.id }, b.key);
  assert.equal((await call(e, "DELETE", `/api/leagues/${code}/members/${b.id}`, undefined, b.key)).status, 204);
  assert.deepEqual((await call(e, "GET", `/api/leagues/${code}`)).body.entries.map((x) => x.pseudo), ["Romusan"]);
  await call(e, "DELETE", `/api/leagues/${code}/members/${a.id}`, undefined, a.key);
  assert.equal((await call(e, "GET", `/api/leagues/${code}`)).status, 404);
});

test("a player removed from the site leaves all his leagues", async () => {
  const e = env();
  const a = await player(e, "Romusan");
  const b = await player(e, "Alpha");
  const { code } = (await call(e, "POST", "/api/leagues", { name: "Les potes", player_id: a.id }, a.key)).body;
  await call(e, "POST", `/api/leagues/${code}/members`, { player_id: b.id }, b.key);
  await call(e, "DELETE", `/api/players/${b.id}`, undefined, b.key);
  assert.deepEqual((await call(e, "GET", `/api/leagues/${code}`)).body.entries.map((x) => x.pseudo), ["Romusan"]);
});

test("admin can delete a league", async () => {
  const e = env();
  const a = await player(e, "Romusan");
  const { code } = (await call(e, "POST", "/api/leagues", { name: "Nom douteux", player_id: a.id }, a.key)).body;
  assert.equal((await call(e, "DELETE", `/api/leagues/${code}`, undefined, a.key)).status, 401);
  assert.equal((await call(e, "DELETE", `/api/leagues/${code}`, undefined, "admin-secret")).status, 204);
  assert.equal((await call(e, "GET", `/api/leagues/${code}`)).status, 404);
});

test("league share link gives a Discord card", async () => {
  const PAGE = '<!doctype html><html><head><title>T</title>\n<meta name="description" content="x">\n</head><body>b</body></html>';
  const e = { ...env(), ASSETS: { fetch: async () => new Response(PAGE) } };
  const a = await player(e, "Romusan");
  const { code } = (await call(e, "POST", "/api/leagues", { name: "CoDQG France", player_id: a.id }, a.key)).body;
  const res = await worker.fetch(new Request(`https://site.test/l/${code}`), e, {});
  const html = await res.text();
  assert.equal(res.status, 200);
  assert.match(html, /og:title" content="Ligue CoDQG France · Track COD"/);
  assert.match(html, /<base href="\/">/);
});
