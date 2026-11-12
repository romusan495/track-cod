import { test } from "node:test";
import assert from "node:assert/strict";
import { playerSummary } from "../../site/joueur.js";

const NOW = 1_800_000_000;
const player = (over = {}) => ({
  id: "x", pseudo: "Romusan", updated_at: NOW * 1000,
  data: {
    global: { kills: 2134, deaths: 2372, wins: 70, losses: 58, games: 128, calibrated: true },
    matches: [{ at: NOW - 7200, mode: "Match à mort par équipe", map: "Village", kills: 33, deaths: 18, score: 4270, result: "win" }],
    level: 54, prestige: 1, mastery: { or: 6, platine: 1, rupture: 0 }, ...over,
  },
});

test("summary of a calibrated player", () => {
  const s = playerSummary(player(), NOW);
  assert.equal(s.title, "Romusan");
  assert.equal(s.sub, "Niv. 54 · Prestige 1");
  assert.deepEqual(s.tiles.map((t) => t[1]), ["0.90", "55 %", "2 134", "128"]);
  assert.equal(s.note, "");
  assert.deepEqual(s.matches[0], { title: "Match à mort par équipe", sub: "Village · il y a 2 h", kd: "33 / 18", pts: "4 270 pts", result: "win" });
  assert.deepEqual(s.mastery, [["Or", "6"], ["Platine", "1/33"], ["Rupture", "0/33"]]);
});

test("uncalibrated global", () => {
  const s = playerSummary(player({ global: { kills: 0, deaths: 0, wins: 0, losses: 0, games: 0, calibrated: false } }), NOW);
  assert.equal(s.note, "global en attente de calibrage");
  assert.ok(s.tiles.every((t) => t[1] === "—"));
});

test("no mastery, no level", () => {
  const s = playerSummary(player({ mastery: null, level: null, prestige: null }), NOW);
  assert.equal(s.mastery, null);
  assert.equal(s.sub, "");
});

test("zero deaths never gives NaN", () => {
  const s = playerSummary(player({
    global: { kills: 12, deaths: 0, wins: 1, losses: 0, games: 1, calibrated: true },
    matches: [{ at: NOW - 60, mode: null, map: null, kills: 12, deaths: 0, score: null, result: null }],
  }), NOW);
  assert.equal(s.tiles[0][1], "12.00");
  assert.equal(s.matches[0].kd, "12 / 0");
  assert.equal(s.matches[0].title, "Partie");
  assert.ok(!JSON.stringify(s).includes("NaN"));
});
