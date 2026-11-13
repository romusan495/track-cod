// Track COD site: the static pages in ../site are served by Workers static assets;
// this Worker sees /api/* (JSON API), /p/<id> (share links) and the daily cron.

import { leaderboard, SORTS } from "./rank.js";
import { sharePage } from "./share.js";
import { makeStore } from "./store.js";
import { validatePseudo, validateUpdate } from "./validate.js";

const RATE_MS = 30_000;              // at most one update per 30 s per player
const IDLE_MS = 90 * 86_400_000;     // profiles idle for 90 days are removed
const BOARD_TTL_MS = 60_000;          // leaderboard kept 1 min: protects the free D1 daily quota
const boards = new WeakMap();         // per database: sort -> { at, body }

export function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });
}

const empty = (status = 204) => new Response(null, { status });
const now = (env) => (typeof env.NOW === "number" ? env.NOW : Date.now());

function hex(bytes) {
  return [...new Uint8Array(bytes)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function sha256(text) {
  return hex(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text)));
}

function bearer(request) {
  const m = /^Bearer\s+(.+)$/.exec(request.headers.get("authorization") || "");
  return m ? m[1].trim() : null;
}

async function readJson(request) {
  try {
    return await request.json();
  } catch {
    return null;
  }
}

async function register(request, env, store) {
  const body = await readJson(request);
  const p = validatePseudo(body?.pseudo);
  if (!p.ok) return json({ error: p.error }, 400);
  if (await store.byKey(p.key)) return json({ error: "pseudo déjà pris" }, 409);
  const key = hex(crypto.getRandomValues(new Uint8Array(32)));
  const id = crypto.randomUUID();
  await store.create({ id, pseudo: p.pseudo, pseudoKey: p.key, keyHash: await sha256(key), now: now(env) });
  return json({ id, key }, 201);
}

async function update(request, env, store, id) {
  const player = await store.get(id);
  const key = bearer(request);
  if (!player) return json({ error: "introuvable" }, 404);
  if (!key || (await sha256(key)) !== player.key_hash) return json({ error: "clé invalide" }, 401);
  const published = Object.keys(player.data).length > 0;  // the first update right after joining is allowed
  if (published && now(env) - player.updated_at < RATE_MS) return json({ error: "trop rapide" }, 429);
  const v = validateUpdate(await readJson(request));
  if (!v.ok) return json({ error: v.error }, 400);
  await store.update(id, v.data, now(env));
  return empty();
}

async function remove(request, env, store, id) {
  const player = await store.get(id);
  const key = bearer(request);
  if (!player) return json({ error: "introuvable" }, 404);
  const admin = env.ADMIN_KEY && key === env.ADMIN_KEY;
  if (!admin && (!key || (await sha256(key)) !== player.key_hash)) return json({ error: "clé invalide" }, 401);
  await store.remove(id);
  return empty();
}

export default {
  async fetch(request, env, ctx) {
    try {
      return await route(request, env);
    } catch (err) {
      // D1 over the free daily quota (or down): a clear message instead of an error page
      console.error(err);
      return json({ error: "site surchargé, réessaie dans quelques minutes" }, 503);
    }
  },

  async scheduled(event, env, ctx) {
    await makeStore(env.DB).purge(now(env) - IDLE_MS);
  },
};

async function route(request, env) {
  const url = new URL(request.url);
  const store = makeStore(env.DB);
  const method = request.method;
  const one = /^\/api\/players\/([0-9a-f-]{36})$/.exec(url.pathname);

  const share = /^\/p\/([0-9a-f-]{36})$/.exec(url.pathname);
  if (share && method === "GET") {
    const p = await store.get(share[1]);
    if (!p) return Response.redirect(`${url.origin}/`, 302);
    return sharePage(p, url.origin, env.ASSETS);
  }
  if (url.pathname === "/api/players" && method === "POST") return register(request, env, store);
  if (url.pathname === "/api/leaderboard" && method === "GET") {
    const sort = SORTS.includes(url.searchParams.get("sort")) ? url.searchParams.get("sort") : "kd";
    if (!boards.has(env.DB)) boards.set(env.DB, new Map());
    const cache = boards.get(env.DB);
    const hit = cache.get(sort);
    if (hit && now(env) - hit.at < BOARD_TTL_MS) return json(hit.body);
    const body = { sort, entries: leaderboard(await store.all(), sort) };
    cache.set(sort, { at: now(env), body });
    return json(body);
  }
  if (one && method === "GET") {
    const p = await store.get(one[1]);
    if (!p) return json({ error: "introuvable" }, 404);
    return json({ id: p.id, pseudo: p.pseudo, updated_at: p.updated_at, data: p.data });
  }
  if (one && method === "PUT") return update(request, env, store, one[1]);
  if (one && method === "DELETE") return remove(request, env, store, one[1]);
  return json({ error: "introuvable" }, 404);
}
