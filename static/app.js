const PAGE = 80;
const COPIES_PAGE = 8;
const state = {
  view: "gallery",
  filters: {},
  offset: 0,
  total: 0,
  items: [],
  selected: new Set(),
  selectAnchor: null,
  trashSelected: new Set(),
  trashOffset: 0,
  trashTotal: 0,
  trashItems: [],
  copiesOffset: 0,
  copiesTotal: 0,
  copiesExtra: 0,
  lastJob: null,
  people: [],
  reviewPerson: null,
  reviewScene: null,
  pendingDelete: null,
  pendingDeletePage: null,
  pendingAlbum: null,
  map: null,
  mapLayer: null,
  lbIndex: -1,
  lbItem: null,
  lbSeq: null,
  lbSeqKind: null,
  lbFocusByMedia: null,
  lbTotal: 0,
  lbZoom: { scale: 1, x: 0, y: 0 },
  playing: false,
  delay: 5000,
  castDevice: null,
  indexedYears: new Set(),
  libraryYears: [],
  albums: [],
  moveFolders: [],
  sceneCatalog: [],
  scenePlaces: [],
  sceneScopeReady: false,
  me: null,
  authEnabled: false,
  signedOut: false,
};

function lecturePreview() {
  return new URLSearchParams(location.search).get("lecture") === "1";
}

function isViewer() {
  if (state.me && state.me.role === "viewer") return true;
  return !state.authEnabled && lecturePreview();
}

let slideGen = 0;
let slideTimer = null;
let chromeTimer = null;
let photoEdit = null;

const $ = (id) => document.getElementById(id);

function tr(key) {
  return window.GalerieI18n ? GalerieI18n.t(key) : key;
}

function trf(key, vars) {
  let text = tr(key);
  const data = vars || {};
  Object.keys(data).forEach((name) => {
    text = text.split("{" + name + "}").join(String(data[name]));
  });
  return text;
}

const COUNTRY_FLAGS = {
  argentine: "🇦🇷", argentina: "🇦🇷", argentinien: "🇦🇷",
  autriche: "🇦🇹", austria: "🇦🇹", osterreich: "🇦🇹",
  australie: "🇦🇺", australia: "🇦🇺", australien: "🇦🇺",
  belgique: "🇧🇪", belgium: "🇧🇪", belgica: "🇧🇪", belgien: "🇧🇪",
  bresil: "🇧🇷", brazil: "🇧🇷", brasil: "🇧🇷", brasilien: "🇧🇷",
  canada: "🇨🇦", kanada: "🇨🇦",
  suisse: "🇨🇭", switzerland: "🇨🇭", suiza: "🇨🇭", schweiz: "🇨🇭",
  chili: "🇨🇱", chile: "🇨🇱",
  "costa rica": "🇨🇷", "costa-rica": "🇨🇷",
  cuba: "🇨🇺", kuba: "🇨🇺",
  allemagne: "🇩🇪", germany: "🇩🇪", alemania: "🇩🇪", deutschland: "🇩🇪",
  espagne: "🇪🇸", spain: "🇪🇸", espana: "🇪🇸", spanien: "🇪🇸",
  france: "🇫🇷", francia: "🇫🇷", frankreich: "🇫🇷",
  "royaume-uni": "🇬🇧", "royaume uni": "🇬🇧", "united kingdom": "🇬🇧",
  "reino unido": "🇬🇧", "vereinigtes konigreich": "🇬🇧", uk: "🇬🇧",
  "grande-bretagne": "🇬🇧", "grande bretagne": "🇬🇧",
  grece: "🇬🇷", greece: "🇬🇷", grecia: "🇬🇷", griechenland: "🇬🇷",
  croatie: "🇭🇷", croatia: "🇭🇷", croacia: "🇭🇷", kroatien: "🇭🇷",
  irlande: "🇮🇪", ireland: "🇮🇪", irlanda: "🇮🇪", irland: "🇮🇪",
  italie: "🇮🇹", italy: "🇮🇹", italia: "🇮🇹", italien: "🇮🇹",
  jamaique: "🇯🇲", jamaica: "🇯🇲", jamaika: "🇯🇲",
  japon: "🇯🇵", japan: "🇯🇵",
  maroc: "🇲🇦", morocco: "🇲🇦", marruecos: "🇲🇦", marokko: "🇲🇦",
  mexique: "🇲🇽", mexico: "🇲🇽", mexiko: "🇲🇽",
  nicaragua: "🇳🇮",
  "pays-bas": "🇳🇱", "pays bas": "🇳🇱", netherlands: "🇳🇱",
  "paises bajos": "🇳🇱", niederlande: "🇳🇱", hollande: "🇳🇱", holland: "🇳🇱",
  "nouvelle-zelande": "🇳🇿", "nouvelle zelande": "🇳🇿", "new zealand": "🇳🇿",
  "nueva zelanda": "🇳🇿", neuseeland: "🇳🇿",
  philippines: "🇵🇭", filipinas: "🇵🇭", philippinen: "🇵🇭",
  portugal: "🇵🇹",
  thailande: "🇹🇭", thailand: "🇹🇭", tailandia: "🇹🇭",
  tunisie: "🇹🇳", tunisia: "🇹🇳", tunez: "🇹🇳", tunesien: "🇹🇳",
  "etats-unis": "🇺🇸", "etats unis": "🇺🇸", "united states": "🇺🇸",
  "estados unidos": "🇺🇸", "vereinigte staaten": "🇺🇸", usa: "🇺🇸",
  reunion: "🇷🇪", guadeloupe: "🇬🇵", martinique: "🇲🇶",
};

function foldPlace(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/\./g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function placeLabel(name) {
  const raw = String(name || "").trim();
  if (!raw) return "";
  const direct = COUNTRY_FLAGS[foldPlace(raw)];
  if (direct) return direct;
  const parts = raw.split(/\s*(?:·|,|\/)\s*/);
  if (parts.length > 1) {
    const flag = COUNTRY_FLAGS[foldPlace(parts[parts.length - 1])];
    if (flag) {
      parts[parts.length - 1] = flag;
      return parts.join(" · ");
    }
  }
  return raw;
}

function placeOption(name) {
  return { value: name, label: name };
}

function placePathLabel(rel) {
  const parts = String(rel || "").split(/[/\\]/);
  if (parts.length < 2) return String(rel || "");
  return parts
    .map((part, index) => (index === parts.length - 1 ? part : placeLabel(part)))
    .join("/");
}

/* Windows (Chrome, Edge) n’a pas de glyphe pour les drapeaux emoji.
 * On dessine une image SVG, y compris dans les listes qui ne montrent pas d’emoji. */

function flagImg(cc) {
  const img = document.createElement("img");
  img.className = "flag";
  img.alt = "";
  img.decoding = "async";
  img.src = "/static/flags/" + cc + ".svg";
  img.addEventListener("error", () => {
    const code = document.createElement("span");
    code.className = "flag-code";
    code.textContent = String(cc || "").toUpperCase();
    img.replaceWith(code);
  });
  return img;
}

function setFlagText(el, text) {
  if (!el) return;
  const src = String(text ?? "");
  el.replaceChildren();
  const re = /\p{Regional_Indicator}{2}/gu;
  let last = 0;
  for (const match of src.matchAll(re)) {
    if (match.index > last) el.append(src.slice(last, match.index));
    const cc = Array.from(match[0])
      .map((ch) => String.fromCharCode(ch.codePointAt(0) - 0x1F1E6 + 65))
      .join("")
      .toLowerCase();
    el.append(cc ? flagImg(cc) : match[0]);
    last = match.index + match[0].length;
  }
  if (last < src.length) el.append(src.slice(last));
}

function mountFlagSelect(select) {
  if (!select || select.dataset.flagUi) return;
  select.dataset.flagUi = "1";
  const compact = select.id === "prefLang";
  const ui = document.createElement("span");
  ui.className = "flag-select" + (compact ? " is-compact" : "");
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "flag-select-btn";
  btn.setAttribute("aria-haspopup", "listbox");
  btn.setAttribute("aria-expanded", "false");
  const menu = document.createElement("ul");
  menu.className = "flag-select-menu";
  menu.hidden = true;
  menu.setAttribute("role", "listbox");
  ui.append(btn, menu);
  select.before(ui);
  select.classList.add("flag-native");

  let picking = false;

  function closeMenu() {
    menu.hidden = true;
    btn.setAttribute("aria-expanded", "false");
  }

  function paintBtn() {
    const opt = select.selectedOptions[0];
    const label = document.createElement("span");
    label.className = "flag-select-label";
    setFlagText(label, opt ? opt.textContent : "");
    btn.replaceChildren(label);
    const name = (opt && (opt.title || opt.textContent)) || "";
    const base = select.getAttribute("aria-label") || "";
    btn.setAttribute("aria-label", [base, name].filter(Boolean).join(" : "));
    if (name) btn.title = name;
    for (const li of menu.querySelectorAll("[role='option']")) {
      li.setAttribute("aria-selected", li.dataset.value === select.value ? "true" : "false");
    }
  }

  function rebuild() {
    menu.replaceChildren();
    for (const opt of select.options) {
      const li = document.createElement("li");
      li.setAttribute("role", "option");
      li.dataset.value = opt.value;
      setFlagText(li, opt.textContent);
      if (compact && opt.title) li.append(document.createTextNode(" " + opt.title));
      if (opt.title) {
        li.title = opt.title;
        li.setAttribute("aria-label", opt.title);
      }
      li.setAttribute("aria-selected", opt.value === select.value ? "true" : "false");
      li.addEventListener("mousedown", (ev) => ev.preventDefault());
      li.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        picking = true;
        select.value = opt.value;
        select.dispatchEvent(new Event("change", { bubbles: true }));
        closeMenu();
      });
      menu.append(li);
    }
    paintBtn();
  }

  const desc = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value");
  Object.defineProperty(select, "value", {
    configurable: true,
    get() {
      return desc.get.call(select);
    },
    set(next) {
      desc.set.call(select, next);
      paintBtn();
    },
  });

  btn.addEventListener("click", (ev) => {
    ev.preventDefault();
    ev.stopPropagation();
    if (picking) {
      picking = false;
      closeMenu();
      return;
    }
    document.querySelectorAll(".flag-select-menu").forEach((other) => {
      if (other === menu) return;
      other.hidden = true;
      const otherBtn = other.parentElement && other.parentElement.querySelector(".flag-select-btn");
      if (otherBtn) otherBtn.setAttribute("aria-expanded", "false");
    });
    if (menu.hidden) {
      menu.hidden = false;
      btn.setAttribute("aria-expanded", "true");
      const current = menu.querySelector("[aria-selected='true']");
      if (current) current.scrollIntoView({ block: "nearest" });
    } else {
      closeMenu();
    }
  });
  document.addEventListener("click", (ev) => {
    if (!ui.contains(ev.target)) closeMenu();
  });
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape") closeMenu();
  });
  new MutationObserver(rebuild).observe(select, { childList: true });
  rebuild();
}

function kindLabel(kind) {
  const labels = {
    icloud: tr("job.icloud"),
    sort: tr("job.sort"),
    index: tr("job.index"),
    backup: tr("job.backup"),
    "copies-trash": tr("job.copies"),
    "trash-restore": tr("job.restore"),
    "trash-purge": tr("job.purge"),
    "trash-expire": tr("job.expire"),
    faces: tr("job.faces"),
    scenes: tr("job.task"),
    task: tr("job.task"),
  };
  return labels[kind] || kind || tr("job.task");
}

function jobMessage(job) {
  if (!job) return "";
  const vars = Object.assign({}, job.message_vars || {});
  if (vars.current) vars.current = kindLabel(vars.current);
  const code = job.message_code || "";
  if (code) {
    const text = trf(code, vars);
    if (text && text !== code) return text;
  }
  return job.message || "";
}

function trn(n, oneKey, manyKey, vars) {
  const count = Number(n) || 0;
  const data = Object.assign({ n: fmtN(count) }, vars || {});
  return trf(count > 1 ? manyKey : oneKey, data);
}

function personSpan(person) {
  if (!person || !person.year_min || !person.year_max) return "";
  if (person.year_min === person.year_max) return trf("empty.inYear", { year: person.year_min });
  return trf("empty.between", { a: person.year_min, b: person.year_max });
}

function sceneLabel(tag, fallback) {
  if (!tag) return fallback || "";
  const key = "scene." + tag;
  const text = tr(key);
  return text === key ? (fallback || tag) : text;
}

function notLabel(name) {
  return tr("faces.not").replaceAll("{name}", name);
}

const THEME_COLORS = {
  amber: "#1b1916",
  ink: "#1c1f26",
  ocean: "#152433",
  forest: "#1a2420",
  paper: "#fffdf9",
  daylight: "#ffffff",
};

function applyChrome() {
  if (window.GalerieI18n) GalerieI18n.apply(document);
  const theme = document.documentElement.getAttribute("data-theme") || "amber";
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", THEME_COLORS[theme] || THEME_COLORS.amber);
}

async function refreshTranslatedStatus() {
  applyPhoneKind();
  if (state.lastJob) renderJob(state.lastJob);
  if (state.authEnabled) applyAccess(state.me, true);
  if (!state.authEnabled || state.me) {
    try {
      await loadFilters();
    } catch (err) {
      /* sans effet */
    }
    try {
      await loadHealth();
    } catch (err) {
      /* sans effet */
    }
    if (state.view === "gallery") {
      try {
        await loadGallery();
      } catch (err) {
        /* sans effet */
      }
    }
    if (state.view === "faces") loadFacesView();
    if (state.view === "scenes") loadScenesView();
    if (state.view === "copies") loadCopiesView();
    if (state.view === "map") loadMapView();
    if (state.view === "albums") loadAlbumsView();
    if (state.view === "trash") loadTrashView();
    if (state.view === "settings") {
      loadSettings().catch(() => {});
      loadBackups().catch(() => {});
    }
    if (typeof updateCastButton === "function") updateCastButton();
  }
  syncSelectionChrome();
  if (state.me && !isViewer() && $("usersList")) loadUsers().catch(() => {});
}

function initPrefs() {
  if (!window.GalerieI18n) return;
  const langSel = $("prefLang");
  const themeSel = $("prefTheme");
  GalerieI18n.setLang(GalerieI18n.getLang());
  GalerieI18n.setTheme(GalerieI18n.getTheme());
  if (langSel) langSel.value = GalerieI18n.getLang();
  if (themeSel) themeSel.value = GalerieI18n.getTheme();
  applyChrome();
  syncHelpLink();
  if (langSel) {
    langSel.addEventListener("change", () => {
      GalerieI18n.setLang(langSel.value);
      applyChrome();
      syncHelpLink();
      if (state.view === "help") loadHelp();
      refreshTranslatedStatus();
    });
  }
  if (themeSel) {
    themeSel.addEventListener("change", () => {
      GalerieI18n.setTheme(themeSel.value);
      applyChrome();
    });
  }
  mountFlagSelect(langSel);
}

function mediaCacheTok(item) {
  return item && (item.mtime_ns || item.size || 0);
}

function mediaThumbUrl(item) {
  return `/api/media/${item.id}/thumb?v=${mediaCacheTok(item)}`;
}

function mediaPreviewUrl(item) {
  return `/api/media/${item.id}/preview?v=${mediaCacheTok(item)}`;
}

function lightboxMediaEl() {
  const stage = $("lbStage");
  if (!stage) return null;
  return stage.querySelector(".lb-photo img, .lb-video-wrap video, .lb-edit-wrap canvas");
}

function lightboxMediaNaturalSize(el) {
  if (!el) return null;
  if (el.tagName === "VIDEO") {
    const w = el.videoWidth;
    const h = el.videoHeight;
    return w && h ? { w, h } : null;
  }
  if (el.tagName === "CANVAS") {
    const w = el.width;
    const h = el.height;
    return w && h ? { w, h } : null;
  }
  const w = el.naturalWidth;
  const h = el.naturalHeight;
  return w && h ? { w, h } : null;
}

function fitLightboxMedia() {
  const stage = $("lbStage");
  const el = lightboxMediaEl();
  const nat = lightboxMediaNaturalSize(el);
  if (!stage || !el || !nat) return;
  const cs = getComputedStyle(stage);
  const padX = (parseFloat(cs.paddingLeft) || 0) + (parseFloat(cs.paddingRight) || 0);
  const padY = (parseFloat(cs.paddingTop) || 0) + (parseFloat(cs.paddingBottom) || 0);
  const sw = Math.max(1, stage.clientWidth - padX);
  const sh = Math.max(1, stage.clientHeight - padY);
  const scale = Math.min(sw / nat.w, sh / nat.h);
  const w = Math.max(1, Math.round(nat.w * scale));
  const h = Math.max(1, Math.round(nat.h * scale));
  el.style.width = `${w}px`;
  el.style.height = `${h}px`;
  applyLbZoom();
  if (photoEdit) layoutCropBox();
}

function applyLbZoom() {
  const el = lightboxMediaEl();
  if (!el) return;
  const z = state.lbZoom || { scale: 1, x: 0, y: 0 };
  el.style.transformOrigin = "center center";
  if (z.scale <= 1.02) {
    el.style.transform = "";
    return;
  }
  el.style.transform = `translate(${z.x}px, ${z.y}px) scale(${z.scale})`;
}

function resetLbZoom() {
  state.lbZoom = { scale: 1, x: 0, y: 0 };
  applyLbZoom();
}

function fmtN(n) {
  const loc = { fr: "fr-CA", en: "en", es: "es", de: "de" }[document.documentElement.lang] || "fr-CA";
  return Number(n || 0).toLocaleString(loc);
}

function clearGalleryFilters() {
  $("filterYear").value = "";
  $("filterPlace").value = "";
  const moment = $("filterMoment");
  if (moment) moment.value = "";
  $("filterKind").value = "";
  const person = $("filterPerson");
  if (person) person.value = "";
  const personQ = $("filterPersonQ");
  if (personQ) personQ.value = "";
  $("filterAlbum").value = "";
  $("filterQ").value = "";
  const month = $("filterMonth");
  if (month) month.value = "";
  const scene = $("filterScene");
  if (scene) scene.value = "";
}

async function showAllPhotosGallery() {
  state.offset = 0;
  state.selected.clear();
  state.selectAnchor = null;
  clearGalleryFilters();
  setView("gallery");
  const lb = $("lightbox");
  if (lb && lb.open) await closeLightbox();
  try {
    await Promise.all([loadFilters(), loadHealth()]);
  } catch (err) {
    $("status").textContent = String(err.message || err);
  }
  clearGalleryFilters();
  await loadGallery();
}

function paramsFromFilters() {
  const p = new URLSearchParams();
  const year = $("filterYear").value;
  const month = $("filterMonth") && $("filterMonth").value;
  const place = $("filterPlace").value;
  const moment = $("filterMoment") && $("filterMoment").value;
  const kind = $("filterKind").value;
  const person = $("filterPerson") && $("filterPerson").value;
  const album = $("filterAlbum").value;
  const q = $("filterQ").value.trim();
  if (year) p.set("year", year);
  if (month) p.set("month", month);
  if (place) p.set("place", place);
  if (moment) p.set("moment", moment);
  if (kind) p.set("kind", kind);
  if (person) p.set("person_id", person);
  if (album) p.set("album_id", album);
  const scene = $("filterScene") && $("filterScene").value;
  if (scene) {
    if (scene === "kind:landscape" || scene === "kind:building") {
      p.set("scene_kind", scene.slice(5));
    } else {
      p.set("scene", scene);
    }
  }
  if (q) p.set("q", q);
  return p;
}

async function api(path, opts) {
  const res = await fetch(path, { credentials: "same-origin", ...(opts || {}) });
  if (
    res.status === 401 &&
    path !== "/api/auth/login" &&
    path !== "/api/auth/status" &&
    path !== "/api/auth/logout"
  ) {
    if (state.signedOut) {
      await showLoggedOut();
    } else {
      await showLoginGate();
    }
  }
  if (!res.ok) {
    const raw = await res.text();
    let msg = res.statusText || `Erreur ${res.status}`;
    try {
      const data = JSON.parse(raw);
      const detail = data.detail;
      if (detail && typeof detail === "object" && !Array.isArray(detail) && detail.code) {
        let key = "err." + detail.code;
        if (detail.code === "bad_password" && Number(detail.n) === 1) key = "err.bad_password_one";
        const translated = tr(key);
        msg = translated === key ? detail.message || translated : translated.replaceAll("{n}", String(detail.n ?? ""));
      } else if (typeof detail === "string") msg = detail;
      else if (Array.isArray(detail)) {
        msg = detail.map((item) => item.msg || JSON.stringify(item)).join("; ");
      } else if (detail) msg = JSON.stringify(detail);
      else if (raw) msg = raw.slice(0, 300);
    } catch {
      if (raw) msg = raw.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim().slice(0, 300);
    }
    throw new Error(msg);
  }
  const ctype = res.headers.get("content-type") || "";
  if (ctype.includes("application/json")) return res.json();
  return res;
}

function fillSelect(el, items, extra, selected) {
  const cur = el.multiple ? null : el.value;
  el.innerHTML = "";
  for (const item of extra || []) {
    const opt = document.createElement("option");
    opt.value = item.value;
    opt.textContent = item.label;
    if (item.title) opt.title = item.title;
    el.appendChild(opt);
  }
  for (const item of items) {
    const opt = document.createElement("option");
    if (typeof item === "object") {
      opt.value = item.value;
      opt.textContent = item.label;
      if (item.title) opt.title = item.title;
    } else {
      opt.value = item;
      opt.textContent = item;
    }
    el.appendChild(opt);
  }
  if (el.multiple) {
    const want = new Set((selected || []).map(String));
    for (const opt of el.options) opt.selected = want.has(opt.value);
  } else if ([...el.options].some((o) => o.value === cur)) {
    el.value = cur;
  }
}

function foldPerson(name) {
  return (name || "").trim().toLocaleLowerCase("fr");
}

function fillPersonFilter(people) {
  state.people = people || [];
  const list = $("filterPersonList");
  if (list) {
    list.innerHTML = "";
    for (const p of state.people) {
      const opt = document.createElement("option");
      opt.value = p.name;
      list.appendChild(opt);
    }
  }
  const idEl = $("filterPerson");
  const qEl = $("filterPersonQ");
  if (!idEl || !qEl) return;
  const cur = state.people.find((p) => String(p.id) === idEl.value);
  if (cur) qEl.value = cur.name;
  else {
    idEl.value = "";
    if (!qEl.value.trim()) qEl.value = "";
  }
}

function bumpGalleryFromFilters() {
  state.offset = 0;
  state.selected.clear();
  state.selectAnchor = null;
  loadGallery();
}

function commitPersonFilter() {
  const qEl = $("filterPersonQ");
  const idEl = $("filterPerson");
  if (!qEl || !idEl) return;
  const raw = (qEl.value || "").trim();
  if (!raw) {
    if (idEl.value) {
      idEl.value = "";
      bumpGalleryFromFilters();
    }
    return;
  }
  const hit = (state.people || []).find((p) => foldPerson(p.name) === foldPerson(raw));
  if (!hit) {
    $("status").textContent = trf("ui.personMissing", { name: raw });
    return;
  }
  qEl.value = hit.name;
  idEl.value = String(hit.id);
  bumpGalleryFromFilters();
}

function filtersUrl() {
  const year = $("filterYear").value;
  return year ? `/api/filters?year=${encodeURIComponent(year)}` : "/api/filters";
}

function fillPlaces(places) {
  fillSelect(
    $("filterPlace"),
    (places || []).map((p) => placeOption(p)),
    [
      { value: "", label: tr("filter.all") },
      { value: "__none__", label: tr("filter.noPlace") },
    ]
  );
  const list = $("placeSuggestions");
  if (list) {
    list.innerHTML = "";
    for (const p of places || []) {
      const opt = document.createElement("option");
      opt.value = p;
      list.appendChild(opt);
    }
  }
}

function fillMoments(moments) {
  const el = $("filterMoment");
  if (!el) return;
  fillSelect(
    el,
    (moments || []).map((m) => ({ value: m, label: m })),
    [
      { value: "", label: tr("filter.all") },
      { value: "__none__", label: tr("filter.noMoment") },
    ]
  );
}

async function loadPlaces() {
  const data = await api(filtersUrl());
  fillPlaces(data.places);
  fillMoments(data.moments);
}

async function loadFilters() {
  const [data, lib] = await Promise.all([api(filtersUrl()), api("/api/library/years")]);
  state.indexedYears = new Set(data.years || []);
  state.libraryYears = lib.years || [];
  fillSelect(
    $("filterYear"),
    state.libraryYears.map((y) => ({
      value: String(y),
      label: state.indexedYears.has(y)
        ? String(y)
        : tr("filter.toIndex").replace("{year}", String(y)),
    })),
    [{ value: "", label: tr("filter.allYears") }]
  );
  fillPlaces(data.places);
  fillMoments(data.moments);
  fillPersonFilter(data.people);
  state.albums = data.albums || [];
  fillSelect(
    $("filterAlbum"),
    state.albums.map((a) => ({ value: String(a.id), label: `${a.name} (${a.count})` })),
    [{ value: "", label: tr("filter.all") }]
  );
  fillSelect(
    $("indexYear"),
    (lib.years || []).map((y) => ({ value: String(y), label: String(y) })),
    [{ value: "", label: tr("filter.wholeLibrary") }]
  );
  fillSceneFilter(data.scenes || []);
  state.sceneCatalog = data.scene_catalog || [];
  state.scenePlaces = data.places || [];
}

function fillSceneFilter(scenes) {
  const el = $("filterScene");
  if (!el) return;
  const cur = el.value;
  el.innerHTML = "";
  const add = (value, label) => {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = label;
    el.appendChild(opt);
  };
  add("", tr("filter.all"));
  add("kind:landscape", tr("filter.allLandscapes"));
  add("kind:building", tr("filter.allBuildings"));
  const land = scenes.filter((s) => s.kind === "landscape");
  const build = scenes.filter((s) => s.kind === "building");
  if (land.length) {
    const g = document.createElement("optgroup");
    g.label = tr("filter.landscapes");
    for (const s of land) {
      const opt = document.createElement("option");
      opt.value = s.value;
      opt.textContent = `${sceneLabel(s.value, s.label)} (${s.count})`;
      g.appendChild(opt);
    }
    el.appendChild(g);
  }
  if (build.length) {
    const g = document.createElement("optgroup");
    g.label = tr("filter.buildings");
    for (const s of build) {
      const opt = document.createElement("option");
      opt.value = s.value;
      opt.textContent = `${sceneLabel(s.value, s.label)} (${s.count})`;
      g.appendChild(opt);
    }
    el.appendChild(g);
  }
  if ([...el.options].some((o) => o.value === cur)) el.value = cur;
}

function fillSceneTagSelect(catalog, el) {
  if (!el) return;
  const cur = el.value;
  el.innerHTML = "";
  const groups = [
    ["landscape", tr("filter.landscapes")],
    ["building", tr("filter.buildings")],
  ];
  for (const [kind, label] of groups) {
    const g = document.createElement("optgroup");
    g.label = label;
    for (const s of (catalog || []).filter((x) => x.kind === kind)) {
      const opt = document.createElement("option");
      opt.value = s.value;
      opt.textContent = sceneLabel(s.value, s.label);
      g.appendChild(opt);
    }
    if (g.childElementCount) el.appendChild(g);
  }
  if ([...el.options].some((o) => o.value === cur)) el.value = cur;
}

function sceneScopeParams() {
  const p = new URLSearchParams();
  const y = $("sceneYear") && $("sceneYear").value;
  const place = $("scenePlace") && $("scenePlace").value;
  if (y) p.set("year", y);
  if (place) p.set("place", place);
  return p;
}

function fillSceneYearSelect() {
  const el = $("sceneYear");
  if (!el) return;
  fillSelect(
    el,
    (state.libraryYears || []).map((y) => ({ value: String(y), label: String(y) })),
    [{ value: "", label: tr("filter.allYears") }]
  );
}

function fillScenePlaceSelect(places) {
  const el = $("scenePlace");
  if (!el) return;
  fillSelect(
    el,
    (places || []).map((p) => placeOption(p)),
    [{ value: "", label: tr("filter.allPlaces") }]
  );
}

function ensureSceneScopeDefaults() {
  if (state.sceneScopeReady) return;
  const yearEl = $("sceneYear");
  if (yearEl && !yearEl.value) {
    if ((state.libraryYears || []).includes(2025)) yearEl.value = "2025";
    else if ($("indexYear") && $("indexYear").value) yearEl.value = $("indexYear").value;
  }
  const placeEl = $("scenePlace");
  const gp = $("filterPlace") && $("filterPlace").value;
  if (placeEl && !placeEl.value && gp && gp !== "__none__") {
    if ([...placeEl.options].some((o) => o.value === gp)) placeEl.value = gp;
  }
  state.sceneScopeReady = true;
}

function renderSceneChips(scenes) {
  const el = $("sceneChips");
  if (!el) return;
  el.innerHTML = "";
  if (isViewer()) return;
  if (!(scenes || []).length) {
    const p = document.createElement("span");
    p.className = "muted";
    p.textContent = tr("scenes.noneYet");
    el.appendChild(p);
    return;
  }
  for (const s of scenes) {
    const chip = document.createElement("span");
    chip.className = "chip person-chip";
    const name = document.createElement("span");
    name.textContent = sceneLabel(s.value, s.label);
    const count = document.createElement("span");
    count.className = "chip-count";
    count.textContent = String(s.count);
    const review = document.createElement("button");
    review.type = "button";
    review.textContent = tr("faces.review");
    review.title = tr("faces.reviewSceneTitle").replaceAll("{name}", sceneLabel(s.value, s.label));
    review.addEventListener("click", () => {
      loadSceneReview(s.value, 0).catch((err) =>
        alert(err.message || String(err))
      );
    });
    chip.append(name, count, review);
    el.appendChild(chip);
  }
}

function setSceneReviewOpen(on) {
  const review = $("sceneReview");
  const clusters = $("sceneClusters");
  if (review) review.classList.toggle("hidden", !on);
  if (clusters) clusters.classList.toggle("hidden", on);
}

async function closeSceneReview() {
  state.reviewScene = null;
  const root = $("sceneReview");
  if (root) {
    root.classList.add("hidden");
    root.innerHTML = "";
  }
  setSceneReviewOpen(false);
  await loadScenesView();
}

async function loadSceneReview(tag, offset) {
  const root = $("sceneReview");
  if (!root) return;
  offset = offset || 0;
  const qs = sceneScopeParams();
  qs.set("offset", String(offset));
  qs.set("limit", "200");
  const data = await api(
    `/api/scenes/${encodeURIComponent(tag)}/media?${qs.toString()}`
  );
  const label = sceneLabel(data.tag, data.label);
  state.reviewScene = {
    tag: data.tag,
    label,
    total: data.total,
    offset,
  };
  setSceneReviewOpen(true);
  root.classList.remove("hidden");
  root.innerHTML = "";
  const head = document.createElement("div");
  head.className = "face-review-head";
  const title = document.createElement("p");
  title.className = "cluster-legend";
  title.textContent =
    tr("scenes.reviewCount")
      .replaceAll("{name}", label)
      .replaceAll("{n}", fmtN(data.total))
      .replaceAll("{not}", notLabel(label));
  const back = document.createElement("button");
  back.type = "button";
  back.textContent = tr("ui.backScenes");
  back.addEventListener("click", () => {
    closeSceneReview().catch((err) => alert(err.message || String(err)));
  });
  head.append(title, back);
  root.appendChild(head);
  if (!data.items.length) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = trf("ui.noScenesLeft", { label: label });
    root.appendChild(empty);
    return;
  }
  const grid = document.createElement("div");
  grid.className = "cluster-faces";
  const ids = data.items.map((it) => it.id);
  for (const item of data.items) {
    const card = document.createElement("div");
    card.className = "review-face";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "cluster-face";
    btn.title = tr("ui.clickLarge");
    const img = document.createElement("img");
    img.alt = label;
    img.loading = "lazy";
    img.src = mediaThumbUrl(item);
    btn.appendChild(img);
    btn.addEventListener("click", () => {
      openLightboxFromSeq(item.id, ids, null, "scenes").catch((err) => {
        alert(err.message || tr("ui.openFail"));
      });
    });
    const reject = document.createElement("button");
    reject.type = "button";
    reject.className = "danger";
    reject.textContent = notLabel(label);
    reject.addEventListener("click", async () => {
      reject.disabled = true;
      try {
        await api("/api/scenes/untag-many", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ids: [item.id], tag: data.tag }),
        });
        await Promise.all([loadSceneReview(data.tag, offset), loadFilters()]);
      } catch (err) {
        alert(err.message);
        reject.disabled = false;
      }
    });
    card.append(btn, reject);
    grid.appendChild(card);
  }
  root.appendChild(grid);
  if (offset + data.items.length < data.total) {
    const more = document.createElement("button");
    more.type = "button";
    more.textContent = tr("ui.more");
    more.addEventListener("click", () => {
      loadSceneReview(data.tag, offset + data.items.length).catch((err) =>
        alert(err.message || String(err))
      );
    });
    root.appendChild(more);
  }
}

function renderSceneUntagged(root, untagged, catalog) {
  if (!root) return;
  if (!untagged || !untagged.items || !untagged.items.length) {
    const box = document.createElement("div");
    box.className = "empty";
    const p = document.createElement("p");
    p.textContent = untagged && untagged.total
      ? tr("scenes.pageDone")
      : tr("scenes.allTagged");
    box.appendChild(p);
    root.appendChild(box);
    return;
  }
  const box = document.createElement("div");
  box.className = "cluster";
  const legend = document.createElement("p");
  legend.className = "cluster-legend";
  const n = untagged.total;
  const shown = untagged.items.length;
  legend.textContent =
    trn(shown, "scenes.shown.one", "scenes.shown.many") +
    (n > shown ? " " + trf("scenes.of", { n: fmtN(n) }) : "") +
    tr("scenes.untaggedHint");
  const facesEl = document.createElement("div");
  facesEl.className = "cluster-faces";
  const checks = [];
  const submit = document.createElement("button");
  submit.type = "submit";
  submit.className = "primary";
  const syncSubmit = () => {
    const picked = checks.filter((c) => c.checked).length;
    submit.disabled = picked === 0;
    submit.textContent =
      picked === 0
        ? tr("scenes.tagSel")
        : trf("scenes.tagSelN", { n: picked });
  };
  const ids = untagged.items.map((it) => it.id);
  for (const item of untagged.items) {
    const wrap = document.createElement("div");
    wrap.className = "cluster-face-pick";
    const check = document.createElement("input");
    check.type = "checkbox";
    check.setAttribute("aria-label", tr("scenes.include"));
    check.addEventListener("change", () => {
      wrap.classList.toggle("on", check.checked);
      syncSubmit();
    });
    checks.push(check);
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "cluster-face";
    btn.title = tr("ui.clickLarge");
    const img = document.createElement("img");
    img.alt = tr("scenes.photoAlt");
    img.loading = "lazy";
    img.src = mediaThumbUrl(item);
    btn.appendChild(img);
    btn.addEventListener("click", () => {
      openLightboxFromSeq(item.id, ids, null, "scenes").catch((err) => {
        alert(err.message || tr("ui.openFail"));
      });
    });
    wrap.append(check, btn);
    facesEl.appendChild(wrap);
  }
  const tools = document.createElement("div");
  tools.className = "cluster-toolbar";
  const all = document.createElement("button");
  all.type = "button";
  all.textContent = tr("ui.checkAll");
  all.addEventListener("click", () => {
    for (const c of checks) {
      c.checked = true;
      c.parentElement.classList.add("on");
    }
    syncSubmit();
  });
  const none = document.createElement("button");
  none.type = "button";
  none.textContent = tr("ui.checkNone");
  none.addEventListener("click", () => {
    for (const c of checks) {
      c.checked = false;
      c.parentElement.classList.remove("on");
    }
    syncSubmit();
  });
  tools.append(all, none);
  const form = document.createElement("form");
  const sel = document.createElement("select");
  sel.setAttribute("aria-label", tr("ui.tagAria"));
  fillSceneTagSelect(catalog, sel);
  form.append(sel, submit);
  syncSubmit();
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const tag = sel.value;
    const picked = untagged.items
      .filter((_, i) => checks[i] && checks[i].checked)
      .map((it) => it.id);
    if (!tag || !picked.length) return;
    const label = sel.selectedOptions[0] && sel.selectedOptions[0].textContent;
    if (
      picked.length > 20 &&
      !confirm(
        trf("ui.confirmTag", { n: picked.length, label: label || tag })
      )
    ) {
      return;
    }
    submit.disabled = true;
    try {
      await api("/api/scenes/tag-many", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids: picked, tag }),
      });
      await Promise.all([loadScenesView(), loadFilters()]);
    } catch (err) {
      alert(err.message);
      syncSubmit();
    }
  });
  box.append(legend, facesEl, tools, form);
  const hint = document.createElement("p");
  hint.className = "muted cluster-hint";
  hint.textContent = tr("scenes.hint");
  box.appendChild(hint);
  if (untagged.offset + untagged.items.length < untagged.total) {
    const more = document.createElement("button");
    more.type = "button";
    more.textContent = tr("ui.more");
    more.addEventListener("click", () => {
      loadSceneUntaggedPage(untagged.offset + untagged.items.length).catch((err) =>
        alert(err.message || String(err))
      );
    });
    box.appendChild(more);
  }
  root.appendChild(box);
}

async function loadSceneUntaggedPage(offset) {
  const qs = sceneScopeParams();
  qs.set("offset", String(offset || 0));
  qs.set("limit", "80");
  const data = await api(`/api/scenes/untagged?${qs.toString()}`);
  const root = $("sceneClusters");
  if (!root) return;
  root.innerHTML = "";
  renderSceneUntagged(root, data, state.sceneCatalog || []);
}

async function loadScenesView() {
  const root = $("sceneClusters");
  const stats = $("sceneStats");
  if (!root || isViewer()) return;
  try {
    if (!(state.libraryYears || []).length) await loadFilters();
    fillSceneYearSelect();
    if (!state.sceneScopeReady) {
      fillScenePlaceSelect(state.scenePlaces || []);
      ensureSceneScopeDefaults();
    }
    const qs = sceneScopeParams();
    qs.set("limit", "80");
    const data = await api(`/api/scenes/workspace?${qs.toString()}`);
    state.sceneCatalog = data.catalog || state.sceneCatalog || [];
    const wantPlace = $("scenePlace") ? $("scenePlace").value : "";
    fillScenePlaceSelect(data.places || []);
    const placeEl = $("scenePlace");
    if (placeEl && wantPlace && placeEl.value !== wantPlace) {
      await loadScenesView();
      return;
    }
    const st = data.status || {};
    const tagged = st.tagged || 0;
    const untagged = st.untagged || 0;
    const pending = st.pending || 0;
    stats.textContent =
      trn(tagged, "scenes.tagged.one", "scenes.tagged.many") +
      " · " + trf("scenes.untagged", { n: fmtN(untagged) }) +
      (pending ? " · " + trf("scenes.pending", { n: fmtN(pending) }) : "");
    const btn = $("btnScenesPage");
    if (btn) {
      btn.textContent = pending
        ? trf("scenes.detectLeft", { n: fmtN(pending) })
        : tr("scenes.detectBtn");
    }
    renderSceneChips(data.tags || []);
    if (state.reviewScene) {
      root.innerHTML = "";
      root.classList.add("hidden");
      await loadSceneReview(state.reviewScene.tag, state.reviewScene.offset || 0);
      return;
    }
    root.classList.remove("hidden");
    const reviewEl = $("sceneReview");
    if (reviewEl) {
      reviewEl.classList.add("hidden");
      reviewEl.innerHTML = "";
    }
    root.innerHTML = "";
    renderSceneUntagged(root, data.untagged, data.catalog || []);
  } catch (err) {
    if (stats) stats.textContent = "";
    root.innerHTML = "";
    const p = document.createElement("p");
    p.className = "muted";
    p.textContent = trf("ui.scenesFail", { msg: err.message });
    root.appendChild(p);
  }
}

function sceneScanBodyFrom(yearEl, placeEl) {
  const year = yearEl && yearEl.value;
  const place = placeEl && placeEl.value;
  const body = {};
  if (year) body.year = Number(year);
  if (place && place !== "__none__") body.place = place;
  return body;
}

function startSceneScan(yearEl, placeEl) {
  const body = sceneScanBodyFrom(yearEl, placeEl);
  if (!body.year && !body.place) {
    if (
      !confirm(
        tr("scenes.confirmAll")
      )
    ) {
      return;
    }
  }
  startJob("/api/scenes/scan", body);
}

function appendSceneTags(root, item) {
  if (!root || !item || isViewer()) return;
  for (const old of [...root.querySelectorAll(".scene-tag, .scene-add")]) {
    old.remove();
  }
  const scenes = item.scenes || [];
  for (const s of scenes) {
    const tag = document.createElement("span");
    tag.className = "scene-tag";
    tag.addEventListener("click", (ev) => ev.stopPropagation());
    const label = document.createElement("span");
    label.textContent = sceneLabel(s.tag, s.label);
    const reject = document.createElement("button");
    reject.type = "button";
    reject.className = "tag-reject danger";
    reject.textContent = notLabel(sceneLabel(s.tag, s.label));
    reject.addEventListener("click", async (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      reject.disabled = true;
      try {
        await api("/api/scenes/untag-many", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ids: [item.id], tag: s.tag }),
        });
        item.scenes = (item.scenes || []).filter((x) => x.tag !== s.tag);
        appendSceneTags(root, item);
        await loadFilters();
        if (state.view === "scenes") {
          if (state.reviewScene && state.reviewScene.tag === s.tag) {
            loadSceneReview(
              state.reviewScene.tag,
              state.reviewScene.offset || 0
            ).catch(() => {});
          } else {
            loadScenesView().catch(() => {});
          }
        }
      } catch (err) {
        alert(err.message);
        reject.disabled = false;
      }
    });
    tag.append(label, reject);
    root.appendChild(tag);
  }
  const have = new Set(scenes.map((s) => s.tag));
  const available = (state.sceneCatalog || []).filter((s) => !have.has(s.value));
  if (!available.length) return;
  const form = document.createElement("form");
  form.className = "scene-add";
  form.addEventListener("click", (ev) => ev.stopPropagation());
  const sel = document.createElement("select");
  sel.setAttribute("aria-label", tr("scenes.addLabel"));
  fillSceneTagSelect(available, sel);
  const addBtn = document.createElement("button");
  addBtn.type = "submit";
  addBtn.textContent = tr("action.add");
  form.append(sel, addBtn);
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const tag = sel.value;
    if (!tag) return;
    addBtn.disabled = true;
    try {
      const data = await api("/api/scenes/tag-many", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids: [item.id], tag }),
      });
      const label = sceneLabel(
        tag,
        (data && data.label) ||
          (sel.selectedOptions[0] && sel.selectedOptions[0].textContent) ||
          tag
      );
      const kind =
        (available.find((s) => s.value === tag) || {}).kind || "building";
      item.scenes = [...(item.scenes || []), { tag, label, kind }];
      appendSceneTags(root, item);
      await loadFilters();
      if (state.view === "scenes") loadScenesView().catch(() => {});
    } catch (err) {
      alert(err.message);
      addBtn.disabled = false;
    }
  });
  root.appendChild(form);
}

function applyAccess(user, enabled) {
  state.me = user || null;
  state.authEnabled = !!enabled;
  const viewer = isViewer();
  document.body.classList.toggle("viewer-mode", viewer);
  const who = $("whoami");
  const out = $("btnLogout");
  if (enabled && user) {
    who.classList.remove("hidden");
    who.textContent = viewer
      ? tr("role.viewerLine").replace("{name}", user.username)
      : user.username;
    out.classList.remove("hidden");
  } else if (viewer && lecturePreview()) {
    who.classList.remove("hidden");
    who.textContent = tr("role.preview");
    out.classList.add("hidden");
  } else {
    who.classList.add("hidden");
    out.classList.add("hidden");
  }
  if (viewer && !["gallery", "map", "albums", "help"].includes(state.view)) {
    setView("gallery");
  }
}

function helpPageUrl(lang) {
  const code = lang || (window.GalerieI18n ? GalerieI18n.getLang() : "fr");
  return `/static/help/${code}.html`;
}

function syncHelpLink() {
  const link = $("prefHelp");
  if (link) link.href = helpPageUrl();
}

let helpLangLoaded = "";

async function loadHelp() {
  const mount = $("helpMount");
  if (!mount) return;
  const lang = window.GalerieI18n ? GalerieI18n.getLang() : "fr";
  if (helpLangLoaded === lang && mount.querySelector("#helpArticle")) return;
  mount.textContent = tr("help.loading");
  try {
    const res = await fetch(helpPageUrl(lang), { cache: "no-store" });
    if (!res.ok) throw new Error(String(res.status));
    const doc = new DOMParser().parseFromString(await res.text(), "text/html");
    const article = doc.getElementById("helpArticle");
    if (!article) throw new Error("help");
    mount.replaceChildren(document.importNode(article, true));
    helpLangLoaded = lang;
  } catch (err) {
    helpLangLoaded = "";
    mount.textContent = tr("help.failed");
  }
}

function resetToken() {
  return new URLSearchParams(location.search).get("reset") || "";
}

function showAuthCard(mode) {
  const gate = $("loginGate");
  if (gate) gate.classList.remove("hidden");
  document.body.classList.add("signed-out");
  const cards = {
    login: "loginForm",
    out: "loggedOutCard",
    forgot: "forgotForm",
    reset: "resetForm",
  };
  Object.keys(cards).forEach((key) => {
    const el = $(cards[key]);
    if (el) el.classList.toggle("hidden", key !== mode);
  });
}

async function showLoginGate() {
  const token = resetToken();
  if (token) {
    showAuthCard("reset");
    const form = $("resetForm");
    if (form) form.dataset.token = token;
    return;
  }
  showAuthCard("login");
}

async function showLoggedOut() {
  showAuthCard("out");
  const user = $("loginUser");
  const pass = $("loginPass");
  if (user) user.value = "";
  if (pass) pass.value = "";
  const err = $("loginErr");
  if (err) err.textContent = "";
}

function hideLoginGate() {
  const gate = $("loginGate");
  if (gate) gate.classList.add("hidden");
  document.body.classList.remove("signed-out");
  state.signedOut = false;
}

function wipeSessionUi() {
  state.items = [];
  state.selected.clear();
  state.selectAnchor = null;
  state.offset = 0;
  const grid = $("grid");
  if (grid) grid.innerHTML = "";
  const status = $("status");
  if (status) status.textContent = tr("status.signedOut");
  if (pollTimer) {
    clearTimeout(pollTimer);
    pollTimer = null;
  }
  const lb = $("lightbox");
  if (lb && lb.open) {
    try {
      lb.close();
    } catch {
      /* sans effet */
    }
  }
}

async function loadUsers() {
  const list = $("usersList");
  const msg = $("usersMsg");
  if (!list) return;
  try {
    const data = await api("/api/users");
    list.innerHTML = "";
    if (!(data.users || []).length) {
      list.innerHTML = "";
      const empty = document.createElement("li");
      empty.textContent = tr("accounts.none");
      list.appendChild(empty);
      return;
    }
    for (const u of data.users) {
      const li = document.createElement("li");
      const label = document.createElement("span");
      const role = u.role === "admin" ? tr("role.admin") : tr("role.viewer");
      label.textContent = `${u.username} · ${role}${u.locked ? " · " + tr("role.paused") : ""}`;
      const email = document.createElement("input");
      email.type = "email";
      email.className = "user-email";
      email.value = u.email || "";
      email.placeholder = tr("accounts.emailPh");
      email.autocomplete = "off";
      const save = document.createElement("button");
      save.type = "button";
      save.textContent = tr("action.save");
      save.addEventListener("click", async () => {
        if (msg) msg.textContent = "";
        try {
          await api(`/api/users/${u.id}/email`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email: email.value.trim() }),
          });
          if (msg) msg.textContent = tr("accounts.emailSaved");
        } catch (err) {
          if (msg) msg.textContent = err.message || String(err);
        }
      });
      const del = document.createElement("button");
      del.type = "button";
      del.textContent = tr("accounts.remove");
      del.addEventListener("click", async () => {
        if (!confirm(tr("accounts.confirmRemove").replace("{name}", u.username))) return;
        try {
          await api(`/api/users/${u.id}`, { method: "DELETE" });
          await loadUsers();
        } catch (err) {
          if (msg) msg.textContent = err.message || String(err);
        }
      });
      li.append(label, email, save, del);
      list.appendChild(li);
    }
  } catch (err) {
    if (msg) msg.textContent = err.message || String(err);
  }
}

async function loadHealth() {
  try {
    const ping = await api("/api/health");
    $("brandName").textContent = "Galerie Médias";
    document.title = ping && ping.version ? `Galerie Médias ${ping.version}` : "Galerie Médias";
    const ver = ping && ping.version ? String(ping.version) : "";
    const brandVer = $("brandVersion");
    if (brandVer && ver) brandVer.textContent = ver;
    const verEl = $("appVersion");
    if (verEl && ver) verEl.textContent = `Galerie Médias ${ver}`;
    document.querySelectorAll(".login-version").forEach((el) => {
      if (ver) el.textContent = `Version ${ver}`;
    });
    const auth = (ping && ping.auth) || {};
    applyAccess(auth.user, auth.enabled);
    if (auth.enabled && !auth.user) {
      $("status").textContent = tr("status.connecting");
      $("status").title = "";
      await showLoginGate();
      return ping;
    }
    const h = await api("/api/status");
    if (h.portable) {
      const usb = $("usbHint");
      if (usb) usb.classList.remove("hidden");
    }
    if (h.library) {
      const key = h.library_ok ? "status.library" : "status.missing";
      $("status").textContent = tr(key)
        .replace("{n}", fmtN(h.media))
        .replace("{path}", h.library);
    } else {
      $("status").textContent = tr("status.count").replace("{n}", fmtN(h.media));
    }
    $("status").title = tr("status.title");
    const trashTab = $("tabTrash");
    if (trashTab && h.trash != null) {
      trashTab.textContent = h.trash
        ? tr("nav.trashCount").replace("{n}", String(h.trash))
        : tr("nav.trash");
    }
    if (h.job) renderJob(h.job);
    applyAccess((h.auth || {}).user, (h.auth || {}).enabled);
    hideLoginGate();
    return h;
  } catch {
    $("status").textContent = tr("ui.serverDown");
    return null;
  }
}

function phoneKindValue() {
  if ($("cfgPhoneFacebook") && $("cfgPhoneFacebook").checked) return "facebook";
  if ($("cfgPhoneAndroid") && $("cfgPhoneAndroid").checked) return "android";
  return "iphone";
}

function applyPhoneKind() {
  const kind = phoneKindValue();
  $("secIcloud").classList.toggle("hidden", kind !== "iphone");
  $("secGoogle").classList.toggle("hidden", kind !== "android");
  const facebook = $("secFacebook");
  if (facebook) facebook.classList.toggle("hidden", kind !== "facebook");
  const hint = $("classerSourceHint");
  const btnTriage = $("btnSortApply");
  if (hint) {
    const key = kind === "android"
      ? "organize.hintGoogle"
      : kind === "facebook"
        ? "organize.hintFacebook"
        : "organize.hintIcloud";
    hint.textContent = tr(key);
  }
  if (btnTriage) {
    const key = kind === "android"
      ? "classer.btnTakeout"
      : kind === "facebook"
        ? "organize.fromFacebook"
        : "organize.fromTriage";
    btnTriage.textContent = tr(key);
  }
}

async function loadSettings() {
  const data = await api("/api/settings");
  const kind = data.phone_kind === "android" || data.phone_kind === "facebook"
    ? data.phone_kind
    : "iphone";
  $("cfgPhoneIphone").checked = kind === "iphone";
  $("cfgPhoneAndroid").checked = kind === "android";
  if ($("cfgPhoneFacebook")) $("cfgPhoneFacebook").checked = kind === "facebook";
  applyPhoneKind();
  $("cfgTriage").value = data.triage_dir || "";
  $("cfgAppleId").value = data.apple_id || "";
  $("cfgApplePassword").value = "";
  $("cfgApplePassword").placeholder = data.password_set
    ? tr("settings.savedPh")
    : tr("settings.icloudPh");
  $("cfgPasswordHint").textContent = data.password_set
    ? tr("settings.pwEnc")
    : tr("settings.pwLocal");
  $("cfgGoogleDir").value = data.google_dir || "";
  if ($("cfgFacebookDir")) $("cfgFacebookDir").value = data.facebook_dir || "";
  $("cfgLibrarySrc").value = data.library_src || "";
  $("cfgLibraryDest").value = data.library_dest || "";
  $("cfgBackupDir").value = data.backup_dir || "";
  if ($("cfgCinemaDir")) $("cfgCinemaDir").value = data.cinema_dir || "";
  if ($("cfgOpticalDevice")) $("cfgOpticalDevice").value = data.optical_device || "";
  if ($("cfgCinemaStatus")) {
    const st = data.cinema_status || {};
    if (!st.configured) {
      $("cfgCinemaStatus").textContent = tr("cinema.statusUnconfigured");
    } else if (st.status === "ready") {
      $("cfgCinemaStatus").textContent = tr("cinema.statusReady").replace("{path}", st.path || "");
    } else if (st.status === "missing_mount") {
      $("cfgCinemaStatus").textContent = tr("cinema.statusMissingMount").replace("{path}", st.path || "");
    } else {
      $("cfgCinemaStatus").textContent = tr("cinema.statusMissing").replace("{path}", st.path || "");
    }
  }
  const smtpHost = $("cfgSmtpHost");
  if (smtpHost) smtpHost.value = data.smtp_host || "";
  const smtpPort = $("cfgSmtpPort");
  if (smtpPort) smtpPort.value = data.smtp_port || "587";
  const smtpUser = $("cfgSmtpUser");
  if (smtpUser) smtpUser.value = data.smtp_user || "";
  const smtpFrom = $("cfgSmtpFrom");
  if (smtpFrom) smtpFrom.value = data.smtp_from || "";
  const smtpTls = $("cfgSmtpTls");
  if (smtpTls) smtpTls.checked = data.smtp_tls !== "0";
  const publicUrl = $("cfgPublicUrl");
  if (publicUrl) publicUrl.value = data.public_url || "";
  const smtpPass = $("cfgSmtpPassword");
  if (smtpPass) {
    smtpPass.value = "";
    smtpPass.placeholder = data.smtp_password_set
      ? tr("status.saved")
      : tr("settings.smtpPassPh");
  }
  if (!$("cfgIcloudYear").value) {
    $("cfgIcloudYear").value = String(new Date().getFullYear());
  }
}

function renderJob(job) {
  state.lastJob = job || null;
  const bar = $("jobbar");
  const barText = $("jobbarText") || bar;
  const barMeter = $("jobbarMeter");
  const barFill = $("jobbarBar");
  const card = $("cfgProgress");
  const titleEl = $("cfgProgressTitle");
  const detailEl = $("cfgProgressDetail");
  const cardMeter = $("cfgProgressMeter");
  const cardFill = $("cfgProgressBar");
  const mfaBox = $("cfgMfaBox");
  if (mfaBox) {
    const need = Boolean(job && job.mfa_needed);
    mfaBox.classList.toggle("hidden", !need);
    if (need && state.view !== "settings") setView("settings");
  }
  const labels = {
    icloud: kindLabel("icloud"),
    sort: kindLabel("sort"),
    index: kindLabel("index"),
    backup: kindLabel("backup"),
    "copies-trash": kindLabel("copies-trash"),
    "trash-restore": kindLabel("trash-restore"),
    "trash-purge": kindLabel("trash-purge"),
    "trash-expire": kindLabel("trash-expire"),
    faces: kindLabel("faces"),
    "cinema-scan": tr("cinema.scan"),
    "cinema-enrich": tr("cinema.enrich"),
  };
  const allExtras = $("btnCopiesTrashAll");
  if (allExtras) {
    const busy =
      job &&
      job.kind === "copies-trash" &&
      (job.status === "running" || job.status === "queued");
    allExtras.disabled = Boolean(busy) || !state.copiesExtra;
  }
  const trashBusy =
    job &&
    (job.kind === "trash-restore" || job.kind === "trash-purge") &&
    (job.status === "running" || job.status === "queued");
  if (typeof syncTrashChrome === "function") syncTrashChrome(Boolean(trashBusy));
  function setMeter(meter, fill, jobState) {
    if (!meter || !fill) return;
    if (!jobState || jobState.status === "queued") {
      meter.classList.add("hidden");
      meter.classList.remove("indeterminate");
      return;
    }
    meter.classList.remove("hidden");
    const done = Number(jobState.done) || 0;
    const total = jobState.total;
    if (jobState.status === "done") {
      meter.classList.remove("indeterminate");
      fill.style.width = "100%";
      return;
    }
    if (jobState.status === "error") {
      meter.classList.add("hidden");
      return;
    }
    if (total && total > 0) {
      meter.classList.remove("indeterminate");
      fill.style.width = Math.max(2, Math.min(100, (100 * done) / total)) + "%";
    } else {
      meter.classList.add("indeterminate");
      fill.style.width = "";
    }
  }
  if (!job) {
    bar.classList.add("hidden");
    if (card) card.classList.add("hidden");
    return;
  }
  const label = labels[job.kind] || job.kind || tr("job.task");
  const queued = (job.queued || []).map((q) => labels[q.kind] || q.kind).join(", ");
  let counts = "";
  if (job.total) counts = ` ${job.done}/${job.total}`;
  else if (job.done) counts = trn(job.done, "job.files.one", "job.files.many");
  const detail = jobMessage(job);
  let text = "";
  if (job.status === "running") {
    text = `${label}${counts} — ${detail}`;
  } else if (job.status === "queued") {
    text = detail || trf("job.queued", { label: label });
  } else if (job.status === "error") {
    text = trf("job.error", { msg: detail || job.error || "" });
  } else if (job.status === "done") {
    text = detail || trf("job.done", { label: label });
  }
  if (queued) text += trf("job.then", { list: queued });
  if (text) {
    bar.classList.remove("hidden");
    barText.textContent = text;
    setMeter(barMeter, barFill, job);
  } else {
    bar.classList.add("hidden");
  }
  const showCard = job.kind === "icloud" || job.kind === "sort" || job.kind === "backup";
  if (card && showCard && text) {
    card.classList.remove("hidden");
    if (titleEl) titleEl.textContent = label + (job.status === "running" ? counts : "");
    if (detailEl) detailEl.textContent = detail || text;
    setMeter(cardMeter, cardFill, job);
  } else if (card) {
    card.classList.add("hidden");
  }
}

function pageFullySelected() {
  return state.items.length > 0 && state.items.every((it) => state.selected.has(it.id));
}

function selectIndexRange(fromIdx, toIdx) {
  const a = Math.min(fromIdx, toIdx);
  const b = Math.max(fromIdx, toIdx);
  for (let i = a; i <= b; i++) {
    const it = state.items[i];
    if (it) state.selected.add(it.id);
  }
}

function pageSelectedIds() {
  return state.items.filter((it) => state.selected.has(it.id)).map((it) => it.id);
}

function hasOffPageSelection() {
  if (!state.selected.size) return false;
  const onPage = new Set(state.items.map((it) => it.id));
  for (const id of state.selected) {
    if (!onPage.has(id)) return true;
  }
  return false;
}

function startFreshOnPage(idx) {
  state.selected.clear();
  const it = state.items[idx];
  if (it) state.selected.add(it.id);
  state.selectAnchor = idx;
}

function syncGridChecks() {
  const cards = $("grid").querySelectorAll(".card");
  state.items.forEach((item, i) => {
    const card = cards[i];
    if (!card) return;
    const on = state.selected.has(item.id);
    card.classList.toggle("sel", on);
    const box = card.querySelector('input[type="checkbox"]');
    if (box) box.checked = on;
  });
  updateCountLabel();
  syncSelectionChrome();
}

function updateCountLabel(extra) {
  const el = $("count");
  if (!el) return;
  const total = state.total;
  const n = state.selected.size;
  const onPage = state.items.length;
  const page = Math.max(1, Math.floor(state.offset / PAGE) + 1);
  const pages = Math.max(1, Math.ceil((total || 0) / PAGE) || 1);
  const outside = Boolean(n && total && n > total);
  el.replaceChildren();
  const add = (label, value, cls) => {
    const item = document.createElement("span");
    item.className = "count-item" + (cls ? " " + cls : "");
    const k = document.createElement("em");
    k.textContent = label;
    const v = document.createElement("strong");
    v.textContent = value;
    item.append(k, v);
    el.appendChild(item);
  };
  add(tr("count.filter"), tr("count.files").replace("{n}", fmtN(total)));
  add(tr("count.page"), tr("count.pageLine").replace("{n}", fmtN(onPage)).replace("{page}", String(page)).replace("{pages}", String(pages)));
  add(tr("count.selected"), n ? fmtN(n) : tr("count.none"), n > onPage ? "count-warn" : "");
  if (n > onPage) {
    add(tr("count.offscreen"), fmtN(n - onPage), "count-warn");
  }
  if (outside) {
    add(tr("count.warn"), tr("count.warnText"), "count-warn");
  }
  if (extra) {
    add(tr("count.last"), String(extra).replace(/^ · /, ""));
  }
}

function syncSelectionChrome() {
  const allPage = pageFullySelected();
  const pageBtn = $("btnSelectPage");
  if (pageBtn) {
    pageBtn.textContent = allPage ? tr("action.pageAll") : tr("action.page");
    pageBtn.classList.toggle("on", allPage);
    pageBtn.setAttribute("aria-pressed", String(allPage));
    pageBtn.title = allPage ? tr("action.pageAllTitle") : tr("action.pageTitle");
  }
  const albumBtn = $("btnAlbum");
  const albumRm = $("btnAlbumRemove");
  const moveBtn = $("btnMove");
  const n = state.selected.size;
  if (albumBtn) albumBtn.classList.toggle("hidden", !n);
  if (moveBtn) moveBtn.classList.toggle("hidden", !n);
  if (albumRm) {
    albumRm.classList.toggle("hidden", !n);
    const albumId = $("filterAlbum") ? $("filterAlbum").value : "";
    const album = (state.albums || []).find((a) => String(a.id) === String(albumId));
    albumRm.textContent = album
      ? tr("action.removeFrom").replace("{name}", album.name)
      : tr("action.removeAlbum");
    albumRm.title = album
      ? tr("action.removeFrom").replace("{name}", album.name)
      : tr("action.removeAlbum");
  }
}

async function loadGallery() {
  const p = paramsFromFilters();
  p.set("offset", String(state.offset));
  p.set("limit", String(PAGE));
  let data;
  try {
    data = await api("/api/media?" + p.toString());
  } catch (err) {
    $("status").textContent = String(err.message || err);
    return;
  }
  state.total = data.total;
  state.items = data.items;
  updateCountLabel();
  const grid = $("grid");
  grid.innerHTML = "";
  if (!data.items.length) {
    const year = $("filterYear").value;
    const box = document.createElement("div");
    box.className = "empty";
    const p = document.createElement("p");
    if (year && !state.indexedYears.has(Number(year))) {
      p.textContent = trf("empty.yearDisk", { year: year });
      box.append(p);
      if (!isViewer()) {
        const b = document.createElement("button");
        b.className = "primary";
        b.type = "button";
        b.textContent = trf("ui.indexYear", { year: year });
        b.addEventListener("click", () => {
          $("indexYear").value = year;
          startJob("/api/index", { year: Number(year) });
        });
        box.append(b);
      }
    } else if (year) {
      const personId = $("filterPerson").value;
      const person = (state.people || []).find((p) => String(p.id) === personId);
      if (person) {
        p.textContent =
          person.name + " : " + trn(person.count, "unit.photo.one", "unit.photo.many") +
          personSpan(person) + ". " + trf("empty.noneYear", { year: year });
        const b = document.createElement("button");
        b.className = "primary";
        b.type = "button";
        b.textContent = trf("ui.seePerson", { name: person.name });
        b.addEventListener("click", async () => {
          $("filterYear").value = "";
          $("filterPlace").value = "";
          if ($("filterMoment")) $("filterMoment").value = "";
          $("filterKind").value = "";
          $("filterAlbum").value = "";
          $("filterQ").value = "";
          if ($("filterMonth")) $("filterMonth").value = "";
          try {
            await loadPlaces();
          } catch (err) {
            $("status").textContent = String(err.message || err);
          }
          bumpGalleryFromFilters();
        });
        box.append(p, b);
      } else {
        p.textContent = tr("empty.year").replace("{year}", String(year));
        box.append(p);
      }
    } else if ($("filterPerson").value) {
      const personId = $("filterPerson").value;
      const person = (state.people || []).find((p) => String(p.id) === personId);
      p.textContent = person
        ? person.name + " : " + trn(person.count, "unit.photo.one", "unit.photo.many") +
          personSpan(person) + ". " + tr("empty.noneFilters")
        : tr("empty.person");
      box.append(p);
    } else {
      p.textContent = isViewer() ? tr("empty.filters") : tr("empty.library");
      box.append(p);
    }
    grid.appendChild(box);
  }
  data.items.forEach((item, idx) => {
    const card = document.createElement("div");
    card.className = "card" + (state.selected.has(item.id) ? " sel" : "");
    const img = document.createElement("img");
    img.loading = "lazy";
    img.alt = item.name;
    img.src = mediaThumbUrl(item);
    const badge = document.createElement("span");
    badge.className = "badge";
    setFlagText(
      badge,
      item.kind === "video"
        ? item.thumb_ok
          ? tr("media.video")
          : tr("media.videoBad")
        : placeLabel(item.place) || item.moment || item.year || ""
    );
    if (item.place && placeLabel(item.place) !== item.place) badge.title = item.place;
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = state.selected.has(item.id);
    cb.title = tr("media.shift");
    cb.addEventListener("mousedown", (ev) => {
      if (ev.shiftKey || hasOffPageSelection()) ev.preventDefault();
    });
    cb.addEventListener("click", (ev) => {
      ev.stopPropagation();
      if (ev.shiftKey && state.selectAnchor != null) {
        ev.preventDefault();
        if (hasOffPageSelection()) state.selected.clear();
        selectIndexRange(state.selectAnchor, idx);
        syncGridChecks();
        return;
      }
      if (hasOffPageSelection()) {
        ev.preventDefault();
        startFreshOnPage(idx);
        syncGridChecks();
        return;
      }
      state.selectAnchor = idx;
      if (cb.checked) state.selected.add(item.id);
      else state.selected.delete(item.id);
      card.classList.toggle("sel", cb.checked);
      updateCountLabel();
      syncSelectionChrome();
    });
    const inAlbum = Boolean(item.album_ids && item.album_ids.length);
    card.append(img, badge, cb);
    if (!isViewer()) {
      const fav = document.createElement("button");
      fav.type = "button";
      fav.className = "fav" + (inAlbum ? " on" : "");
      fav.title = inAlbum ? tr("album.edit") : tr("album.add");
      fav.textContent = inAlbum ? "★" : "☆";
      fav.addEventListener("click", (ev) => {
        ev.stopPropagation();
        openAlbumDialog({ ids: [item.id], replace: true, currentIds: item.album_ids || [] });
      });
      card.append(fav);
    }
    card.addEventListener("click", (ev) => {
      if (ev.shiftKey) {
        ev.preventDefault();
        if (hasOffPageSelection()) state.selected.clear();
        if (state.selectAnchor == null) {
          startFreshOnPage(idx);
        } else {
          selectIndexRange(state.selectAnchor, idx);
        }
        syncGridChecks();
        return;
      }
      openLightboxFromItem(item);
    });
    grid.appendChild(card);
  });
  const page = Math.floor(state.offset / PAGE) + 1;
  const pages = Math.max(1, Math.ceil(state.total / PAGE));
  $("pageInfo").textContent = tr("pager.page").replace("{page}", String(page)).replace("{pages}", String(pages));
  $("btnPrev").disabled = state.offset <= 0;
  $("btnNext").disabled = state.offset + PAGE >= state.total;
  syncSelectionChrome();
}

function wrapIndex(index, total) {
  if (total <= 0) return 0;
  return ((index % total) + total) % total;
}

function stopAdvance() {
  if (slideTimer) {
    clearTimeout(slideTimer);
    slideTimer = null;
  }
}

function bumpChrome() {
  const lb = $("lightbox");
  lb.classList.add("chrome-on");
  clearTimeout(chromeTimer);
  if (lb.classList.contains("presenting")) {
    chromeTimer = setTimeout(() => lb.classList.remove("chrome-on"), 2500);
  }
}

function setPresenting(on) {
  const lb = $("lightbox");
  lb.classList.toggle("presenting", on);
  if (on) bumpChrome();
  else {
    lb.classList.add("chrome-on");
    clearTimeout(chromeTimer);
  }
}

function updatePlayButton() {
  $("lbPlay").textContent = state.playing ? "Pause" : "Diaporama";
}

async function enterFullscreen() {
  const lb = $("lightbox");
  const inner = $("lbInner");
  lb.classList.add("is-full");
  setPresenting(true);
  if (!lb.open) lb.showModal();
  if (document.fullscreenElement) return;
  try {
    await inner.requestFullscreen();
  } catch {
    try {
      await document.documentElement.requestFullscreen();
    } catch {
      /* le dialogue occupe déjà la fenêtre via .is-full */
    }
  }
  if (!lb.open) lb.showModal();
  requestAnimationFrame(() => {
    fitLightboxMedia();
    requestAnimationFrame(fitLightboxMedia);
  });
}

async function exitFullscreen() {
  $("lightbox").classList.remove("is-full");
  if (document.fullscreenElement) {
    try {
      await document.exitFullscreen();
    } catch {
      /* sans effet */
    }
  }
}

function prefetchItem(item) {
  if (!item) return;
  const img = new Image();
  img.src = item.kind === "video" ? mediaThumbUrl(item) : mediaPreviewUrl(item);
}

function scheduleAdvance() {
  stopAdvance();
  if (!state.playing || !$("lightbox").open) return;
  const item = state.lbItem;
  if (!item || item.kind === "video") return;
  slideTimer = setTimeout(() => {
    openLightboxAt(state.lbIndex + 1, { wrap: true });
  }, state.delay);
}

function startSlideshow() {
  state.playing = true;
  setPresenting(true);
  updatePlayButton();
  const video = $("lbStage").querySelector("video");
  if (video) {
    video.controls = false;
    return;
  }
  const img = $("lbStage").querySelector("img");
  if (img && !img.complete) return;
  scheduleAdvance();
}

function pauseSlideshow() {
  state.playing = false;
  stopAdvance();
  setPresenting(Boolean(document.fullscreenElement));
  updatePlayButton();
  const video = $("lbStage").querySelector("video");
  if (video) video.controls = true;
}

const SHARE_EXT = {
  "image/jpeg": ".jpg",
  "image/png": ".png",
  "image/webp": ".webp",
  "image/gif": ".gif",
  "image/heic": ".heic",
  "image/heif": ".heif",
  "video/mp4": ".mp4",
  "video/quicktime": ".mov",
  "video/webm": ".webm",
};
let shareAbort = null;
let shareFile = null;

function shareFileName(name, type) {
  const clean = String(type || "").split(";")[0].trim().toLowerCase();
  const ext = SHARE_EXT[clean];
  const base = String(name || "galerie").replace(/\.[^.]+$/, "") || "galerie";
  return ext ? base + ext : (name || "galerie");
}

function canShareFile(file) {
  if (!file || !navigator.canShare) return false;
  try {
    return navigator.canShare({ files: [file] });
  } catch (err) {
    return false;
  }
}

async function fetchShareBlob(url, item, signal) {
  const res = await fetch(url, { signal, credentials: "same-origin" });
  if (!res.ok) throw new Error(String(res.status));
  const blob = await res.blob();
  const type = (blob.type || "").split(";")[0].trim().toLowerCase()
    || (item.kind === "video" ? "video/mp4" : "image/jpeg");
  return new File([blob], shareFileName(item.name, type), { type });
}

async function prepareShare(item) {
  if (shareAbort) shareAbort.abort();
  const ctrl = new AbortController();
  shareAbort = ctrl;
  shareFile = null;
  const buttons = document.querySelectorAll("#shareNets [data-share]");
  buttons.forEach((btn) => { btn.disabled = true; });
  const msg = $("shareMsg");
  if (msg) msg.textContent = tr("share.preparing");
  const urls = item.kind === "video"
    ? [`/api/media/${item.id}/play`, `/api/media/${item.id}/file`]
    : [`/api/media/${item.id}/file`];
  try {
    let file = null;
    let lastErr = null;
    for (const url of urls) {
      try {
        file = await fetchShareBlob(url, item, ctrl.signal);
        break;
      } catch (err) {
        if (err && err.name === "AbortError") throw err;
        lastErr = err;
      }
    }
    if (!file) throw lastErr || new Error("share");
    if (item.kind === "photo" && !canShareFile(file)) {
      try {
        const preview = await fetchShareBlob(`/api/media/${item.id}/preview`, item, ctrl.signal);
        if (canShareFile(preview)) file = preview;
      } catch (err) {
        if (err && err.name === "AbortError") throw err;
      }
    }
    if (ctrl.signal.aborted || !state.lbItem || state.lbItem.id !== item.id) return;
    shareFile = file;
    buttons.forEach((btn) => { btn.disabled = false; });
    if (msg) msg.textContent = tr("share.ready");
  } catch (err) {
    if (err && err.name === "AbortError") return;
    if (msg) msg.textContent = tr("share.failed");
  }
}

function openShare() {
  const item = state.lbItem;
  if (!item) return;
  if (state.playing) pauseSlideshow();
  const dlg = $("shareDlg");
  if (dlg && !dlg.open) dlg.showModal();
  prepareShare(item);
}

function downloadShare(file, name) {
  const href = URL.createObjectURL(file);
  const a = document.createElement("a");
  a.href = href;
  a.download = file.name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(href), 4000);
  const msg = $("shareMsg");
  if (msg) msg.textContent = tr("share.downloaded").split("{name}").join(name);
}

function sharePrepared(network) {
  const file = shareFile;
  if (!file) return;
  const name = tr("share." + network);
  const payload = { files: [file], title: "Galerie Médias", text: file.name };
  let pending = null;
  try {
    if (canShareFile(file)) pending = navigator.share(payload);
  } catch (err) {
    pending = null;
  }
  if (!pending) {
    downloadShare(file, name);
    return;
  }
  pending.then(() => {
    const msg = $("shareMsg");
    if (msg) msg.textContent = tr("share.sent");
  }).catch((err) => {
    if (err && err.name === "AbortError") {
      const msg = $("shareMsg");
      if (msg) msg.textContent = tr("share.ready");
      return;
    }
    downloadShare(file, name);
  });
}

async function fetchSlide(index) {
  if (state.lbSeq && state.lbSeq.length) {
    const total = state.lbSeq.length;
    const want = wrapIndex(index, total);
    const item = await api(`/api/media/${state.lbSeq[want]}`);
    return { total, items: [item], offset: want };
  }
  const p = paramsFromFilters();
  p.set("offset", String(index));
  p.set("limit", "1");
  return api("/api/media?" + p.toString());
}

function updateNavArrows(total) {
  const show = total > 1;
  $("lbPrev").classList.toggle("hidden", !show);
  $("lbNext").classList.toggle("hidden", !show);
}

function openLightboxFromItem(item) {
  const selected = [...state.selected];
  if (selected.length >= 2 && state.selected.has(item.id)) {
    state.lbSeq = selected;
    state.lbSeqKind = "sel";
    state.lbFocusByMedia = null;
    openLightboxAt(selected.indexOf(item.id));
    return;
  }
  state.lbSeq = null;
  state.lbSeqKind = null;
  state.lbFocusByMedia = null;
  openLightboxAt(state.offset + state.items.indexOf(item));
}

function openLightboxFromSeq(mediaId, ids, focusByMedia, kind) {
  const uniq = [];
  const seen = new Set();
  for (const id of ids) {
    if (seen.has(id)) continue;
    seen.add(id);
    uniq.push(id);
  }
  if (!uniq.length) return Promise.resolve();
  state.lbSeq = uniq;
  state.lbSeqKind = kind || (focusByMedia ? "faces" : "sel");
  state.lbFocusByMedia = focusByMedia || null;
  const idx = uniq.indexOf(mediaId);
  return openLightboxAt(idx < 0 ? 0 : idx);
}

async function fillPeopleNames() {
  try {
    const data = await api("/api/people");
    const list = $("peopleNames");
    list.innerHTML = "";
    for (const p of data.people || []) {
      const opt = document.createElement("option");
      opt.value = p.name;
      list.appendChild(opt);
    }
  } catch {
    /* sans effet */
  }
}

async function renderFaceTags(mediaId, gen, detect) {
  const root = $("lbTags");
  if (!root) return;
  root.innerHTML = "";
  if (isViewer()) {
    return;
  }
  const loading = document.createElement("div");
  loading.className = "face-tag-msg";
  loading.textContent = detect ? tr("faces.loading") : tr("faces.short");
  root.appendChild(loading);

  const paint = (faces) => {
    root.innerHTML = "";
    if (!faces.length) {
      const msg = document.createElement("div");
      msg.className = "face-tag-msg";
      msg.textContent = tr("ui.noFace");
      root.appendChild(msg);
      return;
    }
    for (const face of faces) {
      const tag = document.createElement("form");
      const focusId = state.lbFocusByMedia && state.lbFocusByMedia[mediaId];
      tag.className =
        "face-tag" +
        (face.name ? " named" : "") +
        (face.id === focusId ? " focus" : "");
      tag.addEventListener("click", (ev) => ev.stopPropagation());
      const img = document.createElement("img");
      img.alt = face.name || tr("faces.alt");
      img.src = `/api/faces/${face.id}/thumb`;
      const input = document.createElement("input");
      input.type = "text";
      input.placeholder = tr("ui.firstName");
      input.value = face.name || "";
      input.title = tr("faces.fix");
      input.setAttribute("list", "peopleNames");
      input.autocomplete = "off";
      input.spellcheck = false;
        let saving = false;
        const save = async () => {
          const name = input.value.trim();
          if (name === (face.name || "") || saving) return;
          if (!name && !face.name) return;
          saving = true;
          input.disabled = true;
          try {
            await api(`/api/faces/${face.id}/name`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ name }),
            });
            face.name = name;
            tag.classList.toggle("named", Boolean(name));
            await Promise.all([fillPeopleNames(), loadFilters()]);
          } catch (err) {
            alert(err.message);
            input.value = face.name || "";
          } finally {
            saving = false;
            input.disabled = false;
          }
        };
      tag.addEventListener("submit", (ev) => {
        ev.preventDefault();
        save();
      });
      input.addEventListener("change", save);
      tag.append(img, input);
      if (face.name) {
        const reject = document.createElement("button");
        reject.type = "button";
        reject.className = "tag-reject danger";
        reject.textContent = notLabel(face.name);
        reject.addEventListener("click", async (ev) => {
          ev.preventDefault();
          ev.stopPropagation();
          input.value = "";
          await save();
          if (state.playing && state.lbTotal > 1) {
            openLightboxAt(state.lbIndex + 1, { wrap: true });
          } else if (state.reviewPerson) {
            loadPersonReview(state.reviewPerson.id, state.reviewPerson.offset || 0).catch(
              () => {}
            );
          } else if (state.view === "faces") {
            loadFacesView().catch(() => {});
          }
        });
        tag.appendChild(reject);
      }
      root.appendChild(tag);
    }
  };

  try {
    let data = await api(`/api/media/${mediaId}/faces`);
    if (gen !== slideGen) return;
    if (detect && !data.face_scanned && data.file_ok !== false) {
      loading.textContent = tr("ui.facesWait");
      data = await api(`/api/media/${mediaId}/faces/scan`, { method: "POST" });
      if (gen !== slideGen) return;
    }
    paint(data.faces || []);
    appendSceneTags(root, state.lbItem);
    if (data.file_ok === false) {
      const note = document.createElement("div");
      note.className = "face-tag-msg";
      note.textContent = tr("ui.fileMissing");
      root.appendChild(note);
    }
  } catch (err) {
    if (gen !== slideGen) return;
    root.innerHTML = "";
    const msg = document.createElement("div");
    msg.className = "face-tag-msg";
    msg.textContent = err.message || tr("ui.facesOff");
    root.appendChild(msg);
    appendSceneTags(root, state.lbItem);
  }
}

async function openLightboxAt(index, opts = {}) {
  const gen = ++slideGen;
  stopAdvance();
  let data;
  try {
    data = await fetchSlide(Math.max(0, index));
  } catch (err) {
    if (gen !== slideGen) return;
    if (opts.play) alert(tr("ui.nothingPlay"));
    else alert(err.message || tr("ui.photoMissing"));
    return;
  }
  if (gen !== slideGen) return;
  let total = data.total;
  if (!total) {
    if (opts.play) alert(tr("ui.nothingPlay"));
    return;
  }
  let want = opts.wrap ? wrapIndex(index, total) : Math.min(Math.max(0, index), total - 1);
  if (want !== Math.max(0, index) || !data.items.length) {
    try {
      data = await fetchSlide(want);
    } catch (err) {
      if (gen !== slideGen) return;
      alert(err.message || tr("ui.photoMissing"));
      return;
    }
    if (gen !== slideGen) return;
    total = data.total;
    if (!data.items.length) return;
    want = wrapIndex(want, total);
  }
  const item = data.items[0];
  stopPhotoEdit();
  resetLbZoom();
  if (!state.lbSeq) state.total = total;
  state.lbTotal = total;
  state.lbIndex = want;
  state.lbItem = item;
  const stage = $("lbStage");
  stage.innerHTML = "";
  setFlagText(
    $("lbCaption"),
    `${want + 1} / ${total}` +
      (state.lbSeqKind === "faces" ? tr("lb.faceGroup") : state.lbSeq ? tr("lb.selection") : "") +
      ` · ${placePathLabel(item.relpath)}` +
      (item.taken_at ? " · " + item.taken_at.replace("T", " ") : "") +
      (item.scenes && item.scenes.length
        ? " · " + item.scenes.map((s) => sceneLabel(s.tag, s.label)).join(", ")
        : "")
  );
  $("lbCaption").title = item.relpath || "";
  $("lbOrig").href = `/api/media/${item.id}/file`;
  $("lbOrig").setAttribute("download", item.name);
  if ($("shareDlg") && $("shareDlg").open) prepareShare(item);
  $("lbEdit").classList.toggle("hidden", item.kind !== "photo" || isViewer());
  updateNavArrows(total);
  renderFaceTags(item.id, gen, !state.playing && !opts.play);
  if (item.kind === "video") {
    const showMissing = async () => {
      if (gen !== slideGen) return;
      let fileOk = null;
      try {
        const res = await fetch(`/api/media/${item.id}`);
        fileOk = res.ok;
      } catch {
        fileOk = null;
      }
      if (gen !== slideGen) return;
      stage.innerHTML = "";
      const wrap = document.createElement("div");
      wrap.className = "lb-missing";
      const img = document.createElement("img");
      img.alt = item.name;
      img.src = mediaPreviewUrl(item);
      const p = document.createElement("p");
      if (fileOk === false) {
        p.textContent = tr("video.missing");
      } else if (!item.thumb_ok) {
        p.textContent = tr("video.incomplete");
      } else {
        p.textContent = tr("video.convert");
      }
      wrap.append(img, p);
      stage.appendChild(wrap);
    };
    if (!item.thumb_ok) {
      showMissing();
    } else {
      const wrap = document.createElement("div");
      wrap.className = "lb-video-wrap";
      const v = document.createElement("video");
      v.controls = !state.playing;
      v.autoplay = true;
      v.playsInline = true;
      v.preload = "auto";
      v.poster = mediaThumbUrl(item);
      v.addEventListener("loadedmetadata", () => fitLightboxMedia());
      v.addEventListener("resize", () => fitLightboxMedia());
      const hint = document.createElement("p");
      hint.className = "lb-play-hint";
      hint.hidden = true;
      hint.textContent = tr("ui.converting");
      let triedConvert = false;
      let playFailTimer = 0;
      v.addEventListener("ended", () => {
        if (state.playing && gen === slideGen) openLightboxAt(state.lbIndex + 1, { wrap: true });
      });
      v.addEventListener("playing", () => {
        hint.hidden = true;
        if (playFailTimer) clearTimeout(playFailTimer);
      });
      v.addEventListener("error", () => {
        if (gen !== slideGen) return;
        if (!triedConvert) {
          triedConvert = true;
          hint.hidden = false;
          v.src = `/api/media/${item.id}/play`;
          v.play().catch(() => {
            v.muted = true;
            v.play().catch(() => {});
          });
          return;
        }
        if (playFailTimer) clearTimeout(playFailTimer);
        playFailTimer = setTimeout(() => {
          if (gen !== slideGen || v.readyState >= 2) return;
          showMissing();
          if (state.playing) {
            slideTimer = setTimeout(() => openLightboxAt(state.lbIndex + 1, { wrap: true }), 1500);
          }
        }, 800);
      });
      v.src = `/api/media/${item.id}/file`;
      wrap.append(v, hint);
      stage.appendChild(wrap);
      v.play().catch(() => {
        v.muted = true;
        v.play().catch(() => {});
      });
    }
  } else {
    const wrap = document.createElement("div");
    wrap.className = "lb-photo";
    const img = document.createElement("img");
    img.alt = item.name;
    img.src = mediaPreviewUrl(item);
    img.addEventListener("load", () => {
      fitLightboxMedia();
      if (gen === slideGen) scheduleAdvance();
    });
    if (img.complete && img.naturalWidth) fitLightboxMedia();
    img.addEventListener("error", () => {
      if (state.playing && gen === slideGen) {
        slideTimer = setTimeout(() => openLightboxAt(state.lbIndex + 1, { wrap: true }), 1500);
      }
    });
    wrap.appendChild(img);
    const focusId = state.lbFocusByMedia && state.lbFocusByMedia[item.id];
    const face = focusId && Array.isArray(item.faces)
      ? item.faces.find((f) => f.id === focusId)
      : null;
    if (face && Number.isFinite(face.x) && Number.isFinite(face.w)) {
      const box = document.createElement("div");
      box.className = "lb-face-box";
      box.style.left = `${face.x * 100}%`;
      box.style.top = `${face.y * 100}%`;
      box.style.width = `${face.w * 100}%`;
      box.style.height = `${face.h * 100}%`;
      wrap.appendChild(box);
    }
    stage.appendChild(wrap);
  }
  const lb = $("lightbox");
  if (!lb.open) {
    fillPeopleNames();
    lb.showModal();
  }
  requestAnimationFrame(() => {
    fitLightboxMedia();
    requestAnimationFrame(fitLightboxMedia);
  });
  bumpChrome();
  if (opts.fullscreen) await enterFullscreen();
  if (opts.play) startSlideshow();
  else if (state.playing && item.kind !== "video") scheduleAdvance();
  fetchSlide(wrapIndex(want + 1, total))
    .then((next) => {
      if (gen === slideGen && next.items[0]) prefetchItem(next.items[0]);
    })
    .catch(() => {});
  maybeCastCurrent();
}

async function closeLightbox() {
  stopPhotoEdit();
  pauseSlideshow();
  setPresenting(false);
  await exitFullscreen();
  $("lightbox").close();
  $("lbStage").innerHTML = "";
  $("lbTags").innerHTML = "";
  state.lbItem = null;
}

function startFaceScan() {
  const year = $("indexYear").value;
  const body = year ? { year: Number(year) } : {};
  startJob("/api/faces/scan", body);
}

async function closePersonReview() {
  state.reviewPerson = null;
  const root = $("faceReview");
  if (root) {
    root.classList.add("hidden");
    root.innerHTML = "";
  }
  const clusters = $("clusters");
  if (clusters) clusters.classList.remove("hidden");
  await loadFacesView();
}

async function loadPersonReview(personId, offset) {
  const root = $("faceReview");
  if (!root) return;
  offset = offset || 0;
  const data = await api(
    `/api/people/${personId}/faces?offset=${offset}&limit=200`
  );
  state.reviewPerson = {
    id: data.id,
    name: data.name,
    total: data.total,
    offset,
  };
  const clusters = $("clusters");
  if (clusters) {
    clusters.innerHTML = "";
    clusters.classList.add("hidden");
  }
  root.classList.remove("hidden");
  root.innerHTML = "";
  const head = document.createElement("div");
  head.className = "face-review-head";
  const title = document.createElement("p");
  title.className = "cluster-legend";
  title.textContent =
    tr("faces.reviewCount")
      .replaceAll("{name}", data.name)
      .replaceAll("{n}", fmtN(data.total))
      .replaceAll("{not}", notLabel(data.name));
  const back = document.createElement("button");
  back.type = "button";
  back.textContent = tr("ui.backGroups");
  back.addEventListener("click", () => {
    closePersonReview().catch((err) => alert(err.message || String(err)));
  });
  head.append(title, back);
  root.appendChild(head);
  if (!data.faces.length) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = trf("ui.noFacesLeft", { name: data.name });
    root.appendChild(empty);
    return;
  }
  const grid = document.createElement("div");
  grid.className = "cluster-faces";
  for (const f of data.faces) {
    const card = document.createElement("div");
    card.className = "review-face";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "cluster-face";
    btn.title = tr("ui.clickLarge");
    const img = document.createElement("img");
    img.alt = data.name;
    img.loading = "lazy";
    img.src = `/api/faces/${f.id}/thumb`;
    btn.appendChild(img);
    btn.addEventListener("click", () => {
      const ids = [];
      const focus = {};
      for (const other of data.faces) {
        ids.push(other.media_id);
        if (focus[other.media_id] == null) focus[other.media_id] = other.id;
      }
      focus[f.media_id] = f.id;
      openLightboxFromSeq(f.media_id, ids, focus, "review").catch((err) => {
        alert(err.message || tr("ui.openFail"));
      });
    });
    const reject = document.createElement("button");
    reject.type = "button";
    reject.className = "danger";
    reject.textContent = notLabel(data.name);
    reject.addEventListener("click", async () => {
      reject.disabled = true;
      try {
        await api("/api/faces/unname-many", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ids: [f.id] }),
        });
        await Promise.all([
          loadPersonReview(personId, offset),
          loadFilters(),
          fillPeopleNames(),
        ]);
      } catch (err) {
        alert(err.message);
        reject.disabled = false;
      }
    });
    card.append(btn, reject);
    grid.appendChild(card);
  }
  root.appendChild(grid);
  const firstFace = grid.querySelector(".review-face");
  if (firstFace) {
    requestAnimationFrame(() => {
      const compact = document.documentElement.classList.contains("is-phone")
        || document.documentElement.classList.contains("is-narrow");
      const sticky = compact ? null : document.querySelector(".chrome");
      const offsetY = (sticky ? sticky.getBoundingClientRect().height : 0) + 12;
      const top = firstFace.getBoundingClientRect().top + window.scrollY - offsetY;
      window.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
    });
  }
  if (offset + data.faces.length < data.total) {
    const more = document.createElement("button");
    more.type = "button";
    more.textContent = tr("ui.more");
    more.addEventListener("click", () => {
      loadPersonReview(personId, offset + data.faces.length).catch((err) =>
        alert(err.message || String(err))
      );
    });
    root.appendChild(more);
  }
}

async function loadFacesView() {
  const root = $("clusters");
  const plist = $("peopleList");
  const stats = $("faceStats");
  try {
    const [people, clusters, status] = await Promise.all([
      api("/api/people"),
      api("/api/faces/clusters"),
      api("/api/faces/status"),
    ]);
    const pending = status.pending || 0;
    const scanned = status.scanned || 0;
    const faces = status.faces || 0;
    stats.textContent =
      trn(faces, "faces.detected.one", "faces.detected.many") +
      " · " + trn(scanned, "faces.scanned.one", "faces.scanned.many") +
      (pending ? " · " + trf("scenes.pending", { n: fmtN(pending) }) : "") +
      (status.copy_groups
        ? " · " + trn(status.copy_groups, "faces.series.one", "faces.series.many")
        : "");
    const btn = $("btnFacesPage");
    btn.textContent = pending
      ? trf("faces.detectLeft", { n: fmtN(pending) })
      : tr("faces.attach");
    plist.innerHTML = "";
    if (!people.people.length) {
      plist.textContent = tr("ui.noNames");
      fillMergeSelects([]);
    } else {
      for (const p of people.people) {
        const chip = document.createElement("form");
        chip.className = "chip person-chip";
        const input = document.createElement("input");
        input.type = "text";
        input.value = p.name;
        input.style.width = Math.max(6, p.name.length + 1) + "ch";
        input.title = tr("faces.spell");
        input.autocomplete = "off";
        input.spellcheck = true;
        const count = document.createElement("span");
        count.className = "chip-count";
        count.textContent = String(p.count);
        const del = document.createElement("button");
        del.type = "button";
        del.className = "chip-x";
        del.setAttribute("aria-label", trf("ui.removeName", { name: p.name }));
        del.textContent = "×";
        const review = document.createElement("button");
        review.type = "button";
        review.textContent = tr("faces.review");
        review.title = tr("faces.reviewTitle");
        chip.addEventListener("submit", async (ev) => {
          ev.preventDefault();
          const name = input.value.trim();
          if (!name || name === p.name) return;
          input.disabled = true;
          try {
            await api(`/api/people/${p.id}`, {
              method: "PATCH",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ name }),
            });
            await Promise.all([loadFacesView(), loadFilters(), fillPeopleNames()]);
          } catch (err) {
            alert(err.message);
            input.value = p.name;
            input.disabled = false;
          }
        });
        del.addEventListener("click", async () => {
          if (!confirm(trf("ui.confirmRemoveName", { name: p.name, n: p.count }))) return;
          try {
            if (state.reviewPerson && state.reviewPerson.id === p.id) {
              state.reviewPerson = null;
            }
            await api(`/api/people/${p.id}`, { method: "DELETE" });
            await Promise.all([loadFacesView(), loadFilters(), fillPeopleNames()]);
          } catch (err) {
            alert(err.message);
          }
        });
        review.addEventListener("click", () => {
          loadPersonReview(p.id, 0).catch((err) => alert(err.message || String(err)));
        });
        chip.append(input, count, review, del);
        plist.appendChild(chip);
      }
      fillMergeSelects(people.people);
    }
    if (state.reviewPerson) {
      root.innerHTML = "";
      root.classList.add("hidden");
      await loadPersonReview(state.reviewPerson.id, state.reviewPerson.offset || 0);
      return;
    }
    root.classList.remove("hidden");
    const reviewEl = $("faceReview");
    if (reviewEl) {
      reviewEl.classList.add("hidden");
      reviewEl.innerHTML = "";
    }
    root.innerHTML = "";
    if (!clusters.clusters.length) {
      const box = document.createElement("div");
      box.className = "empty";
      const p = document.createElement("p");
      p.textContent = pending
        ? tr("faces.emptyPending")
        : clusters.unlabeled
          ? tr("faces.emptyUngrouped")
          : tr("faces.emptyNamed");
      box.appendChild(p);
      root.appendChild(box);
      return;
    }
    for (const cl of clusters.clusters) {
      const box = document.createElement("div");
      box.className = "cluster";
      const legend = document.createElement("p");
      legend.className = "cluster-legend";
      const n = cl.photos || cl.count;
      legend.textContent = trn(n, "faces.pack.one", "faces.pack.many");
      const facesEl = document.createElement("div");
      facesEl.className = "cluster-faces";
      const checks = [];
      const submit = document.createElement("button");
      submit.type = "submit";
      submit.className = "primary";
      const syncSubmit = () => {
        const picked = checks.filter((c) => c.checked).length;
        submit.disabled = picked === 0;
        submit.textContent =
          picked === 0
            ? tr("faces.nameSel")
            : trf("faces.nameSelN", { n: picked });
      };
      for (const f of cl.faces) {
        const wrap = document.createElement("div");
        wrap.className = "cluster-face-pick";
        const check = document.createElement("input");
        check.type = "checkbox";
        check.setAttribute("aria-label", tr("faces.include"));
        check.addEventListener("change", () => {
          wrap.classList.toggle("on", check.checked);
          syncSubmit();
        });
        checks.push(check);
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "cluster-face";
        btn.title = tr("ui.clickLarge");
        const img = document.createElement("img");
        img.alt = tr("faces.alt");
        img.loading = "lazy";
        img.src = `/api/faces/${f.id}/thumb`;
        btn.appendChild(img);
        btn.addEventListener("click", () => {
          const ids = [];
          const focus = {};
          for (const other of cl.faces) {
            ids.push(other.media_id);
            if (focus[other.media_id] == null) focus[other.media_id] = other.id;
          }
          focus[f.media_id] = f.id;
          openLightboxFromSeq(f.media_id, ids, focus).catch((err) => {
            alert(err.message || tr("ui.openFail"));
          });
        });
        wrap.append(check, btn);
        facesEl.appendChild(wrap);
      }
      const tools = document.createElement("div");
      tools.className = "cluster-toolbar";
      const all = document.createElement("button");
      all.type = "button";
      all.textContent = tr("ui.checkAll");
      all.addEventListener("click", () => {
        for (const c of checks) {
          c.checked = true;
          c.parentElement.classList.add("on");
        }
        syncSubmit();
      });
      const none = document.createElement("button");
      none.type = "button";
      none.textContent = tr("ui.checkNone");
      none.addEventListener("click", () => {
        for (const c of checks) {
          c.checked = false;
          c.parentElement.classList.remove("on");
        }
        syncSubmit();
      });
      tools.append(all, none);
      const form = document.createElement("form");
      const input = document.createElement("input");
      input.type = "text";
      input.required = true;
      input.placeholder = tr("ui.nameChecked");
      input.setAttribute("list", "peopleNames");
      input.autocomplete = "off";
      input.spellcheck = false;
      input.setAttribute("aria-label", tr("ui.nameChecked"));
      form.append(input, submit);
      syncSubmit();
      form.addEventListener("submit", async (ev) => {
        ev.preventDefault();
        const name = input.value.trim();
        const ids = cl.faces
          .filter((_, i) => checks[i] && checks[i].checked)
          .map((f) => f.id);
        if (!name || !ids.length) return;
        if (
          ids.length > 20 &&
          !confirm(
            trf("ui.confirmName", { n: ids.length, name: name })
          )
        ) {
          return;
        }
        submit.disabled = true;
        try {
          await api("/api/faces/name-many", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ids, name }),
          });
          await Promise.all([loadFacesView(), loadFilters(), fillPeopleNames()]);
        } catch (err) {
          alert(err.message);
          syncSubmit();
        }
      });
      box.append(legend, facesEl, tools, form);
      const hint = document.createElement("p");
      hint.className = "muted cluster-hint";
      hint.textContent = tr("faces.hint");
      box.appendChild(hint);
      if (cl.copies) {
        const note = document.createElement("p");
        note.className = "muted cluster-copies";
        note.textContent = trn(cl.copies, "faces.hidden.one", "faces.hidden.many");
        box.appendChild(note);
      }
      root.appendChild(box);
    }
  } catch (err) {
    stats.textContent = "";
    plist.innerHTML = "";
    root.innerHTML = "";
    const p = document.createElement("p");
    p.className = "muted";
    p.textContent = trf("ui.facesFail", { msg: err.message });
    root.appendChild(p);
  }
}

async function startJob(path, body) {
  if (isViewer()) return;
  try {
    await api(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    pollJob();
  } catch (err) {
    alert(err.message);
  }
}

let pollTimer = null;
async function pollJob() {
  if (isViewer()) return;
  const data = await api("/api/job");
  renderJob(data.job);
  if (data.job && (data.job.status === "running" || data.job.status === "queued" || (data.job.queued && data.job.queued.length))) {
    clearTimeout(pollTimer);
    pollTimer = setTimeout(pollJob, 700);
  } else if (data.job && data.job.status === "done") {
    await Promise.all([
      loadFilters(),
      loadHealth(),
      loadGallery(),
      loadFacesView(),
      loadScenesView(),
    ]);
    if (data.job.kind === "backup") loadBackups().catch(() => {});
    if (data.job.kind === "copies-trash") {
      state.copiesOffset = 0;
      if (state.view === "copies") await loadCopiesView();
      if (state.view === "trash") await loadTrashView();
    }
    if (data.job.kind === "trash-restore" || data.job.kind === "trash-purge") {
      state.trashSelected.clear();
      await Promise.all([loadTrashView(), loadGallery(), loadFilters(), loadHealth()]);
      const result = data.job.result || {};
      if (result.errors && result.errors.length) {
        const done = result.restored ?? result.deleted ?? 0;
        alert(trf("trash.partial", { done: done, n: result.errors.length }));
      }
    }
    if (data.job.kind === "trash-expire") {
      await Promise.all([loadTrashView(), loadHealth()]);
    }
    if (
      (data.job.kind === "cinema-scan" || data.job.kind === "cinema-enrich") &&
      window.GalerieCinema
    ) {
      window.GalerieCinema.refresh().catch(() => {});
    }
  }
}

function setView(name) {
  if (isViewer() && !["gallery", "cinema", "map", "albums", "help"].includes(name)) name = "gallery";
  state.view = name;
  const views = ["gallery", "cinema", "help", "faces", "scenes", "copies", "map", "albums", "trash", "settings"];
  for (const v of views) {
    const el = $(`view-${v}`);
    if (el) el.classList.toggle("hidden", name !== v);
  }
  const galleryChrome = $("galleryChrome");
  if (galleryChrome) galleryChrome.classList.toggle("hidden", name !== "gallery");
  $("tabGallery").classList.toggle("on", name === "gallery");
  if ($("tabCinema")) $("tabCinema").classList.toggle("on", name === "cinema");
  $("tabFaces").classList.toggle("on", name === "faces");
  if ($("tabScenes")) $("tabScenes").classList.toggle("on", name === "scenes");
  $("tabCopies").classList.toggle("on", name === "copies");
  $("tabMap").classList.toggle("on", name === "map");
  $("tabAlbums").classList.toggle("on", name === "albums");
  $("tabTrash").classList.toggle("on", name === "trash");
  $("tabSettings").classList.toggle("on", name === "settings");
  if ($("tabHelp")) $("tabHelp").classList.toggle("on", name === "help");
  if (name === "gallery") {
    loadFilters().catch((err) => {
      $("status").textContent = err.message || String(err);
    });
  }
  if (name === "cinema" && window.GalerieCinema) {
    window.scrollTo(0, 0);
    window.GalerieCinema.loadView();
  }
  if (name === "faces") {
    window.scrollTo(0, 0);
    loadFacesView();
  }
  if (name === "scenes") {
    window.scrollTo(0, 0);
    loadScenesView();
  }
  if (name === "copies") {
    window.scrollTo(0, 0);
    loadCopiesView();
  }
  if (name === "map") {
    window.scrollTo(0, 0);
    loadMapView();
  }
  if (name === "albums") {
    window.scrollTo(0, 0);
    loadAlbumsView();
  }
  if (name === "trash") {
    window.scrollTo(0, 0);
    loadTrashView();
  }
  if (name !== "settings") {
    restoreSettingsSaveButton();
    const savedNote = $("cfgMsg");
    if (savedNote) savedNote.textContent = "";
  }
  if (name === "settings") {
    loadSettings().catch((err) => {
      $("cfgMsg").textContent = err.message || String(err);
    });
    loadBackups().catch(() => {});
    loadUsers().catch(() => {});
  }
  if (name === "help") {
    window.scrollTo(0, 0);
    loadHelp();
  }
}

$("btnIndex").addEventListener("click", () => {
  const year = $("indexYear").value;
  const body = year ? { year: Number(year) } : { all: true };
  startJob("/api/index", body);
});
$("btnFaces").addEventListener("click", startFaceScan);
$("btnFacesPage").addEventListener("click", startFaceScan);
$("btnScenes").addEventListener("click", () => {
  startSceneScan($("indexYear"), $("filterPlace"));
});
$("btnScenesPage").addEventListener("click", () => {
  startSceneScan($("sceneYear"), $("scenePlace"));
});
$("sceneYear").addEventListener("change", () => {
  state.reviewScene = null;
  loadScenesView().catch((err) => alert(err.message || String(err)));
});
$("scenePlace").addEventListener("change", () => {
  state.reviewScene = null;
  loadScenesView().catch((err) => alert(err.message || String(err)));
});
$("btnLogout").addEventListener("click", async () => {
  if (pollTimer) {
    clearTimeout(pollTimer);
    pollTimer = null;
  }
  try {
    await api("/api/auth/logout", { method: "POST" });
  } catch {
    /* sans effet */
  }
  state.signedOut = true;
  wipeSessionUi();
  applyAccess(null, true);
  await showLoggedOut();
});
if ($("btnSignInAgain")) {
  $("btnSignInAgain").addEventListener("click", () => {
    if (location.search) history.replaceState({}, "", location.pathname);
    showAuthCard("login");
  });
}
if ($("btnShowForgot")) {
  $("btnShowForgot").addEventListener("click", () => {
    const msg = $("forgotMsg");
    if (msg) msg.textContent = "";
    showAuthCard("forgot");
  });
}
if ($("btnForgotBack")) {
  $("btnForgotBack").addEventListener("click", () => showAuthCard("login"));
}
if ($("btnResetBack")) {
  $("btnResetBack").addEventListener("click", () => {
    if (location.search) history.replaceState({}, "", location.pathname);
    showAuthCard("login");
  });
}
if ($("forgotForm")) {
  $("forgotForm").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const msg = $("forgotMsg");
    if (msg) msg.textContent = "";
    try {
      await api("/api/auth/forgot", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: $("forgotEmail").value.trim() }),
      });
      if (msg) msg.textContent = tr("login.sent");
    } catch (err) {
      if (msg) msg.textContent = err.message || String(err);
    }
  });
}
if ($("resetForm")) {
  $("resetForm").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const msg = $("resetMsg");
    if (msg) msg.textContent = "";
    const pass = $("resetPass").value;
    const again = $("resetPass2").value;
    if (pass !== again) {
      if (msg) msg.textContent = tr("login.mismatch");
      return;
    }
    try {
      await api("/api/auth/reset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          token: resetToken() || $("resetForm").dataset.token || "",
          password: pass,
        }),
      });
      $("resetPass").value = "";
      $("resetPass2").value = "";
      if (location.search) history.replaceState({}, "", location.pathname);
      if (msg) msg.textContent = tr("login.resetOk");
      showAuthCard("login");
      const err = $("loginErr");
      if (err) err.textContent = tr("login.resetOk");
    } catch (err) {
      if (msg) msg.textContent = err.message || String(err);
    }
  });
}
$("loginForm").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const err = $("loginErr");
  if (err) err.textContent = "";
  try {
    const data = await api("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: $("loginUser").value,
        password: $("loginPass").value,
      }),
    });
    $("loginPass").value = "";
    applyAccess(data.user, true);
    hideLoginGate();
    await Promise.all([loadFilters(), loadHealth(), loadGallery()]);
  } catch (e) {
    if (err) err.textContent = e.message || String(e);
  }
});
$("btnAddUser").addEventListener("click", async () => {
  const msg = $("usersMsg");
  if (msg) msg.textContent = "";
  const email = ($("newUserEmail") && $("newUserEmail").value.trim()) || "";
  if (!email) {
    if (msg) msg.textContent = tr("err.email_required");
    return;
  }
  try {
    const data = await api("/api/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: $("newUserName").value,
        password: $("newUserPass").value,
        role: $("newUserRole").value,
        email,
      }),
    });
    $("newUserName").value = "";
    $("newUserPass").value = "";
    if ($("newUserEmail")) $("newUserEmail").value = "";
    if (data.first) {
      applyAccess(data.user, true);
      if (msg) msg.textContent = tr("accounts.first");
    }
    await loadUsers();
  } catch (e) {
    if (msg) msg.textContent = e.message || String(e);
  }
});
$("tabGallery").addEventListener("click", () => setView("gallery"));
if ($("tabCinema")) $("tabCinema").addEventListener("click", () => setView("cinema"));
$("tabFaces").addEventListener("click", () => setView("faces"));
$("tabScenes").addEventListener("click", () => setView("scenes"));
$("tabCopies").addEventListener("click", () => setView("copies"));
$("tabMap").addEventListener("click", () => setView("map"));
$("tabAlbums").addEventListener("click", () => setView("albums"));
$("tabTrash").addEventListener("click", () => setView("trash"));
$("tabSettings").addEventListener("click", () => setView("settings"));
$("tabHelp").addEventListener("click", () => setView("help"));
let settingsSavedTimer = 0;

function settingsSaveButton() {
  const form = $("settingsForm");
  return form ? form.querySelector("button[type=submit]") : null;
}

function restoreSettingsSaveButton() {
  if (settingsSavedTimer) {
    clearTimeout(settingsSavedTimer);
    settingsSavedTimer = 0;
  }
  const btn = settingsSaveButton();
  if (!btn) return;
  btn.disabled = false;
  btn.classList.remove("is-saved");
  btn.textContent = tr("settings.saveAll");
}

function flashSettingsSaveButton() {
  const btn = settingsSaveButton();
  if (!btn) return;
  if (settingsSavedTimer) clearTimeout(settingsSavedTimer);
  btn.disabled = false;
  btn.classList.add("is-saved");
  btn.textContent = tr("settings.savedOk");
  settingsSavedTimer = window.setTimeout(() => {
    settingsSavedTimer = 0;
    btn.classList.remove("is-saved");
    btn.textContent = tr("settings.saveAll");
  }, 5000);
}

async function saveSettingsForm(opts) {
  const quiet = !!(opts && opts.quiet);
  if (!quiet) $("cfgMsg").textContent = tr("status.saveWait");
  const data = await api("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      phone_kind: phoneKindValue(),
      triage_dir: $("cfgTriage").value.trim(),
      apple_id: $("cfgAppleId").value.trim(),
      apple_password: $("cfgApplePassword").value,
      google_dir: $("cfgGoogleDir").value.trim(),
      facebook_dir: ($("cfgFacebookDir") && $("cfgFacebookDir").value.trim()) || "",
      library_src: $("cfgLibrarySrc").value.trim(),
      library_dest: $("cfgLibraryDest").value.trim(),
      backup_dir: $("cfgBackupDir").value.trim(),
      smtp_host: ($("cfgSmtpHost") && $("cfgSmtpHost").value.trim()) || "",
      smtp_port: ($("cfgSmtpPort") && $("cfgSmtpPort").value.trim()) || "587",
      smtp_user: ($("cfgSmtpUser") && $("cfgSmtpUser").value.trim()) || "",
      smtp_password: ($("cfgSmtpPassword") && $("cfgSmtpPassword").value) || "",
      smtp_from: ($("cfgSmtpFrom") && $("cfgSmtpFrom").value.trim()) || "",
      smtp_tls: $("cfgSmtpTls") && $("cfgSmtpTls").checked ? "1" : "0",
      public_url: ($("cfgPublicUrl") && $("cfgPublicUrl").value.trim()) || "",
      cinema_dir: ($("cfgCinemaDir") && $("cfgCinemaDir").value.trim()) || "",
      optical_device: ($("cfgOpticalDevice") && $("cfgOpticalDevice").value.trim()) || "",
    }),
  });
  $("cfgApplePassword").value = "";
  $("cfgPasswordHint").textContent = data.password_set
    ? tr("settings.pwEnc")
    : $("cfgPasswordHint").textContent;
  if (!quiet) {
    $("cfgMsg").textContent = data.message_code
      ? tr(data.message_code)
      : data.message || tr("status.saved");
  }
  const smtpPass = $("cfgSmtpPassword");
  if (smtpPass) smtpPass.value = "";
  return data;
}
$("settingsForm").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const btn = settingsSaveButton();
  if (btn) {
    btn.disabled = true;
    btn.classList.remove("is-saved");
    btn.textContent = tr("status.saveWait");
  }
  if ($("cfgMsg")) $("cfgMsg").textContent = "";
  try {
    const data = await saveSettingsForm({ quiet: true });
    if (data && data.restart_needed) {
      restoreSettingsSaveButton();
      $("cfgMsg").textContent = tr("settings.savedLib");
      return;
    }
    if ($("cfgMsg")) $("cfgMsg").textContent = "";
    flashSettingsSaveButton();
  } catch (err) {
    restoreSettingsSaveButton();
    $("cfgMsg").textContent = err.message || String(err);
  }
});
$("cfgPhoneIphone").addEventListener("change", applyPhoneKind);
$("cfgPhoneAndroid").addEventListener("change", applyPhoneKind);
$("cfgPhoneFacebook").addEventListener("change", applyPhoneKind);
$("btnSortDry").addEventListener("click", async () => {
  try {
    await saveSettingsForm();
    $("cfgMsg").textContent = tr("ui.simSort");
    startJob("/api/sort", { apply: false, source: "triage" });
  } catch (err) {
    $("cfgMsg").textContent = err.message || String(err);
  }
});
$("btnSortApply").addEventListener("click", async () => {
  const kind = phoneKindValue();
  const msg = kind === "android"
    ? tr("organize.confirmGoogle")
    : kind === "facebook"
      ? tr("organize.confirmFacebook")
      : tr("organize.confirmIcloud");
  if (!confirm(msg)) return;
  try {
    await saveSettingsForm();
    $("cfgMsg").textContent = phoneKindValue() === "facebook"
      ? tr("ui.sortFacebook")
      : tr("ui.sortTriage");
    startJob("/api/sort", { apply: true, source: "triage" });
  } catch (err) {
    $("cfgMsg").textContent = err.message || String(err);
  }
});
$("btnSortLibrary").addEventListener("click", async () => {
  if (
    !confirm(
      tr("organize.confirmLibrary")
    )
  ) {
    return;
  }
  try {
    await saveSettingsForm();
    $("cfgMsg").textContent = tr("ui.sortLibrary");
    startJob("/api/sort", { apply: true, source: "library" });
  } catch (err) {
    $("cfgMsg").textContent = err.message || String(err);
  }
});
$("btnSortMonthsDry").addEventListener("click", async () => {
  try {
    await saveSettingsForm();
    $("cfgMsg").textContent = tr("ui.simMonth");
    startJob("/api/sort", { apply: false, source: "year-month" });
  } catch (err) {
    $("cfgMsg").textContent = err.message || String(err);
  }
});
$("btnSortMonths").addEventListener("click", async () => {
  if (
    !confirm(
      tr("organize.confirmMonths")
    )
  ) {
    return;
  }
  try {
    await saveSettingsForm();
    $("cfgMsg").textContent = tr("ui.sortMonth");
    startJob("/api/sort", { apply: true, source: "year-month" });
  } catch (err) {
    $("cfgMsg").textContent = err.message || String(err);
  }
});

async function loadBackups() {
  const el = $("backupList");
  if (!el) return;
  const data = await api("/api/backups");
  const items = data.backups || [];
  if (!items.length) {
    el.textContent = trf("backup.none", { dir: data.backup_dir || "—" });
    return;
  }
  const summary = items
    .slice(0, 4)
    .map((b) => {
      const n = b.media_count != null ? trn(b.media_count, "backup.media.one", "backup.media.many") : "";
      return `${b.name}${n ? " · " + n : ""}`;
    })
    .join(" · ");
  el.textContent = trf("backup.latest", { keep: data.keep, summary: summary });
}

$("btnBackup").addEventListener("click", async () => {
  try {
    await saveSettingsForm();
    $("cfgMsg").textContent = tr("ui.backupRun");
    startJob("/api/backup", {});
  } catch (err) {
    $("cfgMsg").textContent = err.message || String(err);
  }
});
$("btnIcloudExec").addEventListener("click", async () => {
  const year = Number($("cfgIcloudYear").value);
  if (!year) {
    $("cfgMsg").textContent = tr("ui.needYear");
    return;
  }
  const monthRaw = $("cfgIcloudMonth").value;
  const body = {
    year,
    apple_id: $("cfgAppleId").value.trim(),
    triage_dir: $("cfgTriage").value.trim(),
  };
  if (monthRaw) body.month = Number(monthRaw);
  const pw = $("cfgApplePassword").value;
  if (pw) body.apple_password = pw;
  try {
    $("cfgMsg").textContent = tr("icloud.started");
    startJob("/api/icloud/download", body);
  } catch (err) {
    $("cfgMsg").textContent = err.message || String(err);
  }
});
$("btnMfa").addEventListener("click", async () => {
  const code = $("cfgMfaCode").value.trim();
  if (!code) return;
  $("btnMfa").disabled = true;
  try {
    await api("/api/icloud/mfa", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    });
    $("cfgMfaCode").value = "";
    $("cfgMsg").textContent = tr("ui.mfaSent");
    pollJob();
  } catch (err) {
    $("cfgMsg").textContent = err.message || String(err);
  } finally {
    $("btnMfa").disabled = false;
  }
});
$("cfgMfaCode").addEventListener("keydown", (ev) => {
  if (ev.key === "Enter") {
    ev.preventDefault();
    $("btnMfa").click();
  }
});
["filterYear", "filterMonth", "filterPlace", "filterMoment", "filterKind", "filterAlbum", "filterScene"].forEach((id) => {
  const el = $(id);
  if (!el) return;
  el.addEventListener("change", async () => {
    if (id === "filterYear") {
      if ($("filterYear").value) {
        $("indexYear").value = $("filterYear").value;
      }
      try {
        await loadPlaces();
      } catch (err) {
        $("status").textContent = String(err.message || err);
      }
    }
    state.offset = 0;
    state.selected.clear();
    state.selectAnchor = null;
    loadGallery();
  });
});
const filterPersonQ = $("filterPersonQ");
if (filterPersonQ) {
  filterPersonQ.addEventListener("change", commitPersonFilter);
  filterPersonQ.addEventListener("search", commitPersonFilter);
  filterPersonQ.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") {
      ev.preventDefault();
      commitPersonFilter();
    }
  });
}
let searchTimer = null;
function commitSearchFilter() {
  const q = $("filterQ").value.trim();
  if (!q) {
    showAllPhotosGallery();
    return;
  }
  state.offset = 0;
  state.selected.clear();
  state.selectAnchor = null;
  $("status").textContent = `Recherche « ${q} »…`;
  loadGallery();
}
$("filterQ").addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(commitSearchFilter, 280);
});
$("filterQ").addEventListener("keydown", (ev) => {
  if (ev.key === "Enter") {
    ev.preventDefault();
    clearTimeout(searchTimer);
    commitSearchFilter();
  }
});
$("filterQ").addEventListener("search", () => {
  clearTimeout(searchTimer);
  commitSearchFilter();
});
$("filterQ").addEventListener("change", () => {
  clearTimeout(searchTimer);
  commitSearchFilter();
});
$("btnPrev").addEventListener("click", () => {
  state.offset = Math.max(0, state.offset - PAGE);
  state.selectAnchor = null;
  loadGallery();
});
$("btnNext").addEventListener("click", () => {
  state.offset += PAGE;
  state.selectAnchor = null;
  loadGallery();
});
$("btnSelectPage").addEventListener("click", () => {
  if (pageFullySelected()) {
    for (const item of state.items) state.selected.delete(item.id);
  } else {
    for (const item of state.items) state.selected.add(item.id);
  }
  loadGallery();
});
$("btnSelectAll").addEventListener("click", async () => {
  const p = paramsFromFilters();
  p.set("limit", "2000");
  const data = await api("/api/media/ids?" + p.toString());
  state.selected.clear();
  for (const id of data.ids) state.selected.add(id);
  state.selectAnchor = null;
  if (data.total > data.ids.length) {
    alert(trf("ui.selectCap", { n: data.ids.length, total: data.total }));
  }
  loadGallery();
});
$("btnClearSel").addEventListener("click", () => {
  state.selected.clear();
  state.selectAnchor = null;
  loadGallery();
});
$("btnSlideshow").addEventListener("click", () => {
  if (state.selected.size >= 2) {
    state.lbSeq = [...state.selected];
    state.lbSeqKind = "sel";
  } else {
    state.lbSeq = null;
    state.lbSeqKind = null;
  }
  state.lbFocusByMedia = null;
  openLightboxAt(0, { wrap: true, fullscreen: true, play: true });
});
function exportFileName(header, fallback) {
  const star = header && /filename\*=(?:UTF-8|utf-8)''([^;]+)/.exec(header);
  let name = "";
  if (star) {
    try { name = decodeURIComponent(star[1].trim()); } catch { name = ""; }
  }
  if (!name && header) {
    const quoted = /filename="([^"]+)"/.exec(header);
    const plain = /filename=([^;]+)/.exec(header);
    name = (quoted && quoted[1]) || (plain && plain[1].trim()) || "";
  }
  name = name.split(/[\\/]/).pop().replace(/[\u0000-\u001f]/g, "").trim();
  return name || fallback;
}

async function exportFileHandle(dir, name) {
  const dot = name.lastIndexOf(".");
  const stem = dot > 0 ? name.slice(0, dot) : name;
  const ext = dot > 0 ? name.slice(dot) : "";
  let candidate = name;
  for (let n = 2; n < 10000; n += 1) {
    try {
      await dir.getFileHandle(candidate);
      candidate = `${stem}_${n}${ext}`;
    } catch (err) {
      if (err && err.name === "NotFoundError") {
        return dir.getFileHandle(candidate, { create: true });
      }
      throw err;
    }
  }
  throw new Error(name);
}

async function exportOriginalsToDirectory(dir, ids) {
  let copied = 0;
  const errors = [];
  for (const id of ids) {
    try {
      const res = await fetch(`/api/media/${id}/file`, { credentials: "same-origin" });
      if (!res.ok) throw new Error(String(res.status));
      const handle = await exportFileHandle(
        dir,
        exportFileName(res.headers.get("Content-Disposition"), `photo-${id}`)
      );
      const writable = await handle.createWritable();
      if (res.body && typeof res.body.pipeTo === "function") {
        await res.body.pipeTo(writable);
      } else {
        await writable.write(await res.blob());
        await writable.close();
      }
      copied += 1;
    } catch (err) {
      errors.push(err && err.message ? err.message : String(id));
    }
  }
  return { copied, errors };
}

function setExportBusy(busy) {
  for (const id of ["exportCopy", "exportZip"]) {
    const btn = $(id);
    if (btn) btn.disabled = busy;
  }
}

$("btnExport").addEventListener("click", () => {
  if (!state.selected.size) {
    askSelectPhotos(tr("export.need"));
    return;
  }
  $("exportCount").textContent = trn(state.selected.size, "unit.file.one", "unit.file.many");
  $("exportMsg").textContent = "";
  setExportBusy(false);
  $("exportDlg").showModal();
});
$("exportForm").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const submitter = ev.submitter;
  const value = submitter ? submitter.value : "cancel";
  if (value === "cancel") {
    $("exportDlg").close();
    return;
  }
  const ids = [...state.selected];
  if (value === "copy" && typeof window.showDirectoryPicker !== "function") {
    $("exportMsg").textContent = tr("export.needDest");
    return;
  }
  setExportBusy(true);
  try {
    if (value === "copy") {
      let dir;
      try {
        dir = await window.showDirectoryPicker({ mode: "readwrite", id: "galerie-export" });
      } catch (err) {
        if (err && err.name === "AbortError") return;
        throw err;
      }
      $("exportMsg").textContent = tr("ui.exportRun");
      const data = await exportOriginalsToDirectory(dir, ids);
      if (data.errors.length || !data.copied) {
        const fail = trn(data.errors.length || ids.length, "export.err.one", "export.err.many");
        $("exportMsg").textContent = data.copied
          ? trf("export.copied", { n: data.copied, dest: dir.name || "" }) + " · " + fail
          : fail;
        return;
      }
      $("exportDlg").close();
    } else if (value === "zip") {
      $("exportMsg").textContent = tr("ui.exportRun");
      const res = await api("/api/export/zip", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids }),
      });
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "photos.zip";
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 60000);
      $("exportDlg").close();
    }
  } catch (err) {
    $("exportMsg").textContent = err.message;
  } finally {
    setExportBusy(false);
  }
});
$("btnDelete").addEventListener("click", () => {
  if (isViewer()) return;
  openTrashDialog([...state.selected]);
});
$("deleteForm").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const value = ev.submitter ? ev.submitter.value : "cancel";
  if (value === "cancel") {
    $("deleteDlg").close();
    state.pendingDelete = null;
    state.pendingDeletePage = null;
    return;
  }
  if (value === "clear") {
    $("deleteDlg").close();
    state.pendingDelete = null;
    state.pendingDeletePage = null;
    state.selected.clear();
    state.selectAnchor = null;
    loadGallery();
    return;
  }
  const ids =
    value === "page"
      ? state.pendingDeletePage || pageSelectedIds()
      : state.pendingDelete || [...state.selected];
  if (!ids.length) {
    $("deleteMsg").textContent = tr("ui.noneDelete");
    return;
  }
  if (ids.length > 500) {
    $("deleteMsg").textContent = tr("ui.maxDelete");
    return;
  }
  $("deleteConfirm").disabled = true;
  $("deleteMsg").textContent = tr("ui.trashing");
  try {
    const data = await api("/api/media/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids }),
    });
    for (const id of data.ids || []) state.selected.delete(id);
    state.pendingDelete = null;
    state.pendingDeletePage = null;
    $("deleteDlg").close();
    await showAllPhotosGallery();
    if (data.errors && data.errors.length) {
      const n = data.trashed ?? data.deleted ?? 0;
      alert(
        trn(n, "delete.sent.one", "delete.sent.many") +
          " · " + trn(data.errors.length, "export.err.one", "export.err.many")
      );
    }
  } catch (err) {
    $("deleteMsg").textContent = err.message;
    $("deleteConfirm").disabled = false;
  }
});
$("lbClose").addEventListener("click", () => closeLightbox());
$("lbPrev").addEventListener("click", () => openLightboxAt(state.lbIndex - 1, { wrap: true }));
$("lbNext").addEventListener("click", () => openLightboxAt(state.lbIndex + 1, { wrap: true }));
$("lbPlay").addEventListener("click", () => {
  if (state.playing) pauseSlideshow();
  else startSlideshow();
});
function setCastMsg(text) {
  const el = $("castMsg");
  if (el) el.textContent = text || "";
}

function updateCastButton() {
  const label = state.castDevice ? trf("cast.linked", { name: state.castDevice.name }) : tr("action.cast");
  for (const id of ["lbCast", "btnCast"]) {
    const btn = $(id);
    if (btn) btn.textContent = label;
  }
}

function renderCastList(devices) {
  const root = $("castList");
  if (!root) return;
  root.innerHTML = "";
  if (!devices.length) {
    const p = document.createElement("p");
    p.className = "muted";
    p.textContent = tr("ui.noTv");
    root.appendChild(p);
    return;
  }
  for (const device of devices) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className =
      "cast-device" +
      (state.castDevice && state.castDevice.control_url === device.control_url
        ? " active"
        : "");
    btn.textContent = device.maker ? `${device.name} (${device.maker})` : device.name;
    btn.addEventListener("click", () => {
      state.castDevice = { control_url: device.control_url, name: device.name };
      updateCastButton();
      renderCastList(devices);
      sendToTv();
    });
    root.appendChild(btn);
  }
}

async function refreshCastDevices() {
  setCastMsg(tr("ui.castSearch"));
  const refresh = $("castRefresh");
  if (refresh) refresh.disabled = true;
  try {
    const data = await api("/api/cast/devices");
    const devices = data.devices || [];
    renderCastList(devices);
    if (!devices.length) setCastMsg(data.hint || "");
    else if (state.lbItem) setCastMsg(tr("ui.castTouch"));
    else setCastMsg(tr("ui.castOpen"));
  } catch (err) {
    setCastMsg(err.message || tr("ui.tvSearchFail"));
  }
  if (refresh) refresh.disabled = false;
}

async function sendToTv() {
  if (!state.castDevice) return;
  if (state.castCinemaItem) {
    setCastMsg(trf("ui.castPrep", { name: state.castDevice.name }));
    try {
      const data = await api("/api/cast/cinema", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          control_url: state.castDevice.control_url,
          item_id: state.castCinemaItem.id,
        }),
      });
      setCastMsg(data.note || trf("cast.on", { name: state.castDevice.name }));
    } catch (err) {
      setCastMsg(err.message || tr("ui.tvSendFail"));
    }
    return;
  }
  if (!state.lbItem) {
    setCastMsg(tr("cast.openAgain"));
    return;
  }
  const video = state.lbItem.kind === "video";
  setCastMsg(
    video
      ? trf("ui.castPrep", { name: state.castDevice.name })
      : trf("ui.castSend", { name: state.castDevice.name })
  );
  try {
    const data = await api("/api/cast/play", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        control_url: state.castDevice.control_url,
        media_id: state.lbItem.id,
      }),
    });
    setCastMsg(data.note || trf("cast.on", { name: state.castDevice.name }));
  } catch (err) {
    setCastMsg(err.message || tr("ui.tvSendFail"));
  }
}

function maybeCastCurrent() {
  if (!state.castDevice || !state.lbItem) return;
  sendToTv();
}

function openCastDialog(opts) {
  state.castCinemaItem = opts && opts.cinemaItem ? opts.cinemaItem : null;
  const dlg = $("castDlg");
  if (!dlg) return;
  const lb = $("lightbox");
  const inner = $("lbInner");
  const cinDlg = $("cinemaPlayerDlg");
  if (state.castCinemaItem && cinDlg && cinDlg.open) cinDlg.appendChild(dlg);
  else if (lb && lb.open && inner) inner.appendChild(dlg);
  else document.body.appendChild(dlg);
  if (!dlg.open) dlg.showModal();
  refreshCastDevices();
}

$("lbCast").addEventListener("click", () => openCastDialog());
$("btnCast").addEventListener("click", () => openCastDialog());
$("castRefresh").addEventListener("click", () => refreshCastDevices());
$("castStop").addEventListener("click", async () => {
  const device = state.castDevice;
  state.castDevice = null;
  updateCastButton();
  if (!device) {
    setCastMsg(tr("cast.none"));
    return;
  }
  setCastMsg(tr("cast.stop"));
  try {
    const data = await api("/api/cast/stop", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ control_url: device.control_url }),
    });
    setCastMsg(data.note || tr("cast.stopped"));
  } catch (err) {
    setCastMsg(tr("cast.gone"));
  }
});
$("lbFull").addEventListener("click", () => {
  const on = Boolean(document.fullscreenElement) || $("lightbox").classList.contains("is-full");
  if (on) exitFullscreen();
  else enterFullscreen();
});
$("lbDelay").addEventListener("change", () => {
  state.delay = Number($("lbDelay").value) || 5000;
  if (state.playing) scheduleAdvance();
});
$("lbShare").addEventListener("click", openShare);
$("shareNets").addEventListener("click", (ev) => {
  const btn = ev.target.closest("[data-share]");
  if (!btn || btn.disabled) return;
  sharePrepared(btn.getAttribute("data-share"));
});
$("shareDlg").addEventListener("close", () => {
  if (shareAbort) shareAbort.abort();
});
$("lightbox").addEventListener("mousemove", bumpChrome);
$("lightbox").addEventListener("close", () => {
  const fromFaces = state.lbSeqKind === "faces";
  const fromScenes = state.lbSeqKind === "scenes" || state.view === "scenes";
  slideGen += 1;
  stopPhotoEdit();
  pauseSlideshow();
  setPresenting(false);
  stopAdvance();
  $("lbStage").innerHTML = "";
  $("lbTags").innerHTML = "";
  state.lbItem = null;
  if ($("shareDlg") && $("shareDlg").open) $("shareDlg").close();
  state.lbSeqKind = null;
  state.lbFocusByMedia = null;
  $("lightbox").classList.remove("is-full");
  if (document.fullscreenElement) {
    document.exitFullscreen().catch(() => {});
  }
  if (fromFaces && state.view === "faces") loadFacesView();
  if (fromScenes && state.view === "scenes") loadScenesView();
});
document.addEventListener("fullscreenchange", () => {
  const lb = $("lightbox");
  const on = Boolean(document.fullscreenElement);
  if (on) {
    lb.classList.add("is-full");
    if (!lb.open && state.lbItem) lb.showModal();
    setPresenting(true);
  } else {
    lb.classList.remove("is-full");
    if (!state.playing) setPresenting(false);
  }
  bumpChrome();
  fitLightboxMedia();
});
window.addEventListener("resize", () => {
  if ($("lightbox").open) fitLightboxMedia();
});
document.addEventListener("keydown", (ev) => {
  if (!$("lightbox").open) return;
  const tag = (ev.target && ev.target.tagName) || "";
  if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
  if (photoEdit) {
    if (ev.key === "Escape") {
      ev.preventDefault();
      stopPhotoEdit(true);
    }
    return;
  }
  if (ev.key === "ArrowLeft") {
    ev.preventDefault();
    if (state.lbTotal > 1) openLightboxAt(state.lbIndex - 1, { wrap: true });
  } else if (ev.key === "ArrowRight") {
    ev.preventDefault();
    if (state.lbTotal > 1) openLightboxAt(state.lbIndex + 1, { wrap: true });
  } else if (ev.key === " ") {
    ev.preventDefault();
    if (state.playing) pauseSlideshow();
    else startSlideshow();
  } else if (ev.key === "f" || ev.key === "F") {
    ev.preventDefault();
    $("lbFull").click();
  } else if (
    !isViewer() &&
    (ev.key === "x" || ev.key === "X" || ev.key === "Backspace")
  ) {
    ev.preventDefault();
    rejectNamedFaceFromKeys();
  }
});

function rejectNamedFaceFromKeys() {
  const tags = $("lbTags");
  if (!tags) return;
  const want = state.reviewPerson && state.reviewPerson.name;
  let btn = tags.querySelector(".face-tag.focus.named .tag-reject");
  if (!btn && want) {
    for (const el of tags.querySelectorAll(".face-tag.named .tag-reject")) {
      if (el.textContent === notLabel(want)) {
        btn = el;
        break;
      }
    }
  }
  if (!btn) btn = tags.querySelector(".face-tag.named .tag-reject");
  if (btn) btn.click();
}

function isPhone() {
  const touch = window.matchMedia("(pointer: coarse)").matches || navigator.maxTouchPoints > 0;
  const shortSide = Math.min(window.screen.width || 0, window.screen.height || 0);
  return touch && shortSide > 0 && shortSide <= 520;
}

function isNarrow() {
  return window.matchMedia("(max-width: 720px)").matches || isPhone();
}

function syncLayoutMode() {
  const narrow = isNarrow();
  document.documentElement.classList.toggle("is-narrow", narrow);
  document.documentElement.classList.toggle("is-phone", isPhone());
  document.documentElement.classList.toggle(
    "is-touch",
    window.matchMedia("(pointer: coarse)").matches
  );
  const filters = $("filtersPanel");
  const tools = $("toolsPanel");
  if (!narrow) {
    filters.classList.remove("is-collapsed");
    tools.classList.remove("is-collapsed");
  }
  $("btnFiltersToggle").setAttribute("aria-expanded", String(!filters.classList.contains("is-collapsed")));
  $("btnToolsToggle").setAttribute("aria-expanded", String(!tools.classList.contains("is-collapsed")));
}

$("btnFiltersToggle").addEventListener("click", () => {
  $("filtersPanel").classList.toggle("is-collapsed");
  syncLayoutMode();
});
$("btnToolsToggle").addEventListener("click", () => {
  $("toolsPanel").classList.toggle("is-collapsed");
  syncLayoutMode();
});
window.matchMedia("(max-width: 720px)").addEventListener("change", () => {
  if (isNarrow()) {
    $("filtersPanel").classList.add("is-collapsed");
    $("toolsPanel").classList.add("is-collapsed");
  }
  syncLayoutMode();
});
window.addEventListener("orientationchange", () => {
  if (isPhone()) {
    $("filtersPanel").classList.add("is-collapsed");
    $("toolsPanel").classList.add("is-collapsed");
  }
  syncLayoutMode();
});

function openTrashDialog(ids) {
  if (!ids.length) {
    askSelectPhotos(tr("delete.need"));
    return;
  }
  const pageIds = pageSelectedIds();
  const offPage = ids.length - pageIds.length;
  const tooBig = ids.length > 500;
  const pageBtn = $("deletePageOnly");
  const clearBtn = $("deleteClearSel");
  const confirmBtn = $("deleteConfirm");
  state.pendingDeletePage = pageIds;
  if (tooBig) {
    state.pendingDelete = null;
    $("deleteQuestion").textContent =
      trf("delete.checked", { n: fmtN(ids.length) }) +
      (offPage > 0
        ? trf("delete.off", { page: fmtN(pageIds.length), off: fmtN(offPage) })
        : ".") +
      tr("delete.cap");
    $("deleteHint").textContent = tr("delete.hintFew");
  } else {
    state.pendingDelete = ids;
    const n = ids.length;
    $("deleteQuestion").textContent =
      n === 1
        ? tr("delete.sureOne")
        : trf("delete.sureMany", { n: fmtN(n) }) +
          (offPage > 0 ? trf("delete.offShort", { page: fmtN(pageIds.length), off: fmtN(offPage) }) : "") +
          " ?";
    $("deleteHint").textContent = tr("delete.trashNote");
  }
  if (pageBtn) {
    const showPage = tooBig && pageIds.length > 0 && pageIds.length <= 500;
    pageBtn.classList.toggle("hidden", !showPage);
    pageBtn.textContent = trf("delete.pageOnly", { n: fmtN(pageIds.length) });
  }
  if (clearBtn) clearBtn.classList.toggle("hidden", !tooBig && offPage <= 0);
  if (confirmBtn) {
    confirmBtn.classList.toggle("hidden", tooBig);
    confirmBtn.disabled = tooBig;
  }
  $("deleteMsg").textContent = "";
  $("deleteDlg").showModal();
}

function fillMergeSelects(people) {
  const absorb = $("mergeAbsorb");
  const keep = $("mergeKeep");
  const box = $("mergeBox");
  if (!absorb || !keep) return;
  const items = people || [];
  box.classList.toggle("hidden", items.length < 2);
  fillSelect(absorb, items.map((p) => ({ value: String(p.id), label: p.name })));
  fillSelect(keep, items.map((p) => ({ value: String(p.id), label: p.name })));
  if (items.length >= 2) {
    absorb.value = String(items[0].id);
    keep.value = String(items[1].id);
  }
}

async function openPlaceInGallery(place) {
  state.offset = 0;
  state.selected.clear();
  state.selectAnchor = null;
  clearGalleryFilters();
  setView("gallery");
  try {
    await loadPlaces();
  } catch (err) {
    $("status").textContent = String(err.message || err);
  }
  const sel = $("filterPlace");
  if (place && ![...sel.options].some((o) => o.value === place)) {
    const opt = document.createElement("option");
    opt.value = place;
    opt.textContent = place;
    sel.appendChild(opt);
  }
  sel.value = place || "";
  loadGallery();
}

async function loadCopiesView() {
  const root = $("copiesList");
  const stats = $("copiesStats");
  try {
    const data = await api(
      `/api/media/copies?limit=${COPIES_PAGE}&offset=${state.copiesOffset}`
    );
    state.copiesTotal = data.group_count || 0;
    state.copiesExtra = data.extra_count || 0;
    stats.textContent =
      trn(data.group_count, "copies.series.one", "copies.series.many") +
      " · " + trn(data.extra_count || 0, "copies.extra.one", "copies.extra.many");
    const allBtn = $("btnCopiesTrashAll");
    if (allBtn) {
      allBtn.disabled = !state.copiesExtra;
      allBtn.textContent = state.copiesExtra
        ? trf("copies.trashN", { n: state.copiesExtra })
        : tr("ui.noExtra");
    }
    root.innerHTML = "";
    if (!data.groups.length) {
      const p = document.createElement("p");
      p.className = "muted";
      p.style.padding = "0 20px";
      p.textContent = state.copiesOffset
        ? tr("copies.more")
        : tr("copies.noneFound");
      root.appendChild(p);
    }
    for (const grp of data.groups) {
      const box = document.createElement("div");
      box.className = "copy-group";
      const title = document.createElement("h3");
      title.textContent = tr("copies.group").replaceAll("{n}", String(grp.count));
      const row = document.createElement("div");
      row.className = "copy-row";
      for (const item of grp.items) {
        const cell = document.createElement("div");
        cell.className = "copy-item" + (item.keep ? " keep" : "");
        const img = document.createElement("img");
        img.alt = item.name;
        img.src = mediaThumbUrl(item);
        img.addEventListener("click", () => {
          openLightboxFromSeq(item.id, grp.items.map((x) => x.id), null, "copies");
        });
        const lab = document.createElement("label");
        const cb = document.createElement("input");
        cb.type = "checkbox";
        cb.className = "copy-cb";
        cb.dataset.id = String(item.id);
        cb.checked = !item.keep;
        const cap = document.createElement("span");
        cap.className = "name";
        cap.textContent =
          (item.keep ? tr("copies.keep") : "") +
          (item.screenshot ? tr("copies.shot") : "") +
          item.name;
        lab.append(cb, cap);
        cell.append(img, lab);
        row.appendChild(cell);
      }
      box.append(title, row);
      root.appendChild(box);
    }
    const page = Math.floor(state.copiesOffset / COPIES_PAGE) + 1;
    const pages = Math.max(1, Math.ceil(state.copiesTotal / COPIES_PAGE));
    $("copiesPage").textContent = tr("pager.page").replace("{page}", String(page)).replace("{pages}", String(pages));
    $("btnCopiesPrev").disabled = state.copiesOffset <= 0;
    $("btnCopiesNext").disabled = state.copiesOffset + COPIES_PAGE >= state.copiesTotal;
  } catch (err) {
    stats.textContent = "";
    root.textContent = trf("ui.copiesFail", { msg: err.message });
  }
}

let mapObj = null;
let mapPins = null;

async function loadMapView() {
  const stats = $("mapStats");
  const unknown = $("mapUnknown");
  try {
    const data = await api("/api/map");
    stats.textContent =
      trn(data.pin_count, "map.places.one", "map.places.many") +
      " · " + trn(data.photo_count, "map.photos.one", "map.photos.many") +
      (data.unknown_count
        ? " · " + trn(data.unknown_count, "map.folders.one", "map.folders.many")
        : "");
    if (typeof L === "undefined") {
      stats.textContent += tr("map.missing");
      return;
    }
    if (!mapObj) {
      mapObj = L.map("mapCanvas", { worldCopyJump: true }).setView([25, 0], 2);
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 18,
      }).addTo(mapObj);
    }
    if (mapPins) mapPins.clearLayers();
    mapPins = L.layerGroup().addTo(mapObj);
    const bounds = [];
    for (const pin of data.pins || []) {
      const r = Math.min(16, 6 + Math.log10((pin.count || 1) + 1) * 4);
      const marker = L.circleMarker([pin.lat, pin.lon], {
        radius: r,
        color: "#e8d3b0",
        weight: 1,
        fillColor: "#c4a574",
        fillOpacity: 0.85,
      });
      const years =
        pin.year_min && pin.year_max && pin.year_min !== pin.year_max
          ? `${pin.year_min}–${pin.year_max}`
          : pin.year_min || "";
          const tip = document.createElement("span");
          setFlagText(
            tip,
            placeLabel(pin.place) + " · " + trn(pin.count, "map.media.one", "map.media.many") +
              (years ? " · " + years : "")
          );
          marker.bindTooltip(tip.innerHTML);
          marker.on("click", () =>
            openPlaceInGallery(pin.filter_place || pin.place)
          );
      marker.addTo(mapPins);
      bounds.push([pin.lat, pin.lon]);
    }
    setTimeout(() => {
      mapObj.invalidateSize();
      if (bounds.length === 1) mapObj.setView(bounds[0], 6);
      else if (bounds.length > 1) mapObj.fitBounds(bounds, { padding: [28, 28], maxZoom: 6 });
    }, 80);
    unknown.innerHTML = "";
    for (const u of data.unknown || []) {
      const b = document.createElement("button");
      b.type = "button";
      setFlagText(b, `${placeLabel(u.place)} (${u.count})`);
      if (placeLabel(u.place) !== u.place) b.title = u.place;
      b.addEventListener("click", () => openPlaceInGallery(u.place));
      unknown.appendChild(b);
    }
  } catch (err) {
    stats.textContent = trf("ui.mapFail", { msg: err.message });
  }
}

let placePickMap = null;
let placeSearchTimer = 0;
let placeMoveTimer = 0;
const placePick = {
  lat: null,
  lon: null,
  cc: "",
  manual: false,
  filling: false,
  programmatic: false,
};

function highlightPlaceHit(btn) {
  const box = $("placePickHits");
  if (!box) return;
  for (const el of box.querySelectorAll("button")) el.classList.toggle("on", el === btn);
}

function refreshPlacePickMap() {
  if (!placePickMap) return;
  placePickMap.invalidateSize();
  if (placePickMap.dragging && placePickMap.dragging.enable) placePickMap.dragging.enable();
}

function syncPlaceFromMap() {
  if (!placePickMap) return;
  const c = placePickMap.getCenter();
  placePick.lat = c.lat;
  placePick.lon = c.lng;
}

function ensurePlacePickMap() {
  const canvas = $("placePickMap");
  if (!canvas) return;
  if (typeof L === "undefined") {
    canvas.classList.add("hidden");
    return;
  }
  canvas.classList.remove("hidden");
  if (placePickMap) {
    setTimeout(refreshPlacePickMap, 40);
    return;
  }
  placePickMap = L.map(canvas, {
    worldCopyJump: true,
    dragging: true,
    tap: false,
    scrollWheelZoom: true,
    doubleClickZoom: true,
    boxZoom: false,
    keyboard: true,
  }).setView([25, 0], 2);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 18,
  }).addTo(placePickMap);
  L.DomEvent.disableScrollPropagation(canvas);
  placePickMap.on("click", (ev) => {
    placePick.manual = true;
    setPlacePick(ev.latlng.lat, ev.latlng.lng, placePick.cc, false);
    reversePlacePick(ev.latlng.lat, ev.latlng.lng, true);
  });
  placePickMap.on("dragstart", () => {
    if (!placePick.programmatic) placePick.manual = true;
  });
  placePickMap.on("moveend", () => {
    syncPlaceFromMap();
    if (placePick.programmatic || !placePick.manual) return;
    const c = placePickMap.getCenter();
    clearTimeout(placeMoveTimer);
    placeMoveTimer = setTimeout(() => reversePlacePick(c.lat, c.lng, true), 200);
  });
}

function setPlacePick(lat, lon, cc, fly) {
  placePick.lat = lat;
  placePick.lon = lon;
  placePick.cc = cc || "";
  if (typeof L === "undefined") return;
  ensurePlacePickMap();
  if (!placePickMap) return;
  placePick.programmatic = true;
  const here = [lat, lon];
  if (fly !== false) placePickMap.setView(here, Math.max(placePickMap.getZoom() || 0, 5));
  else placePickMap.setView(here, placePickMap.getZoom() || 5, { animate: false });
  refreshPlacePickMap();
  setTimeout(() => {
    placePick.programmatic = false;
    syncPlaceFromMap();
  }, 350);
}

function applyReverseName(data) {
  const input = $("placeNew");
  const hint = $("placePickHint");
  const label = (data && (data.label || "").trim()) || "";
  if (hint) setFlagText(hint, placeLabel((data && data.display) || label || ""));
  if (!input || !label) return;
  placePick.filling = true;
  input.value = label;
  placePick.filling = false;
}

async function reversePlacePick(lat, lon, rename) {
  placePick.lat = lat;
  placePick.lon = lon;
  try {
    const data = await api(
      `/api/geo/reverse?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}`
    );
    if (data && data.lat != null) {
      placePick.cc = data.cc || "";
      if (rename) applyReverseName(data);
      else if (data.display) setFlagText($("placePickHint"), placeLabel(data.display));
    }
  } catch (_) {
    /* le centre de la carte reste la position enregistrée */
  }
}

async function searchPlacePick(q) {
  const box = $("placePickHits");
  const hint = $("placePickHint");
  if (!box) return null;
  const query = String(q || "").trim();
  if (query.length < 2) {
    box.innerHTML = "";
    return null;
  }
  try {
    const data = await api(`/api/geo/search?q=${encodeURIComponent(query)}`);
    box.innerHTML = "";
    const matches = data.matches || [];
    if (!matches.length) {
      if (hint) hint.textContent = tr("ui.noPlace");
      return null;
    }
    for (const m of matches) {
      const b = document.createElement("button");
      b.type = "button";
      setFlagText(b, placeLabel(m.display || m.label));
      b.title = m.display || m.label || "";
      b.addEventListener("click", () => {
        placePick.manual = true;
        if (m.label) {
          placePick.filling = true;
          $("placeNew").value = m.label;
          placePick.filling = false;
        }
        setPlacePick(m.lat, m.lon, m.cc);
        if (hint) setFlagText(hint, placeLabel(m.display || ""));
        highlightPlaceHit(b);
      });
      box.appendChild(b);
    }
    if (!placePick.manual && matches[0] && Number.isFinite(matches[0].lat)) {
      const m = matches[0];
      setPlacePick(m.lat, m.lon, m.cc);
      if (hint) setFlagText(hint, placeLabel(m.display || ""));
      highlightPlaceHit(box.firstChild);
      return m;
    }
    return matches[0];
  } catch (err) {
    if ($("placeDlgMsg")) $("placeDlgMsg").textContent = err.message;
    return null;
  }
}

async function loadAlbumsView() {
  const grid = $("albumGrid");
  const msg = $("albumMsg");
  try {
    const data = await api("/api/albums");
    state.albums = data.albums || [];
    if (!state.albums.length) {
      grid.innerHTML = "";
      msg.textContent = isViewer()
        ? tr("album.noneNow")
        : tr("album.noneCreate");
      return;
    }
    msg.textContent = trn(state.albums.length, "album.count.one", "album.count.many");
    grid.innerHTML = "";
    for (const a of state.albums) {
      const card = document.createElement("div");
      card.className = "album-card";
      if (a.cover_id) {
        const img = document.createElement("img");
        img.alt = a.name;
        img.src = mediaThumbUrl({ id: a.cover_id });
        card.appendChild(img);
      }
      const meta = document.createElement("div");
      meta.className = "meta";
      const h = document.createElement("h3");
      h.textContent = a.name;
      const p = document.createElement("p");
      p.className = "muted";
      p.textContent = trn(a.count, "album.photos.one", "album.photos.many");
      const del = document.createElement("button");
      del.type = "button";
      del.className = "album-del admin-only";
      del.textContent = tr("ui.deleteAlbum");
      del.addEventListener("click", async (ev) => {
        ev.stopPropagation();
        if (!confirm(trf("ui.confirmDeleteAlbum", { name: a.name }))) return;
        try {
          await api(`/api/albums/${a.id}`, { method: "DELETE" });
          await Promise.all([loadAlbumsView(), loadFilters()]);
        } catch (err) {
          alert(err.message);
        }
      });
      meta.append(h, p, del);
      card.appendChild(meta);
      card.addEventListener("click", () => {
        $("filterAlbum").value = String(a.id);
        state.offset = 0;
        state.selected.clear();
        state.selectAnchor = null;
        setView("gallery");
        loadGallery();
      });
      grid.appendChild(card);
    }
  } catch (err) {
    msg.textContent = err.message;
  }
}

function trashPageFullySelected() {
  const items = state.trashItems || [];
  return items.length > 0 && items.every((item) => state.trashSelected.has(item.id));
}

function trashActionBody() {
  const ids = [...state.trashSelected];
  if (state.trashTotal && ids.length === state.trashTotal) {
    return { all: true };
  }
  return { ids };
}

function syncTrashChrome(busy) {
  const n = state.trashSelected.size;
  const restore = $("btnTrashRestore");
  const purge = $("btnTrashPurge");
  const pageBtn = $("btnTrashPage");
  const allBtn = $("btnTrashAll");
  const clearBtn = $("btnTrashClear");
  const locked = Boolean(busy);
  if (restore) {
    restore.disabled = locked || n === 0;
    restore.textContent = n ? trf("trash.restoreN", { n: fmtN(n) }) : tr("trash.restore");
  }
  if (purge) {
    purge.disabled = locked || n === 0;
    purge.textContent = n ? trf("trash.purgeN", { n: fmtN(n) }) : tr("trash.purge");
  }
  if (pageBtn) {
    const allPage = trashPageFullySelected();
    pageBtn.disabled = locked || !(state.trashItems || []).length;
    pageBtn.textContent = allPage ? tr("trash.pageOn") : tr("action.page");
    pageBtn.classList.toggle("on", allPage);
    pageBtn.setAttribute("aria-pressed", String(allPage));
  }
  if (allBtn) allBtn.disabled = locked || !state.trashTotal;
  if (clearBtn) clearBtn.disabled = locked || n === 0;
  const prev = $("btnTrashPrev");
  const next = $("btnTrashNext");
  if (prev) prev.disabled = locked || state.trashOffset <= 0;
  if (next) next.disabled = locked || state.trashOffset + PAGE >= state.trashTotal;
}

function updateTrashCountLabel(data) {
  const el = $("trashCount");
  if (!el) return;
  const total = state.trashTotal;
  const onPage = (state.trashItems || []).length;
  const n = state.trashSelected.size;
  const page = Math.max(1, Math.floor(state.trashOffset / PAGE) + 1);
  const pages = Math.max(1, Math.ceil((total || 0) / PAGE) || 1);
  el.replaceChildren();
  const add = (label, value, cls) => {
    const item = document.createElement("span");
    item.className = "count-item" + (cls ? " " + cls : "");
    const k = document.createElement("em");
    k.textContent = label;
    const v = document.createElement("strong");
    v.textContent = value;
    item.append(k, v);
    el.appendChild(item);
  };
  add(tr("nav.trash"), trn(total, "trash.files.one", "trash.files.many"));
  add(tr("action.page"), tr("count.pageLine").replace("{n}", fmtN(onPage)).replace("{page}", String(page)).replace("{pages}", String(pages)));
  add(tr("trash.checked"), n ? fmtN(n) : tr("count.none"), n > onPage ? "count-warn" : "");
  if (data && data.keep_days) {
    add(tr("trash.keep"), trf("trash.days", { n: data.keep_days }));
  }
  if (data && data.purged) {
    add(tr("trash.expired"), fmtN(data.purged));
  }
  if (data && data.expiring) {
    add(tr("trash.over"), trf("trash.expiring", { n: fmtN(data.expiring) }));
  }
}

async function loadTrashView() {
  if (window.GalerieCinema && window.GalerieCinema.loadTrash) {
    window.GalerieCinema.loadTrash().catch(() => {});
  }
  const grid = $("trashGrid");
  const count = $("trashCount");
  try {
    const data = await api(`/api/trash?offset=${state.trashOffset}&limit=${PAGE}`);
    const items = data.items || [];
    state.trashItems = items;
    state.trashTotal = data.count || 0;
    if (state.trashTotal && state.trashOffset >= state.trashTotal) {
      state.trashOffset = Math.max(0, Math.floor((state.trashTotal - 1) / PAGE) * PAGE);
      return loadTrashView();
    }
    updateTrashCountLabel(data);
    grid.innerHTML = "";
    const pageEl = $("trashPageInfo");
    const pages = Math.max(1, Math.ceil((state.trashTotal || 0) / PAGE) || 1);
    const page = Math.floor(state.trashOffset / PAGE) + 1;
    if (pageEl) pageEl.textContent = tr("pager.page").replace("{page}", String(page)).replace("{pages}", String(pages));
    if (!state.trashTotal) {
      const p = document.createElement("p");
      p.className = "muted";
      p.style.padding = "0 20px";
      p.textContent = tr("ui.trashEmpty");
      grid.appendChild(p);
      syncTrashChrome();
      return;
    }
    for (const item of items) {
      const card = document.createElement("div");
      card.className = "card" + (state.trashSelected.has(item.id) ? " sel" : "");
      const img = document.createElement("img");
      img.loading = "lazy";
      img.alt = item.name;
      img.src = mediaThumbUrl(item);
      const badge = document.createElement("span");
      badge.className = "badge";
      badge.textContent =
        item.reason === "edit"
          ? tr("trash.before")
          : (item.trashed_at || "").slice(0, 10);
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.dataset.reason = item.reason || "deleted";
      cb.checked = state.trashSelected.has(item.id);
      cb.setAttribute("aria-label", trf("ui.checkAria", { name: item.name }));
      cb.title = tr("trash.checkTitle");
      const mark = (on) => {
        if (on) state.trashSelected.add(item.id);
        else state.trashSelected.delete(item.id);
        cb.checked = on;
        card.classList.toggle("sel", on);
        updateTrashCountLabel(data);
        syncTrashChrome();
      };
      cb.addEventListener("click", (ev) => {
        ev.stopPropagation();
        mark(cb.checked);
      });
      card.append(img, badge, cb);
      card.addEventListener("click", () => mark(!cb.checked));
      grid.appendChild(card);
    }
    syncTrashChrome();
  } catch (err) {
    count.textContent = err.message;
  }
}

$("btnCopiesPrev").addEventListener("click", () => {
  state.copiesOffset = Math.max(0, state.copiesOffset - COPIES_PAGE);
  loadCopiesView();
});
$("btnCopiesNext").addEventListener("click", () => {
  state.copiesOffset += COPIES_PAGE;
  loadCopiesView();
});
$("btnCopiesTrash").addEventListener("click", () => {
  const ids = [...document.querySelectorAll("#copiesList .copy-cb:checked")].map((el) =>
    Number(el.dataset.id)
  );
  openTrashDialog(ids);
});
$("btnCopiesTrashAll").addEventListener("click", () => {
  const n = state.copiesExtra || 0;
  if (!n) {
    alert(tr("ui.noExtra"));
    return;
  }
  const ok = confirm(
    trf("copies.confirm", { n: n })
  );
  if (!ok) return;
  $("btnCopiesTrashAll").disabled = true;
  startJob("/api/media/copies/trash-extras", { confirm: true });
});
$("albumCreate").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const name = $("albumName").value.trim();
  if (!name) return;
  try {
    await api("/api/albums", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    $("albumName").value = "";
    await Promise.all([loadAlbumsView(), loadFilters()]);
  } catch (err) {
    $("albumMsg").textContent = err.message;
  }
});
function sharedAlbumIds(ids) {
  const items = ids
    .map((id) => state.items.find((it) => it.id === id))
    .filter(Boolean);
  if (!items.length) return [];
  let set = new Set(items[0].album_ids || []);
  for (const it of items.slice(1)) {
    const other = new Set(it.album_ids || []);
    set = new Set([...set].filter((x) => other.has(x)));
  }
  return [...set];
}

function dropSelectedIds(ids) {
  for (const id of ids) state.selected.delete(id);
  if (!state.selected.size) state.selectAnchor = null;
}

async function openAlbumDialog({ ids, replace, currentIds, intent }) {
  state.pendingAlbum = { ids, replace: Boolean(replace) };
  const title = $("albumDlgTitle");
  const confirmBtn = $("albumConfirm");
  const empty = $("albumDlgEmpty");
  const pickLabel = $("albumPickLabel");
  const hint = $("albumPickHint");
  const removing = intent === "remove";
  if (title) {
    title.textContent = removing
      ? tr("album.removeTitle")
      : replace
        ? tr("album.thisPhoto")
        : tr("album.selection");
  }
  if (confirmBtn) confirmBtn.textContent = replace ? tr("action.save") : tr("action.add");
  const removeBtn = $("albumRemove");
  $("albumDlgCount").textContent = replace
    ? tr("album.exact")
    : removing
      ? trn(ids.length, "album.fileRemove.one", "album.fileRemove.many")
      : trn(ids.length, "album.fileAdd.one", "album.fileAdd.many");
  $("albumDlgMsg").textContent = "";
  $("albumNew").value = "";
  let albums = [];
  try {
    const data = await api("/api/albums");
    albums = data.albums || [];
    state.albums = albums;
  } catch (err) {
    $("albumDlgMsg").textContent = err.message;
  }
  const none = albums.length === 0;
  if (empty) empty.classList.toggle("hidden", !none);
  if (pickLabel) pickLabel.classList.toggle("hidden", none);
  if (hint) hint.classList.toggle("hidden", none);
  if (removeBtn) removeBtn.classList.toggle("hidden", none);
  fillSelect(
    $("albumPick"),
    albums.map((a) => ({ value: String(a.id), label: a.name })),
    [],
    replace || removing ? currentIds || [] : []
  );
  $("albumDlg").showModal();
  if (none) $("albumNew").focus();
  else if (removing && removeBtn) removeBtn.focus();
}

function askSelectPhotos(msg, title) {
  const heading = $("needSelTitle");
  if (heading) heading.textContent = title || tr("album.needTitle");
  $("needSelText").textContent = msg;
  $("needSelDlg").showModal();
}

$("btnAlbum").addEventListener("click", () => {
  if (!state.selected.size) return;
  openAlbumDialog({ ids: [...state.selected], replace: false, currentIds: [] });
});
$("btnAlbumRemove").addEventListener("click", async () => {
  if (!state.selected.size) return;
  const albumId = Number($("filterAlbum") && $("filterAlbum").value);
  if (Number.isFinite(albumId) && albumId > 0) {
    const album = (state.albums || []).find((a) => Number(a.id) === albumId);
    const name = album ? album.name : tr("album.this");
    const ids = [...state.selected];
    const n = ids.length;
    if (
      !confirm(
        trf("ui.removePhotos", { n: fmtN(n), name: name })
      )
    ) {
      return;
    }
    try {
      const data = await api("/api/albums/remove", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids, album_ids: [albumId] }),
      });
      dropSelectedIds(ids);
      await Promise.all([loadFilters(), loadGallery()]);
      if (state.view === "albums") await loadAlbumsView();
      const r = data.removed || 0;
      updateCountLabel(` · ${r} retrait${r > 1 ? "s" : ""}`);
    } catch (err) {
      askSelectPhotos(String(err.message || err), tr("ui.removeAlbum"));
    }
    return;
  }
  openAlbumDialog({
    ids: [...state.selected],
    replace: false,
    currentIds: sharedAlbumIds([...state.selected]),
    intent: "remove",
  });
});
function renderMoveFolders(filter) {
  const select = $("moveDest");
  if (!select) return;
  const needle = (filter || "").trim().toLocaleLowerCase("fr");
  const current = select.value;
  select.innerHTML = "";
  const folders = (state.moveFolders || []).filter((folder) => {
    if (!needle) return true;
    return String(folder.label || "").toLocaleLowerCase("fr").includes(needle);
  });
  for (const folder of folders) {
    const opt = document.createElement("option");
    opt.value = folder.path;
    opt.textContent = folder.label;
    select.appendChild(opt);
  }
  if ([...select.options].some((opt) => opt.value === current)) select.value = current;
  else if (select.options.length) select.selectedIndex = 0;
  const confirm = $("moveConfirm");
  if (confirm) confirm.disabled = !select.value;
}

async function openMoveDialog() {
  if (isViewer()) return;
  const ids = [...state.selected];
  if (!ids.length) {
    askSelectPhotos(tr("move.need"));
    return;
  }
  if (ids.length > 500) {
    $("status").textContent = tr("ui.maxDelete");
    return;
  }
  $("moveCount").textContent = trn(ids.length, "unit.photo.one", "unit.photo.many");
  $("moveMsg").textContent = tr("ui.loadingFolders");
  $("moveFilter").value = "";
  $("moveDest").innerHTML = "";
  $("moveConfirm").disabled = true;
  state.moveFolders = [];
  $("moveDlg").showModal();
  try {
    const data = await api("/api/media/move-targets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids }),
    });
    state.moveFolders = data.folders || [];
    $("moveCount").textContent = trf("move.withYear", {
      count: trn(ids.length, "unit.photo.one", "unit.photo.many"),
      year: data.year_dir || data.year || "",
    });
    renderMoveFolders("");
    if (!state.moveFolders.length) {
      $("moveMsg").textContent = tr("ui.noYearFolder");
    } else {
      $("moveMsg").textContent = "";
      $("moveFilter").focus();
    }
  } catch (err) {
    $("moveMsg").textContent = err.message;
  }
}

$("btnMove").addEventListener("click", () => {
  openMoveDialog();
});
$("moveFilter").addEventListener("input", () => {
  renderMoveFolders($("moveFilter").value);
});
$("moveFilter").addEventListener("keydown", (ev) => {
  if (ev.key === "Enter") ev.preventDefault();
});
$("moveCancel").addEventListener("click", () => {
  $("moveDlg").close();
});
$("moveForm").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const value = ev.submitter ? ev.submitter.value : "cancel";
  if (value !== "move") {
    $("moveDlg").close();
    return;
  }
  const dest = $("moveDest").value;
  const ids = [...state.selected];
  if (!dest || !ids.length) {
    $("moveMsg").textContent = tr("ui.pickFolder");
    return;
  }
  const label = $("moveDest").selectedOptions[0]
    ? $("moveDest").selectedOptions[0].textContent
    : dest;
  $("moveConfirm").disabled = true;
  $("moveMsg").textContent = tr("ui.moving");
  try {
    const data = await api("/api/media/move", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids, dest }),
    });
    for (const id of data.ids || []) state.selected.delete(id);
    $("moveDlg").close();
    const bits = [trn(data.moved, "move.done.one", "move.done.many", { dest: data.dest_label || label })];
    if (data.skipped) bits.push(trf("move.skipped", { n: data.skipped }));
    if (data.renamed) bits.push(tr("move.renamed"));
    $("status").textContent = bits.join(" · ");
    try {
      await loadFilters();
    } catch (err) {
      $("status").textContent = String(err.message || err);
    }
    await loadGallery();
    if (data.errors && data.errors.length) {
      alert(
        trn(data.moved, "move.short.one", "move.short.many") +
          " · " + trn(data.errors.length, "export.err.one", "export.err.many")
      );
    }
  } catch (err) {
    $("moveMsg").textContent = err.message;
    $("moveConfirm").disabled = !$("moveDest").value;
  }
});
$("btnPlace").addEventListener("click", () => {
  if (!state.selected.size) {
    askSelectPhotos(tr("place.need"));
    return;
  }
  const picked = state.items.filter((it) => state.selected.has(it.id));
  const places = [...new Set(picked.map((it) => it.place).filter(Boolean))];
  const dirs = [
    ...new Set(
      picked
        .map((it) => {
          const parts = String(it.relpath || "")
            .replace(/\\/g, "/")
            .split("/")
            .filter(Boolean);
          return parts.length > 1 ? parts.slice(0, -1).join("/") : "";
        })
        .filter(Boolean)
    ),
  ];
  const folderNote =
    dirs.length === 1
      ? trf("place.folder", { name: dirs[0] })
      : dirs.length > 1
        ? trf("place.folders", { n: dirs.length })
        : "";
  setFlagText(
    $("placeDlgCount"),
    trn(state.selected.size, "unit.photo.one", "unit.photo.many") +
      (places.length === 1 ? trf("place.current", { name: placeLabel(places[0]) }) : "") +
      folderNote
  );
  $("placeNew").value = places.length === 1 ? places[0] : "";
  $("placeFolder").checked = false;
  $("placeDlgMsg").textContent = "";
  $("placePickHint").textContent = tr("place.drag");
  $("placePickHits").innerHTML = "";
  placePick.lat = null;
  placePick.lon = null;
  placePick.cc = "";
  placePick.manual = false;
  placePick.filling = false;
  placePick.programmatic = false;
  $("placeDlg").showModal();
  ensurePlacePickMap();
  searchPlacePick($("placeNew").value);
  setTimeout(refreshPlacePickMap, 80);
  setTimeout(refreshPlacePickMap, 250);
  $("placeNew").focus();
});
$("placeNew").addEventListener("input", () => {
  if (placePick.filling) return;
  placePick.manual = false;
  clearTimeout(placeSearchTimer);
  placeSearchTimer = setTimeout(() => searchPlacePick($("placeNew").value), 280);
});
$("placeForm").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const value = ev.submitter ? ev.submitter.value : "cancel";
  if (value !== "save") {
    $("placeDlg").close();
    return;
  }
  const ids = [...state.selected];
  $("placeDlgMsg").textContent = tr("ui.saving");
  try {
    clearTimeout(placeSearchTimer);
    if (!placePick.manual) {
      await searchPlacePick($("placeNew").value.trim());
    }
    const body = {
      ids,
      place: $("placeNew").value.trim(),
      apply_folder: $("placeFolder").checked,
    };
    if (placePickMap) syncPlaceFromMap();
    if (Number.isFinite(placePick.lat) && Number.isFinite(placePick.lon)) {
      body.lat = placePick.lat;
      body.lon = placePick.lon;
      body.cc = placePick.cc || "";
    }
    const data = await api("/api/media/place", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    $("placeDlg").close();
    await showAllPhotosGallery();
    updateCountLabel(trn(data.updated, "place.updated.one", "place.updated.many"));
  } catch (err) {
    $("placeDlgMsg").textContent = err.message;
  }
});
$("albumForm").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const value = ev.submitter ? ev.submitter.value : "cancel";
  if (value !== "add" && value !== "remove") {
    $("albumDlg").close();
    state.pendingAlbum = null;
    return;
  }
  const pending = state.pendingAlbum;
  const ids = pending && pending.ids && pending.ids.length ? pending.ids : [...state.selected];
  const replace = Boolean(pending && pending.replace);
  const albumIds = [...$("albumPick").selectedOptions]
    .map((opt) => Number(opt.value))
    .filter((n) => Number.isFinite(n) && n > 0);
  const created = $("albumNew").value.trim();
  $("albumDlgMsg").textContent = value === "remove" ? tr("album.removing") : replace ? tr("ui.saving") : tr("album.adding");
  try {
    if (value === "remove") {
      if (!albumIds.length) {
        throw new Error(tr("album.needAlbums"));
      }
      const data = await api("/api/albums/remove", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids, album_ids: albumIds }),
      });
      $("albumDlg").close();
      state.pendingAlbum = null;
      const currentAlbum = Number($("filterAlbum") && $("filterAlbum").value);
      if (albumIds.includes(currentAlbum)) dropSelectedIds(ids);
      await Promise.all([loadFilters(), loadGallery()]);
      if (state.view === "albums") await loadAlbumsView();
      const n = data.removed || 0;
      updateCountLabel(trn(n, "album.pull.one", "album.pull.many"));
      return;
    }
    if (!albumIds.length && !created) {
      throw new Error(tr("album.needName"));
    }
    const data = await api("/api/albums/assign", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ids,
        album_ids: albumIds,
        create: created,
        replace,
      }),
    });
    $("albumDlg").close();
    state.pendingAlbum = null;
    await Promise.all([loadFilters(), loadGallery()]);
    if (state.view === "albums") await loadAlbumsView();
    const n = data.added || 0;
    updateCountLabel(replace ? tr("album.saved") : trn(n, "album.push.one", "album.push.many"));
  } catch (err) {
    $("albumDlgMsg").textContent = err.message;
  }
});
async function runTrashAction(path, confirmMsg) {
  const n = state.trashSelected.size;
  if (!n) {
    alert(tr("ui.needChecks"));
    return;
  }
  if (!confirm(confirmMsg)) return;
  try {
    const data = await api(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(trashActionBody()),
    });
    if (data.status === "running" || data.status === "queued") {
      pollJob();
      return;
    }
    state.trashSelected.clear();
    await Promise.all([loadTrashView(), loadGallery(), loadFilters(), loadHealth()]);
    if (data.errors && data.errors.length) {
      const done = data.restored ?? data.deleted ?? 0;
      alert(trf("trash.partial", { done: done, n: data.errors.length }));
    }
  } catch (err) {
    alert(err.message);
  }
}

$("btnTrashPage").addEventListener("click", () => {
  if (trashPageFullySelected()) {
    for (const item of state.trashItems) state.trashSelected.delete(item.id);
  } else {
    for (const item of state.trashItems) state.trashSelected.add(item.id);
  }
  loadTrashView();
});
$("btnTrashAll").addEventListener("click", async () => {
  const total = state.trashTotal;
  if (!total) return;
  if (
    !confirm(
      trf("trash.checkAll", { n: fmtN(total) })
    )
  ) {
    return;
  }
  try {
    const data = await api("/api/trash/ids");
    state.trashSelected.clear();
    for (const id of data.ids) state.trashSelected.add(id);
    await loadTrashView();
  } catch (err) {
    alert(err.message);
  }
});
$("btnTrashClear").addEventListener("click", () => {
  state.trashSelected.clear();
  loadTrashView();
});
$("btnTrashPrev").addEventListener("click", () => {
  state.trashOffset = Math.max(0, state.trashOffset - PAGE);
  loadTrashView();
});
$("btnTrashNext").addEventListener("click", () => {
  state.trashOffset += PAGE;
  loadTrashView();
});
$("btnTrashRestore").addEventListener("click", async () => {
  const n = state.trashSelected.size;
  const hasEdit = (state.trashItems || []).some(
    (item) => state.trashSelected.has(item.id) && item.reason === "edit"
  );
  const okMsg =
    n === state.trashTotal
      ? trf("trash.restoreAll", { n: fmtN(n) })
      : n === 1
        ? tr("trash.restoreOne")
        : trf("trash.restoreChecked", { n: fmtN(n) });
  const extra = hasEdit ? tr("trash.restoreEdit") : "";
  await runTrashAction("/api/trash/restore", okMsg + extra);
});
$("btnTrashPurge").addEventListener("click", async () => {
  const n = state.trashSelected.size;
  const onlyEdit =
    (state.trashItems || []).length &&
    (state.trashItems || []).every(
      (item) => !state.trashSelected.has(item.id) || item.reason === "edit"
    ) &&
    (state.trashItems || []).some((item) => state.trashSelected.has(item.id));
  const pageOnly = n <= (state.trashItems || []).length;
  let msg;
  if (onlyEdit && pageOnly) {
    msg =
      n === 1
        ? tr("trash.purgeOrigOne")
        : trf("trash.purgeOrigMany", { n: fmtN(n) });
  } else if (n === 1) {
    msg = tr("trash.purgeOne");
  } else {
    msg = trf("trash.purgeMany", { n: fmtN(n) });
  }
  await runTrashAction("/api/trash/purge", msg);
});
$("btnMerge").addEventListener("click", async () => {
  const absorb = Number($("mergeAbsorb").value);
  const keep = Number($("mergeKeep").value);
  if (!absorb || !keep) return;
  if (absorb === keep) {
    alert(tr("ui.twoNames"));
    return;
  }
  const fromName = $("mergeAbsorb").selectedOptions[0].textContent;
  const toName = $("mergeKeep").selectedOptions[0].textContent;
  if (!confirm(trf("ui.confirmMerge", { from: fromName, to: toName }))) return;
  try {
    await api("/api/people/merge", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ keep_id: keep, absorb_id: absorb }),
    });
    await Promise.all([loadFacesView(), loadFilters(), fillPeopleNames()]);
  } catch (err) {
    alert(err.message);
  }
});

function stopPhotoEdit(reload) {
  window.removeEventListener("resize", layoutCropBox);
  const item = photoEdit && photoEdit.item;
  photoEdit = null;
  $("lightbox").classList.remove("is-editing");
  $("lbNavEdit").classList.add("hidden");
  $("lbNavView").classList.remove("hidden");
  $("lbEditMsg").textContent = "";
  $("lbCrop").classList.remove("primary");
  if (reload && item && $("lightbox").open) openLightboxAt(state.lbIndex);
}

function drawEditCanvas() {
  if (!photoEdit || !photoEdit.img.naturalWidth) return;
  const img = photoEdit.img;
  const rot = photoEdit.rotate;
  const cw = rot % 180 === 0 ? img.naturalWidth : img.naturalHeight;
  const ch = rot % 180 === 0 ? img.naturalHeight : img.naturalWidth;
  const canvas = photoEdit.canvas;
  canvas.width = cw;
  canvas.height = ch;
  const ctx = canvas.getContext("2d");
  ctx.save();
  ctx.translate(cw / 2, ch / 2);
  ctx.rotate((rot * Math.PI) / 180);
  ctx.drawImage(img, -img.naturalWidth / 2, -img.naturalHeight / 2);
  ctx.restore();
  fitLightboxMedia();
  layoutCropBox();
}

function layoutCropBox() {
  if (!photoEdit) return;
  const box = photoEdit.cropEl;
  if (!photoEdit.cropOn || !photoEdit.crop) {
    box.hidden = true;
    return;
  }
  const canvas = photoEdit.canvas;
  const w = canvas.clientWidth;
  const h = canvas.clientHeight;
  const c = photoEdit.crop;
  box.hidden = false;
  box.style.left = `${c.x * w}px`;
  box.style.top = `${c.y * h}px`;
  box.style.width = `${c.w * w}px`;
  box.style.height = `${c.h * h}px`;
}

function cropFromPointer(clientX, clientY) {
  const r = photoEdit.canvas.getBoundingClientRect();
  const x = Math.max(0, Math.min(1, (clientX - r.left) / r.width));
  const y = Math.max(0, Math.min(1, (clientY - r.top) / r.height));
  return { x, y };
}

function startPhotoEdit() {
  const item = state.lbItem;
  if (!item || item.kind !== "photo") return;
  pauseSlideshow();
  stopAdvance();
  photoEdit = {
    item,
    rotate: 0,
    cropOn: false,
    crop: null,
    drag: null,
    img: new Image(),
    canvas: document.createElement("canvas"),
    cropEl: document.createElement("div"),
  };
  $("lightbox").classList.add("is-editing");
  $("lbNavView").classList.add("hidden");
  $("lbNavEdit").classList.remove("hidden");
  $("lbEditMsg").textContent = tr("ui.editHint");
  $("lbTags").innerHTML = "";
  const wrap = document.createElement("div");
  wrap.className = "lb-edit-wrap";
  const layer = document.createElement("div");
  layer.className = "lb-crop-layer";
  photoEdit.cropEl.className = "lb-crop-box";
  photoEdit.cropEl.hidden = true;
  ["nw", "ne", "sw", "se"].forEach((k) => {
    const h = document.createElement("div");
    h.className = `lb-crop-handle ${k}`;
    h.dataset.handle = k;
    photoEdit.cropEl.appendChild(h);
  });
  wrap.append(photoEdit.canvas, layer, photoEdit.cropEl);
  $("lbStage").innerHTML = "";
  $("lbStage").appendChild(wrap);
  photoEdit.img.onload = () => drawEditCanvas();
  photoEdit.img.src = mediaPreviewUrl(item);

  layer.addEventListener("pointerdown", (ev) => {
    if (!photoEdit.cropOn) return;
    ev.preventDefault();
    layer.setPointerCapture(ev.pointerId);
    const p = cropFromPointer(ev.clientX, ev.clientY);
    const handle = ev.target.dataset && ev.target.dataset.handle;
    if (handle) {
      photoEdit.drag = { kind: "resize", handle, start: p, crop: { ...photoEdit.crop } };
    } else if (photoEdit.crop) {
      const c = photoEdit.crop;
      const inside = p.x >= c.x && p.x <= c.x + c.w && p.y >= c.y && p.y <= c.y + c.h;
      photoEdit.drag = inside
        ? { kind: "move", start: p, crop: { ...c } }
        : { kind: "new", start: p };
    } else {
      photoEdit.drag = { kind: "new", start: p };
    }
  });
  layer.appendChild(photoEdit.cropEl);
  layer.addEventListener("pointermove", (ev) => {
    if (!photoEdit || !photoEdit.drag) return;
    const p = cropFromPointer(ev.clientX, ev.clientY);
    const d = photoEdit.drag;
    if (d.kind === "new") {
      photoEdit.crop = {
        x: Math.min(d.start.x, p.x),
        y: Math.min(d.start.y, p.y),
        w: Math.abs(p.x - d.start.x),
        h: Math.abs(p.y - d.start.y),
      };
    } else if (d.kind === "move") {
      const nx = Math.max(0, Math.min(1 - d.crop.w, d.crop.x + (p.x - d.start.x)));
      const ny = Math.max(0, Math.min(1 - d.crop.h, d.crop.y + (p.y - d.start.y)));
      photoEdit.crop = { x: nx, y: ny, w: d.crop.w, h: d.crop.h };
    } else {
      const c = { ...d.crop };
      const x2 = c.x + c.w;
      const y2 = c.y + c.h;
      if (d.handle.includes("w")) c.x = Math.min(p.x, x2 - 0.04);
      if (d.handle.includes("e")) c.w = Math.max(0.04, p.x - c.x);
      if (d.handle.includes("n")) c.y = Math.min(p.y, y2 - 0.04);
      if (d.handle.includes("s")) c.h = Math.max(0.04, p.y - c.y);
      if (d.handle.includes("w")) c.w = x2 - c.x;
      if (d.handle.includes("n")) c.h = y2 - c.y;
      c.x = Math.max(0, c.x);
      c.y = Math.max(0, c.y);
      c.w = Math.min(1 - c.x, c.w);
      c.h = Math.min(1 - c.y, c.h);
      photoEdit.crop = c;
    }
    layoutCropBox();
  });
  const endDrag = () => {
    if (photoEdit) photoEdit.drag = null;
  };
  layer.addEventListener("pointerup", endDrag);
  layer.addEventListener("pointercancel", endDrag);
  window.addEventListener("resize", layoutCropBox);
}

$("lbEdit").addEventListener("click", () => startPhotoEdit());
$("lbRotLeft").addEventListener("click", () => {
  if (!photoEdit) return;
  photoEdit.rotate = (photoEdit.rotate + 270) % 360;
  photoEdit.crop = null;
  photoEdit.cropOn = false;
  $("lbCrop").classList.remove("primary");
  drawEditCanvas();
});
$("lbRotRight").addEventListener("click", () => {
  if (!photoEdit) return;
  photoEdit.rotate = (photoEdit.rotate + 90) % 360;
  photoEdit.crop = null;
  photoEdit.cropOn = false;
  $("lbCrop").classList.remove("primary");
  drawEditCanvas();
});
$("lbCrop").addEventListener("click", () => {
  if (!photoEdit) return;
  photoEdit.cropOn = !photoEdit.cropOn;
  $("lbCrop").classList.toggle("primary", photoEdit.cropOn);
  if (photoEdit.cropOn && !photoEdit.crop) {
    photoEdit.crop = { x: 0, y: 0, w: 1, h: 1 };
  }
  if (!photoEdit.cropOn) photoEdit.crop = null;
  layoutCropBox();
});
$("lbEditCancel").addEventListener("click", () => stopPhotoEdit(true));
$("lbEditSave").addEventListener("click", async () => {
  if (!photoEdit) return;
  const item = photoEdit.item;
  const rotate = photoEdit.rotate;
  const rawCrop = photoEdit.cropOn ? photoEdit.crop : null;
  const crop =
    rawCrop &&
    (rawCrop.x > 0.002 ||
      rawCrop.y > 0.002 ||
      rawCrop.x + rawCrop.w < 0.998 ||
      rawCrop.y + rawCrop.h < 0.998)
      ? rawCrop
      : null;
  if (!rotate && !crop) {
    $("lbEditMsg").textContent = tr("ui.editNeed");
    return;
  }
  if (
    !confirm(
      tr("edit.confirm")
    )
  ) {
    return;
  }
  $("lbEditSave").disabled = true;
  $("lbEditMsg").textContent = tr("ui.saving");
  try {
    const data = await api(`/api/media/${item.id}/edit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rotate, crop }),
    });
    Object.assign(item, data);
    if (state.lbItem && state.lbItem.id === item.id) Object.assign(state.lbItem, data);
    const card = state.items.find((x) => x.id === item.id);
    if (card) Object.assign(card, data);
    stopPhotoEdit(false);
    await openLightboxAt(state.lbIndex);
    await loadGallery();
  } catch (err) {
    $("lbEditMsg").textContent = err.message || tr("ui.editFail");
  } finally {
    $("lbEditSave").disabled = false;
  }
});
$("lightbox").addEventListener("cancel", (ev) => {
  if (!photoEdit) return;
  ev.preventDefault();
  stopPhotoEdit(true);
});

(function bindLightboxGestures() {
  const stage = $("lbStage");
  let startX = null;
  let startY = null;
  let pinch = null;
  let panning = false;
  let panStart = null;

  function touchDist(a, b) {
    return Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
  }

  stage.addEventListener(
    "touchstart",
    (ev) => {
      if (photoEdit) return;
      if (ev.touches.length >= 2) {
        startX = startY = null;
        panning = false;
        const z = state.lbZoom || { scale: 1, x: 0, y: 0 };
        pinch = {
          dist: touchDist(ev.touches[0], ev.touches[1]) || 1,
          scale: z.scale,
          x: z.x,
          y: z.y,
        };
        return;
      }
      pinch = null;
      const t = ev.changedTouches[0];
      if (state.lbZoom && state.lbZoom.scale > 1.05) {
        panning = true;
        panStart = {
          x: t.clientX,
          y: t.clientY,
          ox: state.lbZoom.x,
          oy: state.lbZoom.y,
        };
        startX = startY = null;
        return;
      }
      startX = t.clientX;
      startY = t.clientY;
    },
    { passive: true }
  );
  stage.addEventListener(
    "touchmove",
    (ev) => {
      if (photoEdit) return;
      if (pinch && ev.touches.length >= 2) {
        ev.preventDefault();
        const d = touchDist(ev.touches[0], ev.touches[1]) || 1;
        const scale = Math.min(5, Math.max(1, pinch.scale * (d / pinch.dist)));
        state.lbZoom =
          scale <= 1.02
            ? { scale: 1, x: 0, y: 0 }
            : { scale, x: pinch.x, y: pinch.y };
        applyLbZoom();
      } else if (panning && ev.touches.length === 1 && state.lbZoom) {
        ev.preventDefault();
        const t = ev.touches[0];
        state.lbZoom = {
          scale: state.lbZoom.scale,
          x: panStart.ox + (t.clientX - panStart.x),
          y: panStart.oy + (t.clientY - panStart.y),
        };
        applyLbZoom();
      }
    },
    { passive: false }
  );
  stage.addEventListener(
    "touchend",
    (ev) => {
      if (photoEdit) return;
      if (pinch) {
        if (ev.touches.length < 2) pinch = null;
        startX = startY = null;
        panning = false;
        return;
      }
      if (panning) {
        panning = false;
        panStart = null;
        startX = startY = null;
        return;
      }
      if (startX == null) return;
      const t = ev.changedTouches[0];
      const dx = t.clientX - startX;
      const dy = t.clientY - startY;
      startX = startY = null;
      if (state.lbZoom && state.lbZoom.scale > 1.05) return;
      if (Math.abs(dx) < 56 || Math.abs(dx) < Math.abs(dy)) return;
      if (state.lbTotal < 2) return;
      if (dx < 0) openLightboxAt(state.lbIndex + 1, { wrap: true });
      else openLightboxAt(state.lbIndex - 1, { wrap: true });
    },
    { passive: true }
  );
  stage.addEventListener(
    "wheel",
    (ev) => {
      if (!$("lightbox").open || photoEdit) return;
      ev.preventDefault();
      const z = state.lbZoom || { scale: 1, x: 0, y: 0 };
      const next = Math.min(5, Math.max(1, z.scale * (ev.deltaY < 0 ? 1.12 : 0.9)));
      state.lbZoom =
        next <= 1.02 ? { scale: 1, x: 0, y: 0 } : { scale: next, x: z.x, y: z.y };
      applyLbZoom();
    },
    { passive: false }
  );
})();

window.GalerieBridge = {
  api: api,
  tr: tr,
  isViewer: isViewer,
  startJob: startJob,
  setView: setView,
  saveSettingsForm: saveSettingsForm,
  openCastDialog: openCastDialog,
  loadHealth: loadHealth,
};

(async function init() {
  initPrefs();
  if (isNarrow()) {
    $("filtersPanel").classList.add("is-collapsed");
    $("toolsPanel").classList.add("is-collapsed");
  }
  syncLayoutMode();
  const health = await loadHealth();
  if (health && health.auth && health.auth.enabled && !health.auth.user) {
    return;
  }
  await loadFilters();
  await loadGallery();
  pollJob();
  if (health && health.needs_setup && !isViewer()) setView("settings");
})();

if (
  location.protocol === "https:" ||
  location.hostname === "localhost" ||
  location.hostname === "127.0.0.1"
) {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }
}
