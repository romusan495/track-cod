// Checks what a tracker sends before it is stored. Only the listed fields are kept: anything else
// (another player's name, unknown keys) is dropped. Limits come from the site design (2026-11-13).

const PSEUDO = /^[\p{L}\p{N} _\-\[\]]{3,20}$/u;
const RESULTS = new Set(["win", "loss", "draw", null]);
const MAX_MATCHES = 5;

const fail = (error) => ({ ok: false, error });
const isInt = (n, min, max = Number.MAX_SAFE_INTEGER) => Number.isInteger(n) && n >= min && n <= max;
const text = (s, max = 60) => (typeof s === "string" ? s.trim().slice(0, max) : null);

export function validatePseudo(p) {
  if (typeof p !== "string") return fail("pseudo manquant");
  const pseudo = p.trim().normalize("NFC");
  if (!PSEUDO.test(pseudo)) {
    return fail("pseudo invalide : 3 à 20 caractères, lettres, chiffres, espaces, - _ [ ]");
  }
  return { ok: true, pseudo, key: pseudo.toLowerCase() };
}

function validateGlobal(g) {
  if (!g || typeof g !== "object") return fail("stats globales manquantes");
  const { kills, deaths, wins, losses, games } = g;
  if (![kills, deaths, wins, losses, games].every((n) => isInt(n, 0))) {
    return fail("stats globales invalides");
  }
  // before calibration the global is only a few recorded matches: a 25/0 game is real, not absurd
  if (g.calibrated === true && kills / Math.max(deaths, 1) > 20) return fail("K/D global invraisemblable (plus de 20)");
  if (games < wins + losses) return fail("plus de victoires et défaites que de parties");
  return { ok: true, data: { kills, deaths, wins, losses, games, calibrated: g.calibrated === true } };
}

function validateMatch(m) {
  if (!m || typeof m !== "object") return fail("partie invalide");
  if (!isInt(m.at, 0)) return fail("date de partie invalide");
  if (!isInt(m.kills, 0, 150)) return fail("éliminations de partie invraisemblables (0 à 150)");
  if (!isInt(m.deaths, 0, 500)) return fail("morts de partie invalides");
  const score = m.score ?? null;
  if (score !== null && !isInt(score, 0, 50000)) return fail("score de partie invraisemblable (0 à 50 000)");
  const result = m.result ?? null;
  if (!RESULTS.has(result)) return fail("résultat de partie invalide");
  return { ok: true, data: { at: m.at, mode: text(m.mode), map: text(m.map), kills: m.kills, deaths: m.deaths, score, result } };
}

export function validateUpdate(body) {
  if (!body || typeof body !== "object") return fail("données manquantes");
  const global = validateGlobal(body.global);
  if (!global.ok) return global;

  const raw = Array.isArray(body.matches) ? body.matches : [];
  const matches = [];
  for (const m of raw) {
    const r = validateMatch(m);
    if (!r.ok) return r;
    matches.push(r.data);
  }
  matches.sort((a, b) => b.at - a.at);

  const level = body.level ?? null;
  if (level !== null && !isInt(level, 1, 99)) return fail("niveau invalide (1 à 99)");
  const prestige = body.prestige ?? null;
  if (prestige !== null && !isInt(prestige, 0, 99)) return fail("prestige invalide (0 à 99)");

  let mastery = null;
  if (body.mastery) {
    const { or, platine, rupture } = body.mastery;
    if (![or, platine, rupture].every((n) => isInt(n, 0, 1000))) return fail("maîtrise invalide");
    mastery = { or, platine, rupture };
  }
  return { ok: true, data: { global: global.data, matches: matches.slice(0, MAX_MATCHES), level, prestige, mastery } };
}
