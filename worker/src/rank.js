// Leaderboard (layout B): only calibrated players with at least 10 games; the « 5 dernières » tab
// needs 5 published matches.

export const MIN_GAMES = 10;
export const FORM_MATCHES = 5;
export const SORTS = ["kd", "wins", "kills", "form"];

export const kd = (kills, deaths) => kills / Math.max(deaths, 1);

const FORM = { win: "w", loss: "l", draw: "d" };

function entry(p) {
  const g = p.data?.global;
  if (!g || !g.calibrated || g.games < MIN_GAMES) return null;
  const recent = (p.data.matches || []).slice(0, FORM_MATCHES);
  const formKd = recent.length >= FORM_MATCHES
    ? kd(recent.reduce((s, m) => s + m.kills, 0), recent.reduce((s, m) => s + m.deaths, 0))
    : null;
  return {
    id: p.id, pseudo: p.pseudo, games: g.games, winRate: g.wins / g.games, kd: kd(g.kills, g.deaths),
    kills: g.kills, form: recent.map((m) => FORM[m.result] || "d"), formKd,
  };
}

const VALUE = { kd: (e) => e.kd, wins: (e) => e.winRate, kills: (e) => e.kills, form: (e) => e.formKd };

export function leaderboard(players, sort) {
  const key = SORTS.includes(sort) ? sort : "kd";
  return players
    .map(entry)
    .filter((e) => e && VALUE[key](e) !== null)
    .map((e) => ({ ...e, value: VALUE[key](e) }))
    .sort((a, b) => b.value - a.value || a.pseudo.localeCompare(b.pseudo, "fr"));
}
