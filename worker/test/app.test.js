import { test } from "node:test";
import assert from "node:assert/strict";
import { fmtInt, fmtKd, fmtPct, fmtWhen, sortLabel } from "../../site/app.js";

const NNBSP = " ";

test("number formats", () => {
  assert.equal(fmtKd(0.9), "0.90");
  assert.equal(fmtKd(12), "12.00");
  assert.equal(fmtPct(0.552), `55${NNBSP}%`);
  assert.equal(fmtInt(2134), `2${NNBSP}134`);
  assert.equal(fmtInt(128), "128");
});

test("relative dates", () => {
  const now = 1_800_000_000;
  assert.equal(fmtWhen(now - 7200, now), "il y a 2 h");
  assert.equal(fmtWhen(now - 600, now), "il y a 10 min");
  assert.equal(fmtWhen(now - 26 * 3600, now), "hier");
  assert.match(fmtWhen(now - 5 * 86400, now), /^\d{2}\/\d{2}$/);
});

test("labels of the sorted value", () => {
  assert.equal(sortLabel("kd"), "K/D");
  assert.equal(sortLabel("form"), "K/D 5 dern.");
});

test("league code from the address", async () => {
  const { leagueCode } = await import("../../site/app.js");
  assert.equal(leagueCode("/l/qg7k2p", ""), "QG7K2P");
  assert.equal(leagueCode("/ligue", "?code=ABCDEF"), "ABCDEF");
  assert.equal(leagueCode("/", ""), null);
  assert.equal(leagueCode("/l/trop-long", ""), null);
});
