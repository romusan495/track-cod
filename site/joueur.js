// Player page (joueur.html?id=...). playerSummary is pure (tested in Node); rendering uses textContent only.

import { el, fmtInt, fmtKd, fmtPct, fmtWhen, setDownloadLinks } from "./app.js";

const HARMONIC_GOAL = 33;
const NONE = "—";

export function playerSummary(player, now = Date.now() / 1000) {
  const d = player.data || {};
  const g = d.global;
  const sub = [d.level != null ? `Niv. ${d.level}` : null, d.prestige != null ? `Prestige ${d.prestige}` : null]
    .filter(Boolean).join(" · ");
  const calibrated = Boolean(g && g.calibrated);
  const tiles = [
    ["K/D global", calibrated ? fmtKd(g.kills / Math.max(g.deaths, 1)) : NONE],
    ["Victoires", calibrated ? fmtPct(g.wins / Math.max(g.games, 1)) : NONE],
    ["Éliminations", calibrated ? fmtInt(g.kills) : NONE],
    ["Parties", calibrated ? String(g.games) : NONE],
  ];
  const matches = (d.matches || []).map((m) => ({
    title: m.mode || "Partie",
    sub: [m.map, fmtWhen(m.at, now)].filter(Boolean).join(" · "),
    kd: `${m.kills} / ${m.deaths}`,
    pts: m.score != null ? `${fmtInt(m.score)} pts` : "",
    result: m.result || null,
  }));
  const mastery = d.mastery
    ? [["Or", String(d.mastery.or)], ["Platine", `${d.mastery.platine}/${HARMONIC_GOAL}`],
       ["Rupture", `${d.mastery.rupture}/${HARMONIC_GOAL}`]]
    : null;
  return { title: player.pseudo, sub, tiles, note: calibrated ? "" : "global en attente de calibrage", matches, mastery };
}

export function renderPlayer(container, player, now) {
  const s = playerSummary(player, now);
  document.title = `${s.title} · Track COD`;
  const head = el("div", "head");
  head.append(el("h1", null, s.title), el("span", null, s.sub));
  const tiles = el("div", "tiles");
  for (const [label, value] of s.tiles) {
    const t = el("div", "tile");
    t.append(el("b", null, value), el("span", null, label));
    tiles.append(t);
  }
  container.replaceChildren(head, tiles);
  if (s.note) container.append(el("p", "note", s.note));

  const n = s.matches.length;
  container.append(el("div", "sect", n > 1 ? `${n} dernières parties` : n === 1 ? "Dernière partie" : "Dernières parties"));
  if (!s.matches.length) container.append(el("p", "note", "Aucune partie publiée pour l'instant."));
  for (const m of s.matches) {
    const row = el("div", `match ${m.result || ""}`.trim());
    const left = el("div", null, m.title);
    left.append(el("small", null, m.sub));
    const right = el("div", "kd", m.kd);
    right.append(el("small", null, m.pts));
    row.append(left, right);
    container.append(row);
  }

  if (s.mastery) {
    container.append(el("div", "sect", "Maîtrise des camos"));
    const grid = el("div", "mast");
    for (const [label, value] of s.mastery) {
      const c = el("div");
      c.append(el("b", null, value), el("span", null, label));
      grid.append(c);
    }
    container.append(grid);
  }
}

async function initPlayer() {
  setDownloadLinks();
  const box = document.querySelector("#player");
  const id = new URLSearchParams(location.search).get("id") || "";
  try {
    const res = await fetch(`/api/players/${encodeURIComponent(id)}`);
    if (res.status === 404) {
      box.replaceChildren(el("p", "empty", "Joueur introuvable."));
      return;
    }
    if (!res.ok) throw new Error(res.status);
    renderPlayer(box, await res.json());
  } catch {
    box.replaceChildren(el("p", "empty", "Page indisponible pour le moment, réessaie plus tard."));
  }
}

if (typeof document !== "undefined" && document.querySelector("#player")) initPlayer();
