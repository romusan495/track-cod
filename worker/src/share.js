// Share link /p/<id>: the player page with its card already in the HTML, because Discord, WhatsApp and the
// like read the raw HTML and never run the page's JavaScript.

const NNBSP = " ";

const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const int = (n) => String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, NNBSP);

export function shareText(player) {
  const d = player.data || {};
  const g = d.global;
  const title = g && g.calibrated
    ? `${player.pseudo} · K/D ${(g.kills / Math.max(g.deaths, 1)).toFixed(2)} · ${Math.round((g.wins / Math.max(g.games, 1)) * 100)}${NNBSP}% de victoires`
    : `${player.pseudo} · stats Call of Duty MW4`;
  const parts = [];
  if (g && g.calibrated) parts.push(`${g.games} parties`, `${int(g.kills)} éliminations`);
  if (d.level != null) parts.push(`Niv. ${d.level}`);
  if (d.prestige != null) parts.push(`Prestige ${d.prestige}`);
  const description = `${parts.join(" · ")}${parts.length ? " — " : ""}stats MW4 suivies avec Track COD`;
  return { title, description };
}

export function shareMeta(player, origin) {
  const { title, description } = shareText(player);
  const url = `${origin}/p/${player.id}`;
  return [
    `<meta property="og:type" content="profile">`,
    `<meta property="og:site_name" content="Track COD">`,
    `<meta property="og:title" content="${esc(title)}">`,
    `<meta property="og:description" content="${esc(description)}">`,
    `<meta property="og:url" content="${esc(url)}">`,
    `<meta property="og:image" content="${origin}/og-banner.jpg">`,
    `<meta property="og:image:width" content="1200">`,
    `<meta property="og:image:height" content="630">`,
    `<meta name="twitter:card" content="summary_large_image">`,
    `<meta name="theme-color" content="#f2b134">`,
    `<link rel="canonical" href="${esc(url)}">`,
  ].join("\n");
}

function inject(html, { pageTitle, title, description, url, type }, origin) {
  html = html.replace("<head>", `<head><base href="/">`);
  html = html.replace(/<title>[^<]*<\/title>/, `<title>${esc(pageTitle)}</title>`);
  html = html.replace(/<meta name="description"[^>]*>/, `<meta name="description" content="${esc(description)}">`);
  const meta = [
    `<meta property="og:type" content="${type}">`,
    `<meta property="og:site_name" content="Track COD">`,
    `<meta property="og:title" content="${esc(title)}">`,
    `<meta property="og:description" content="${esc(description)}">`,
    `<meta property="og:url" content="${esc(url)}">`,
    `<meta property="og:image" content="${origin}/og-banner.jpg">`,
    `<meta name="twitter:card" content="summary_large_image">`,
    `<meta name="theme-color" content="#f2b134">`,
  ].join("\n");
  return html.replace("</head>", `${meta}\n</head>`);
}

export async function leaguePage(league, members, origin, assets) {
  const res = await assets.fetch(new Request(`${origin}/ligue`));
  const title = `Ligue ${league.name} · Track COD`;
  const description = `Classement privé de ${members} joueur${members > 1 ? "s" : ""} sur Track COD (Call of Duty MW4). Code : ${league.code}`;
  const html = inject(await res.text(), { pageTitle: title, title, description, url: `${origin}/l/${league.code}`, type: "website" }, origin);
  return new Response(html, { headers: { "content-type": "text/html; charset=utf-8", "cache-control": "public, max-age=300" } });
}

export async function sharePage(player, origin, assets) {
  const res = await assets.fetch(new Request(`${origin}/joueur`));
  let html = await res.text();
  html = html.replace("<head>", `<head><base href="/">`);  // relative links (style.css, joueur.js) from /p/<id>
  html = html.replace(/<title>[^<]*<\/title>/, `<title>${esc(player.pseudo)} · Track COD</title>`);
  html = html.replace(/<meta name="description"[^>]*>/, `<meta name="description" content="${esc(shareText(player).description)}">`);
  html = html.replace("</head>", `${shareMeta(player, origin)}\n</head>`);
  return new Response(html, { headers: { "content-type": "text/html; charset=utf-8", "cache-control": "public, max-age=300" } });
}
