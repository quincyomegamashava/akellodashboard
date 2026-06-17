/**
 * Meeting Notes roadmap: decisions, meeting mode, scorecard, carry-forward suggestions, collab.
 */
(function () {
  const API = window.MN_API || window.MN && window.MN.API;

  const userOpts = Array.isArray(window.MN_USER_OPTS) ? window.MN_USER_OPTS.slice() : [];

  let decisionsCache = [];
  let liveEasyMDE = null;
  let meetingTimerStart = null;
  let meetingTimerElapsed = 0;
  let meetingTimerInterval = null;
  let activeAgendaIndex = -1;
  let meetingSocket = null;
  let boardObserver = null;
  let agendaSaveTimers = {};
  let agendaPanelWired = false;
  let agendaPanelTyping = false;

  function $(id) { return document.getElementById(id); }

  function meetingId() {
    if (window.MN && window.MN.meetingNoteId != null) return window.MN.meetingNoteId;
    const raw = window.MN_MEETING_NOTE_ID;
    if (typeof raw === "number" && !isNaN(raw)) return raw;
    if (typeof raw === "string" && /^\d+$/.test(raw)) return parseInt(raw, 10);
    return null;
  }

  function escapeHtml(s) {
    return String(s || "").replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function fetchJson(url, options) {
    return fetch(url, Object.assign({ credentials: "same-origin", headers: { Accept: "application/json" } }, options || {}));
  }

  function getFocusRows() {
    if (window.MN && Array.isArray(window.MN.focusRows) && window.MN.focusRows.length) {
      return window.MN.focusRows;
    }
    return Array.isArray(window.MN_FOCUS_ROWS) ? window.MN_FOCUS_ROWS : [];
  }

  function syncFocusRowCache(row) {
    if (!row || !row.id) return;
    const rows = getFocusRows().slice();
    const idx = rows.findIndex(function (r) { return r.id === row.id; });
    const entry = {
      id: row.id,
      platform: row.platform || "",
      focus_area: row.focus_area || "",
      discussion_notes: row.discussion_notes || "",
    };
    if (idx >= 0) rows[idx] = Object.assign({}, rows[idx], entry);
    else rows.push(entry);
    window.MN_FOCUS_ROWS = rows;
    if (window.MN) window.MN.focusRows = rows;
  }

  function findFocusRowByTitle(title) {
    const key = (title || "").trim().toLowerCase();
    if (!key) return null;
    return getFocusRows().find(function (r) {
      const first = (r.focus_area || r.platform || "").split("\n")[0].trim().toLowerCase();
      return first === key;
    }) || null;
  }

  function buildAgendaItems() {
    const raw = typeof window.MN_MEETING_AGENDA === "string" ? window.MN_MEETING_AGENDA : "";
    const rows = getFocusRows();
    if (!raw.trim()) {
      const seen = {};
      const items = [];
      rows.forEach(function (r) {
        const area = (r.focus_area || r.platform || "").split("\n")[0].trim();
        if (!area) return;
        const key = area.toLowerCase();
        if (seen[key]) return;
        seen[key] = true;
        items.push({ index: items.length, title: area, focusRowId: r.id, focusRow: r });
      });
      return items;
    }
    const lines = raw.split("\n").map(function (line) {
      return line.replace(/^\d+[\.\)]\s*/, "").trim();
    }).filter(Boolean);
    return lines.map(function (title, index) {
      const fr = findFocusRowByTitle(title);
      return { index: index, title: title, focusRowId: fr ? fr.id : null, focusRow: fr };
    });
  }

  function parseAgendaLines() {
    return buildAgendaItems().map(function (it) { return it.title; });
  }

  function getAgendaItem(index) {
    return buildAgendaItems().find(function (it) { return it.index === index; }) || null;
  }

  function setAgendaSaveHint(text) {
    const el = $("mn-live-agenda-save-hint");
    if (el) el.textContent = text || "";
  }

  function debounceAgendaSave(key, fn, ms) {
    if (agendaSaveTimers[key]) clearTimeout(agendaSaveTimers[key]);
    agendaSaveTimers[key] = setTimeout(fn, ms || 500);
  }

  function buildNumberedAgenda(titles) {
    return titles.map(function (t, i) { return (i + 1) + ". " + t; }).join("\n");
  }

  async function saveMeetingFields(payload) {
    const mid = meetingId();
    if (!mid) return null;
    const res = await fetchJson("/meeting-notes/api/meetings/" + mid, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Object.assign({ silent: true }, payload)),
    });
    if (!res.ok) return null;
    return res.json();
  }

  async function saveFocusRowFields(focusRowId, payload) {
    const url = (API && API.focusRowById)
      ? API.focusRowById(focusRowId)
      : "/meeting-notes/api/focus-rows/" + focusRowId;
    setAgendaSaveHint("Saving…");
    const res = await fetchJson(url, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Object.assign({}, payload, { silent: true })),
    });
    if (!res.ok) {
      setAgendaSaveHint("Error saving");
      return null;
    }
    const data = await res.json();
    syncFocusRowCache(data);
    setAgendaSaveHint("Saved");
    return data;
  }

  function rewriteAgendaLine(index, newTitle) {
    const items = buildAgendaItems();
    const titles = items.map(function (it, i) {
      return i === index ? (newTitle || "").trim() : it.title;
    }).filter(Boolean);
    const numbered = buildNumberedAgenda(titles);
    window.MN_MEETING_AGENDA = numbered;
    const meta = $("mn-meta-agenda");
    if (meta) meta.value = numbered;
    return numbered;
  }

  function updateFocusRowTitleInArea(focusArea, newTitle) {
    const lines = (focusArea || "").split("\n");
    if (lines.length) lines[0] = newTitle;
    else lines.push(newTitle);
    return lines.join("\n");
  }

  function getAgendaItemNotes(index) {
    const notes = window.MN_AGENDA_ITEM_NOTES;
    if (!notes || typeof notes !== "object") return "";
    return notes[String(index)] || "";
  }

  function setAgendaItemNotesLocal(index, text) {
    if (!window.MN_AGENDA_ITEM_NOTES || typeof window.MN_AGENDA_ITEM_NOTES !== "object") {
      window.MN_AGENDA_ITEM_NOTES = {};
    }
    window.MN_AGENDA_ITEM_NOTES[String(index)] = text || "";
  }

  function showLiveOverview() {
    activeAgendaIndex = -1;
    const overview = $("mn-live-overview-panel");
    const detail = $("mn-live-agenda-item-panel");
    if (overview) overview.classList.remove("d-none");
    if (detail) detail.classList.add("d-none");
    applyBoardFocusFilter(null);
    renderAgendaRail();
  }

  function populateAgendaItemPanel(item) {
    if (!item) return;
    const titleEl = $("mn-live-agenda-title");
    const platformEl = $("mn-live-agenda-platform");
    const focusEl = $("mn-live-agenda-focus");
    const notesEl = $("mn-live-agenda-notes");
    const linked = $("mn-live-agenda-linked-fields");
    const unlinked = $("mn-live-agenda-unlinked-actions");
    if (titleEl) titleEl.value = item.title || "";
    const hasRow = !!item.focusRowId;
    if (linked) linked.classList.toggle("d-none", !hasRow);
    if (unlinked) unlinked.classList.toggle("d-none", hasRow);
    if (hasRow && item.focusRow) {
      if (platformEl) platformEl.value = item.focusRow.platform || "";
      if (focusEl) focusEl.value = item.focusRow.focus_area || "";
      if (notesEl) notesEl.value = item.focusRow.discussion_notes || "";
    } else {
      if (platformEl) platformEl.value = "";
      if (focusEl) focusEl.value = "";
      if (notesEl) notesEl.value = getAgendaItemNotes(item.index);
    }
    renderAgendaItemTasks(item.focusRowId);
    applyBoardFocusFilter(item.focusRowId);
  }

  function showAgendaItemDetail(index) {
    activeAgendaIndex = index;
    const overview = $("mn-live-overview-panel");
    const detail = $("mn-live-agenda-item-panel");
    if (overview) overview.classList.add("d-none");
    if (detail) detail.classList.remove("d-none");
    const item = getAgendaItem(index);
    populateAgendaItemPanel(item);
    renderAgendaRail();
    const notesEl = $("mn-live-agenda-notes");
    if (notesEl) notesEl.focus();
  }

  function renderAgendaItemTasks(focusRowId) {
    const host = $("mn-live-agenda-tasks");
    if (!host) return;
    if (!focusRowId) {
      host.innerHTML = '<p class="text-muted small mb-0">Link or create a focus row to attach tasks.</p>';
      return;
    }
    const items = (window.MN && window.MN.getItemsCache) ? window.MN.getItemsCache() : [];
    const related = items.filter(function (it) { return it.focus_row_id === focusRowId; });
    if (!related.length) {
      host.innerHTML = '<p class="text-muted small mb-0">No action items for this topic yet.</p>';
      return;
    }
    const statusColors = { open: "#94a3b8", in_progress: "#f59e0b", done: "#22c55e" };
    host.innerHTML = related.map(function (it) {
      const title = (it.task_title || it.call_to_action || "Untitled").split("\n")[0];
      const color = statusColors[it.status] || statusColors.open;
      return (
        '<button type="button" class="mn-live-agenda-task-chip" data-item-id="' + it.id + '">' +
        '<span class="d-flex align-items-center gap-2">' +
        '<span class="mn-task-status-dot" style="background:' + color + '"></span>' +
        "<span>" + escapeHtml(title) + "</span></span></button>"
      );
    }).join("");
    host.querySelectorAll(".mn-live-agenda-task-chip").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const id = parseInt(btn.getAttribute("data-item-id"), 10);
        if (!id || !window.MN || !window.MN.openTaskPanel) return;
        const items = window.MN.getItemsCache ? window.MN.getItemsCache() : [];
        const item = items.find(function (it) { return it.id === id; });
        window.MN.openTaskPanel(item || id, false);
      });
    });
  }

  function applyBoardFocusFilter(focusRowId) {
    const board = $("mn-board");
    if (!board) return;
    if (!focusRowId || activeAgendaIndex < 0) {
      board.classList.remove("mn-board-focus-filter");
      board.querySelectorAll(".mn-task-card").forEach(function (c) {
        c.classList.remove("mn-task-card-focus-match");
      });
      return;
    }
    board.classList.add("mn-board-focus-filter");
    board.querySelectorAll(".mn-task-card").forEach(function (card) {
      const frId = parseInt(card.getAttribute("data-focus-row-id"), 10);
      card.classList.toggle("mn-task-card-focus-match", frId === focusRowId);
    });
  }

  function refreshAgendaItemPanelIfOpen(force) {
    if (activeAgendaIndex < 0) return;
    if (!force && agendaPanelTyping) return;
    const item = getAgendaItem(activeAgendaIndex);
    if (item) populateAgendaItemPanel(item);
  }

  function getActiveAgendaFocusRowId() {
    if (activeAgendaIndex < 0) return null;
    const item = getAgendaItem(activeAgendaIndex);
    return item && item.focusRowId ? item.focusRowId : null;
  }

  async function createFocusRowFromAgendaItem(index) {
    const item = getAgendaItem(index);
    if (!item) return;
    const mid = meetingId();
    if (!mid) return;
    setAgendaSaveHint("Creating…");
    const res = await fetchJson("/meeting-notes/api/meetings/" + mid + "/focus-rows", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        platform: "General",
        focus_area: item.title,
      }),
    });
    if (!res.ok) {
      setAgendaSaveHint("Error");
      return;
    }
    const row = await res.json();
    syncFocusRowCache(row);
    rewriteAgendaLine(index, item.title);
    await saveMeetingFields({ agenda: window.MN_MEETING_AGENDA });
    showAgendaItemDetail(index);
  }

  async function linkAgendaItemToFocusRow(index, focusRowId) {
    if (!focusRowId) return;
    const item = getAgendaItem(index);
    if (!item) return;
    const row = getFocusRows().find(function (r) { return r.id === focusRowId; });
    if (!row) return;
    const title = (row.focus_area || row.platform || "").split("\n")[0].trim() || item.title;
    rewriteAgendaLine(index, title);
    await saveMeetingFields({ agenda: window.MN_MEETING_AGENDA });
    showAgendaItemDetail(index);
  }

  function initAgendaItemPanel() {
    if (agendaPanelWired) return;
    agendaPanelWired = true;

    const backBtn = $("mn-live-back-overview");
    if (backBtn) backBtn.addEventListener("click", showLiveOverview);

    const titleEl = $("mn-live-agenda-title");
    if (titleEl) {
      titleEl.addEventListener("input", function () {
        agendaPanelTyping = true;
        const idx = activeAgendaIndex;
        debounceAgendaSave("title", async function () {
          const item = getAgendaItem(idx);
          if (!item) return;
          const newTitle = titleEl.value.trim();
          rewriteAgendaLine(idx, newTitle);
          await saveMeetingFields({ agenda: window.MN_MEETING_AGENDA });
          if (item.focusRowId) {
            const fr = getFocusRows().find(function (r) { return r.id === item.focusRowId; });
            const focusArea = updateFocusRowTitleInArea(fr ? fr.focus_area : "", newTitle);
            await saveFocusRowFields(item.focusRowId, { focus_area: focusArea });
          }
          renderAgendaRail();
          agendaPanelTyping = false;
        });
      });
    }

    const platformEl = $("mn-live-agenda-platform");
    if (platformEl) {
      platformEl.addEventListener("input", function () {
        agendaPanelTyping = true;
        const idx = activeAgendaIndex;
        debounceAgendaSave("platform", async function () {
          const item = getAgendaItem(idx);
          if (!item || !item.focusRowId) return;
          await saveFocusRowFields(item.focusRowId, { platform: platformEl.value.trim() });
          agendaPanelTyping = false;
        });
      });
    }

    const focusEl = $("mn-live-agenda-focus");
    if (focusEl) {
      focusEl.addEventListener("input", function () {
        agendaPanelTyping = true;
        const idx = activeAgendaIndex;
        debounceAgendaSave("focus", async function () {
          const item = getAgendaItem(idx);
          if (!item || !item.focusRowId) return;
          await saveFocusRowFields(item.focusRowId, { focus_area: focusEl.value });
          const firstLine = (focusEl.value || "").split("\n")[0].trim();
          if (firstLine && firstLine !== item.title) {
            rewriteAgendaLine(idx, firstLine);
            await saveMeetingFields({ agenda: window.MN_MEETING_AGENDA });
            if (titleEl) titleEl.value = firstLine;
            renderAgendaRail();
          }
          agendaPanelTyping = false;
        });
      });
    }

    const notesEl = $("mn-live-agenda-notes");
    if (notesEl) {
      notesEl.addEventListener("input", function () {
        agendaPanelTyping = true;
        const idx = activeAgendaIndex;
        debounceAgendaSave("notes", async function () {
          const item = getAgendaItem(idx);
          if (!item) return;
          if (item.focusRowId) {
            await saveFocusRowFields(item.focusRowId, { discussion_notes: notesEl.value });
          } else {
            setAgendaSaveHint("Saving…");
            setAgendaItemNotesLocal(idx, notesEl.value);
            await saveMeetingFields({ agenda_item_notes: window.MN_AGENDA_ITEM_NOTES });
            setAgendaSaveHint("Saved");
          }
          agendaPanelTyping = false;
        });
      });
    }

    const createRowBtn = $("mn-live-agenda-create-row");
    if (createRowBtn) {
      createRowBtn.addEventListener("click", function () {
        createFocusRowFromAgendaItem(activeAgendaIndex).catch(function () {
          alert("Could not create focus row");
        });
      });
    }

    const linkGo = $("mn-live-agenda-link-go");
    const linkSel = $("mn-live-agenda-link-select");
    if (linkGo && linkSel) {
      linkGo.addEventListener("click", function () {
        const rowId = parseInt(linkSel.value, 10);
        if (!rowId) return;
        linkAgendaItemToFocusRow(activeAgendaIndex, rowId).catch(function () {
          alert("Could not link focus row");
        });
      });
    }

    const capGo = $("mn-live-agenda-capture-go");
    const capInput = $("mn-live-agenda-capture-input");
    if (capGo && capInput) {
      async function submitAgendaCapture() {
        const text = capInput.value.trim();
        if (!text) return;
        try {
          await submitAgendaScopedCapture(text);
          capInput.value = "";
        } catch (e) {
          alert((e && e.message) ? e.message : "Could not capture item");
        }
      }
      capGo.addEventListener("click", submitAgendaCapture);
      capInput.addEventListener("keydown", function (e) {
        if (e.key === "Enter") { e.preventDefault(); submitAgendaCapture(); }
      });
    }
  }

  async function submitAgendaScopedCapture(text) {
    const raw = (text || "").trim();
    if (!raw) return;
    if (/^(>>|decision:)/i.test(raw)) {
      const body = raw.replace(/^(>>|decision:)\s*/i, "").trim();
      if (!body) return;
      await createDecision(body);
      return;
    }
    let focusRowId = getActiveAgendaFocusRowId();
    if (!focusRowId && activeAgendaIndex >= 0) {
      await createFocusRowFromAgendaItem(activeAgendaIndex);
      focusRowId = getActiveAgendaFocusRowId();
    }
    if (typeof window.MN_submitQuickCapture === "function") {
      await window.MN_submitQuickCapture(raw, { focusRowId: focusRowId });
      renderAgendaItemTasks(focusRowId);
      if (window.MN && window.MN.refreshItems) await window.MN.refreshItems();
      return;
    }
    await submitLiveQuickCapture(raw);
  }

  function ownerOptionsHtml(selectedId) {
    return '<option value="">Team</option>' + userOpts.map(function (u) {
      const sel = selectedId && String(selectedId) === String(u.id) ? " selected" : "";
      return '<option value="' + u.id + '"' + sel + ">" + escapeHtml(u.label) + "</option>";
    }).join("");
  }

  function renderDecisionCard(d, compact) {
    const ownerSel = compact
      ? '<span class="mn-decision-owner-badge">' + escapeHtml(d.owner_name || "Team") + "</span>"
      : '<select class="form-select form-select-sm mn-decision-owner" data-id="' + d.id + '">' +
        ownerOptionsHtml(d.owner_user_id) + "</select>";
    const dateVal = d.decided_at ? String(d.decided_at).slice(0, 10) : "";
    return (
      '<div class="mn-decision-card' + (compact ? " mn-decision-card-compact" : "") + '" data-decision-id="' + d.id + '">' +
      '<div class="mn-decision-card-head">' +
      ownerSel +
      '<input type="date" class="form-control form-control-sm mn-decision-date" data-id="' + d.id + '" value="' + escapeHtml(dateVal) + '" />' +
      (compact ? "" :
        '<button type="button" class="btn btn-sm mn-btn-ghost mn-decision-delete" data-id="' + d.id + '" title="Delete"><i class="fas fa-trash"></i></button>') +
      "</div>" +
      '<div class="mn-decision-body" contenteditable="true" data-id="' + d.id + '">' + escapeHtml(d.body) + "</div>" +
      "</div>"
    );
  }

  function wireDecisionCards(root) {
    if (!root) return;
    root.querySelectorAll(".mn-decision-owner").forEach(function (sel) {
      sel.addEventListener("change", function () {
        updateDecision(parseInt(sel.getAttribute("data-id"), 10), {
          owner_user_id: sel.value ? parseInt(sel.value, 10) : null,
        });
      });
    });
    root.querySelectorAll(".mn-decision-date").forEach(function (inp) {
      inp.addEventListener("change", function () {
        updateDecision(parseInt(inp.getAttribute("data-id"), 10), { decided_at: inp.value || null });
      });
    });
    root.querySelectorAll(".mn-decision-body").forEach(function (el) {
      el.addEventListener("blur", function () {
        const body = (el.textContent || "").trim();
        const id = parseInt(el.getAttribute("data-id"), 10);
        const prev = decisionsCache.find(function (d) { return d.id === id; });
        if (prev && prev.body !== body) updateDecision(id, { body: body });
      });
    });
    root.querySelectorAll(".mn-decision-delete").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const id = parseInt(btn.getAttribute("data-id"), 10);
        if (!confirm("Delete this decision?")) return;
        deleteDecision(id);
      });
    });
  }

  function renderDecisionsList(host, rows, compact) {
    if (!host) return;
    if (!rows.length) {
      host.innerHTML = compact
        ? '<p class="text-muted small mb-0">No decisions yet.</p>'
        : '<div class="mn-decisions-empty"><i class="fas fa-gavel mb-2"></i><p class="small text-muted mb-2">No decisions recorded yet.</p><button type="button" class="btn btn-sm mn-btn-primary" id="mn-decision-empty-cta">Record first decision</button></div>';
      const cta = $("mn-decision-empty-cta");
      if (cta) cta.addEventListener("click", function () {
        showDecisionsTab();
        const inp = $("mn-decision-input");
        if (inp) inp.focus();
      });
      return;
    }
    host.innerHTML = rows.map(function (d) { return renderDecisionCard(d, !!compact); }).join("");
    wireDecisionCards(host);
  }

  function renderLiveDecisionsStrip() {
    const host = $("mn-live-decisions-list");
    if (!host) return;
    renderDecisionsList(host, decisionsCache.slice(0, 3), true);
  }

  function showDecisionsTab() {
    document.querySelectorAll("[data-mn-detail-tab]").forEach(function (btn) {
      if (btn.getAttribute("data-mn-detail-tab") === "decisions") btn.click();
    });
  }

  async function loadDecisions() {
    const host = $("mn-decisions-list");
    const mid = meetingId();
    if (!mid) return;
    try {
      const url = (API && API.decisions) ? API.decisions(mid) : "/meeting-notes/api/meetings/" + mid + "/decisions";
      const res = await fetchJson(url);
      if (!res.ok) throw new Error("Failed to load");
      const rows = await res.json();
      decisionsCache = Array.isArray(rows) ? rows : [];
      if (host) renderDecisionsList(host, decisionsCache, false);
      renderLiveDecisionsStrip();
    } catch (e) {
      if (host) host.innerHTML = '<p class="text-danger small">Could not load decisions.</p>';
    }
  }

  async function createDecision(body, ownerId) {
    const trimmed = (body || "").trim();
    const mid = meetingId();
    if (!trimmed || !mid) return null;
    const res = await fetchJson("/meeting-notes/api/meetings/" + mid + "/decisions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body: trimmed, owner_user_id: ownerId || undefined }),
    });
    if (!res.ok) {
      const err = await res.json().catch(function () { return {}; });
      throw new Error(err.error || "Could not save decision");
    }
    const created = await res.json();
    await loadDecisions();
    return created;
  }

  async function updateDecision(id, payload) {
    const res = await fetchJson("/meeting-notes/api/decisions/" + id, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error("Update failed");
    await loadDecisions();
  }

  async function deleteDecision(id) {
    const res = await fetchJson("/meeting-notes/api/decisions/" + id, { method: "DELETE" });
    if (!res.ok) throw new Error("Delete failed");
    await loadDecisions();
  }

  window.MN_createDecision = createDecision;
  window.MN_loadDecisions = loadDecisions;
  window.MN_showDecisionsTab = showDecisionsTab;

  async function loadCarrySuggestions() {
    const banner = $("mn-carry-suggestions");
    const mid = meetingId();
    if (!banner || !mid) return;
    try {
      const data = await fetchJson("/meeting-notes/api/meetings/" + mid + "/carry-forward/suggestions").then(function (r) { return r.json(); });
      const items = data.suggestions || [];
      if (!items.length) { banner.classList.add("d-none"); return; }
      banner.classList.remove("d-none");
      banner.innerHTML = '<strong class="small">Suggested carry-forward</strong> (' + items.length + ' open items from prior meeting) ' +
        '<button type="button" class="btn btn-sm btn-outline-primary ms-2" id="mn-carry-suggestions-go">Review</button>';
      const go = $("mn-carry-suggestions-go");
      if (go) go.addEventListener("click", function () {
        const modal = document.getElementById("mnCarryForwardModal");
        if (modal && window.bootstrap) new bootstrap.Modal(modal).show();
      });
    } catch (e) { banner.classList.add("d-none"); }
  }

  function formatTimer(ms) {
    const s = Math.floor(ms / 1000);
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    return [h, m, sec].map(function (n) { return String(n).padStart(2, "0"); }).join(":");
  }

  function timerStorageKey() {
    return "mn_meeting_timer_" + meetingId();
  }

  function loadTimerState() {
    try {
      const raw = sessionStorage.getItem(timerStorageKey());
      if (raw) meetingTimerElapsed = parseInt(raw, 10) || 0;
    } catch (e) { meetingTimerElapsed = 0; }
  }

  function saveTimerState() {
    try { sessionStorage.setItem(timerStorageKey(), String(meetingTimerElapsed)); } catch (e) { /* ignore */ }
  }

  function updateTimerDisplay() {
    const el = $("mn-live-timer");
    if (!el) return;
    let ms = meetingTimerElapsed;
    if (meetingTimerStart) ms += Date.now() - meetingTimerStart;
    el.textContent = formatTimer(ms);
  }

  function startMeetingTimer() {
    if (meetingTimerInterval) return;
    meetingTimerStart = Date.now();
    meetingTimerInterval = setInterval(updateTimerDisplay, 1000);
    updateTimerDisplay();
  }

  function stopMeetingTimer() {
    if (meetingTimerStart) {
      meetingTimerElapsed += Date.now() - meetingTimerStart;
      meetingTimerStart = null;
      saveTimerState();
    }
    if (meetingTimerInterval) {
      clearInterval(meetingTimerInterval);
      meetingTimerInterval = null;
    }
    updateTimerDisplay();
  }

  function renderAgendaRail() {
    const rail = $("mn-live-agenda-rail");
    const progress = $("mn-live-agenda-progress");
    const items = buildAgendaItems();
    if (!rail) return;
    if (!items.length) {
      rail.innerHTML = '<p class="small text-muted px-2 mb-2">Add agenda in Meeting details</p>' +
        '<button type="button" class="btn btn-sm mn-btn-ghost mx-2" id="mn-live-agenda-open-details">Open meeting details</button>';
      const openBtn = $("mn-live-agenda-open-details");
      if (openBtn) openBtn.addEventListener("click", function () {
        const modal = document.getElementById("mnMeetingDetailsModal");
        if (modal && window.bootstrap) bootstrap.Modal.getOrCreateInstance(modal).show();
      });
      if (progress) progress.textContent = "";
      return;
    }
    const overviewActive = activeAgendaIndex < 0;
    let html =
      '<button type="button" class="mn-agenda-item mn-agenda-overview' + (overviewActive ? " active" : "") + '" data-idx="-1">' +
      '<span class="mn-agenda-num"><i class="fas fa-home"></i></span>' +
      '<span class="mn-agenda-text">Meeting overview</span></button>';
    html += items.map(function (item) {
      return '<button type="button" class="mn-agenda-item' + (item.index === activeAgendaIndex ? " active" : "") + '" data-idx="' + item.index + '">' +
        '<span class="mn-agenda-num">' + (item.index + 1) + "</span>" +
        '<span class="mn-agenda-text">' + escapeHtml(item.title) + "</span></button>";
    }).join("");
    rail.innerHTML = html;
    rail.querySelectorAll(".mn-agenda-item").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const idx = parseInt(btn.getAttribute("data-idx"), 10);
        if (idx < 0) showLiveOverview();
        else showAgendaItemDetail(idx);
        if (progress) {
          if (activeAgendaIndex < 0) progress.textContent = "Meeting overview";
          else progress.textContent = "Agenda item " + (activeAgendaIndex + 1) + " of " + items.length;
        }
      });
    });
    if (progress) {
      if (activeAgendaIndex < 0) progress.textContent = "Meeting overview";
      else progress.textContent = "Agenda item " + (activeAgendaIndex + 1) + " of " + items.length;
    }
  }

  function focusLiveNotes() {
    if (liveEasyMDE && liveEasyMDE.codemirror) {
      liveEasyMDE.codemirror.focus();
      return;
    }
    const ta = $("mn-live-notes");
    if (ta) ta.focus();
  }

  function initLiveNotesEditor() {
    const ta = $("mn-live-notes");
    if (!ta || liveEasyMDE) return;
    if (typeof EasyMDE !== "undefined") {
      liveEasyMDE = new EasyMDE({
        element: ta,
        spellChecker: false,
        minHeight: "200px",
        toolbar: ["bold", "italic", "heading", "|", "unordered-list", "ordered-list", "|", "preview"],
      });
    }
  }

  function getLiveNotesValue() {
    if (liveEasyMDE) return liveEasyMDE.value();
    const ta = $("mn-live-notes");
    return ta ? ta.value : "";
  }

  function setLiveNotesValue(val) {
    if (liveEasyMDE) liveEasyMDE.value(val || "");
    else {
      const ta = $("mn-live-notes");
      if (ta) ta.value = val || "";
    }
    const meta = $("mn-meta-summary");
    if (meta) meta.value = val || "";
    if (window.easyMDE) window.easyMDE.value(val || "");
    window.MN_MEETING_SUMMARY = val || "";
  }

  function syncLiveBoard() {
    const liveBoard = $("mn-live-board");
    const mainBoard = $("mn-board");
    if (!liveBoard || !mainBoard) return;
    liveBoard.innerHTML = mainBoard.innerHTML;
    liveBoard.querySelectorAll(".mn-task-card").forEach(function (card) {
      card.addEventListener("click", function () {
        const id = parseInt(card.getAttribute("data-item-id"), 10);
        if (id && window.MN && window.MN.openTaskPanel) window.MN.openTaskPanel(id, false);
      });
    });
    const focusRowId = getActiveAgendaFocusRowId();
    if (focusRowId && activeAgendaIndex >= 0) {
      liveBoard.classList.add("mn-board-focus-filter");
      liveBoard.querySelectorAll(".mn-task-card").forEach(function (card) {
        const frId = parseInt(card.getAttribute("data-focus-row-id"), 10);
        card.classList.toggle("mn-task-card-focus-match", frId === focusRowId);
      });
    } else {
      liveBoard.classList.remove("mn-board-focus-filter");
    }
  }

  function watchMainBoard() {
    const mainBoard = $("mn-board");
    if (!mainBoard || boardObserver) return;
    boardObserver = new MutationObserver(function () {
      if ($("mn-page-detail") && $("mn-page-detail").classList.contains("mn-meeting-mode")) {
        syncLiveBoard();
      }
    });
    boardObserver.observe(mainBoard, { childList: true, subtree: true });
  }

  function isMeetingModeOn() {
    const page = $("mn-page-detail");
    return page && page.classList.contains("mn-meeting-mode");
  }

  function applyMeetingModeShell(on) {
    const shell = $("mn-meeting-mode-shell");
    const page = $("mn-page-detail");
    const tasksTab = $("mn-tab-tasks");
    const viewPills = document.querySelector(".mn-view-pills.mb-2.d-none.d-md-flex");
    const btn = $("mn-btn-meeting-mode");
    if (!shell || !page) return;

    shell.classList.toggle("d-none", !on);
    shell.setAttribute("aria-hidden", on ? "false" : "true");
    page.classList.toggle("mn-meeting-mode", on);
    if (tasksTab) tasksTab.classList.toggle("d-none", on);
    if (viewPills) viewPills.classList.toggle("d-none", on);
    if (btn) {
      btn.classList.toggle("active", on);
      btn.textContent = on ? "Exit meeting mode" : "Meeting mode";
    }

    if (on) {
      loadTimerState();
      startMeetingTimer();
      activeAgendaIndex = -1;
      initAgendaItemPanel();
      renderAgendaRail();
      showLiveOverview();
      initLiveNotesEditor();
      setLiveNotesValue(typeof window.MN_MEETING_SUMMARY === "string" ? window.MN_MEETING_SUMMARY : "");
      syncLiveBoard();
      setTimeout(syncLiveBoard, 400);
      renderLiveDecisionsStrip();
      loadDecisions();
    } else {
      stopMeetingTimer();
      showLiveOverview();
    }
  }

  async function submitLiveQuickCapture(text) {
    const raw = (text || "").trim();
    if (!raw) return;
    if (/^(>>|decision:)/i.test(raw)) {
      const body = raw.replace(/^(>>|decision:)\s*/i, "").trim();
      if (!body) return;
      await createDecision(body);
      return;
    }
    if (typeof window.MN_submitQuickCapture === "function") {
      await window.MN_submitQuickCapture(raw);
      return;
    }
    const mainInput = $("mn-quick-capture-input");
    const mainGo = $("mn-quick-capture-go");
    if (mainInput) mainInput.value = raw;
    if (mainGo) mainGo.click();
  }

  function initMeetingMode() {
    const btn = $("mn-btn-meeting-mode");
    const shell = $("mn-page-detail");
    const mid = meetingId();
    if (!btn || !shell || !mid) return;
    const key = "mn_meeting_mode_" + mid;

    function apply(on) {
      sessionStorage.setItem(key, on ? "1" : "0");
      applyMeetingModeShell(on);
    }

    apply(sessionStorage.getItem(key) === "1");
    btn.addEventListener("click", function () {
      apply(!isMeetingModeOn());
    });

    const exitBtn = $("mn-live-btn-exit");
    if (exitBtn) exitBtn.addEventListener("click", function () { apply(false); });

    const saveLive = $("mn-live-btn-save");
    if (saveLive) saveLive.addEventListener("click", function () {
      setLiveNotesValue(getLiveNotesValue());
      const sm = $("mn-btn-save-meta");
      if (sm) sm.click();
    });

    const taskBtn = $("mn-live-btn-task");
    if (taskBtn) taskBtn.addEventListener("click", function () {
      if (activeAgendaIndex >= 0) {
        const inp = $("mn-live-agenda-capture-input");
        if (inp) inp.focus();
        return;
      }
      const inp = $("mn-live-quick-capture-input");
      if (inp) inp.focus();
    });

    const decisionBtn = $("mn-live-btn-decision");
    const recordBtn = $("mn-live-record-decision");
    function promptDecision() {
      const text = prompt("Record decision:");
      if (!text || !text.trim()) return;
      createDecision(text.trim()).catch(function () { alert("Could not save decision"); });
    }
    if (decisionBtn) decisionBtn.addEventListener("click", promptDecision);
    if (recordBtn) recordBtn.addEventListener("click", promptDecision);

    const extractBtn = $("mn-live-btn-extract");
    if (extractBtn) extractBtn.addEventListener("click", function () {
      const ai = $("mn-btn-ai-extract");
      if (ai) ai.click();
    });

    const pdfBtn = $("mn-live-btn-pdf");
    if (pdfBtn) pdfBtn.addEventListener("click", function () {
      const pdf = $("mn-btn-export-pdf");
      if (pdf) pdf.click();
    });

    const liveGo = $("mn-live-quick-capture-go");
    const liveInput = $("mn-live-quick-capture-input");
    if (liveGo && liveInput) {
      async function submitLiveCapture() {
        const text = liveInput.value.trim();
        if (!text) return;
        try {
          await submitLiveQuickCapture(text);
          liveInput.value = "";
        } catch (e) {
          alert((e && e.message) ? e.message : "Could not capture item");
        }
      }
      liveGo.addEventListener("click", submitLiveCapture);
      liveInput.addEventListener("keydown", function (e) {
        if (e.key === "Enter") { e.preventDefault(); submitLiveCapture(); }
      });
    }

    document.addEventListener("keydown", function (e) {
      if (!isMeetingModeOn()) return;
      if (e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.isContentEditable)) return;
      if (e.key === "d" || e.key === "D") { e.preventDefault(); promptDecision(); }
      if (e.key === "n" || e.key === "N") { e.preventDefault(); focusLiveNotes(); }
      if (e.key === "t" || e.key === "T") {
        e.preventDefault();
        if (activeAgendaIndex >= 0) {
          const inp = $("mn-live-agenda-capture-input");
          if (inp) inp.focus();
        } else {
          const inp = $("mn-live-quick-capture-input");
          if (inp) inp.focus();
        }
      }
    });

    if (window.MN && window.MN.refreshItems) {
      const origRefresh = window.MN.refreshItems;
      window.MN.refreshItems = function () {
        const p = origRefresh.apply(this, arguments);
        function after() {
          if (!isMeetingModeOn()) return;
          syncLiveBoard();
          if (activeAgendaIndex >= 0) {
            renderAgendaItemTasks(getActiveAgendaFocusRowId());
            applyBoardFocusFilter(getActiveAgendaFocusRowId());
          }
        }
        if (p && typeof p.then === "function") return p.then(function (r) { after(); return r; });
        after();
        return p;
      };
    }
    watchMainBoard();
  }

  function initPresence() {
    const mid = meetingId();
    if (!mid || typeof io === "undefined") return;
    try {
      meetingSocket = io("/meeting-notes");
      meetingSocket.emit("presence_join", { meeting_id: mid, username: window.MN_CURRENT_USER || "User" });
      meetingSocket.emit("join_meeting", { meeting_id: mid });

      function renderPresence(users, targetId) {
        const el = $(targetId);
        if (!el || !users) return;
        el.innerHTML = users.map(function (u) {
          const name = String(u || "");
          return '<span class="mn-presence-chip" title="' + escapeHtml(name) + '">' + escapeHtml(name.slice(0, 2).toUpperCase()) + "</span>";
        }).join(" ");
      }

      meetingSocket.on("presence_update", function (data) {
        renderPresence(data.users, "mn-presence-avatars");
        renderPresence(data.users, "mn-presence-avatars-live");
      });

      meetingSocket.on("decision_updated", function () {
        loadDecisions();
      });

      meetingSocket.on("focus_row_updated", function () {
        fetchJson("/meeting-notes/api/meetings/" + mid + "/focus-rows")
          .then(function (r) { return r.ok ? r.json() : []; })
          .then(function (rows) {
            if (Array.isArray(rows)) {
              window.MN_FOCUS_ROWS = rows;
              if (window.MN) window.MN.focusRows = rows;
            }
            refreshAgendaItemPanelIfOpen(false);
            renderAgendaRail();
          })
          .catch(function () { /* ignore */ });
      });

      meetingSocket.on("agenda_updated", function (data) {
        if (data && data.agenda_item_notes && typeof data.agenda_item_notes === "object") {
          window.MN_AGENDA_ITEM_NOTES = data.agenda_item_notes;
        }
        refreshAgendaItemPanelIfOpen(false);
        renderAgendaRail();
      });
    } catch (e) { /* ignore */ }
  }

  async function loadExtendedAnalytics() {
    const el = $("mn-hub-analytics");
    if (!el || !window.MN_HUB_MODE) return;
    try {
      const data = await fetchJson("/meeting-notes/api/hub/analytics/extended").then(function (r) { return r.json(); });
      let html =
        '<span class="mn-analytics-chip">' + (data.completion_rate || 0) + "% complete</span>" +
        '<span class="mn-analytics-chip">' + (data.overdue_items || 0) + " overdue</span>";
      (data.per_user || []).slice(0, 3).forEach(function (u) {
        html += '<span class="mn-analytics-chip" title="Avg days late">' + escapeHtml(u.name) + ": " + u.completion_rate + "%</span>";
      });
      el.innerHTML = html;
    } catch (e) { /* fallback handled by mn-extensions */ }
  }

  function switchDetailTab(t) {
    document.querySelectorAll(".mn-detail-tab-pane").forEach(function (p) {
      if (p.id === "mn-tab-tasks") {
        p.classList.toggle("d-none", t !== "tasks" && t !== "filters");
      } else {
        p.classList.toggle("d-none", p.id !== "mn-tab-" + t);
      }
    });
    document.querySelectorAll("[data-mn-detail-tab]").forEach(function (b) {
      b.classList.toggle("active", b.getAttribute("data-mn-detail-tab") === t);
    });
    if (t === "decisions") loadDecisions();
    if (t === "filters") {
      const sheet = document.getElementById("mn-filter-sheet");
      if (sheet && window.bootstrap) bootstrap.Offcanvas.getOrCreateInstance(sheet).show();
    }
  }

  function initDecisionsTab() {
    document.querySelectorAll("[data-mn-detail-tab]").forEach(function (tab) {
      tab.addEventListener("click", function () {
        switchDetailTab(tab.getAttribute("data-mn-detail-tab"));
      });
    });
    const addBtn = $("mn-decision-add");
    if (addBtn) addBtn.addEventListener("click", async function () {
      const input = $("mn-decision-input");
      const body = (input && input.value || "").trim();
      if (!body) return;
      try {
        await createDecision(body);
        if (input) input.value = "";
      } catch (e) {
        alert("Could not save decision");
      }
    });
    const decisionInput = $("mn-decision-input");
    if (decisionInput) {
      decisionInput.addEventListener("keydown", function (e) {
        if (e.key === "Enter") { e.preventDefault(); addBtn && addBtn.click(); }
      });
    }
    const filterSheet = document.getElementById("mn-filter-sheet");
    if (filterSheet) {
      filterSheet.addEventListener("hidden.bs.offcanvas", function () {
        const active = document.querySelector("[data-mn-detail-tab].active");
        if (active && active.getAttribute("data-mn-detail-tab") === "filters") {
          switchDetailTab("tasks");
        }
      });
    }
  }

  function initRoadmap() {
    const mid = meetingId();
    if (!mid) return;
    loadDecisions();
    loadCarrySuggestions();
    initMeetingMode();
    initPresence();
    initDecisionsTab();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      initRoadmap();
      if (window.MN_HUB_MODE) loadExtendedAnalytics();
    });
  } else {
    initRoadmap();
    if (window.MN_HUB_MODE) loadExtendedAnalytics();
  }

  window.MN_API = window.MN_API || {};
  window.MN_API.decisions = function (mid) { return "/meeting-notes/api/meetings/" + mid + "/decisions"; };
})();
