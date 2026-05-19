/**
 * Meeting notes: filters, inline table, FullCalendar, Frappe Gantt.
 * Globals: MN_MEETING_NOTE_ID, MN_USER_OPTS, MN_FOCUS_ROWS, MN_IS_ADMIN
 */
(function () {
  const API = {
    items: "/meeting-notes/api/action-items",
    cal: "/meeting-notes/api/calendar-events",
    gantt: "/meeting-notes/api/gantt-tasks",
    activity: function (mid) { return "/meeting-notes/api/meetings/" + mid + "/activity"; },
    actionItem: function (id) { return "/meeting-notes/api/action-items/" + id; },
    createItem: function (rowId) { return "/meeting-notes/api/focus-rows/" + rowId + "/action-items"; },
    focusRow: function (meetingId) { return "/meeting-notes/api/meetings/" + meetingId + "/focus-rows"; },
    focusRowById: function (id) { return "/meeting-notes/api/focus-rows/" + id; },
    meeting: function (id) { return "/meeting-notes/api/meetings/" + id; },
    duplicateMeeting: function (id) { return "/meeting-notes/api/meetings/" + id + "/duplicate"; },
    carryForward: function (id) { return "/meeting-notes/api/meetings/" + id + "/carry-forward"; },
    carryForwardPreview: function (id, fromId) {
      return "/meeting-notes/api/meetings/" + id + "/carry-forward/preview?from_meeting_id=" + encodeURIComponent(fromId);
    },
    bulkItems: "/meeting-notes/api/action-items/bulk",
  };

  function resolveMeetingNoteId() {
    if (typeof MN_MEETING_NOTE_ID === "number" && !isNaN(MN_MEETING_NOTE_ID)) {
      return MN_MEETING_NOTE_ID;
    }
    if (typeof MN_MEETING_NOTE_ID === "string" && /^\d+$/.test(MN_MEETING_NOTE_ID)) {
      return parseInt(MN_MEETING_NOTE_ID, 10);
    }
    return null;
  }

  function resolveIsAdmin() {
    return typeof MN_IS_ADMIN !== "undefined" && !!MN_IS_ADMIN;
  }

  function resolveCanViewActivity() {
    if (typeof MN_CAN_VIEW_ACTIVITY !== "undefined") return !!MN_CAN_VIEW_ACTIVITY;
    return resolveIsAdmin();
  }

  const meetingNoteId = resolveMeetingNoteId();
  const userOpts = Array.isArray(MN_USER_OPTS) ? MN_USER_OPTS : [];
  const isAdmin = resolveIsAdmin();
  const canViewActivity = resolveCanViewActivity();
  const platformList = Array.isArray(typeof MN_PLATFORMS !== "undefined" ? MN_PLATFORMS : null)
    ? MN_PLATFORMS.slice()
    : [];
  let columnPreset = "full";
  let lastDeletedItem = null;
  const DEBOUNCE_MS = 400;

  let mnMeetingAttendeeIds = Array.isArray(typeof MN_MEETING_ATTENDEE_IDS !== "undefined" ? MN_MEETING_ATTENDEE_IDS : null)
    ? MN_MEETING_ATTENDEE_IDS.slice()
    : [];
  let mnMeetingGuestNames = Array.isArray(typeof MN_MEETING_GUEST_NAMES !== "undefined" ? MN_MEETING_GUEST_NAMES : null)
    ? MN_MEETING_GUEST_NAMES.slice()
    : [];

  let attendeePickerEl = null;
  let guestPickerEl = null;

  let calendar = null;
  let ganttInst = null;
  let ganttTasksCache = [];
  const saveTimers = {};

  function $(sel, root) { return (root || document).querySelector(sel); }
  function $all(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  function escapeHtml(s) {
    const d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML;
  }

  function normalizeBulletText(value) {
    if (value == null) return "";
    const raw = String(value).replace(/\r\n/g, "\n").replace(/\r/g, "\n").trim();
    if (!raw) return "";
    const lines = [];
    raw.split("\n").forEach(function (line) {
      const cleaned = line.trim().replace(/^[-*•]\s*/, "");
      if (cleaned) lines.push(cleaned);
    });
    return lines.join("\n");
  }

  function linesToBulletCell(text) {
    return normalizeBulletText(text).split("\n").filter(Boolean).map(function (l) {
      return "• " + l;
    }).join("\n");
  }

  function formatBulletsHtml(text) {
    const lines = normalizeBulletText(text).split("\n").filter(Boolean);
    if (!lines.length) return '<span class="text-muted">—</span>';
    return '<ul class="mn-bullets mb-0 ps-3">' + lines.map(function (l) {
      return "<li>" + escapeHtml(l) + "</li>";
    }).join("") + "</ul>";
  }

  function debounce(key, fn) {
    if (saveTimers[key]) clearTimeout(saveTimers[key]);
    saveTimers[key] = setTimeout(fn, DEBOUNCE_MS);
  }

  function hasActiveFilters() {
    const platform = ($("#mn-filter-platform") || {}).value;
    const assignee = ($("#mn-filter-assignee") || {}).value;
    const status = ($("#mn-filter-status") || {}).value;
    const due = ($("#mn-filter-due") || {}).value;
    if (platform || assignee) return true;
    if (status && status !== "all") return true;
    if (due) return true;
    return false;
  }

  function readFilters() {
    const p = new URLSearchParams();
    if (meetingNoteId) p.set("meeting_note_id", String(meetingNoteId));
    const platform = ($("#mn-filter-platform") || {}).value;
    if (platform) p.set("platform", platform);
    const assignee = ($("#mn-filter-assignee") || {}).value;
    if (assignee) p.set("assignee_user_id", assignee);
    const status = ($("#mn-filter-status") || {}).value;
    if (status && status !== "all") p.set("status", status);
    const due = ($("#mn-filter-due") || {}).value;
    if (due) p.set("due_preset", due);
    const ds = ($("#mn-due-start") || {}).value;
    const de = ($("#mn-due-end") || {}).value;
    if (due === "custom") {
      if (ds) p.set("due_start", ds);
      if (de) p.set("due_end", de);
    }
    return p;
  }

  function setUrlView(view) {
    const u = new URL(window.location.href);
    u.searchParams.set("view", view);
    window.history.replaceState({}, "", u.toString());
  }

  function getViewFromUrl() {
    const v = new URLSearchParams(window.location.search).get("view");
    if (v === "calendar" || v === "gantt") return v;
    return "table";
  }

  function getGanttModeFromUrl() {
    const defaultMode = meetingNoteId ? "week" : "month";
    const m = (new URLSearchParams(window.location.search).get("gantt_mode") || defaultMode).toLowerCase();
    if (m === "week") return "Week";
    if (m === "day") return "Day";
    return "Month";
  }

  function setGanttModeInUrl(mode) {
    const u = new URL(window.location.href);
    u.searchParams.set("gantt_mode", mode.toLowerCase());
    window.history.replaceState({}, "", u.toString());
  }

  function showView(mode) {
    $all(".mn-view").forEach(function (el) { el.classList.add("d-none"); });
    const el = $("#mn-view-" + mode);
    if (el) el.classList.remove("d-none");
    $all("[data-mn-view-btn]").forEach(function (b) {
      b.classList.toggle("active", b.getAttribute("data-mn-view-btn") === mode);
    });
    setUrlView(mode);
    if (mode === "calendar") refreshCalendar();
    if (mode === "gantt") refreshGantt();
  }

  function setRowSaveState(tr, state, msg) {
    if (!tr) return;
    tr.setAttribute("data-save-state", state);
    const hint = tr.querySelector(".mn-save-hint");
    if (!hint) return;
    hint.className = "mn-save-hint";
    if (state === "saving") {
      hint.classList.add("is-saving");
      hint.textContent = msg || "Saving…";
    } else if (state === "saved") {
      hint.classList.add("is-saved");
      hint.textContent = msg || "Saved";
    } else if (state === "error") {
      hint.classList.add("is-error");
      hint.textContent = msg || "Error";
    } else {
      hint.textContent = "";
    }
  }

  function applyStatusRowClass(tr, status) {
    tr.classList.remove("mn-row-open", "mn-row-in_progress", "mn-row-done", "table-warning");
    const st = (status || "open").toLowerCase();
    tr.classList.add("mn-row-" + st);
    const hl = new URLSearchParams(window.location.search).get("highlight");
    const id = tr.getAttribute("data-item-id");
    if (hl && id && String(hl) === String(id)) tr.classList.add("table-warning");
  }

  function getAssigneeLabels(ids) {
    const idSet = new Set((ids || []).map(function (x) { return parseInt(x, 10); }));
    return userOpts.filter(function (u) { return idSet.has(u.id); }).map(function (u) { return u.label; });
  }

  function getAssigneeIdsFromPicker(picker) {
    if (!picker) return [];
    try {
      return JSON.parse(picker.getAttribute("data-assignee-ids") || "[]");
    } catch (e) {
      return [];
    }
  }

  function setAssigneeIdsOnPicker(picker, ids) {
    picker.setAttribute("data-assignee-ids", JSON.stringify(ids || []));
  }

  function statusBadgeHtml(status) {
    const st = (status || "open").toLowerCase();
    const label = st === "in_progress" ? "In progress" : st.charAt(0).toUpperCase() + st.slice(1);
    return '<span class="mn-status-badge mn-status-' + st + '">' + escapeHtml(label) + "</span>";
  }

  function assigneeChipsHtml(names) {
    if (!names || !names.length) return '<span class="text-muted">—</span>';
    return '<div class="mn-assignee-readonly">' + names.map(function (n) {
      return '<span class="mn-assignee-chip">' + escapeHtml(n) + "</span>";
    }).join("") + "</div>";
  }

  function buildAssigneePicker(selectedIds, onChange) {
    const wrap = document.createElement("div");
    wrap.className = "mn-assignee-picker";
    let selected = (selectedIds || []).map(function (x) { return parseInt(x, 10); }).filter(Boolean);
    setAssigneeIdsOnPicker(wrap, selected);

    const chipsEl = document.createElement("div");
    chipsEl.className = "mn-assignee-chips";

    const input = document.createElement("input");
    input.type = "text";
    input.className = "mn-assignee-input";
    input.placeholder = "Type name…";
    input.autocomplete = "off";

    const list = document.createElement("div");
    list.className = "mn-assignee-suggestions";

    let activeIdx = -1;

    function renderChips() {
      chipsEl.innerHTML = "";
      selected.forEach(function (uid) {
        const u = userOpts.find(function (o) { return o.id === uid; });
        if (!u) return;
        const chip = document.createElement("span");
        chip.className = "mn-assignee-chip";
        chip.textContent = u.label;
        const rm = document.createElement("button");
        rm.type = "button";
        rm.className = "mn-assignee-chip-remove";
        rm.innerHTML = "&times;";
        rm.setAttribute("aria-label", "Remove " + u.label);
        rm.addEventListener("click", function (e) {
          e.preventDefault();
          selected = selected.filter(function (id) { return id !== uid; });
          setAssigneeIdsOnPicker(wrap, selected);
          renderChips();
          if (onChange) onChange();
        });
        chip.appendChild(rm);
        chipsEl.appendChild(chip);
      });
    }

    function filteredUsers(q) {
      const qq = (q || "").trim().toLowerCase();
      if (!qq) return userOpts.filter(function (u) { return selected.indexOf(u.id) < 0; }).slice(0, 8);
      return userOpts.filter(function (u) {
        return selected.indexOf(u.id) < 0 && u.label.toLowerCase().indexOf(qq) >= 0;
      }).slice(0, 8);
    }

    function closeList() {
      list.classList.remove("is-open");
      activeIdx = -1;
    }

    function openList() {
      const matches = filteredUsers(input.value);
      list.innerHTML = "";
      if (!matches.length) {
        closeList();
        return;
      }
      matches.forEach(function (u, i) {
        const item = document.createElement("div");
        item.className = "mn-assignee-suggestion";
        item.textContent = u.label;
        item.setAttribute("data-id", String(u.id));
        item.addEventListener("mousedown", function (e) {
          e.preventDefault();
          addUser(u.id);
        });
        list.appendChild(item);
      });
      list.classList.add("is-open");
    }

    function addUser(uid) {
      if (selected.indexOf(uid) >= 0) return;
      selected.push(uid);
      setAssigneeIdsOnPicker(wrap, selected);
      input.value = "";
      renderChips();
      closeList();
      if (onChange) onChange();
    }

    input.addEventListener("input", openList);
    input.addEventListener("focus", openList);
    input.addEventListener("blur", function () {
      setTimeout(closeList, 150);
    });
    input.addEventListener("keydown", function (e) {
      const items = $all(".mn-assignee-suggestion", list);
      if (e.key === "Escape") {
        closeList();
        return;
      }
      if (e.key === "Enter") {
        e.preventDefault();
        if (activeIdx >= 0 && items[activeIdx]) {
          addUser(parseInt(items[activeIdx].getAttribute("data-id"), 10));
        } else if (items.length === 1) {
          addUser(parseInt(items[0].getAttribute("data-id"), 10));
        }
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        activeIdx = Math.min(activeIdx + 1, items.length - 1);
        items.forEach(function (el, i) { el.classList.toggle("is-active", i === activeIdx); });
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        activeIdx = Math.max(activeIdx - 1, 0);
        items.forEach(function (el, i) { el.classList.toggle("is-active", i === activeIdx); });
      }
    });

    renderChips();
    wrap.appendChild(chipsEl);
    wrap.appendChild(input);
    wrap.appendChild(list);
    return wrap;
  }

  function getGuestNamesFromPicker(picker) {
    if (!picker) return [];
    try {
      return JSON.parse(picker.getAttribute("data-guest-names") || "[]");
    } catch (e) {
      return [];
    }
  }

  function setGuestNamesOnPicker(picker, names) {
    picker.setAttribute("data-guest-names", JSON.stringify(names || []));
  }

  function buildGuestChipPicker(selectedNames) {
    const wrap = document.createElement("div");
    wrap.className = "mn-guest-picker";
    let selected = (selectedNames || []).map(function (n) { return String(n).trim(); }).filter(Boolean);
    setGuestNamesOnPicker(wrap, selected);

    const chipsEl = document.createElement("div");
    chipsEl.className = "mn-guest-chips";

    const input = document.createElement("input");
    input.type = "text";
    input.className = "mn-guest-input";
    input.placeholder = "Type guest name…";
    input.autocomplete = "off";

    function renderChips() {
      chipsEl.innerHTML = "";
      selected.forEach(function (name, idx) {
        const chip = document.createElement("span");
        chip.className = "mn-guest-chip";
        chip.textContent = name;
        const rm = document.createElement("button");
        rm.type = "button";
        rm.className = "mn-guest-chip-remove";
        rm.innerHTML = "&times;";
        rm.setAttribute("aria-label", "Remove " + name);
        rm.addEventListener("click", function (e) {
          e.preventDefault();
          selected = selected.filter(function (_, i) { return i !== idx; });
          setGuestNamesOnPicker(wrap, selected);
          renderChips();
        });
        chip.appendChild(rm);
        chipsEl.appendChild(chip);
      });
    }

    function addGuest(name) {
      const n = (name || "").trim();
      if (!n) return;
      const key = n.toLowerCase();
      if (selected.some(function (s) { return s.toLowerCase() === key; })) return;
      selected.push(n);
      setGuestNamesOnPicker(wrap, selected);
      input.value = "";
      renderChips();
    }

    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        e.preventDefault();
        addGuest(input.value);
      }
    });

    renderChips();
    wrap.appendChild(chipsEl);
    wrap.appendChild(input);
    return wrap;
  }

  function initMeetingAttendeePickers() {
    const attendeeHost = $("#mn-attendee-picker");
    if (attendeeHost) {
      attendeePickerEl = buildAssigneePicker(mnMeetingAttendeeIds, null);
      attendeeHost.appendChild(attendeePickerEl);
    }
    const guestHost = $("#mn-guest-picker");
    if (guestHost) {
      guestPickerEl = buildGuestChipPicker(mnMeetingGuestNames);
      guestHost.appendChild(guestPickerEl);
    }
  }

  function formatAttendeesPdfLine() {
    const userNames = getAssigneeLabels(mnMeetingAttendeeIds);
    const guests = mnMeetingGuestNames || [];
    const parts = [];
    if (userNames.length) parts.push("Attendees: " + userNames.join(", "));
    if (guests.length) parts.push("Guests: " + guests.join(", "));
    return parts.join("; ");
  }

  function dateVal(iso) {
    if (!iso) return "";
    return String(iso).slice(0, 10);
  }

  function collectRowPayload(tr) {
    const get = function (cls) {
      const el = tr.querySelector(cls);
      return el ? el.value.trim() : "";
    };
    const getBullet = function (cls) {
      const el = tr.querySelector(cls);
      return el ? normalizeBulletText(el.value) : "";
    };
    const picker = tr.querySelector(".mn-assignee-picker");
    const assignee_ids = getAssigneeIdsFromPicker(picker);
    return {
      platform: get(".mn-cell-platform"),
      focus_area: getBullet(".mn-cell-focus"),
      call_to_action: getBullet(".mn-cell-cta"),
      expected_impact: getBullet(".mn-cell-impact"),
      challenges: getBullet(".mn-cell-challenges"),
      comments: getBullet(".mn-cell-comments"),
      status: get(".mn-cell-status") || "open",
      start_date: get(".mn-cell-start") || null,
      due_date: get(".mn-cell-due") || null,
      assignee_ids: assignee_ids,
    };
  }

  async function putFocusRow(focusRowId, payload) {
    return fetch(API.focusRowById(focusRowId), {
      method: "PUT",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(payload),
    });
  }

  async function putActionItem(itemId, payload) {
    return fetch(API.actionItem(itemId), {
      method: "PUT",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(payload),
    });
  }

  function scheduleRowSave(tr, opts) {
    opts = opts || {};
    const itemId = tr.getAttribute("data-item-id");
    const focusRowId = tr.getAttribute("data-focus-row-id");
    if (!itemId || !focusRowId || tr.getAttribute("data-template") === "1") return;
    const key = "row-" + itemId;
    const silent = !opts.log;
    debounce(key, async function () {
      setRowSaveState(tr, "saving");
      const p = collectRowPayload(tr);
      try {
        const frRes = await putFocusRow(parseInt(focusRowId, 10), {
          platform: p.platform,
          focus_area: p.focus_area,
          silent: silent,
        });
        if (!frRes.ok) throw new Error("Focus row save failed");
        const itemPayload = {
          call_to_action: p.call_to_action,
          expected_impact: p.expected_impact,
          challenges: p.challenges,
          comments: p.comments,
          status: p.status,
          start_date: p.start_date,
          due_date: p.due_date,
          assignee_ids: p.assignee_ids,
          silent: silent,
        };
        if (opts.logText) itemPayload.log_text_edit = true;
        const itemRes = await putActionItem(parseInt(itemId, 10), itemPayload);
        if (!itemRes.ok) throw new Error("Item save failed");
        applyStatusRowClass(tr, p.status);
        setRowSaveState(tr, "saved");
        if (calendar) calendar.refetchEvents();
        if (ganttInst && $("#mn-view-gantt") && !$("#mn-view-gantt").classList.contains("d-none")) {
          refreshGantt();
        }
        if (opts.log) loadActivity();
      } catch (e) {
        console.error(e);
        setRowSaveState(tr, "error");
      }
    });
  }

  async function commitTemplateRow(tr) {
    if (!meetingNoteId || tr.getAttribute("data-template") !== "1") return;
    const p = collectRowPayload(tr);
    if (!p.platform && !p.focus_area && !p.call_to_action) return;
    setRowSaveState(tr, "saving", "Creating…");
    try {
      const frRes = await fetch(API.focusRow(meetingNoteId), {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          platform: p.platform || "General",
          focus_area: p.focus_area || "General",
          sort_order: 0,
        }),
      });
      if (!frRes.ok) throw new Error("Could not create focus row");
      const fr = await frRes.json();
      const itemRes = await fetch(API.createItem(fr.id), {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          call_to_action: p.call_to_action || "",
          expected_impact: p.expected_impact,
          challenges: p.challenges,
          comments: p.comments,
          status: p.status || "open",
          start_date: p.start_date,
          due_date: p.due_date,
          assignee_ids: p.assignee_ids,
        }),
      });
      if (!itemRes.ok) throw new Error("Could not create item");
      const item = await itemRes.json();
      tr.removeAttribute("data-template");
      tr.setAttribute("data-item-id", String(item.id));
      tr.setAttribute("data-focus-row-id", String(item.focus_row_id));
      setRowSaveState(tr, "saved");
      applyStatusRowClass(tr, item.status);
      loadActivity();
      if (calendar) calendar.refetchEvents();
    } catch (e) {
      console.error(e);
      setRowSaveState(tr, "error", "Create failed");
    }
  }

  function wireInlineRow(tr) {
    $all("input, textarea, select", tr).forEach(function (el) {
      if (el.classList.contains("mn-assignee-input")) return;
      el.addEventListener("input", function () {
        if (tr.getAttribute("data-template") === "1") return;
        if (el.classList.contains("mn-cell-status")) return;
        scheduleRowSave(tr, { silent: true });
      });
      el.addEventListener("change", function () {
        if (tr.getAttribute("data-template") === "1") return;
        if (el.classList.contains("mn-cell-status") || el.classList.contains("mn-cell-start") || el.classList.contains("mn-cell-due")) {
          scheduleRowSave(tr, { log: true });
        } else {
          scheduleRowSave(tr, { silent: true });
        }
      });
      el.addEventListener("blur", function () {
        if (tr.getAttribute("data-template") === "1") commitTemplateRow(tr);
      });
    });
    const del = tr.querySelector(".mn-del");
    if (del) {
      del.addEventListener("click", function () {
        deleteItem(parseInt(tr.getAttribute("data-item-id"), 10), tr);
      });
    }
  }

  function buildInlineRow(it, isTemplate) {
    const tr = document.createElement("tr");
    if (isTemplate) {
      tr.setAttribute("data-template", "1");
      applyStatusRowClass(tr, "open");
    } else {
      tr.setAttribute("data-item-id", String(it.id));
      tr.setAttribute("data-focus-row-id", String(it.focus_row_id));
      applyStatusRowClass(tr, it.status);
    }

    function cellInput(cls, val, tag) {
      const td = document.createElement("td");
      const el = document.createElement(tag || "input");
      el.className = "form-control form-control-sm " + cls;
      if (tag === "textarea") {
        el.rows = 2;
        el.value = val || "";
      } else if (tag === "select") {
        /* handled separately */
      } else {
        el.type = "text";
        if (cls.indexOf("date") >= 0) el.type = "date";
        el.value = val || "";
      }
      td.appendChild(el);
      return td;
    }

    function cellBulletTextarea(cls, val, placeholder) {
      const td = document.createElement("td");
      const el = document.createElement("textarea");
      el.className = "form-control form-control-sm mn-cell-bullets " + cls;
      el.rows = 2;
      el.value = val || "";
      if (placeholder) el.placeholder = placeholder;
      td.appendChild(el);
      return td;
    }

    const platTd = cellInput("mn-cell-platform", isTemplate ? "" : it.platform);
    const platIn = platTd.querySelector(".mn-cell-platform");
    if (platIn && platformList.length) {
      platIn.setAttribute("list", "mn-platform-datalist");
    }
    tr.appendChild(platTd);
    tr.appendChild(cellBulletTextarea(
      "mn-cell-focus",
      isTemplate ? "" : it.focus_area,
      "One bullet per line (shared for this focus row)"
    ));

    tr.appendChild(cellBulletTextarea(
      "mn-cell-cta",
      isTemplate ? "" : (it.call_to_action || ""),
      "One bullet per line"
    ));

    tr.appendChild(cellBulletTextarea(
      "mn-cell-impact",
      isTemplate ? "" : it.expected_impact,
      "One bullet per line"
    ));

    const datesTd = document.createElement("td");
    datesTd.className = "mn-dates-cell col-dates";
    const startLbl = document.createElement("span");
    startLbl.className = "mn-date-label";
    startLbl.textContent = "Start";
    const startIn = document.createElement("input");
    startIn.type = "date";
    startIn.className = "form-control form-control-sm mn-cell-start mb-1";
    startIn.value = isTemplate ? "" : dateVal(it.start_date);
    const dueLbl = document.createElement("span");
    dueLbl.className = "mn-date-label";
    dueLbl.textContent = "Due";
    const dueIn = document.createElement("input");
    dueIn.type = "date";
    dueIn.className = "form-control form-control-sm mn-cell-due";
    dueIn.value = isTemplate ? "" : dateVal(it.due_date);
    datesTd.appendChild(startLbl);
    datesTd.appendChild(startIn);
    datesTd.appendChild(dueLbl);
    datesTd.appendChild(dueIn);
    const duePresets = document.createElement("div");
    duePresets.className = "mn-due-presets mt-1";
    duePresets.innerHTML =
      '<button type="button" class="btn btn-link btn-sm p-0 mn-due-preset" data-days="7">+1w</button> ' +
      '<button type="button" class="btn btn-link btn-sm p-0 mn-due-preset" data-days="14">+2w</button>';
    datesTd.appendChild(duePresets);
    tr.appendChild(datesTd);

    tr.appendChild(cellBulletTextarea(
      "mn-cell-challenges",
      isTemplate ? "" : it.challenges,
      "One bullet per line"
    ));
    tr.appendChild(cellBulletTextarea(
      "mn-cell-comments",
      isTemplate ? "" : it.comments,
      "One bullet per line"
    ));

    const assignTd = document.createElement("td");
    assignTd.appendChild(buildAssigneePicker(isTemplate ? [] : it.assignee_ids, function () {
      if (tr.getAttribute("data-template") !== "1") scheduleRowSave(tr, { log: true });
    }));
    tr.appendChild(assignTd);

    const statusTd = document.createElement("td");
    const statusSel = document.createElement("select");
    statusSel.className = "form-select form-select-sm mn-cell-status";
    ["open", "in_progress", "done"].forEach(function (s) {
      const opt = document.createElement("option");
      opt.value = s;
      opt.textContent = s === "in_progress" ? "In progress" : s.charAt(0).toUpperCase() + s.slice(1);
      if (!isTemplate && it.status === s) opt.selected = true;
      if (isTemplate && s === "open") opt.selected = true;
      statusSel.appendChild(opt);
    });
    statusTd.appendChild(statusSel);
    tr.appendChild(statusTd);

    const actTd = document.createElement("td");
    actTd.className = "text-end text-nowrap align-middle";
    if (!isTemplate) {
      const delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.className = "btn btn-sm mn-btn-ghost text-danger mn-del";
      delBtn.textContent = "Delete";
      actTd.appendChild(delBtn);
    }
    const hint = document.createElement("div");
    hint.className = "mn-save-hint";
    if (isTemplate) hint.textContent = "Fill in and tab out to save";
    actTd.appendChild(hint);
    tr.appendChild(actTd);

    wireInlineRow(tr);
    return tr;
  }

  function renderTableReadOnly(items) {
    const tb = $("#mn-table-body");
    if (!tb) return;
    const hl = new URLSearchParams(window.location.search).get("highlight");
    tb.innerHTML = "";
    if (!items.length) {
      tb.innerHTML = '<tr><td colspan="11" class="text-muted text-center py-4">No action items match.</td></tr>';
      return;
    }
    items.forEach(function (it) {
      const tr = document.createElement("tr");
      if (hl && String(it.id) === String(hl)) tr.classList.add("table-warning");
      tr.innerHTML =
        "<td class=\"small\"><a href=\"/meeting-notes/" + it.meeting_note_id + "?view=table&highlight=" + it.id + "\">" +
        escapeHtml(it.meeting_title || "") + "</a><div class=\"text-muted\">" + escapeHtml(it.meeting_date || "") + "</div></td>" +
        "<td class=\"small\">" + escapeHtml(it.platform || "") + "</td>" +
        "<td class=\"small\">" + formatBulletsHtml(it.focus_area) + "</td>" +
        "<td>" + formatBulletsHtml(it.call_to_action) + "</td>" +
        "<td class=\"small\">" + formatBulletsHtml(it.expected_impact) + "</td>" +
        "<td class=\"small text-nowrap\">" + (it.start_date || "—") + " / " + (it.due_date || "—") + "</td>" +
        "<td class=\"small\">" + formatBulletsHtml(it.challenges) + "</td>" +
        "<td class=\"small\">" + formatBulletsHtml(it.comments) + "</td>" +
        "<td class=\"small\">" + assigneeChipsHtml(it.assignee_names || getAssigneeLabels(it.assignee_ids)) + "</td>" +
        "<td class=\"small\">" + statusBadgeHtml(it.status) + "</td>" +
        "<td class=\"text-end\"><a class=\"btn btn-sm mn-btn-ghost\" href=\"/meeting-notes/" + it.meeting_note_id + "?view=table&highlight=" + it.id + "\">Open meeting</a></td>";
      tb.appendChild(tr);
    });
  }

  function applyColumnPreset(preset) {
    columnPreset = preset || "full";
    const table = document.querySelector(".mn-inline-table");
    if (!table) return;
    table.setAttribute("data-col-preset", columnPreset);
    $all("[data-mn-col-preset]").forEach(function (btn) {
      btn.classList.toggle("active", btn.getAttribute("data-mn-col-preset") === columnPreset);
    });
  }

  function applyRowGrouping(items) {
    const tb = $("#mn-table-body");
    if (!tb || !items.length) return;
    let lastKey = null;
    $all("tr[data-item-id]", tb).forEach(function (tr, idx) {
      const it = items[idx];
      if (!it) return;
      const key = (it.platform || "") + "||" + (it.focus_row_id || "");
      const focusCell = tr.querySelector(".mn-cell-focus");
      const platCell = tr.querySelector(".mn-cell-platform");
      if (key === lastKey) {
        tr.classList.add("mn-group-cont");
        if (focusCell) {
          focusCell.closest("td").classList.add("mn-merged-cell");
          focusCell.style.display = "none";
        }
        if (platCell) {
          platCell.closest("td").classList.add("mn-merged-cell");
          platCell.style.display = "none";
        }
      } else {
        tr.classList.remove("mn-group-cont");
        if (focusCell) {
          focusCell.closest("td").classList.remove("mn-merged-cell");
          focusCell.style.display = "";
        }
        if (platCell) {
          platCell.closest("td").classList.remove("mn-merged-cell");
          platCell.style.display = "";
        }
        lastKey = key;
      }
    });
  }

  function renderTableInline(items) {
    const tb = $("#mn-table-body");
    if (!tb) return;
    tb.innerHTML = "";
    if (!items.length && !hasActiveFilters()) {
      tb.appendChild(buildInlineRow(null, true));
      return;
    }
    if (!items.length) {
      tb.innerHTML = '<tr><td colspan="11" class="text-muted text-center py-4">No action items match filters.</td></tr>';
      return;
    }
    items.forEach(function (it) {
      const tr = buildInlineRow(it, false);
      const chkTd = document.createElement("td");
      chkTd.className = "mn-chk-col";
      const chk = document.createElement("input");
      chk.type = "checkbox";
      chk.className = "mn-row-chk";
      chk.setAttribute("data-item-id", String(it.id));
      chkTd.appendChild(chk);
      tr.insertBefore(chkTd, tr.firstChild);
      tb.appendChild(tr);
    });
    applyRowGrouping(items);
    applyColumnPreset(columnPreset);
  }

  function renderTable(items) {
    if (meetingNoteId) renderTableInline(items);
    else renderTableReadOnly(items);
  }

  async function fetchItems() {
    const p = readFilters();
    const res = await fetch(API.items + "?" + p.toString(), { headers: { Accept: "application/json" } });
    if (!res.ok) throw new Error("Failed to load items");
    const data = await res.json();
    return data.items || [];
  }

  async function refreshTable() {
    try {
      const items = await fetchItems();
      renderTable(items);
    } catch (e) {
      console.error(e);
      const tb = $("#mn-table-body");
      if (tb) {
        tb.innerHTML = '<tr><td colspan="' + (meetingNoteId ? 11 : 11) + '" class="text-danger">Could not load items.</td></tr>';
      }
    }
  }

  async function createNewRow() {
    if (!meetingNoteId) return;
    const tb = $("#mn-table-body");
    if (!tb) return;
    setRowSaveState(null, "");
    try {
      const frRes = await fetch(API.focusRow(meetingNoteId), {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ platform: "", focus_area: "", sort_order: 0 }),
      });
      if (!frRes.ok) throw new Error("Focus row failed");
      const fr = await frRes.json();
      const itemRes = await fetch(API.createItem(fr.id), {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ call_to_action: "", status: "open" }),
      });
      if (!itemRes.ok) throw new Error("Item failed");
      const item = await itemRes.json();
      let tr = buildInlineRow(item, false);
      const chkTd = document.createElement("td");
      chkTd.className = "mn-chk-col";
      const chk = document.createElement("input");
      chk.type = "checkbox";
      chk.className = "mn-row-chk";
      chk.setAttribute("data-item-id", String(item.id));
      chkTd.appendChild(chk);
      tr.insertBefore(chkTd, tr.firstChild);
      const emptyMsg = tb.querySelector("td.text-muted");
      if (emptyMsg) tb.innerHTML = "";
      const template = tb.querySelector('tr[data-template="1"]');
      if (template) template.remove();
      tb.appendChild(tr);
      tr.querySelector(".mn-cell-platform").focus();
      loadActivity();
    } catch (e) {
      console.error(e);
      alert("Could not add row");
    }
  }

  function filterTasksByMonth(tasks, monthStr) {
    if (!monthStr) return tasks;
    const parts = monthStr.split("-");
    if (parts.length < 2) return tasks;
    const y = parseInt(parts[0], 10);
    const m = parseInt(parts[1], 10);
    if (!y || !m) return tasks;
    return tasks.filter(function (t) {
      const start = t.start ? t.start.slice(0, 7) : "";
      const end = t.end ? t.end.slice(0, 7) : "";
      const key = y + "-" + String(m).padStart(2, "0");
      return start <= key || end >= key || start === key;
    });
  }

  function syncGanttToolbarActive() {
    const mode = getGanttModeFromUrl();
    $all("[data-gantt-mode]").forEach(function (btn) {
      btn.classList.toggle("active", btn.getAttribute("data-gantt-mode") === mode);
    });
  }

  function refreshGantt() {
    const el = $("#mn-gantt");
    if (!el || typeof Gantt === "undefined") return;
    const p = readFilters();
    const viewMode = getGanttModeFromUrl();
    syncGanttToolbarActive();
    fetch(API.gantt + "?" + p.toString())
      .then(function (r) { return r.json(); })
      .then(function (data) {
        ganttTasksCache = data.tasks || [];
        const monthInput = $("#mn-gantt-month");
        let monthVal = monthInput && monthInput.value;
        if (!monthVal && ganttTasksCache.length) {
          monthVal = ganttTasksCache[0].start.slice(0, 7);
          if (monthInput) monthInput.value = monthVal;
        }
        if (!monthVal) {
          const now = new Date();
          monthVal = now.getFullYear() + "-" + String(now.getMonth() + 1).padStart(2, "0");
          if (monthInput) monthInput.value = monthVal;
        }
        let tasks = filterTasksByMonth(ganttTasksCache, monthVal);
        el.innerHTML = "";
        ganttInst = null;
        if (!tasks.length) {
          el.innerHTML = '<p class="text-muted p-3 mb-0">No dated tasks for this month. Set start/due dates on action items or pick another month.</p>';
          return;
        }
        ganttInst = new Gantt(el, tasks, {
          view_mode: viewMode,
          date_format: "YYYY-MM-DD",
          language: "en",
          bar_height: 28,
          padding: 20,
          column_width: viewMode === "Day" ? 36 : viewMode === "Week" ? 48 : 42,
        });
      })
      .catch(function (e) {
        console.error(e);
        el.innerHTML = '<p class="text-danger p-3">Could not load Gantt.</p>';
      });
  }

  function refreshCalendar() {
    const el = $("#mn-calendar");
    if (!el || typeof FullCalendar === "undefined") return;
    if (calendar) {
      calendar.refetchEvents();
      return;
    }
    calendar = new FullCalendar.Calendar(el, {
      initialView: "dayGridMonth",
      height: "auto",
      headerToolbar: { left: "prev,next today", center: "title", right: "dayGridMonth,timeGridWeek,listWeek" },
      events: function (info, successCallback) {
        const p = readFilters();
        fetch(API.cal + "?" + p.toString())
          .then(function (r) { return r.json(); })
          .then(function (evs) { successCallback(evs); })
          .catch(function () { successCallback([]); });
      },
      eventClick: function (info) {
        info.jsEvent.preventDefault();
        const url = info.event.url;
        if (url) window.location.href = url;
      },
    });
    calendar.render();
  }

  async function deleteItem(id, tr) {
    if (!meetingNoteId || !confirm("Delete this action item?")) return;
    const res = await fetch(API.actionItem(id), { method: "DELETE" });
    if (!res.ok) { alert("Delete failed"); return; }
    if (tr && tr.parentNode) tr.parentNode.removeChild(tr);
    else await refreshTable();
    const tb = $("#mn-table-body");
    if (tb && !tb.querySelector("tr[data-item-id]") && !tb.querySelector('tr[data-template="1"]')) {
      tb.appendChild(buildInlineRow(null, true));
    }
    if (calendar) calendar.refetchEvents();
    if ($("#mn-view-gantt") && !$("#mn-view-gantt").classList.contains("d-none")) refreshGantt();
    loadActivity();
  }

  async function saveMeetingMeta() {
    if (!meetingNoteId) return;
    const payload = {
      title: $("#mn-meta-title").value.trim(),
      meeting_date: $("#mn-meta-date").value,
      summary: $("#mn-meta-summary").value.trim() || null,
      attendee_ids: getAssigneeIdsFromPicker(attendeePickerEl),
      guest_names: getGuestNamesFromPicker(guestPickerEl),
    };
    const res = await fetch(API.meeting(meetingNoteId), {
      method: "PUT",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) { alert("Update failed"); return; }
    try {
      const data = await res.json();
      if (Array.isArray(data.attendee_ids)) mnMeetingAttendeeIds = data.attendee_ids.slice();
      if (Array.isArray(data.guest_names)) mnMeetingGuestNames = data.guest_names.slice();
    } catch (e) { /* ignore */ }
    loadActivity();
  }

  function getPdfExportOptions() {
    const incDone = $("#mn-pdf-include-done");
    const incSummary = $("#mn-pdf-include-summary");
    const groupPlatform = $("#mn-pdf-group-platform");
    return {
      includeDone: incDone ? incDone.checked : true,
      includeSummary: incSummary ? incSummary.checked : true,
      groupByPlatform: groupPlatform ? groupPlatform.checked : true,
    };
  }

  async function exportTablePdf() {
    if (!window.jspdf || !window.jspdf.jsPDF) {
      alert("PDF library not loaded.");
      return;
    }
    const pdfOpts = getPdfExportOptions();
    let items;
    try {
      items = await fetchItems();
    } catch (e) {
      alert("Could not load data for export.");
      return;
    }
    if (!pdfOpts.includeDone) {
      items = items.filter(function (it) { return (it.status || "open") !== "done"; });
    }
    if (!items.length) {
      alert("No action items to export.");
      return;
    }
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF({ orientation: "landscape", unit: "pt", format: "a4" });
    let y = 28;
    const title = meetingNoteId && typeof MN_MEETING_TITLE === "string"
      ? MN_MEETING_TITLE
      : "All action items";
    const meetingDate = meetingNoteId && typeof MN_MEETING_DATE === "string" ? MN_MEETING_DATE : "";
    doc.setFontSize(14);
    doc.setTextColor(0, 64, 125);
    doc.text(title, 40, y);
    y += 16;
    doc.setFontSize(9);
    doc.setTextColor(80, 80, 80);
    if (meetingDate) {
      doc.text("Meeting date: " + meetingDate, 40, y);
      y += 12;
    }
    if (meetingNoteId) {
      const attendeeLine = formatAttendeesPdfLine();
      if (attendeeLine) {
        doc.text(attendeeLine, 40, y);
        y += 12;
      }
      if (pdfOpts.includeSummary && typeof MN_MEETING_SUMMARY === "string" && MN_MEETING_SUMMARY.trim()) {
        doc.text("Summary:", 40, y);
        y += 10;
        const sumLines = doc.splitTextToSize(MN_MEETING_SUMMARY.trim(), 720);
        doc.text(sumLines, 40, y);
        y += sumLines.length * 10 + 4;
      }
    }
    doc.text("Exported: " + new Date().toISOString().slice(0, 16).replace("T", " "), 40, y);
    y += 14;

    function rowCells(it) {
      const names = (it.assignee_names && it.assignee_names.length)
        ? it.assignee_names.join(", ")
        : getAssigneeLabels(it.assignee_ids).join(", ");
      const st = (it.status || "open").replace(/_/g, " ");
      if (meetingNoteId) {
        return [
          it.platform || "",
          linesToBulletCell(it.focus_area),
          linesToBulletCell(it.call_to_action),
          linesToBulletCell(it.expected_impact),
          it.start_date || "",
          it.due_date || "",
          linesToBulletCell(it.challenges),
          linesToBulletCell(it.comments),
          names,
          st,
        ];
      }
      return [
        (it.meeting_title || "") + " (" + (it.meeting_date || "") + ")",
        it.platform || "",
        linesToBulletCell(it.focus_area),
        linesToBulletCell(it.call_to_action),
        linesToBulletCell(it.expected_impact),
        it.start_date || "",
        it.due_date || "",
        linesToBulletCell(it.challenges),
        linesToBulletCell(it.comments),
        names,
        st,
      ];
    }

    const headers = meetingNoteId
      ? [["Platform", "Focus area", "Call to action", "Impact", "Start", "Due", "Challenges", "Comments", "Led by", "Status"]]
      : [["Meeting", "Platform", "Focus", "Call to action", "Impact", "Start", "Due", "Challenges", "Comments", "Led by", "Status"]];

    if (meetingNoteId && pdfOpts.groupByPlatform) {
      const byPlat = {};
      items.forEach(function (it) {
        const p = it.platform || "General";
        if (!byPlat[p]) byPlat[p] = [];
        byPlat[p].push(it);
      });
      Object.keys(byPlat).sort().forEach(function (plat) {
        doc.setFontSize(10);
        doc.setTextColor(0, 64, 125);
        doc.text(plat, 40, y);
        y += 12;
        doc.setTextColor(80, 80, 80);
        doc.setFontSize(9);
        const body = byPlat[plat].map(rowCells);
        doc.autoTable({
          head: headers,
          body: body,
          startY: y,
          theme: "grid",
          styles: { fontSize: 7, cellPadding: 3, overflow: "linebreak" },
          headStyles: { fillColor: [0, 64, 125], textColor: 255, fontStyle: "bold" },
          margin: { left: 28, right: 28 },
        });
        y = doc.lastAutoTable.finalY + 16;
      });
      const slug = String(title).replace(/[^\w\-]+/g, "_").slice(0, 40) || "export";
      doc.save("meeting-notes_" + slug + "_" + new Date().toISOString().slice(0, 10) + ".pdf");
      return;
    }

    const body = items.map(function (it) {
      return rowCells(it);
    });
    doc.autoTable({
      head: headers,
      body: body,
      startY: y,
      theme: "grid",
      styles: { fontSize: 7, cellPadding: 3, overflow: "linebreak" },
      headStyles: { fillColor: [0, 64, 125], textColor: 255, fontStyle: "bold" },
      margin: { left: 28, right: 28 },
    });
    const slug = String(title).replace(/[^\w\-]+/g, "_").slice(0, 40) || "export";
    doc.save("meeting-notes_" + slug + "_" + new Date().toISOString().slice(0, 10) + ".pdf");
  }

  function renderActivityRows(rows) {
    const box = $("#mn-activity-body");
    if (!box) return;
    if (!rows || !rows.length) {
      box.innerHTML = "<p class=\"text-muted mb-0\">No activity yet.</p>";
      return;
    }
    box.innerHTML = "<ul class=\"list-unstyled small mb-0\" id=\"mn-activity-list\">" + rows.map(function (r) {
      return "<li class=\"mb-1\"><span class=\"text-muted\">" + escapeHtml(r.occurred_at || "") + "</span> — " +
        escapeHtml(r.actor) + " — <strong>" + escapeHtml(r.action) + "</strong> " +
        escapeHtml(r.summary || "") + "</li>";
    }).join("") + "</ul>";
  }

  async function loadActivity() {
    const box = $("#mn-activity-body");
    if (!box) return;
    if (!canViewActivity) {
      box.innerHTML = "<p class=\"text-muted mb-0\">You do not have permission to view activity.</p>";
      return;
    }
    if (!meetingNoteId) {
      box.innerHTML = "<p class=\"text-muted mb-0\">Open a meeting to view activity.</p>";
      return;
    }
    const actFilter = ($("#mn-activity-filter") || {}).value || "all";
    const q = "?per_page=40&coalesce=1" + (actFilter && actFilter !== "all" ? "&action=" + encodeURIComponent(actFilter) : "");
    try {
      const res = await fetch(API.activity(meetingNoteId) + q, {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });
      if (res.status === 403) {
        box.innerHTML = "<p class=\"text-muted mb-0\">You do not have permission to view activity.</p>";
        return;
      }
      if (!res.ok) {
        box.innerHTML = "<p class=\"text-muted mb-0\">Could not load activity (HTTP " + res.status + ").</p>";
        return;
      }
      const data = await res.json();
      renderActivityRows(data.items || []);
    } catch (e) {
      console.error("loadActivity", e);
      if (!box.querySelector("#mn-activity-list") && !box.textContent.trim()) {
        box.innerHTML = "<p class=\"text-muted mb-0\">Could not load activity.</p>";
      }
    }
  }

  function wireFilters() {
    $all(".mn-filter-ctrl").forEach(function (el) {
      el.addEventListener("change", function () {
        refreshTable();
        if (calendar) calendar.refetchEvents();
        if ($("#mn-view-gantt") && !$("#mn-view-gantt").classList.contains("d-none")) refreshGantt();
      });
    });
  }

  function wireViews() {
    $all("[data-mn-view-btn]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        showView(btn.getAttribute("data-mn-view-btn"));
      });
    });
  }

  function wireGanttToolbar() {
    $all("[data-gantt-mode]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const mode = btn.getAttribute("data-gantt-mode");
        setGanttModeInUrl(mode);
        syncGanttToolbarActive();
        refreshGantt();
      });
    });
    const monthInput = $("#mn-gantt-month");
    if (monthInput) {
      monthInput.addEventListener("change", refreshGantt);
    }
    const todayBtn = $("#mn-gantt-today");
    if (todayBtn) {
      todayBtn.addEventListener("click", function () {
        const now = new Date();
        const val = now.getFullYear() + "-" + String(now.getMonth() + 1).padStart(2, "0");
        if (monthInput) monthInput.value = val;
        setGanttModeInUrl("Week");
        syncGanttToolbarActive();
        refreshGantt();
      });
    }
    syncGanttToolbarActive();
  }

  document.addEventListener("DOMContentLoaded", function () {
    const u = new URL(window.location.href);
    if (meetingNoteId && !u.searchParams.get("view")) {
      u.searchParams.set("view", "table");
      window.history.replaceState({}, "", u.toString());
    }

    initMeetingAttendeePickers();
    wireFilters();
    wireViews();
    wireGanttToolbar();
    refreshTable();
    showView(getViewFromUrl());

    var sm = $("#mn-btn-save-meta");
    if (sm) sm.addEventListener("click", saveMeetingMeta);
    var ar = $("#mn-btn-add-row");
    if (ar) ar.addEventListener("click", createNewRow);
    var ni = $("#mn-btn-new-item");
    if (ni) ni.addEventListener("click", createNewRow);
    var exp = $("#mn-btn-export-pdf");
    if (exp) exp.addEventListener("click", exportTablePdf);

    var dueSel = document.getElementById("mn-filter-due");
    var customEls = document.querySelectorAll(".mn-due-custom");
    function syncDueCustom() {
      if (!dueSel) return;
      var on = dueSel.value === "custom";
      customEls.forEach(function (el) { el.classList.toggle("d-none", !on); });
    }
    if (dueSel) {
      dueSel.addEventListener("change", syncDueCustom);
      syncDueCustom();
    }

    loadActivity();

    wireMeetingEnhancements();

    const urlParams = new URLSearchParams(window.location.search);
    if (typeof MN_DEFAULT_ASSIGNEE === "number" && MN_DEFAULT_ASSIGNEE) {
      const assigneeSel = $("#mn-filter-assignee");
      if (assigneeSel) assigneeSel.value = String(MN_DEFAULT_ASSIGNEE);
    }
    const duePreset = urlParams.get("due_preset");
    if (duePreset) {
      const dueSel = $("#mn-filter-due");
      if (dueSel) dueSel.value = duePreset;
    }
    if ((typeof MN_DEFAULT_ASSIGNEE === "number" && MN_DEFAULT_ASSIGNEE) || duePreset) {
      refreshTable();
    }

    if (meetingNoteId && !new URLSearchParams(window.location.search).get("gantt_mode")) {
      setGanttModeInUrl("week");
    }
  });

  function wireMeetingEnhancements() {
    if (!meetingNoteId) return;

    $all("[data-mn-col-preset]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        applyColumnPreset(btn.getAttribute("data-mn-col-preset"));
      });
    });

    const metaToggle = $("#mn-meta-toggle");
    const metaBody = $("#mn-meta-body");
    if (metaToggle && metaBody) {
      metaToggle.addEventListener("click", function () {
        metaBody.classList.toggle("d-none");
      });
    }

    const saveFocus = $("#mn-btn-save-focus");
    if (saveFocus) {
      saveFocus.addEventListener("click", async function () {
        const platform = ($("#mn-fr-platform") || {}).value.trim() || "General";
        const focus = normalizeBulletText(($("#mn-fr-focus") || {}).value) || "General";
        try {
          const res = await fetch(API.focusRow(meetingNoteId), {
            method: "POST",
            headers: { "Content-Type": "application/json", Accept: "application/json" },
            body: JSON.stringify({ platform: platform, focus_area: focus, sort_order: 0 }),
          });
          if (!res.ok) throw new Error("Failed");
          const modal = document.getElementById("mnFocusModal");
          if (modal && window.bootstrap) bootstrap.Modal.getOrCreateInstance(modal).hide();
          await refreshTable();
          loadActivity();
        } catch (e) {
          alert("Could not save focus row");
        }
      });
    }

    const cfModal = document.getElementById("mnCarryForwardModal");
    const cfSource = $("#mn-cf-source");
    const cfPreview = $("#mn-cf-preview");
    const cfConfirm = $("#mn-btn-confirm-carry-forward");
    const cfMarkDone = $("#mn-cf-mark-done");

    async function refreshCarryForwardPreview() {
      if (!cfSource || !cfPreview || !meetingNoteId) return;
      const fromId = parseInt(cfSource.value, 10);
      if (!fromId || isNaN(fromId)) {
        cfPreview.innerHTML = '<span class="text-muted">Select a source meeting.</span>';
        if (cfConfirm) cfConfirm.disabled = true;
        return;
      }
      cfPreview.innerHTML = '<span class="text-muted">Loading preview…</span>';
      if (cfConfirm) cfConfirm.disabled = true;
      try {
        const res = await fetch(API.carryForwardPreview(meetingNoteId, fromId), {
          headers: { Accept: "application/json" },
        });
        const data = await res.json().catch(function () { return {}; });
        if (!res.ok) {
          cfPreview.innerHTML = '<span class="text-danger">' + escapeHtml(data.error || "Could not load preview") + "</span>";
          return;
        }
        const count = data.count || 0;
        const skipped = data.skipped_duplicate || 0;
        let html = "<strong>" + count + "</strong> item" + (count === 1 ? "" : "s") + " will be imported";
        if (data.from_meeting_title) {
          html += " from <em>" + escapeHtml(data.from_meeting_title) + "</em>";
        }
        if (skipped) {
          html += '. <span class="text-muted">' + skipped + " skipped (already on this meeting).</span>";
        }
        if (!count) {
          html = "No new items to import" + (skipped ? " (" + skipped + " duplicates skipped)." : ".");
        }
        cfPreview.innerHTML = html;
        if (cfConfirm) cfConfirm.disabled = count < 1;
      } catch (e) {
        cfPreview.innerHTML = '<span class="text-danger">Preview failed.</span>';
      }
    }

    if (cfSource) {
      cfSource.addEventListener("change", refreshCarryForwardPreview);
    }
    if (cfModal) {
      cfModal.addEventListener("shown.bs.modal", refreshCarryForwardPreview);
    }
    if (cfConfirm) {
      cfConfirm.addEventListener("click", async function () {
        if (!cfSource) return;
        const fromId = parseInt(cfSource.value, 10);
        if (!fromId || isNaN(fromId)) return;
        cfConfirm.disabled = true;
        const body = { from_meeting_id: fromId, mark_source_done: !!(cfMarkDone && cfMarkDone.checked) };
        const res = await fetch(API.carryForward(meetingNoteId), {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify(body),
        });
        const data = await res.json().catch(function () { return {}; });
        cfConfirm.disabled = false;
        if (!res.ok) {
          alert(data.error || "Carry forward failed");
          return;
        }
        let msg = "Added " + (data.created || 0) + " item(s).";
        if (data.skipped) msg += " Skipped " + data.skipped + " duplicate(s).";
        if (data.marked_source_done) msg += " Marked " + data.marked_source_done + " source item(s) done.";
        alert(msg);
        if (cfModal && window.bootstrap) bootstrap.Modal.getOrCreateInstance(cfModal).hide();
        refreshTable();
        loadActivity();
        refreshCarryForwardPreview();
      });
    }

    const dupBtn = $("#mn-btn-duplicate-meeting");
    if (dupBtn) {
      dupBtn.addEventListener("click", async function () {
        const title = prompt("Title for duplicated meeting:", (typeof MN_MEETING_TITLE === "string" ? MN_MEETING_TITLE : "") + " (copy)");
        if (!title) return;
        const res = await fetch(API.duplicateMeeting(meetingNoteId), {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify({ title: title, copy_items: true, copy_open_only: false }),
        });
        const data = await res.json().catch(function () { return {}; });
        if (!res.ok) { alert(data.error || "Duplicate failed"); return; }
        window.location.href = "/meeting-notes/" + data.id + "?view=table";
      });
    }

    const bulkApply = $("#mn-bulk-apply");
    if (bulkApply) {
      bulkApply.addEventListener("click", async function () {
        const ids = $all(".mn-row-chk:checked").map(function (c) {
          return parseInt(c.getAttribute("data-item-id"), 10);
        }).filter(Boolean);
        if (!ids.length) { alert("Select rows first."); return; }
        const payload = { item_ids: ids };
        const st = ($("#mn-bulk-status") || {}).value;
        if (st) payload.status = st;
        const aid = ($("#mn-bulk-assignee") || {}).value;
        if (aid) payload.assignee_ids = [parseInt(aid, 10)];
        const res = await fetch(API.bulkItems, {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify(payload),
        });
        if (!res.ok) { alert("Bulk update failed"); return; }
        refreshTable();
        loadActivity();
      });
    }

    const chkAll = $("#mn-chk-all");
    if (chkAll) {
      chkAll.addEventListener("change", function () {
        $all(".mn-row-chk").forEach(function (c) { c.checked = chkAll.checked; });
      });
    }

    $all(".mn-due-preset").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const tr = btn.closest("tr");
        if (!tr) return;
        const dueIn = tr.querySelector(".mn-cell-due");
        if (!dueIn) return;
        const days = parseInt(btn.getAttribute("data-days"), 10) || 7;
        const d = new Date();
        d.setDate(d.getDate() + days);
        dueIn.value = d.toISOString().slice(0, 10);
        scheduleRowSave(tr, { log: true });
      });
    });

    const actFilter = $("#mn-activity-filter");
    if (actFilter) actFilter.addEventListener("change", loadActivity);

    const expModalBtn = $("#mn-btn-export-pdf");
    if (expModalBtn && document.getElementById("mnExportModal")) {
      expModalBtn.setAttribute("data-bs-toggle", "modal");
      expModalBtn.setAttribute("data-bs-target", "#mnExportModal");
      const confirmExp = $("#mn-btn-confirm-export");
      if (confirmExp) {
        confirmExp.addEventListener("click", function () {
          const modal = document.getElementById("mnExportModal");
          if (modal && window.bootstrap) bootstrap.Modal.getOrCreateInstance(modal).hide();
          exportTablePdf();
        });
      }
    }
  }
})();
