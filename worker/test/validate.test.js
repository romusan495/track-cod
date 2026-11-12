import { test } from "node:test";
import assert from "node:assert/strict";
import { validatePseudo, validateUpdate } from "../src/validate.js";

const match = (at, kills = 20, deaths = 10) =>
  ({ at, mode: "Match à mort par équipe", map: "Village", kills, deaths, score: 3000, result: "win" });

const body = (over = {}) => ({
  global: { kills: 2134, deaths: 2372, wins: 70, losses: 58, games: 128, calibrated: true },
  matches: [1, 2, 3, 4, 5].map((i) => match(1794500000 + i)),
  level: 54, prestige: 1, mastery: null, ...over,
});

test("pseudo ok", () => {
  assert.deepEqual(validatePseudo(" Romusan "), { ok: true, pseudo: "Romusan", key: "romusan" });
});

test("pseudo accents", () => {
  assert.equal(validatePseudo("Éloïse_[FR]").ok, true);
  assert.equal(validatePseudo("Ядро").ok, true);
});

test("pseudo refused", () => {
  for (const p of ["ab", "a".repeat(21), "<b>x</b>", "a;b", 42, null]) {
    const r = validatePseudo(p);
    assert.equal(r.ok, false, String(p));
    assert.match(r.error, /pseudo/i);
  }
});

test("update ok", () => {
  const r = validateUpdate(body());
  assert.equal(r.ok, true);
  assert.equal(r.data.matches.length, 5);
  assert.equal(r.data.mastery, null);
});

test("limits", () => {
  const bad = [
    body({ global: { kills: 21, deaths: 1, wins: 0, losses: 0, games: 1, calibrated: true } }),
    body({ matches: [match(1, 151, 3)] }),
    body({ matches: [{ ...match(1), score: 50001 }] }),
    body({ global: { kills: 10, deaths: 10, wins: 5, losses: 5, games: 9, calibrated: true } }),
    body({ level: 0 }), body({ level: 100 }), body({ prestige: 100 }),
    body({ global: { kills: -1, deaths: 1, wins: 0, losses: 0, games: 0, calibrated: true } }),
    body({ matches: [{ ...match(1), result: "bof" }] }),
  ];
  for (const b of bad) {
    const r = validateUpdate(b);
    assert.equal(r.ok, false, JSON.stringify(b).slice(0, 120));
    assert.equal(typeof r.error, "string");
  }
});

test("extra matches trimmed", () => {
  const r = validateUpdate(body({ matches: [1, 7, 3, 6, 2, 5, 4].map((i) => match(i)) }));
  assert.equal(r.ok, true);
  assert.deepEqual(r.data.matches.map((m) => m.at), [7, 6, 5, 4, 3]);
});

test("unknown fields dropped", () => {
  const r = validateUpdate({ ...body(), gamertags: ["x"], matches: [{ ...match(1), team: ["autre"] }] });
  assert.equal(r.ok, true);
  assert.equal("gamertags" in r.data, false);
  assert.equal("team" in r.data.matches[0], false);
});

test("mastery kept when given", () => {
  const r = validateUpdate(body({ mastery: { or: 6, platine: 1, rupture: 0 } }));
  assert.deepEqual(r.data.mastery, { or: 6, platine: 1, rupture: 0 });
});

test("uncalibrated global may have a high K/D (a few matches only)", () => {
  const r = validateUpdate(body({ global: { kills: 25, deaths: 0, wins: 1, losses: 0, games: 1, calibrated: false } }));
  assert.equal(r.ok, true);
});
