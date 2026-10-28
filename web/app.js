"use strict";

// UI logic for the Media Downloader window.
// Python calls window.mediadl.receive(batch); the page calls window.pywebview.api.<method>().

const PLAY_SVG =
  '<svg viewBox="0 0 10 10" width="10" height="10" aria-hidden="true"><path d="M3 1.5v7l5.5-3.5z" fill="#fff"/></svg>';
const STATUS_ICONS = {
  ok: '<svg viewBox="0 0 18 18" width="17" height="17" aria-hidden="true"><circle cx="9" cy="9" r="7.5" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M5.6 9.3l2.3 2.3 4.5-4.8" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  error: '<svg viewBox="0 0 18 18" width="17" height="17" aria-hidden="true"><circle cx="9" cy="9" r="7.5" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M9 5.2v4.6M9 12.6v.3" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>',
  info: '<svg viewBox="0 0 18 18" width="17" height="17" aria-hidden="true"><circle cx="9" cy="9" r="3" fill="currentColor"/></svg>',
};
STATUS_ICONS.warn = STATUS_ICONS.error;

const $ = (id) => document.getElementById(id);
const dom = {
  url: $("url"),
  download: $("download"),
  downloadLabel: $("download-label"),
  langLabel: $("lang-label"),
  banner: $("banner"),
  bannerIcon: $("banner-icon"),
  bannerText: $("banner-text"),
  progress: $("progress"),
  bar: $("bar"),
  empty: $("empty"),
  gallery: $("gallery"),
  gear: $("gear"),
  menu: $("menu"),
  menuPath: $("menu-path"),
  maxButton: $("win-max"),
  titlebar: $("titlebar"),
};

const state = {
  format: "video",
  busy: false,
  resultOk: false,
  menuOpen: false,
  hideTimer: null,
  tiles: new Map(), // absolute path -> thumbnail <img>
};

const call = (name, ...args) => window.pywebview.api[name](...args);

// ----- events from Python -----

window.mediadl = {
  receive(batch) {
    batch.forEach(handleEvent);
  },
};

function handleEvent(ev) {
  switch (ev.type) {
    case "status":
      setStatus(ev.text, ev.kind);
      if (ev.idle) setBusy(false);
      break;
    case "progress":
      showProgress(ev.value);
      break;
    case "done":
      finishDownload(ev);
      break;
    case "thumbnail":
      setThumbnail(ev.path, ev.data);
      break;
    case "window":
      setMaximized(ev.maximized);
      break;
  }
}

// ----- status, busy state and progress -----

function setStatus(text, kind = "info") {
  if (!text) {
    dom.banner.hidden = true;
    state.resultOk = false;
    return;
  }
  state.resultOk = kind === "ok";
  dom.banner.hidden = false;
  dom.banner.className = "banner " + (STATUS_ICONS[kind] ? kind : "info");
  dom.bannerIcon.innerHTML = STATUS_ICONS[kind] || STATUS_ICONS.info;
  dom.bannerText.textContent = text;
}

function setBusy(busy) {
  state.busy = busy;
  dom.download.disabled = busy;
  renderDownloadLabel();
}

function renderDownloadLabel() {
  dom.downloadLabel.textContent = t(state.busy ? "downloading" : "download");
}

function showProgress(value) {
  clearTimeout(state.hideTimer);
  dom.progress.hidden = false;
  dom.bar.style.width = Math.max(0, Math.min(100, value)) + "%";
}

function hideProgress() {
  dom.progress.hidden = true;
  dom.bar.style.width = "0%";
}

function finishDownload(ev) {
  setBusy(false);
  setStatus(ev.text, ev.ok ? "ok" : "error");
  showProgress(ev.ok ? 100 : 0);
  state.hideTimer = setTimeout(hideProgress, 1500);
  ev.files.forEach(addTile);
  dom.url.focus();
}

// ----- gallery -----

function addTile(file) {
  if (state.tiles.has(file.path)) return;

  const tile = document.createElement("div");
  tile.className = "tile";
  tile.tabIndex = 0;
  tile.dataset.name = file.name;

  const thumb = document.createElement("img");
  thumb.className = "thumb placeholder";
  thumb.alt = "";
  thumb.src = file.music ? "assets/music.png" : "assets/video.png";

  const play = document.createElement("span");
  play.className = "play";
  play.innerHTML = PLAY_SVG;

  const folderBtn = document.createElement("button");
  folderBtn.className = "tile-folder";
  folderBtn.type = "button";
  folderBtn.innerHTML = '<img src="assets/folder.png" alt="">';
  folderBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    call("show_in_folder", file.path);
  });

  const openFile = () => call("open_file", file.path);
  tile.addEventListener("click", openFile);
  tile.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      openFile();
    }
  });

  tile.append(thumb, play, folderBtn);
  labelTile(tile);
  dom.gallery.append(tile);
  state.tiles.set(file.path, thumb);
  dom.empty.hidden = true;
  dom.gallery.hidden = false;
}

function labelTile(tile) {
  tile.title = t("play_title", { name: tile.dataset.name });
  const folderBtn = tile.querySelector(".tile-folder");
  folderBtn.title = t("show_in_folder");
  folderBtn.setAttribute("aria-label", t("show_in_folder"));
}

function setThumbnail(path, dataUrl) {
  const thumb = state.tiles.get(path);
  if (!thumb) return;
  thumb.classList.remove("placeholder");
  thumb.src = dataUrl;
}

// ----- download flow -----

async function download() {
  if (state.busy) {
    setStatus(t("busy"), "error");
    return;
  }
  const url = dom.url.value.trim();
  if (!url) {
    setStatus(t("need_link"), "error");
    return;
  }

  setBusy(true);
  showProgress(0);
  const platform = await call("detect_platform", url);
  if (platform === "spotify" && state.format !== "music") {
    selectFormat("music");
    setStatus(t("spotify_notice"), "warn");
  } else {
    setStatus(t("loading"), "info");
  }
  await call("start_download", url, state.format === "music");
}

function selectFormat(key) {
  state.format = key;
  document.querySelectorAll(".format").forEach((button) => {
    const active = button.dataset.format === key;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
}

function setActivePlatform(platform) {
  document.querySelectorAll(".badge").forEach((badge) => {
    badge.classList.toggle("active", badge.dataset.platform === platform);
  });
}

let detectTimer = null;
function scheduleDetect() {
  clearTimeout(detectTimer);
  detectTimer = setTimeout(async () => {
    setActivePlatform(await call("detect_platform", dom.url.value));
  }, 120);
}

// ----- settings menu -----

function toggleMenu(open = !state.menuOpen) {
  state.menuOpen = open;
  dom.menu.hidden = !open;
  dom.gear.setAttribute("aria-expanded", String(open));
}

function renderFolder(info) {
  dom.menuPath.textContent = info.path;
  dom.menuPath.title = info.path;
}

async function chooseFolder() {
  toggleMenu(false);
  const info = await call("choose_folder");
  if (info) {
    renderFolder(info);
    setStatus(t("folder_set", { folder: info.folder }), "info");
  }
}

async function openFolder() {
  toggleMenu(false);
  const ok = await call("open_downloads", true);
  if (!ok) setStatus(t("open_failed"), "error");
}

async function toggleLanguage() {
  toggleMenu(false);
  const next = LANGUAGES[(LANGUAGES.indexOf(currentLang) + 1) % LANGUAGES.length];
  applyLanguage(await call("set_language", next));
}

// Re-applies every translated label, including ones built at runtime.
function applyLanguage(lang) {
  setLanguage(lang);
  dom.langLabel.textContent = t("menu_language") + ": " + t("lang_name");
  renderDownloadLabel();
  setMaximized(document.body.classList.contains("maximized"));
  dom.gallery.querySelectorAll(".tile").forEach(labelTile);
}

// ----- window chrome -----

function setMaximized(maximized) {
  document.body.classList.toggle("maximized", maximized);
  dom.maxButton.title = t(maximized ? "restore" : "maximize");
  dom.maxButton.setAttribute("aria-label", dom.maxButton.title);
}

// Frameless window: drag handles resize through the Python API (logical pixels).
function bindResizeHandle(handle) {
  const edge = handle.dataset.edge;
  let start = null;
  let ready = Promise.resolve();
  let pending = null;
  let sending = false;

  async function flush() {
    if (sending) return;
    sending = true;
    try {
      await ready;
      while (pending) {
        const delta = pending;
        pending = null;
        await call("resize_window", delta.dx, delta.dy, edge);
      }
    } finally {
      sending = false;
    }
  }

  handle.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    start = { x: e.screenX, y: e.screenY };
    ready = call("begin_resize");
    handle.setPointerCapture(e.pointerId);
  });
  handle.addEventListener("pointermove", (e) => {
    if (!start) return;
    pending = { dx: e.screenX - start.x, dy: e.screenY - start.y };
    flush();
  });
  const stop = () => {
    start = null;
  };
  handle.addEventListener("pointerup", stop);
  handle.addEventListener("pointercancel", stop);
}

// ----- wiring -----

function init() {
  selectFormat("video");
  setStatus("");
  setBusy(false);
  setMaximized(false);
  call("get_state").then((info) => {
    applyLanguage(info.language);
    renderFolder(info);
  });

  document.querySelectorAll(".format").forEach((button) => {
    button.addEventListener("click", () => selectFormat(button.dataset.format));
  });
  document.querySelectorAll(".badge").forEach((badge) => {
    badge.addEventListener("click", () => dom.url.focus());
  });
  document.querySelectorAll(".rz").forEach(bindResizeHandle);

  dom.url.addEventListener("input", scheduleDetect);
  dom.url.addEventListener("keydown", (e) => {
    if (e.key === "Enter") download();
  });
  dom.download.addEventListener("click", download);
  dom.banner.addEventListener("click", () => {
    if (state.resultOk) call("open_downloads", false);
  });

  dom.gear.addEventListener("click", (e) => {
    e.stopPropagation();
    toggleMenu();
  });
  document.addEventListener("click", (e) => {
    if (state.menuOpen && !dom.menu.contains(e.target)) toggleMenu(false);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") toggleMenu(false);
  });
  dom.menu.querySelector('[data-action="choose"]').addEventListener("click", chooseFolder);
  dom.menu.querySelector('[data-action="open"]').addEventListener("click", openFolder);
  dom.menu.querySelector('[data-action="language"]').addEventListener("click", toggleLanguage);

  $("win-min").addEventListener("click", () => call("minimize"));
  dom.maxButton.addEventListener("click", () => call("toggle_maximize"));
  $("win-close").addEventListener("click", () => call("close"));
  dom.titlebar.addEventListener("dblclick", (e) => {
    if (!e.target.closest("button")) call("toggle_maximize");
  });

  dom.url.focus();
}

// pywebview fires this once window.pywebview.api is ready.
window.addEventListener("pywebviewready", init);
