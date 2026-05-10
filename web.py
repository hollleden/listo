from aiohttp import web

import database

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Listo – Your Second Brain</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #FAF8F5;
  --card: #FFFFFF;
  --accent: #7F77DD;
  --text: #1A1A1A;
  --muted: #6B7280;
  --border: #E5E7EB;
  --danger: #EF4444;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); font-family: Inter, sans-serif; color: var(--text); max-width: 480px; margin: 0 auto; padding: 16px; }
a { color: var(--accent); }

/* Header */
.header { margin-bottom: 20px; }
.header h1 { font-size: 24px; font-weight: 700; }
.header .sub { font-size: 13px; color: var(--muted); margin-top: 2px; }

/* Stats bar */
.stats { font-size: 12px; color: var(--muted); margin-bottom: 16px; }

/* Token gate */
#token-gate { margin-bottom: 20px; }
#token-gate p { font-size: 14px; margin-bottom: 8px; color: var(--muted); }
.token-row { display: flex; gap: 8px; }
#token-input { flex: 1; padding: 8px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 14px; font-family: Inter, sans-serif; outline: none; }
#token-input:focus { border-color: var(--accent); }
#token-go { padding: 8px 16px; background: var(--accent); color: #fff; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; }

/* Tabs */
.tabs { display: flex; gap: 0; margin-bottom: 16px; border-bottom: 1px solid var(--border); }
.tab { padding: 8px 16px; font-size: 14px; font-weight: 500; color: var(--muted); cursor: pointer; border-bottom: 2px solid transparent; margin-bottom: -1px; }
.tab.active { color: var(--accent); border-bottom-color: var(--accent); }

/* Folder pills */
.pills { display: flex; gap: 8px; overflow-x: auto; padding-bottom: 12px; margin-bottom: 16px; scrollbar-width: none; }
.pills::-webkit-scrollbar { display: none; }
.pill { flex-shrink: 0; padding: 5px 12px; border-radius: 20px; font-size: 12px; font-weight: 500; cursor: pointer; border: 1px solid var(--border); background: var(--card); color: var(--text); white-space: nowrap; }
.pill.active { background: var(--accent); color: #fff; border-color: var(--accent); }

/* Search */
#search-input { width: 100%; padding: 10px 14px; border: 1px solid var(--border); border-radius: 10px; font-size: 14px; font-family: Inter, sans-serif; outline: none; margin-bottom: 16px; }
#search-input:focus { border-color: var(--accent); }

/* Cards */
.card { background: var(--card); border-radius: 12px; padding: 14px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); border: 1px solid var(--border); transition: opacity 0.3s; }
.card.fading { opacity: 0; }
.card-title { font-size: 14px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 5px; }
.card-summary { font-size: 13px; color: var(--muted); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; margin-bottom: 8px; line-height: 1.4; }
.card-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px; }
.card-tag { font-size: 11px; padding: 2px 7px; border-radius: 10px; background: rgba(127,119,221,0.12); color: var(--accent); font-weight: 500; }
.card-footer { display: flex; justify-content: space-between; align-items: center; }
.card-date { font-size: 11px; color: var(--muted); }
.delete-btn { background: none; border: none; cursor: pointer; font-size: 14px; padding: 2px 4px; color: var(--muted); opacity: 0.6; }
.delete-btn:hover { opacity: 1; color: var(--danger); }

/* Empty / error states */
.empty { text-align: center; padding: 40px 20px; color: var(--muted); font-size: 14px; line-height: 1.6; }
.error-msg { color: var(--danger); font-size: 13px; padding: 12px; background: rgba(239,68,68,0.07); border-radius: 8px; margin-bottom: 16px; }

/* Hidden */
.hidden { display: none !important; }
</style>
</head>
<body>

<div class="header">
  <h1>🧠 Listo</h1>
  <div class="sub">your second brain</div>
</div>

<div class="stats hidden" id="stats-bar"></div>
<div class="error-msg hidden" id="error-msg"></div>

<div id="token-gate" class="hidden">
  <p>Enter your token to view your saves:</p>
  <div class="token-row">
    <input id="token-input" type="text" placeholder="paste your token">
    <button id="token-go">Go</button>
  </div>
</div>

<div id="main-ui" class="hidden">
  <div class="tabs">
    <div class="tab active" data-tab="browse">Browse</div>
    <div class="tab" data-tab="search">Search</div>
  </div>

  <div id="tab-browse">
    <div class="pills" id="pills"></div>
    <div id="browse-cards"></div>
  </div>

  <div id="tab-search" class="hidden">
    <input id="search-input" type="text" placeholder="Search your saves…">
    <div id="search-cards"></div>
  </div>
</div>

<script>
const FOLDERS = [
  ["All","All"],["🌍","Travel"],["📚","Books"],["🤖","AI"],["🧥","Fashion"],
  ["💄","Beauty"],["🎬","Movies"],["🧶","Knitting"],["🍽️","Food"],["💻","Tech"],
  ["💡","LifeHack"],["🧠","Psychology"],["💪","Health"],["💰","Finance"],
  ["🎨","Design"],["💬","Language"],["🌿","Nature"],["🎵","Music"],
  ["📷","Photography"],["👶","Parenting"],["📌","Other"]
];

let TOKEN = "";
let activeFolder = "All";
let searchTimer = null;

function getToken() {
  const p = new URLSearchParams(location.search);
  return p.get("token") || "";
}

function showError(msg) {
  const el = document.getElementById("error-msg");
  el.textContent = msg;
  el.classList.remove("hidden");
}

function renderCard(e) {
  const tags = (e.tags || "").split(" ").filter(Boolean).slice(0, 5);
  const tagsHtml = tags.map(t => `<span class="card-tag">${escHtml(t)}</span>`).join("");
  const title = e.title || e.folder || "";
  const emoji = folderEmoji(e.folder);
  return `
  <div class="card" id="card-${e.id}">
    <div class="card-title">${emoji} ${escHtml(e.folder.toUpperCase())}${title ? " · " + escHtml(title) : ""}</div>
    <div class="card-summary">${escHtml(e.summary || "")}</div>
    ${tags.length ? `<div class="card-tags">${tagsHtml}</div>` : ""}
    <div class="card-footer">
      <span class="card-date">${e.created_at || ""}</span>
      <button class="delete-btn" onclick="deleteEntry(${e.id})" title="Delete">🗑️</button>
    </div>
  </div>`;
}

function folderEmoji(folder) {
  const map = {Travel:"🌍",Books:"📚",AI:"🤖",Fashion:"🧥",Beauty:"💄",Movies:"🎬",
    Knitting:"🧶",Food:"🍽️",Tech:"💻",LifeHack:"💡",Psychology:"🧠",Health:"💪",
    Finance:"💰",Design:"🎨",Language:"💬",Nature:"🌿",Music:"🎵",Photography:"📷",
    Parenting:"👶",Other:"📌"};
  return map[folder] || "📌";
}

function escHtml(s) {
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

function renderCards(entries, containerId) {
  const el = document.getElementById(containerId);
  if (!entries.length) {
    el.innerHTML = `<div class="empty">Nothing saved yet. Send a photo or video to @listo_brain_bot to get started! 🧠</div>`;
    return;
  }
  el.innerHTML = entries.map(renderCard).join("");
}

async function fetchEntries(folder, query, containerId) {
  let url = `/api/entries?token=${encodeURIComponent(TOKEN)}`;
  if (folder && folder !== "All") url += `&folder=${encodeURIComponent(folder)}`;
  if (query) url += `&q=${encodeURIComponent(query)}`;
  const r = await fetch(url);
  if (r.status === 403) { showError("Invalid token. Please check your /mypage link."); return; }
  if (!r.ok) { showError("Could not load your saves. Try again."); return; }
  const data = await r.json();
  renderCards(data, containerId);
}

async function fetchStats() {
  const r = await fetch(`/api/stats?token=${encodeURIComponent(TOKEN)}`);
  if (!r.ok) return;
  const d = await r.json();
  const bar = document.getElementById("stats-bar");
  bar.textContent = `${d.total} saves · this week: ${d.this_week} · top folder: ${d.top_folder}`;
  bar.classList.remove("hidden");
}

async function deleteEntry(id) {
  if (!confirm("Delete this save?")) return;
  const r = await fetch(`/api/entries/${id}?token=${encodeURIComponent(TOKEN)}`, {method:"DELETE"});
  if (!r.ok) { alert("Could not delete. Try again."); return; }
  const card = document.getElementById(`card-${id}`);
  if (card) {
    card.classList.add("fading");
    setTimeout(() => card.remove(), 300);
  }
}

function buildPills() {
  const container = document.getElementById("pills");
  container.innerHTML = FOLDERS.map(([emoji, name]) => {
    const label = name === "All" ? "All" : `${emoji} ${name}`;
    const active = name === activeFolder ? "active" : "";
    return `<div class="pill ${active}" data-folder="${name}">${label}</div>`;
  }).join("");
  container.querySelectorAll(".pill").forEach(p => {
    p.addEventListener("click", () => {
      activeFolder = p.dataset.folder;
      container.querySelectorAll(".pill").forEach(x => x.classList.remove("active"));
      p.classList.add("active");
      fetchEntries(activeFolder, "", "browse-cards");
    });
  });
}

function initTabs() {
  document.querySelectorAll(".tab").forEach(tab => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      const name = tab.dataset.tab;
      document.getElementById("tab-browse").classList.toggle("hidden", name !== "browse");
      document.getElementById("tab-search").classList.toggle("hidden", name !== "search");
    });
  });
}

function initSearch() {
  document.getElementById("search-input").addEventListener("input", e => {
    clearTimeout(searchTimer);
    const q = e.target.value.trim();
    searchTimer = setTimeout(() => fetchEntries("", q, "search-cards"), 400);
  });
}

function init() {
  TOKEN = getToken();
  if (!TOKEN) {
    document.getElementById("token-gate").classList.remove("hidden");
    document.getElementById("token-go").addEventListener("click", () => {
      const val = document.getElementById("token-input").value.trim();
      if (val) location.href = `?token=${encodeURIComponent(val)}`;
    });
    document.getElementById("token-input").addEventListener("keydown", e => {
      if (e.key === "Enter") document.getElementById("token-go").click();
    });
    return;
  }
  document.getElementById("main-ui").classList.remove("hidden");
  buildPills();
  initTabs();
  initSearch();
  fetchStats();
  fetchEntries("All", "", "browse-cards");
}

init();
</script>
</body>
</html>"""


async def handle_root(request: web.Request) -> web.Response:
    raise web.HTTPFound("/app")


async def handle_app(request: web.Request) -> web.Response:
    return web.Response(text=HTML_PAGE, content_type="text/html")


def _get_token(request: web.Request) -> str:
    return request.rel_url.query.get("token", "")


async def handle_entries(request: web.Request) -> web.Response:
    token = _get_token(request)
    user_id = database.get_user_by_token(token)
    if user_id is None:
        return web.json_response({"error": "forbidden"}, status=403)
    folder = request.rel_url.query.get("folder", None)
    query = request.rel_url.query.get("q", None)
    entries = database.get_entries_web(user_id, folder=folder, query=query)
    return web.json_response(entries)


async def handle_stats(request: web.Request) -> web.Response:
    token = _get_token(request)
    user_id = database.get_user_by_token(token)
    if user_id is None:
        return web.json_response({"error": "forbidden"}, status=403)
    stats = database.get_web_stats(user_id)
    return web.json_response(stats)


async def handle_delete(request: web.Request) -> web.Response:
    token = _get_token(request)
    user_id = database.get_user_by_token(token)
    if user_id is None:
        return web.json_response({"error": "forbidden"}, status=403)
    try:
        entry_id = int(request.match_info["id"])
    except (KeyError, ValueError):
        return web.json_response({"error": "invalid id"}, status=400)
    deleted = database.delete_entry(entry_id, user_id)
    if not deleted:
        return web.json_response({"error": "not found"}, status=404)
    return web.json_response({"ok": True})


def create_web_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", handle_root)
    app.router.add_get("/app", handle_app)
    app.router.add_get("/api/entries", handle_entries)
    app.router.add_get("/api/stats", handle_stats)
    app.router.add_delete("/api/entries/{id}", handle_delete)
    return app
