/* Onglet Cinéma : catalogue, filtres, métadonnées Wikidata et lecteur HLS. */
(function () {
  const $ = (id) => document.getElementById(id);
  const bridge = () => window.GalerieBridge || {};
  const api = (url, opts) => bridge().api(url, opts);
  const tr = (key) => (bridge().tr ? bridge().tr(key) : key);
  const isViewer = () => (bridge().isViewer ? bridge().isViewer() : false);
  const startJob = (url, body) => bridge().startJob && bridge().startJob(url, body);

  const cState = {
    offset: 0,
    limit: 60,
    total: 0,
    allTypes: ["movie", "series", "clip", "documentary", "other"],
    allCategories: [],
    items: [],
    currentItem: null,
    currentDisc: false,
    currentTitleIndex: null,
    currentProbe: null,
    hls: null,
    sessionId: null,
    streamOffsetS: 0,
    progressTimer: 0,
    searchTimer: 0,
    editingItem: null,
  };

  function typeLabel(code) {
    const key = `cinema.type.${code}`;
    const v = tr(key);
    return v === key ? code : v;
  }

  function catLabel(code) {
    const key = `cinema.cat.${code}`;
    const v = tr(key);
    return v === key ? code : v;
  }

  function formatDuration(sec) {
    if (sec === null || sec === undefined || !isFinite(sec) || sec <= 0) return "";
    const total = Math.round(sec);
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = total % 60;
    if (h > 0) return `${h}h${String(m).padStart(2, "0")}`;
    return `${m}:${String(s).padStart(2, "0")}`;
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text == null ? "" : String(text);
    return div.innerHTML;
  }

  function renderBanner(statusData) {
    const banner = $("cinemaBanner");
    if (!banner) return;
    const ds = (statusData && statusData.dir_status) || {};
    if (!ds.configured) {
      banner.classList.remove("hidden");
      banner.textContent = tr("cinema.statusUnconfigured");
      return;
    }
    if (ds.status === "missing_mount") {
      banner.classList.remove("hidden");
      banner.textContent = tr("cinema.statusMissingMount").replace("{path}", ds.path || "");
      return;
    }
    if (ds.status !== "ready") {
      banner.classList.remove("hidden");
      banner.textContent = tr("cinema.statusMissing").replace("{path}", ds.path || "");
      return;
    }
    banner.classList.add("hidden");
    banner.textContent = "";
  }

  async function loadFiltersAndStatus() {
    const [statusData, flt] = await Promise.all([
      api("/api/cinema/status"),
      api("/api/cinema/filters"),
    ]);
    renderBanner(statusData);
    const discBtn = $("btnCinemaDisc");
    if (discBtn) {
      discBtn.classList.toggle("hidden", !(statusData && statusData.optical_device));
    }
    cState.allTypes = flt.all_types || cState.allTypes;
    cState.allCategories = flt.all_categories || cState.allCategories;

    const selType = $("cinemaType");
    if (selType) {
      const prev = selType.value;
      const counts = new Map((flt.types || []).map((x) => [x.value, x.count]));
      selType.innerHTML = `<option value="">${escapeHtml(tr("filter.all"))}</option>`;
      for (const code of cState.allTypes) {
        const c = counts.get(code) || 0;
        const opt = document.createElement("option");
        opt.value = code;
        opt.textContent = c ? `${typeLabel(code)} (${c})` : typeLabel(code);
        selType.appendChild(opt);
      }
      selType.value = prev;
    }

    const selCat = $("cinemaCategory");
    if (selCat) {
      const prev = selCat.value;
      const counts = new Map((flt.categories || []).map((x) => [x.value, x.count]));
      selCat.innerHTML = `<option value="">${escapeHtml(tr("filter.all"))}</option>`;
      for (const code of cState.allCategories) {
        const c = counts.get(code) || 0;
        if (!c && prev !== code) continue;
        const opt = document.createElement("option");
        opt.value = code;
        opt.textContent = `${catLabel(code)} (${c})`;
        selCat.appendChild(opt);
      }
      selCat.value = prev;
    }

    const selYear = $("cinemaYear");
    if (selYear) {
      const prev = selYear.value;
      selYear.innerHTML = `<option value="">${escapeHtml(tr("filter.allYears"))}</option>`;
      for (const y of flt.years || []) {
        const opt = document.createElement("option");
        opt.value = String(y.value);
        opt.textContent = `${y.value} (${y.count})`;
        selYear.appendChild(opt);
      }
      selYear.value = prev;
    }
  }

  function makeCard(item, { compact = false } = {}) {
    const card = document.createElement("article");
    card.className = compact ? "cinema-card cinema-card-compact" : "cinema-card";
    const dur = formatDuration(item.duration_s);
    const prog = item.progress;
    const pct =
      prog && prog.duration_s > 0
        ? Math.min(100, Math.round((prog.position_s / prog.duration_s) * 100))
        : 0;
    const cats = (item.categories || [])
      .slice(0, 3)
      .map((c) => `<span class="cinema-chip">${escapeHtml(catLabel(c))}</span>`)
      .join("");
    const metaParts = [typeLabel(item.media_type)];
    if (item.year) metaParts.push(String(item.year));
    if (item.season && item.episode) {
      metaParts.push(`S${String(item.season).padStart(2, "0")}E${String(item.episode).padStart(2, "0")}`);
    }

    card.innerHTML = `
      <div class="cinema-poster-wrap">
        <img class="cinema-poster" loading="lazy" src="/api/cinema/items/${item.id}/poster?v=${item.mtime_ns || 0}" alt="${escapeHtml(item.title)}">
        ${dur ? `<span class="cinema-dur">${escapeHtml(dur)}</span>` : ""}
        ${pct > 0 ? `<div class="cinema-prog"><div style="width:${pct}%"></div></div>` : ""}
      </div>
      <div class="cinema-card-body">
        <h3 class="cinema-card-title" title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</h3>
        <p class="cinema-card-meta muted">${escapeHtml(metaParts.join(" · "))}</p>
        ${cats ? `<div class="cinema-chips">${cats}</div>` : ""}
      </div>
    `;
    card.addEventListener("click", () => openPlayer(item.id));
    if (compact) {
      const dismissBtn = document.createElement("button");
      dismissBtn.type = "button";
      dismissBtn.className = "cinema-card-edit cinema-card-dismiss";
      dismissBtn.textContent = "✕";
      dismissBtn.title = tr("cinema.dismissContinue");
      dismissBtn.setAttribute("aria-label", tr("cinema.dismissContinue"));
      dismissBtn.addEventListener("click", async (ev) => {
        ev.stopPropagation();
        try {
          await api("/api/cinema/progress/clear", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ item_id: item.id }),
          });
          await Promise.all([loadContinue(), loadItems()]);
        } catch (_e) {}
      });
      card.querySelector(".cinema-poster-wrap").appendChild(dismissBtn);
    } else if (!isViewer()) {
      const editBtn = document.createElement("button");
      editBtn.type = "button";
      editBtn.className = "cinema-card-edit admin-only";
      editBtn.textContent = "✎";
      editBtn.title = tr("cinema.editMeta");
      editBtn.setAttribute("aria-label", tr("cinema.editMeta"));
      editBtn.addEventListener("click", (ev) => {
        ev.stopPropagation();
        openEditDialog(item);
      });
      const trashBtn = document.createElement("button");
      trashBtn.type = "button";
      trashBtn.className = "cinema-card-edit cinema-card-trash admin-only";
      trashBtn.textContent = "🗑";
      trashBtn.title = tr("action.delete");
      trashBtn.setAttribute("aria-label", tr("action.delete"));
      trashBtn.addEventListener("click", (ev) => {
        ev.stopPropagation();
        trashItem(item);
      });
      const pw = card.querySelector(".cinema-poster-wrap");
      pw.appendChild(editBtn);
      pw.appendChild(trashBtn);
    }
    return card;
  }

  async function loadContinue() {
    const wrap = $("cinemaContinueWrap");
    const box = $("cinemaContinue");
    if (!wrap || !box) return;
    try {
      const data = await api("/api/cinema/continue");
      const items = (data && data.items) || [];
      box.innerHTML = "";
      if (!items.length) {
        wrap.classList.add("hidden");
        return;
      }
      wrap.classList.remove("hidden");
      for (const item of items) {
        box.appendChild(makeCard(item, { compact: true }));
      }
    } catch (_err) {
      wrap.classList.add("hidden");
    }
  }

  async function loadItems() {
    const params = new URLSearchParams();
    params.set("offset", String(cState.offset));
    params.set("limit", String(cState.limit));
    const t = $("cinemaType") ? $("cinemaType").value : "";
    const cat = $("cinemaCategory") ? $("cinemaCategory").value : "";
    const y = $("cinemaYear") ? $("cinemaYear").value : "";
    const q = $("cinemaQ") ? $("cinemaQ").value.trim() : "";
    if (t) params.set("media_type", t);
    if (cat) params.set("category", cat);
    if (y) params.set("year", y);
    if (q) params.set("q", q);

    const data = await api(`/api/cinema/items?${params.toString()}`);
    cState.total = data.total || 0;
    cState.items = data.items || [];

    const countEl = $("cinemaCount");
    if (countEl) {
      countEl.textContent = cState.total
        ? tr("cinema.count").replace("{n}", String(cState.total))
        : tr("cinema.empty");
    }

    const grid = $("cinemaGrid");
    if (grid) {
      grid.innerHTML = "";
      for (const item of cState.items) {
        grid.appendChild(makeCard(item));
      }
    }

    const pages = Math.max(1, Math.ceil(cState.total / cState.limit));
    const page = Math.floor(cState.offset / cState.limit) + 1;
    if ($("cinemaPageInfo")) {
      $("cinemaPageInfo").textContent = tr("pager.page")
        .replace("{page}", String(page))
        .replace("{pages}", String(pages));
    }
    if ($("btnCinemaPrev")) $("btnCinemaPrev").disabled = cState.offset <= 0;
    if ($("btnCinemaNext")) $("btnCinemaNext").disabled = cState.offset + cState.limit >= cState.total;
  }

  async function loadView() {
    try {
      await loadFiltersAndStatus();
      await Promise.all([loadContinue(), loadItems()]);
    } catch (err) {
      if ($("cinemaCount")) $("cinemaCount").textContent = err.message || String(err);
    }
  }

  async function stopStream() {
    if (cState.progressTimer) {
      clearInterval(cState.progressTimer);
      cState.progressTimer = 0;
    }
    if (cState.hls) {
      try {
        cState.hls.destroy();
      } catch (_e) {}
      cState.hls = null;
    }
    const video = $("cinemaVideo");
    if (video) {
      try {
        video.pause();
        video.removeAttribute("src");
        video.innerHTML = "";
        video.load();
      } catch (_e) {}
    }
    const sid = cState.sessionId;
    cState.sessionId = null;
    if (sid) {
      try {
        await api(`/api/cinema/stream/${sid}/stop`, { method: "POST" });
      } catch (_e) {}
    }
  }

  function currentAbsolutePosition() {
    const video = $("cinemaVideo");
    if (!video || !isFinite(video.currentTime)) return cState.streamOffsetS;
    return Math.max(0, cState.streamOffsetS + video.currentTime);
  }

  async function saveCurrentProgress() {
    if (!cState.currentItem) return;
    const pos = currentAbsolutePosition();
    const dur =
      (cState.currentProbe && cState.currentProbe.duration_s) ||
      cState.currentItem.duration_s ||
      0;
    const audioSel = $("cinemaAudio");
    const subSel = $("cinemaSub");
    try {
      await api("/api/cinema/progress", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          item_id: cState.currentItem.id,
          position_s: pos,
          duration_s: dur,
          audio_idx: audioSel && audioSel.value !== "" ? Number(audioSel.value) : null,
          subtitle_idx: subSel && subSel.value !== "" ? Number(subSel.value) : null,
        }),
      });
    } catch (_e) {}
  }

  function applySubtitleTrack() {
    const video = $("cinemaVideo");
    const subSel = $("cinemaSub");
    if (!video || !subSel || !cState.currentItem) return;
    Array.from(video.querySelectorAll("track")).forEach((el) => el.remove());
    if (subSel.value === "") return;
    const idx = Number(subSel.value);
    const track = document.createElement("track");
    track.kind = "subtitles";
    track.label = subSel.options[subSel.selectedIndex]?.textContent || "Sub";
    track.src = `/api/cinema/items/${cState.currentItem.id}/subtitles/${idx}.vtt`;
    track.default = true;
    video.appendChild(track);
    if (video.textTracks && video.textTracks[0]) {
      video.textTracks[0].mode = "showing";
    }
  }

  async function startHlsAt(startS) {
    if (!cState.currentItem && !cState.currentDisc) return;
    await stopStream();
    const msg = $("cinemaPlayerMsg");
    if (msg) msg.textContent = tr("cinema.loadingStream");
    const audioSel = $("cinemaAudio");
    const qualSel = $("cinemaQuality");
    const titleSel = $("cinemaTitle");
    const body = {
      item_id: cState.currentDisc ? null : cState.currentItem.id,
      disc: Boolean(cState.currentDisc),
      title_index:
        titleSel && !titleSel.closest("#cinemaTitleWrap")?.classList.contains("hidden") && titleSel.value !== ""
          ? Number(titleSel.value)
          : cState.currentTitleIndex,
      start_s: Math.max(0, Number(startS) || 0),
      audio_idx: audioSel && audioSel.value !== "" ? Number(audioSel.value) : null,
      quality: qualSel ? qualSel.value : "auto",
    };
    const res = await api("/api/cinema/stream/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    cState.sessionId = res.session_id;
    cState.streamOffsetS = res.start_s || 0;
    const video = $("cinemaVideo");
    const playlistUrl = res.playlist_url;

    if (window.Hls && window.Hls.isSupported()) {
      const hls = new window.Hls({
        enableWorker: true,
        lowLatencyMode: false,
        backBufferLength: 30,
      });
      cState.hls = hls;
      hls.loadSource(playlistUrl);
      hls.attachMedia(video);
      hls.on(window.Hls.Events.MANIFEST_PARSED, () => {
        applySubtitleTrack();
        video.play().catch(() => {});
        if (msg) {
          msg.textContent = res.remux
            ? tr("cinema.modeDirect")
            : tr("cinema.modeTranscode").replace("{q}", res.quality || "auto");
        }
      });
      hls.on(window.Hls.Events.ERROR, (_ev, data) => {
        if (data && data.fatal && msg) {
          msg.textContent = tr("cinema.streamError");
        }
      });
    } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
      video.src = playlistUrl;
      applySubtitleTrack();
      video.play().catch(() => {});
      if (msg) msg.textContent = "";
    } else if (msg) {
      msg.textContent = tr("cinema.hlsUnsupported");
    }

    cState.progressTimer = window.setInterval(() => {
      if (video && !video.paused && !video.ended) saveCurrentProgress();
    }, 10000);
  }

  function populateTitles(titles, defaultIdx) {
    const wrap = $("cinemaTitleWrap");
    const sel = $("cinemaTitle");
    if (!wrap || !sel) return;
    if (titles && titles.length) {
      wrap.classList.remove("hidden");
      sel.innerHTML = "";
      for (const t of titles) {
        const opt = document.createElement("option");
        opt.value = String(t.index);
        const dur = formatDuration(t.duration_s);
        opt.textContent = dur ? `${t.label} (${dur})` : t.label;
        sel.appendChild(opt);
      }
      if (defaultIdx != null) sel.value = String(defaultIdx);
      cState.currentTitleIndex = Number(sel.value);
    } else {
      wrap.classList.add("hidden");
      sel.innerHTML = "";
      cState.currentTitleIndex = null;
    }
  }

  async function openDiscPlayer() {
    const dlg = $("cinemaPlayerDlg");
    if (!dlg) return;
    cState.currentItem = null;
    cState.currentDisc = true;
    cState.currentProbe = null;
    if ($("cinemaEditBtn")) $("cinemaEditBtn").classList.add("hidden");
    if ($("cinemaTrashBtn")) $("cinemaTrashBtn").classList.add("hidden");
    if ($("cinemaCast")) $("cinemaCast").classList.add("hidden");
    $("cinemaPlayerTitle").textContent = tr("cinema.readDisc");
    $("cinemaPlayerMeta").textContent = "";
    $("cinemaPlayerOverview").textContent = "";
    if ($("cinemaPlayerMsg")) $("cinemaPlayerMsg").textContent = tr("cinema.discReading");
    if (!dlg.open) dlg.showModal();
    try {
      const data = await api("/api/cinema/disc");
      if (!data.readable || !(data.titles && data.titles.length)) {
        $("cinemaPlayerMsg").textContent =
          data.encryption_hint || tr("cinema.discMissing");
        return;
      }
      $("cinemaPlayerMeta").textContent = `${(data.kind || "").toUpperCase()} · ${data.device || ""}`;
      populateTitles(data.titles, data.default_title);
      const chosen =
        data.titles.find((t) => t.index === data.default_title) || data.titles[0];
      cState.currentProbe = chosen;
      const audioSel = $("cinemaAudio");
      audioSel.innerHTML = "";
      const audios = (chosen && chosen.audio_tracks) || [];
      if (!audios.length) audioSel.innerHTML = `<option value="">—</option>`;
      else {
        audios.forEach((a, idx) => {
          const opt = document.createElement("option");
          opt.value = String(idx);
          opt.textContent = [a.language || `#${idx + 1}`, a.title, a.codec].filter(Boolean).join(" · ");
          audioSel.appendChild(opt);
        });
      }
      $("cinemaSub").innerHTML = `<option value="">${escapeHtml(tr("cinema.subOff"))}</option>`;
      if ($("cinemaChapterWrap")) $("cinemaChapterWrap").classList.add("hidden");
      await startHlsAt(0);
    } catch (err) {
      if ($("cinemaPlayerMsg")) $("cinemaPlayerMsg").textContent = err.message || String(err);
    }
  }

  async function openPlayer(itemId) {
    const dlg = $("cinemaPlayerDlg");
    if (!dlg) return;
    cState.currentDisc = false;
    if ($("cinemaEditBtn")) $("cinemaEditBtn").classList.toggle("hidden", isViewer());
    if ($("cinemaTrashBtn")) $("cinemaTrashBtn").classList.toggle("hidden", isViewer());
    if ($("cinemaCast")) $("cinemaCast").classList.remove("hidden");
    if ($("cinemaPlayerMsg")) $("cinemaPlayerMsg").textContent = tr("cinema.loadingInfo");
    if (!dlg.open) dlg.showModal();
    try {
      const data = await api(`/api/cinema/items/${itemId}/info`);
      const item = data.item;
      const probe = data.probe || {};
      cState.currentItem = item;
      cState.currentProbe = probe;
      populateTitles(data.titles || [], data.default_title);
      if ($("cinemaCast")) {
        $("cinemaCast").classList.toggle("hidden", item.source_type !== "file");
      }
      if (data.encryption_hint && !(data.titles && data.titles.length)) {
        $("cinemaPlayerMsg").textContent = data.encryption_hint;
        return;
      }

      $("cinemaPlayerTitle").textContent = item.title || "";
      const metaParts = [typeLabel(item.media_type)];
      if (item.year) metaParts.push(String(item.year));
      if (item.director) metaParts.push(item.director);
      if (item.duration_s) metaParts.push(formatDuration(item.duration_s));
      if (item.categories && item.categories.length) {
        metaParts.push(item.categories.map(catLabel).join(", "));
      }
      $("cinemaPlayerMeta").textContent = metaParts.join(" · ");
      $("cinemaPlayerOverview").textContent = item.overview || "";

      const audioSel = $("cinemaAudio");
      audioSel.innerHTML = "";
      const audios = probe.audio_tracks || [];
      if (!audios.length) {
        audioSel.innerHTML = `<option value="">—</option>`;
      } else {
        audios.forEach((trAudio, idx) => {
          const opt = document.createElement("option");
          opt.value = String(idx);
          const lbl = [trAudio.language || `#${idx + 1}`, trAudio.title, trAudio.codec]
            .filter(Boolean)
            .join(" · ");
          opt.textContent = lbl;
          audioSel.appendChild(opt);
        });
      }

      const subSel = $("cinemaSub");
      subSel.innerHTML = `<option value="">${escapeHtml(tr("cinema.subOff"))}</option>`;
      for (const s of probe.subtitle_tracks || []) {
        if (!s.is_text) continue;
        const opt = document.createElement("option");
        opt.value = String(s.index);
        opt.textContent = [s.language || `#${s.index + 1}`, s.title, s.codec]
          .filter(Boolean)
          .join(" · ");
        subSel.appendChild(opt);
      }

      const chapWrap = $("cinemaChapterWrap");
      const chapSel = $("cinemaChapter");
      const chapters = probe.chapters || [];
      if (chapters.length && chapWrap && chapSel) {
        chapWrap.classList.remove("hidden");
        chapSel.innerHTML = "";
        for (const ch of chapters) {
          const opt = document.createElement("option");
          opt.value = String(ch.start_s);
          opt.textContent = `${formatDuration(ch.start_s)} — ${ch.title}`;
          chapSel.appendChild(opt);
        }
      } else if (chapWrap) {
        chapWrap.classList.add("hidden");
      }

      const resumeS =
        item.progress && item.progress.position_s >= 15 ? item.progress.position_s : 0;
      if (item.progress && item.progress.audio_idx != null && audios[item.progress.audio_idx]) {
        audioSel.value = String(item.progress.audio_idx);
      }
      await startHlsAt(resumeS);
    } catch (err) {
      if ($("cinemaPlayerMsg")) $("cinemaPlayerMsg").textContent = err.message || String(err);
    }
  }

  async function closePlayer() {
    await saveCurrentProgress();
    await stopStream();
    cState.currentItem = null;
    cState.currentDisc = false;
    cState.currentTitleIndex = null;
    cState.currentProbe = null;
    const dlg = $("cinemaPlayerDlg");
    if (dlg && dlg.open) dlg.close();
    loadContinue().catch(() => {});
  }

  async function trashItem(item, { fromPlayer = false } = {}) {
    const msg = tr("cinema.trashConfirm").replace("{title}", item.title || "");
    if (!confirm(msg)) return;
    if (fromPlayer) {
      await stopStream();
      cState.currentItem = null;
      const dlg = $("cinemaPlayerDlg");
      if (dlg && dlg.open) dlg.close();
    }
    try {
      await api(`/api/cinema/items/${item.id}/trash`, { method: "POST" });
      await loadView();
      if (bridge().loadHealth) bridge().loadHealth().catch(() => {});
    } catch (err) {
      alert(err.message || String(err));
    }
  }

  async function loadTrash() {
    const wrap = $("cinemaTrashWrap");
    const grid = $("cinemaTrashGrid");
    if (!wrap || !grid || isViewer()) return;
    try {
      const data = await api("/api/cinema/trash");
      const items = (data && data.items) || [];
      grid.innerHTML = "";
      if (!items.length) {
        wrap.classList.add("hidden");
        return;
      }
      wrap.classList.remove("hidden");
      for (const item of items) {
        const card = document.createElement("article");
        card.className = "cinema-card cinema-trash-card";
        const days = tr("cinema.trashDays").replace("{n}", String(item.days_left ?? 30));
        card.innerHTML = `
          <div class="cinema-poster-wrap">
            <img class="cinema-poster" loading="lazy" src="/api/cinema/items/${item.id}/poster?v=${item.mtime_ns || 0}" alt="${escapeHtml(item.title)}">
          </div>
          <div class="cinema-card-body">
            <h3 class="cinema-card-title" title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</h3>
            <p class="cinema-card-meta muted">${escapeHtml(days)}</p>
            <div class="cinema-trash-actions">
              <button type="button" class="btn-restore">${escapeHtml(tr("cinema.restore"))}</button>
              <button type="button" class="danger btn-purge">${escapeHtml(tr("cinema.purge"))}</button>
            </div>
          </div>
        `;
        card.querySelector(".btn-restore").addEventListener("click", async () => {
          try {
            await api(`/api/cinema/trash/${item.id}/restore`, { method: "POST" });
            await loadTrash();
            if (bridge().loadHealth) bridge().loadHealth().catch(() => {});
          } catch (err) {
            alert(err.message || String(err));
          }
        });
        card.querySelector(".btn-purge").addEventListener("click", async () => {
          const msg = tr("cinema.purgeConfirm").replace("{title}", item.title || "");
          if (!confirm(msg)) return;
          try {
            await api(`/api/cinema/trash/${item.id}/purge`, { method: "POST" });
            await loadTrash();
            if (bridge().loadHealth) bridge().loadHealth().catch(() => {});
          } catch (err) {
            alert(err.message || String(err));
          }
        });
        grid.appendChild(card);
      }
    } catch (_e) {
      wrap.classList.add("hidden");
    }
  }

  function openEditDialog(item) {
    cState.editingItem = item;
    $("ceTitle").value = item.title || "";
    const selType = $("ceType");
    selType.innerHTML = "";
    for (const code of cState.allTypes) {
      const opt = document.createElement("option");
      opt.value = code;
      opt.textContent = typeLabel(code);
      selType.appendChild(opt);
    }
    selType.value = item.media_type || "movie";
    $("ceYear").value = item.year ? String(item.year) : "";
    $("ceDirector").value = item.director || "";
    $("ceOverview").value = item.overview || "";
    $("ceLocked").checked = true;
    $("ceMsg").textContent = "";

    const catBox = $("ceCategories");
    catBox.innerHTML = "";
    const active = new Set(item.categories || []);
    for (const code of cState.allCategories) {
      const lbl = document.createElement("label");
      lbl.className = "cinema-cat-opt";
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.value = code;
      cb.checked = active.has(code);
      lbl.appendChild(cb);
      lbl.append(" " + catLabel(code));
      catBox.appendChild(lbl);
    }
    $("cinemaEditDlg").showModal();
  }

  function bindEvents() {
    const onFilterChange = () => {
      cState.offset = 0;
      loadItems().catch(() => {});
    };
    if ($("cinemaType")) $("cinemaType").addEventListener("change", onFilterChange);
    if ($("cinemaCategory")) $("cinemaCategory").addEventListener("change", onFilterChange);
    if ($("cinemaYear")) $("cinemaYear").addEventListener("change", onFilterChange);
    if ($("cinemaQ")) {
      $("cinemaQ").addEventListener("input", () => {
        clearTimeout(cState.searchTimer);
        cState.searchTimer = window.setTimeout(onFilterChange, 250);
      });
    }
    if ($("btnCinemaPrev")) {
      $("btnCinemaPrev").addEventListener("click", () => {
        cState.offset = Math.max(0, cState.offset - cState.limit);
        loadItems().catch(() => {});
      });
    }
    if ($("btnCinemaNext")) {
      $("btnCinemaNext").addEventListener("click", () => {
        if (cState.offset + cState.limit < cState.total) {
          cState.offset += cState.limit;
          loadItems().catch(() => {});
        }
      });
    }
    const triggerScan = async () => {
      try {
        if ($("view-settings") && !$("view-settings").classList.contains("hidden") && bridge().saveSettingsForm) {
          await bridge().saveSettingsForm({ quiet: true });
        }
        await startJob("/api/cinema/scan", {});
      } catch (err) {
        alert(err.message || String(err));
      }
    };
    const triggerEnrich = async () => {
      try {
        const lang = (window.GalerieI18n && window.GalerieI18n.getLang()) || "fr";
        await startJob("/api/cinema/enrich", { lang: lang, only_missing: true });
      } catch (err) {
        alert(err.message || String(err));
      }
    };
    if ($("btnCinemaDisc")) $("btnCinemaDisc").addEventListener("click", () => openDiscPlayer());
    if ($("btnCinemaScan")) $("btnCinemaScan").addEventListener("click", triggerScan);
    if ($("btnCfgCinemaScan")) $("btnCfgCinemaScan").addEventListener("click", triggerScan);
    if ($("btnCinemaEnrich")) $("btnCinemaEnrich").addEventListener("click", triggerEnrich);
    if ($("btnCfgCinemaEnrich")) $("btnCfgCinemaEnrich").addEventListener("click", triggerEnrich);

    if ($("cinemaClose")) $("cinemaClose").addEventListener("click", () => closePlayer());
    if ($("cinemaPlayerDlg")) {
      $("cinemaPlayerDlg").addEventListener("cancel", (ev) => {
        ev.preventDefault();
        closePlayer();
      });
    }
    if ($("cinemaTitle")) {
      $("cinemaTitle").addEventListener("change", () => {
        cState.currentTitleIndex = Number($("cinemaTitle").value);
        startHlsAt(0).catch(() => {});
      });
    }
    if ($("btnCinemaClearContinue")) {
      $("btnCinemaClearContinue").addEventListener("click", async () => {
        try {
          await api("/api/cinema/progress/clear", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({}),
          });
          await Promise.all([loadContinue(), loadItems()]);
        } catch (_e) {}
      });
    }
    if ($("cinemaRestart")) {
      $("cinemaRestart").addEventListener("click", () => {
        startHlsAt(0).catch(() => {});
      });
    }
    if ($("cinemaCast")) {
      $("cinemaCast").addEventListener("click", () => {
        if (cState.currentItem && bridge().openCastDialog) {
          bridge().openCastDialog({ cinemaItem: cState.currentItem });
        }
      });
    }
    if ($("cinemaAudio")) {
      $("cinemaAudio").addEventListener("change", () => {
        startHlsAt(currentAbsolutePosition()).catch(() => {});
      });
    }
    if ($("cinemaQuality")) {
      $("cinemaQuality").addEventListener("change", () => {
        startHlsAt(currentAbsolutePosition()).catch(() => {});
      });
    }
    if ($("cinemaChapter")) {
      $("cinemaChapter").addEventListener("change", () => {
        const target = Number($("cinemaChapter").value) || 0;
        startHlsAt(target).catch(() => {});
      });
    }
    if ($("cinemaSub")) {
      $("cinemaSub").addEventListener("change", applySubtitleTrack);
    }
    if ($("cinemaFull")) {
      $("cinemaFull").addEventListener("click", () => {
        const video = $("cinemaVideo");
        if (video && video.requestFullscreen) video.requestFullscreen().catch(() => {});
      });
    }
    if ($("cinemaVideo")) {
      $("cinemaVideo").addEventListener("pause", () => saveCurrentProgress());
    }
    if ($("cinemaEditBtn")) {
      $("cinemaEditBtn").addEventListener("click", () => {
        if (cState.currentItem) openEditDialog(cState.currentItem);
      });
    }
    if ($("cinemaTrashBtn")) {
      $("cinemaTrashBtn").addEventListener("click", () => {
        if (cState.currentItem) trashItem(cState.currentItem, { fromPlayer: true });
      });
    }
    if ($("cinemaEditForm")) {
      $("cinemaEditForm").addEventListener("submit", async (ev) => {
        if (ev.submitter && ev.submitter.value === "cancel") return;
        ev.preventDefault();
        if (!cState.editingItem) return;
        const yearRaw = $("ceYear").value.trim();
        const cats = Array.from($("ceCategories").querySelectorAll("input:checked")).map(
          (cb) => cb.value
        );
        try {
          const updated = await api(`/api/cinema/items/${cState.editingItem.id}/metadata`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              title: $("ceTitle").value.trim(),
              media_type: $("ceType").value,
              year: yearRaw ? Number(yearRaw) : null,
              clear_year: !yearRaw,
              director: $("ceDirector").value.trim(),
              overview: $("ceOverview").value.trim(),
              categories: cats,
              metadata_locked: $("ceLocked").checked,
            }),
          });
          $("cinemaEditDlg").close();
          if (cState.currentItem && cState.currentItem.id === updated.id) {
            cState.currentItem = updated;
            $("cinemaPlayerTitle").textContent = updated.title || "";
            $("cinemaPlayerOverview").textContent = updated.overview || "";
          }
          await loadView();
        } catch (err) {
          $("ceMsg").textContent = err.message || String(err);
        }
      });
    }

    document.addEventListener("keydown", (ev) => {
      const dlg = $("cinemaPlayerDlg");
      if (!dlg || !dlg.open) return;
      if ($("cinemaEditDlg") && $("cinemaEditDlg").open) return;
      if (["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)) return;
      const video = $("cinemaVideo");
      if (!video) return;
      if (ev.key === " ") {
        ev.preventDefault();
        if (video.paused) video.play().catch(() => {});
        else video.pause();
      } else if (ev.key === "f" || ev.key === "F") {
        ev.preventDefault();
        if (video.requestFullscreen) video.requestFullscreen().catch(() => {});
      } else if (ev.key === "ArrowRight") {
        ev.preventDefault();
        video.currentTime = Math.min(video.duration || video.currentTime + 10, video.currentTime + 10);
      } else if (ev.key === "ArrowLeft") {
        ev.preventDefault();
        video.currentTime = Math.max(0, video.currentTime - 10);
      }
    });

    window.addEventListener("beforeunload", () => {
      if (cState.sessionId && navigator.sendBeacon) {
        navigator.sendBeacon(`/api/cinema/stream/${cState.sessionId}/stop`, "");
      }
    });
  }

  bindEvents();

  window.GalerieCinema = {
    loadView: loadView,
    refresh: loadView,
    stopStream: stopStream,
    loadTrash: loadTrash,
    currentFileItem: () => {
      const dlg = $("cinemaPlayerDlg");
      const item = cState.currentItem;
      if (!item || !dlg || !dlg.open || item.source_type !== "file") return null;
      return item;
    },
  };
})();
