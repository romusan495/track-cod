import { test } from "node:test";
import assert from "node:assert/strict";
import { kd, leaderboard } from "../src/rank.js";

const m = (at, kills, deaths, result = "win") => ({ at, mode: "Domination", map: "Port", kills, deaths, score: 1000, result });
const player = (id, pseudo, global, matches = []) => ({ id, pseudo, data: { global, matches, level: null, prestige: null, mastery: null } });
const g = (kills, deaths, wins, losses, games, calibrated = true) => ({ kills, deaths, wins, losses, games, calibrated });

test("kd with zero deaths", () => {
  assert.equal(kd(12, 0), 12);
  assert.equal(kd(9, 10), 0.9);
});

test("uncalibrated not ranked", () => {
  const rows = [player("a", "A", g(100, 50, 10, 5, 20, false)), player("b", "B", g(100, 50, 5, 4, 9)),
                player("c", "C", g(100, 50, 6, 4, 10))];
  assert.deepEqual(leaderboard(rows, "kd").map((e) => e.id), ["c"]);
});

test("form needs 5", () => {
  const four = [1, 2, 3, 4].map((i) => m(i, 10, 5));
  const five = [m(5, 30, 10), m(4, 10, 10, "loss"), m(3, 10, 10), m(2, 0, 0, "draw"), m(1, 10, 0)];
  const rows = [player("a", "A", g(100, 50, 10, 5, 20), four), player("b", "B", g(100, 50, 10, 5, 20), five)];
  const out = leaderboard(rows, "form");
  assert.deepEqual(out.map((e) => e.id), ["b"]);
  assert.equal(out[0].formKd, 60 / 30);
  assert.deepEqual(out[0].form, ["w", "l", "w", "d", "w"]);
});

test("sort wins", () => {
  const rows = [player("a", "Alpha", g(10, 10, 5, 5, 10)), player("b", "Bravo", g(10, 10, 8, 2, 10)),
                player("c", "Charlie", g(10, 10, 5, 5, 10))];
  const out = leaderboard(rows, "wins");
  assert.deepEqual(out.map((e) => e.id), ["b", "a", "c"]);  // ties by pseudo
  assert.equal(out[0].value, 0.8);
  assert.equal(out[0].winRate, 0.8);
});

test("kills and kd sorts", () => {
  const rows = [player("a", "A", g(2000, 2000, 5, 5, 10)), player("b", "B", g(500, 100, 5, 5, 10))];
  assert.deepEqual(leaderboard(rows, "kills").map((e) => e.id), ["a", "b"]);
  assert.deepEqual(leaderboard(rows, "kd").map((e) => e.id), ["b", "a"]);
});

test("form shown on every tab when 5 matches exist", () => {
  const rows = [player("a", "A", g(100, 50, 10, 5, 20), [m(1, 10, 5, "loss")])];
  const out = leaderboard(rows, "kd");
  assert.deepEqual(out[0].form, ["l"]);
  assert.equal(out[0].formKd, null);
});
