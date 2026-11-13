// Track COD site: leaderboard page + formatters shared with joueur.js (also imported by the Node tests,
// so nothing touches the DOM at import time). Player text is always inserted with textContent.

export const DOWNLOAD_URL = "https://github.com/romusan495/track-cod/releases/latest";
const NNBSP = " ";

export const SORTS = [
  { key: "kd", tab: "K/D", label: "K/D" },
  { key: "wins", tab: "Victoires", label: "Vict." },
  { key: "kills", tab: "Élim.", label: "Élim." },
  { key: "form", tab: "5 dernières", label: "K/D 5 dern." },
];

export const fmtKd = (n) => Number(n).toFixed(2);
export const fmtPct = (x) => `${Math.round(x * 100)}${NNBSP}%`;
export const fmtInt = (n) => String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, NNBSP);
export const sortLabel = (key) => (SORTS.find((s) => s.key === key) || SORTS[0]).label;

export function fmtWhen(at, now = Date.now() / 1000) {
  const s = Math.max(0, now - at);
  if (s < 3600) return `il y a ${Math.max(1, Math.round(s / 60))} min`;
  if (s < 86400) return `il y a ${Math.round(s / 3600)} h`;
  if (s < 2 * 86400) return "hier";
  const d = new Date(at * 1000);
  return `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined && text !== null) e.textContent = String(text);
  return e;
}

export function formDots(form) {
  const box = el("div", "form");
  for (const r of form) box.append(el("i", `dot ${r}`));
  return box;
}

function valueText(entry, sort) {
  if (sort === "wins") return fmtPct(entry.value);
  if (sort === "kills") return fmtInt(entry.value);
  return fmtKd(entry.value);
}

export function renderLeaderboard(container, entries, sort) {
  container.replaceChildren();
  if (!entries.length) {
    const box = el("div", "empty", sort === "form"
      ? "Personne n'a encore 5 parties publiées."
      : "Aucun joueur classé pour l'instant — il faut au moins 10 parties.");
    const dl = el("a", "dl", "⬇ Télécharger le traqueur");
    dl.href = DOWNLOAD_URL;
    box.append(el("br"), dl);
    container.append(box);
    return;
  }
  entries.forEach((e, i) => {
    const card = el("a", "card");
    card.href = `joueur.html?id=${encodeURIComponent(e.id)}`;
    const who = el("div", "who");
    who.append(el("b", null, e.pseudo), el("span", null, `${e.games} parties · ${fmtPct(e.winRate)} vict.`), formDots(e.form));
    const big = el("div", "big", valueText(e, sort));
    big.append(el("small", null, sortLabel(sort)));
    card.append(el("div", "rk", i + 1), who, big);
    container.append(card);
  });
}

export function setDownloadLinks() {
  for (const a of document.querySelectorAll("[data-download]")) a.href = DOWNLOAD_URL;
}

async function initLeaderboard() {
  setDownloadLinks();
  const tabs = document.querySelector("#tabs");
  const board = document.querySelector("#board");
  const params = new URLSearchParams(location.search);
  let sort = SORTS.some((s) => s.key === params.get("tri")) ? params.get("tri") : "kd";

  async function load() {
    for (const b of tabs.children) b.setAttribute("aria-pressed", String(b.dataset.key === sort));
    board.replaceChildren(el("p", "empty", "Chargement…"));
    try {
      const res = await fetch(`/api/leaderboard?sort=${sort}`);
      if (!res.ok) throw new Error(res.status);
      renderLeaderboard(board, (await res.json()).entries, sort);
    } catch {
      board.replaceChildren(el("p", "empty", "Classement indisponible pour le moment, réessaie plus tard."));
    }
  }

  for (const s of SORTS) {
    const b = el("button", "tab", s.tab);
    b.type = "button";
    b.dataset.key = s.key;
    b.addEventListener("click", () => {
      sort = s.key;
      history.replaceState(null, "", s.key === "kd" ? location.pathname : `?tri=${s.key}`);
      load();
    });
    tabs.append(b);
  }
  load();
}

if (typeof document !== "undefined" && document.querySelector("#board")) initLeaderboard();
