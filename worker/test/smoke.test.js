import { test } from "node:test";
import assert from "node:assert/strict";
import worker from "../src/index.js";

test("unknown api route is a JSON 404", async () => {
  const res = await worker.fetch(new Request("https://x/api/nope"), {}, {});
  assert.equal(res.status, 404);
  assert.deepEqual(await res.json(), { error: "introuvable" });
});
