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
    subtasks: function (itemId) { return "/meeting-notes/api/action-items/" + itemId + "/subtasks"; },
    subtask: function (id) { return "/meeting-notes/api/subtasks/" + id; },
    subtasksReorder: function (itemId) { return "/meeting-notes/api/action-items/" + itemId + "/subtasks/reorder"; },
    reorderItems: "/meeting-notes/api/action-items/reorder",
    labels: "/meeting-notes/api/labels",
    label: function (id) { return "/meeting-notes/api/labels/" + id; },
    savedViews: "/meeting-notes/api/saved-views",
    savedView: function (id) { return "/meeting-notes/api/saved-views/" + id; },
    meetingsSearch: "/meeting-notes/api/meetings/search",
    hubAnalytics: "/meeting-notes/api/hub/analytics",
    hubMyTasks: "/meeting-notes/api/hub/my-tasks",
    aiExtract: function (mid) { return "/meeting-notes/api/meetings/" + mid + "/ai/extract-tasks"; },
    aiApply: function (mid) { return "/meeting-notes/api/meetings/" + mid + "/ai/apply-tasks"; },
    aiSummarize: function (mid) { return "/meeting-notes/api/meetings/" + mid + "/ai/summarize"; },
    transcript: function (mid) { return "/meeting-notes/api/meetings/" + mid + "/transcript"; },
    emailReport: function (mid) { return "/meeting-notes/api/meetings/" + mid + "/email-report"; },
    templates: "/meeting-notes/api/templates",
    templateCreateMeeting: function (id) { return "/meeting-notes/api/templates/" + id + "/create-meeting"; },
    itemComments: function (id) { return "/meeting-notes/api/action-items/" + id + "/comments"; },
    pdfLogo: function (url) { return "/meeting-notes/api/pdf-logo?url=" + encodeURIComponent(url || ""); },
  };
  window.MN_API = API;

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
  const userOpts = Array.isArray(typeof MN_USER_OPTS !== "undefined" ? MN_USER_OPTS : null)
    ? MN_USER_OPTS
    : [];
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
  let lastItemsCache = [];
  let panelItemId = null;
  let panelItem = null;
  let panelReadOnly = false;
  let panelAssigneePicker = null;
  let dragItemId = null;
  const BOARD_STATUSES = ["open", "in_progress", "done"];
  const BOARD_STATUS_LABELS = { open: "Not started", in_progress: "In progress", done: "Completed" };
  const hubMode = typeof MN_HUB_MODE !== "undefined" && !!MN_HUB_MODE;
  const globalEditMode = typeof MN_GLOBAL_EDIT !== "undefined" && !!MN_GLOBAL_EDIT;
  const hubEditMode = typeof MN_HUB_EDIT !== "undefined" && !!MN_HUB_EDIT;
  function resolveCurrentUserId() {
    if (typeof MN_CURRENT_USER_ID === "number" && !isNaN(MN_CURRENT_USER_ID)) {
      return MN_CURRENT_USER_ID;
    }
    if (typeof MN_CURRENT_USER_ID === "string" && /^\d+$/.test(MN_CURRENT_USER_ID)) {
      return parseInt(MN_CURRENT_USER_ID, 10);
    }
    return null;
  }

  const currentUserId = resolveCurrentUserId();
  const TASK_PALETTES = {
    urgent: { border: "#dc2626", chipBg: "#fef2f2", chipText: "#b91c1c", rowBg: "#fff5f5" },
    high: { border: "#ea580c", chipBg: "#fff7ed", chipText: "#c2410c", rowBg: "#fffaf5" },
    medium: { border: "#0ea5e9", chipBg: "#eff6ff", chipText: "#0369a1", rowBg: "#f8fcff" },
    low: { border: "#94a3b8", chipBg: "#f8fafc", chipText: "#475569", rowBg: "#f8fafc" },
  };
  let boardGroupMode = "status";
  let labelsCache = [];

  function canEditItems() {
    return !!meetingNoteId || globalEditMode || (hubMode && hubEditMode);
  }

  function isReadOnlyView() {
    if (hubMode && !hubEditMode) return true;
    return !canEditItems();
  }
  let statusBoardTemplate = null;

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

  function formatLabelsPdf(labels) {
    if (!labels || !labels.length) return "";
    return labels.map(function (lb) { return lb.name || ""; }).filter(Boolean).join(", ");
  }

  function formatProgressPdf(it) {
    const total = it.subtask_total || 0;
    const done = it.subtask_done_count || 0;
    if (total) return done + "/" + total + " (" + (it.progress || 0) + "%)";
    if (it.progress) return (it.progress || 0) + "%";
    return "";
  }

  function formatSubtasksPdf(subtasks) {
    if (!subtasks || !subtasks.length) return "";
    return subtasks.map(function (st) {
      const mark = st.is_done ? "[x]" : "[ ]";
      const who = st.assignee_name || "(unassigned)";
      return "• " + mark + " " + (st.title || "") + " — " + who;
    }).join("\n");
  }

  function formatCommentThreadPdf(threads) {
    if (!threads || !threads.length) return "";
    return threads.map(function (c) {
      const when = c.created_at ? String(c.created_at).slice(0, 10) : "";
      return (c.author_name || "?") + (when ? " (" + when + ")" : "") + ": " + (c.body || "");
    }).join("\n");
  }

  function loadPdfLogoDataUrl(url) {
    if (!url) return Promise.resolve(null);
    return fetch(API.pdfLogo(url), {
      headers: { Accept: "application/json" },
      credentials: "same-origin",
    })
      .then(function (res) {
        if (!res.ok) throw new Error("logo proxy fetch failed");
        return res.json();
      })
      .then(function (data) {
        const dataUrl = data && data.data_url ? data.data_url : null;
        if (!dataUrl || dataUrl.indexOf("image/webp") === -1) return dataUrl;
        return new Promise(function (resolve) {
          const img = new Image();
          img.onload = function () {
            try {
              const canvas = document.createElement("canvas");
              canvas.width = img.naturalWidth || img.width;
              canvas.height = img.naturalHeight || img.height;
              const ctx = canvas.getContext("2d");
              ctx.drawImage(img, 0, 0);
              resolve(canvas.toDataURL("image/jpeg", 0.92));
            } catch (e) {
              resolve(dataUrl);
            }
          };
          img.onerror = function () { resolve(dataUrl); };
          img.src = dataUrl;
        });
      })
      .catch(function () { return null; });
  }

  function drawPdfPageChrome(doc, logoDataUrl, meta) {
    const pageW = doc.internal.pageSize.getWidth();
    const pageH = doc.internal.pageSize.getHeight();
    const pageNum = doc.internal.getNumberOfPages();
    const accent = [56, 189, 248];
    const primary = [3, 105, 161];
    const muted = [71, 85, 105];

    doc.setFillColor(248, 253, 255);
    doc.rect(0, 0, pageW, 56, "F");
    doc.setDrawColor(accent[0], accent[1], accent[2]);
    doc.setLineWidth(1.2);
    doc.line(24, 55, pageW - 24, 55);

    if (logoDataUrl) {
      try {
        const fmt = logoDataUrl.indexOf("image/png") !== -1 ? "PNG" : "JPEG";
        doc.addImage(logoDataUrl, fmt, 28, 14, 96, 28);
      } catch (e) {
        doc.setFontSize(16);
        doc.setTextColor(primary[0], primary[1], primary[2]);
        doc.text("Akello", 28, 32);
      }
    } else {
      doc.setFontSize(16);
      doc.setTextColor(primary[0], primary[1], primary[2]);
      doc.text("Akello", 28, 32);
    }

    doc.setFontSize(10);
    doc.setTextColor(primary[0], primary[1], primary[2]);
    doc.text("Meeting Notes Intelligence Report", pageW - 28, 30, { align: "right" });

    doc.setFillColor(246, 251, 255);
    doc.rect(0, pageH - 24, pageW, 24, "F");
    doc.setFontSize(8);
    doc.setTextColor(muted[0], muted[1], muted[2]);
    const footerY = pageH - 10;
    doc.text("Page " + pageNum, pageW - 28, footerY, { align: "right" });
    if (meta && meta.title) {
      const snippet = String(meta.title).slice(0, 60);
      doc.text(snippet, 28, footerY);
    }
  }

  function formatBulletsHtml(text) {
    const lines = normalizeBulletText(text).split("\n").filter(Boolean);
    if (!lines.length) return '<span class="text-muted">—</span>';
    return '<ul class="mn-bullets mb-0 ps-3">' + lines.map(function (l) {
      return "<li>" + escapeHtml(l) + "</li>";
    }).join("") + "</ul>";
  }

  function autoResizeTextarea(el) {
    if (!el || el.tagName !== "TEXTAREA") return;
    el.style.height = "auto";
    el.style.height = Math.max(el.scrollHeight, 52) + "px";
  }

  function wireAutoResize(root) {
    $all("textarea.mn-cell-bullets", root || document).forEach(function (ta) {
      autoResizeTextarea(ta);
      if (ta.getAttribute("data-auto-resize") === "1") return;
      ta.setAttribute("data-auto-resize", "1");
      ta.addEventListener("input", function () { autoResizeTextarea(ta); });
    });
  }

  function firstLineOfBullets(text) {
    const lines = normalizeBulletText(text).split("\n").filter(Boolean);
    return lines[0] || "Untitled action item";
  }

  function isItemOverdue(item) {
    if (!item || !item.due_date || item.status === "done") return false;
    const today = new Date().toISOString().slice(0, 10);
    return String(item.due_date).slice(0, 10) < today;
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
    const priority = ($("#mn-filter-priority") || {}).value;
    const label = ($("#mn-filter-label") || {}).value;
    const search = ($("#mn-filter-search") || {}).value;
    if (priority || label || search) return true;
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
    const priority = ($("#mn-filter-priority") || {}).value;
    if (priority) p.set("priority", priority);
    const label = ($("#mn-filter-label") || {}).value;
    if (label) p.set("label_id", label);
    const search = ($("#mn-filter-search") || {}).value;
    if (search) p.set("q", search);
    return p;
  }

  function setUrlView(view) {
    const u = new URL(window.location.href);
    u.searchParams.set("view", view);
    window.history.replaceState({}, "", u.toString());
  }

  function getViewFromUrl() {
    const v = new URLSearchParams(window.location.search).get("view");
    if (v === "calendar" || v === "gantt" || v === "table" || v === "board") return v;
    if ($("#mn-view-board")) return "board";
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

  function getBoardGroupFromUrl() {
    const g = new URLSearchParams(window.location.search).get("board_group");
    if (g === "platform" || g === "priority") return g;
    return "status";
  }

  function setBoardGroupInUrl(mode) {
    const u = new URL(window.location.href);
    u.searchParams.set("board_group", mode === "platform" || mode === "priority" ? mode : "status");
    window.history.replaceState({}, "", u.toString());
  }

  function ensureStatusBoardTemplate() {
    if (statusBoardTemplate) return;
    const board = $("#mn-board");
    if (board) statusBoardTemplate = board.innerHTML;
  }

  function normalizePlatformLabel(platform) {
    const p = (platform || "").trim();
    return p || "General";
  }

  function getBoardPlatforms(items) {
    const platforms = new Set();
    (items || []).forEach(function (it) {
      platforms.add(normalizePlatformLabel(it.platform));
    });
    const ordered = [];
    platformList.forEach(function (p) {
      if (platforms.has(p)) ordered.push(p);
    });
    Array.from(platforms).sort().forEach(function (p) {
      if (ordered.indexOf(p) < 0) ordered.push(p);
    });
    return ordered;
  }

  function sortItemsForBoardPlatform(items, platform, status) {
    const plat = normalizePlatformLabel(platform);
    return items.filter(function (it) {
      return normalizePlatformLabel(it.platform) === plat && (it.status || "open") === status;
    }).sort(function (a, b) {
      return (a.sort_order || 0) - (b.sort_order || 0) || a.id - b.id;
    });
  }

  function buildBoardColumnBody(platform, status, colItems, readOnly) {
    const body = document.createElement("div");
    body.className = "mn-board-column-body";
    body.setAttribute("data-board-drop", status);
    if (platform !== null && platform !== undefined) {
      body.setAttribute("data-platform", platform);
    }
    if (!colItems.length) {
      const empty = document.createElement("div");
      empty.className = "mn-board-empty";
      empty.textContent = status === "done" ? "No completed tasks" : status === "in_progress" ? "No tasks in progress" : "No tasks yet";
      body.appendChild(empty);
      return body;
    }
    colItems.forEach(function (it) {
      if (boardGroupMode === "platform") {
        body.appendChild(buildPlatformAccordionItem(it, status, readOnly));
      } else {
        body.appendChild(buildTaskCard(it, { readOnly: readOnly, compact: hubMode }));
      }
    });
    return body;
  }

  function buildPlatformAccordionItem(item, status, readOnly) {
    const wrap = document.createElement("div");
    wrap.className = "mn-platform-accordion-item";
    wrap.setAttribute("data-item-id", String(item.id));
    wrap.setAttribute("data-status", status);
    wrap.setAttribute("data-priority", (item.priority || "medium").toLowerCase());
    if (!readOnly && canEditItems()) wrap.setAttribute("draggable", "true");
    else wrap.setAttribute("draggable", "false");

    const panelId = "mn-plat-acc-body-" + item.id + "-" + status;
    const titleParts = splitCallToAction(item.call_to_action);
    const title = firstLineOfBullets(item.focus_area) || titleParts.title || "Action item";

    const header = document.createElement("button");
    header.type = "button";
    header.className = "mn-platform-accordion-header";
    header.setAttribute("aria-expanded", "false");
    header.setAttribute("aria-controls", panelId);
    header.innerHTML = '<span class="mn-platform-accordion-title">' + escapeHtml(title) + '</span>' +
      '<span class="mn-platform-accordion-meta">' + statusBadgeHtml(item.status) + "</span>";
    wrap.appendChild(header);

    const body = document.createElement("div");
    body.className = "mn-platform-accordion-body d-none";
    body.id = panelId;

    const previewText = titleParts.title && firstLineOfBullets(item.focus_area)
      ? titleParts.title
      : (titleParts.extra || titleParts.title || "");
    if (previewText) {
      const preview = document.createElement("div");
      preview.className = "mn-platform-accordion-preview";
      preview.textContent = previewText;
      body.appendChild(preview);
    }

    const meta = document.createElement("div");
    meta.className = "mn-task-card-meta";
    if (item.priority && item.priority !== "medium") {
      const pr = document.createElement("span");
      pr.className = "mn-task-chip mn-priority-chip mn-priority-" + item.priority;
      pr.textContent = item.priority;
      meta.appendChild(pr);
    }
    if (item.due_date) {
      const due = document.createElement("span");
      due.className = "mn-task-chip" + (isItemOverdue(item) ? " mn-task-chip-overdue" : "");
      due.textContent = "Due " + dateVal(item.due_date);
      meta.appendChild(due);
    }
    if (item.labels && item.labels.length) {
      const lblWrap = document.createElement("span");
      lblWrap.className = "mn-task-labels";
      lblWrap.innerHTML = labelsHtml(item.labels);
      meta.appendChild(lblWrap);
    }
    body.appendChild(meta);

    const names = item.assignee_names || getAssigneeLabels(item.assignee_ids);
    if (names.length) {
      const assignWrap = document.createElement("div");
      assignWrap.className = "mb-1";
      assignWrap.innerHTML = assigneeChipsHtml(names);
      body.appendChild(assignWrap);
    }

    renderSubtaskProgress(item, body);

    const footer = document.createElement("div");
    footer.className = "mn-task-card-footer";
    if (readOnly) {
      const viewBtn = document.createElement("button");
      viewBtn.type = "button";
      viewBtn.className = "btn btn-sm mn-btn-ghost";
      viewBtn.textContent = "View details";
      viewBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        openTaskPanel(item, true);
      });
      footer.appendChild(viewBtn);
    } else {
      const statusSel = document.createElement("select");
      statusSel.className = "form-select form-select-sm mn-card-status";
      statusSel.style.maxWidth = "8rem";
      ["open", "in_progress", "done"].forEach(function (s) {
        const opt = document.createElement("option");
        opt.value = s;
        opt.textContent = s === "in_progress" ? "In progress" : s.charAt(0).toUpperCase() + s.slice(1);
        if ((item.status || "open") === s) opt.selected = true;
        statusSel.appendChild(opt);
      });
      statusSel.addEventListener("change", async function () {
        const newStatus = statusSel.value;
        try {
          const res = await putActionItem(item.id, { status: newStatus, silent: true });
          if (!res.ok) throw new Error("Status update failed");
          item.status = newStatus;
          await refreshItems();
          loadActivity();
        } catch (e) {
          console.error(e);
          statusSel.value = item.status || "open";
        }
      });
      footer.appendChild(statusSel);

      const editBtn = document.createElement("button");
      editBtn.type = "button";
      editBtn.className = "btn btn-sm mn-btn-ghost";
      editBtn.textContent = "Expand";
      editBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        openTaskPanel(item, false);
      });
      footer.appendChild(editBtn);
    }
    body.appendChild(footer);
    wrap.appendChild(body);

    header.addEventListener("click", function () {
      const hidden = body.classList.toggle("d-none");
      header.setAttribute("aria-expanded", hidden ? "false" : "true");
    });

    if (!readOnly && canEditItems()) {
      wrap.addEventListener("dragstart", function (e) {
        dragItemId = item.id;
        wrap.classList.add("is-dragging");
        if (e.dataTransfer) {
          e.dataTransfer.effectAllowed = "move";
          e.dataTransfer.setData("text/plain", String(item.id));
        }
      });
      wrap.addEventListener("dragend", function () {
        dragItemId = null;
        wrap.classList.remove("is-dragging");
        $all(".mn-board-column.is-drag-over").forEach(function (col) {
          col.classList.remove("is-drag-over");
        });
      });
    }

    return wrap;
  }

  function buildBoardStatusColumns(items, platform, readOnly) {
    const frag = document.createDocumentFragment();
    BOARD_STATUSES.forEach(function (status) {
      const col = document.createElement("div");
      col.className = "mn-board-column";
      col.setAttribute("data-status", status);
      const header = document.createElement("div");
      header.className = "mn-board-column-header";
      const colItems = platform === null
        ? sortItemsForBoard(items, status)
        : sortItemsForBoardPlatform(items, platform, status);
      header.innerHTML = "<span>" + escapeHtml(BOARD_STATUS_LABELS[status] || status) + "</span>" +
        '<span class="mn-board-count" data-board-count="' + status + '">' + colItems.length + "</span>";
      col.appendChild(header);
      col.appendChild(buildBoardColumnBody(platform, status, colItems, readOnly));
      frag.appendChild(col);
    });
    return frag;
  }

  function getBoardPriorities(items) {
    const order = ["urgent", "high", "medium", "low"];
    const found = new Set();
    (items || []).forEach(function (it) { found.add((it.priority || "medium").toLowerCase()); });
    return order.filter(function (p) { return found.has(p); });
  }

  function sortItemsForBoardPriority(items, priority, status) {
    return items.filter(function (it) {
      return (it.priority || "medium").toLowerCase() === priority && (it.status || "open") === status;
    }).sort(function (a, b) {
      return (a.sort_order || 0) - (b.sort_order || 0) || a.id - b.id;
    });
  }

  function setBoardGroupMode(mode) {
    boardGroupMode = mode === "platform" ? "platform" : mode === "priority" ? "priority" : "status";
    setBoardGroupInUrl(boardGroupMode);
    $all("[data-mn-board-group]").forEach(function (btn) {
      btn.classList.toggle("active", btn.getAttribute("data-mn-board-group") === boardGroupMode);
    });
    const toggle = $("#mn-board-group-toggle");
    if (toggle) toggle.classList.remove("d-none");
    if (lastItemsCache.length) renderBoard(lastItemsCache);
  }

  function updateBoardGroupToggleVisibility(viewMode) {
    const toggle = $("#mn-board-group-toggle");
    if (!toggle) return;
    toggle.classList.toggle("d-none", viewMode !== "board");
  }

  function splitCallToAction(text) {
    const normalized = normalizeBulletText(text || "");
    const lines = normalized ? normalized.split("\n") : [];
    return { title: lines[0] || "", extra: lines.slice(1).join("\n") };
  }

  function mergeCallToAction(title, extra) {
    const t = (title || "").trim();
    const e = (extra || "").trim();
    if (!t && !e) return "";
    if (!e) return t;
    return t + "\n" + e;
  }

  function renderSubtaskProgress(item, parentEl) {
    const total = item.subtask_total || 0;
    if (!total) return;
    const done = item.subtask_done_count || 0;
    const wrap = document.createElement("div");
    wrap.className = "mn-task-subtask-progress";
    const label = document.createElement("div");
    label.className = "mn-task-subtask-progress-label";
    label.innerHTML = "<span>Sub-tasks</span><span>" + done + "/" + total + "</span>";
    const bar = document.createElement("div");
    bar.className = "mn-task-subtask-progress-bar";
    const fill = document.createElement("div");
    fill.className = "mn-task-subtask-progress-fill";
    fill.style.width = String(Math.round(100 * done / total)) + "%";
    bar.appendChild(fill);
    wrap.appendChild(label);
    wrap.appendChild(bar);
    parentEl.appendChild(wrap);
  }

  function renderReadonlySubtasksHtml(item) {
    const subtasks = item.subtasks || [];
    if (!subtasks.length) return "";
    let html = '<label class="mn-filter-label">Sub-tasks</label><ul class="list-unstyled mb-2">';
    subtasks.forEach(function (st) {
      const cls = st.is_done ? " mn-subtask-readonly is-done" : " mn-subtask-readonly";
      const who = st.assignee_name ? ' <span class="text-muted small">(' + escapeHtml(st.assignee_name) + ")</span>" : "";
      html += '<li class="' + cls + '">' + (st.is_done ? "☑ " : "☐ ") + escapeHtml(st.title) + who + "</li>";
    });
    html += "</ul>";
    return html;
  }

  function showView(mode) {
    $all(".mn-view").forEach(function (el) { el.classList.add("d-none"); });
    const el = $("#mn-view-" + mode);
    if (el) el.classList.remove("d-none");
    $all("[data-mn-view-btn]").forEach(function (b) {
      b.classList.toggle("active", b.getAttribute("data-mn-view-btn") === mode);
    });
    setUrlView(mode);
    updateBoardGroupToggleVisibility(mode);
    if (mode === "calendar") refreshCalendar();
    if (mode === "gantt") refreshGantt();
    if (mode === "board" && lastItemsCache.length) renderBoard(lastItemsCache);
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
    const pr = ((tr.getAttribute("data-priority") || "medium") + "").toLowerCase();
    const pal = TASK_PALETTES[pr] || TASK_PALETTES.medium;
    tr.style.setProperty("--mn-row-accent", pal.border);
    tr.style.setProperty("--mn-row-bg", pal.rowBg);
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

  function priorityBadgeHtml(priority) {
    const pr = (priority || "medium").toLowerCase();
    const pal = TASK_PALETTES[pr] || TASK_PALETTES.medium;
    return '<span class="mn-priority-badge mn-priority-' + pr + '" style="background:' + pal.chipBg + ";color:" + pal.chipText + ';border-color:' + pal.border + '">' + escapeHtml(pr) + "</span>";
  }

  function labelsHtml(labels) {
    if (!labels || !labels.length) return "";
    return labels.map(function (lb) {
      return '<span class="mn-label-pill" style="--mn-label-color:' + escapeHtml(lb.color || "#64748b") + '">' +
        escapeHtml(lb.name) + "</span>";
    }).join("");
  }

  function assigneeChipsHtml(names) {
    if (!names || !names.length) return '<span class="text-muted">—</span>';
    return '<div class="mn-assignee-readonly">' + names.map(function (n) {
      return '<span class="mn-assignee-chip">' + escapeHtml(n) + "</span>";
    }).join("") + "</div>";
  }

  function buildLabelPicker(selectedIds, onChange) {
    const wrap = document.createElement("div");
    wrap.className = "mn-label-picker";
    let selected = (selectedIds || []).map(function (x) { return parseInt(x, 10); }).filter(Boolean);
    wrap.setAttribute("data-label-ids", JSON.stringify(selected));
    const chipsEl = document.createElement("div");
    chipsEl.className = "mn-label-chips d-flex flex-wrap gap-1 mb-1";
    const sel = document.createElement("select");
    sel.className = "form-select form-select-sm";
    sel.innerHTML = '<option value="">Add label…</option>';
    labelsCache.forEach(function (lb) {
      const opt = document.createElement("option");
      opt.value = String(lb.id);
      opt.textContent = lb.name;
      sel.appendChild(opt);
    });
    function render() {
      chipsEl.innerHTML = "";
      selected.forEach(function (lid) {
        const lb = labelsCache.find(function (l) { return l.id === lid; });
        if (!lb) return;
        const chip = document.createElement("span");
        chip.className = "mn-label-pill";
        chip.style.setProperty("--mn-label-color", lb.color || "#64748b");
        chip.textContent = lb.name;
        const rm = document.createElement("button");
        rm.type = "button";
        rm.className = "mn-label-remove";
        rm.innerHTML = "&times;";
        rm.addEventListener("click", function () {
          selected = selected.filter(function (id) { return id !== lid; });
          wrap.setAttribute("data-label-ids", JSON.stringify(selected));
          render();
          if (onChange) onChange();
        });
        chip.appendChild(rm);
        chipsEl.appendChild(chip);
      });
    }
    sel.addEventListener("change", function () {
      const lid = parseInt(sel.value, 10);
      if (!lid || selected.indexOf(lid) >= 0) return;
      selected.push(lid);
      wrap.setAttribute("data-label-ids", JSON.stringify(selected));
      sel.value = "";
      render();
      if (onChange) onChange();
    });
    render();
    wrap.appendChild(chipsEl);
    wrap.appendChild(sel);
    return wrap;
  }

  function meetingAttendeeUserOpts(item) {
    const allowed = {};
    const meetingIds = item && item.meeting_attendee_ids && item.meeting_attendee_ids.length
      ? item.meeting_attendee_ids
      : mnMeetingAttendeeIds;
    (meetingIds || []).forEach(function (id) {
      const n = parseInt(id, 10);
      if (n) allowed[n] = true;
    });
    (item && item.assignee_ids || []).forEach(function (id) {
      const n = parseInt(id, 10);
      if (n) allowed[n] = true;
    });
    return userOpts.filter(function (u) { return !!allowed[u.id]; });
  }

  function buildAssigneePicker(selectedIds, onChange, pool) {
    const optsPool = Array.isArray(pool) && pool.length ? pool : userOpts;
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
        const u = optsPool.find(function (o) { return o.id === uid; });
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
      if (!qq) return optsPool.filter(function (u) { return selected.indexOf(u.id) < 0; }).slice(0, 8);
      return optsPool.filter(function (u) {
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
      priority: get(".mn-cell-priority") || "medium",
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
          priority: p.priority,
          start_date: p.start_date,
          due_date: p.due_date,
          assignee_ids: p.assignee_ids,
          silent: silent,
        };
        if (opts.logText) itemPayload.log_text_edit = true;
        const itemRes = await putActionItem(parseInt(itemId, 10), itemPayload);
        if (!itemRes.ok) throw new Error("Item save failed");
        tr.setAttribute("data-priority", (p.priority || "medium").toLowerCase());
        applyStatusRowClass(tr, p.status);
        setRowSaveState(tr, "saved");
        if (calendar) calendar.refetchEvents();
        if (ganttInst && $("#mn-view-gantt") && !$("#mn-view-gantt").classList.contains("d-none")) {
          refreshGantt();
        }
        if ($("#mn-view-board") && !$("#mn-view-board").classList.contains("d-none")) {
          refreshItems();
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
      tr.setAttribute("data-priority", (item.priority || "medium").toLowerCase());
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
        if (el.classList.contains("mn-cell-bullets")) autoResizeTextarea(el);
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
      tr.setAttribute("data-priority", "medium");
      applyStatusRowClass(tr, "open");
    } else {
      tr.setAttribute("data-item-id", String(it.id));
      tr.setAttribute("data-focus-row-id", String(it.focus_row_id));
      tr.setAttribute("data-priority", (it.priority || "medium").toLowerCase());
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
      "Enter for new bullets"
    ));

    tr.appendChild(cellBulletTextarea(
      "mn-cell-cta",
      isTemplate ? "" : (it.call_to_action || ""),
      "Enter for new bullets"
    ));

    tr.appendChild(cellBulletTextarea(
      "mn-cell-impact",
      isTemplate ? "" : it.expected_impact,
      "Enter for new bullets"
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
      "Enter for new bullets"
    ));
    tr.appendChild(cellBulletTextarea(
      "mn-cell-comments",
      isTemplate ? "" : it.comments,
      "Enter for new bullets"
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
    $all("textarea.mn-cell-bullets", tr).forEach(autoResizeTextarea);
    return tr;
  }

  function buildTaskCard(item, opts) {
    opts = opts || {};
    const readOnly = !!opts.readOnly;
    const compact = !!opts.compact;
    const card = document.createElement("article");
    card.className = "mn-task-card" + (readOnly ? " mn-task-card-readonly" : "") + (compact ? " mn-task-card-compact" : "");
    card.setAttribute("data-item-id", String(item.id));
    card.setAttribute("data-status", item.status || "open");
    card.setAttribute("data-priority", item.priority || "medium");
    card.setAttribute("data-focus-row-id", String(item.focus_row_id || ""));

    const hl = new URLSearchParams(window.location.search).get("highlight");
    if (hl && String(item.id) === String(hl)) card.classList.add("mn-highlight");

    const focusLine = normalizeBulletText(item.focus_area || "").split("\n").filter(Boolean)[0] || "";
    const ctaParts = splitCallToAction(item.call_to_action);
    const taskTitle = ctaParts.title || "Untitled action item";

    const title = document.createElement("div");
    title.className = "mn-task-card-title";
    if (focusLine) {
      title.textContent = compact ? focusLine + "\n" + taskTitle : focusLine;
    } else {
      title.textContent = taskTitle;
    }
    card.appendChild(title);

    if (!compact) {
      const previewText = focusLine
        ? (ctaParts.extra ? taskTitle + "\n" + ctaParts.extra : taskTitle)
        : (ctaParts.extra || "");
      if (previewText) {
        const preview = document.createElement("div");
        preview.className = "mn-task-card-preview";
        preview.textContent = previewText;
        card.appendChild(preview);
      }
    }

    const meta = document.createElement("div");
    meta.className = "mn-task-card-meta";
    if (item.priority && item.priority !== "medium") {
      const pr = document.createElement("span");
      pr.className = "mn-task-chip mn-priority-chip mn-priority-" + item.priority;
      pr.textContent = item.priority;
      meta.appendChild(pr);
    }
    if (item.platform) {
      const chip = document.createElement("span");
      chip.className = "mn-task-chip";
      chip.textContent = item.platform;
      meta.appendChild(chip);
    }
    if (item.labels && item.labels.length) {
      const lblWrap = document.createElement("span");
      lblWrap.className = "mn-task-labels";
      lblWrap.innerHTML = labelsHtml(item.labels);
      meta.appendChild(lblWrap);
    }
    if (item.due_date) {
      const due = document.createElement("span");
      due.className = "mn-task-chip" + (isItemOverdue(item) ? " mn-task-chip-overdue" : "");
      due.textContent = "Due " + dateVal(item.due_date);
      meta.appendChild(due);
    }
    if (compact && item.meeting_title) {
      const mt = document.createElement("span");
      mt.className = "mn-task-chip";
      mt.textContent = item.meeting_title;
      meta.appendChild(mt);
    }
    card.appendChild(meta);

    const names = item.assignee_names || getAssigneeLabels(item.assignee_ids);
    if (names.length) {
      const assignWrap = document.createElement("div");
      assignWrap.className = "mb-1";
      assignWrap.innerHTML = assigneeChipsHtml(names);
      card.appendChild(assignWrap);
    }

    renderSubtaskProgress(item, card);

    const footer = document.createElement("div");
    footer.className = "mn-task-card-footer";

    if (readOnly) {
      const expandBtn = document.createElement("button");
      expandBtn.type = "button";
      expandBtn.className = "btn btn-sm mn-btn-ghost";
      expandBtn.textContent = "View details";
      expandBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        openTaskPanel(item, true);
      });
      footer.appendChild(expandBtn);
      if (item.meeting_note_id) {
        const link = document.createElement("a");
        link.className = "btn btn-sm mn-btn-primary";
        link.href = "/meeting-notes/" + item.meeting_note_id + "?view=board&highlight=" + item.id;
        link.textContent = "Open";
        footer.appendChild(link);
      }
    } else {
      if (!canEditItems()) card.setAttribute("draggable", "false");
      else card.setAttribute("draggable", "true");

      const statusSel = document.createElement("select");
      statusSel.className = "form-select form-select-sm mn-card-status";
      statusSel.style.maxWidth = "8rem";
      ["open", "in_progress", "done"].forEach(function (s) {
        const opt = document.createElement("option");
        opt.value = s;
        opt.textContent = s === "in_progress" ? "In progress" : s.charAt(0).toUpperCase() + s.slice(1);
        if ((item.status || "open") === s) opt.selected = true;
        statusSel.appendChild(opt);
      });
      statusSel.addEventListener("change", async function () {
        const newStatus = statusSel.value;
        try {
          const res = await putActionItem(item.id, { status: newStatus, silent: true });
          if (!res.ok) throw new Error("Status update failed");
          item.status = newStatus;
          card.setAttribute("data-status", newStatus);
          if (hubMode) await loadMyTasksHub();
          else {
            await refreshItems();
            loadActivity();
          }
        } catch (e) {
          console.error(e);
          statusSel.value = item.status || "open";
        }
      });
      footer.appendChild(statusSel);

      const expandBtn = document.createElement("button");
      expandBtn.type = "button";
      expandBtn.className = "btn btn-sm mn-btn-ghost";
      expandBtn.textContent = "Expand";
      expandBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        openTaskPanel(item, false);
      });
      footer.appendChild(expandBtn);
    }

    card.appendChild(footer);

    if (!readOnly && canEditItems()) {
      card.addEventListener("dragstart", function (e) {
        dragItemId = item.id;
        card.classList.add("is-dragging");
        if (e.dataTransfer) {
          e.dataTransfer.effectAllowed = "move";
          e.dataTransfer.setData("text/plain", String(item.id));
        }
      });
      card.addEventListener("dragend", function () {
        dragItemId = null;
        card.classList.remove("is-dragging");
        $all(".mn-board-column.is-drag-over").forEach(function (col) {
          col.classList.remove("is-drag-over");
        });
      });
    }

    return card;
  }

  function sortItemsForBoard(items, status) {
    return items.filter(function (it) { return (it.status || "open") === status; })
      .sort(function (a, b) {
        return (a.sort_order || 0) - (b.sort_order || 0) || a.id - b.id;
      });
  }

  function renderBoard(items) {
    const board = $("#mn-board");
    if (!board) return;
    lastItemsCache = items || [];
    const readOnly = isReadOnlyView();
    ensureStatusBoardTemplate();

    if (boardGroupMode === "platform" || boardGroupMode === "priority") {
      board.className = "mn-board mn-board-platform-mode";
      board.innerHTML = "";
      const lanes = boardGroupMode === "priority"
        ? getBoardPriorities(lastItemsCache)
        : getBoardPlatforms(lastItemsCache);
      if (!lanes.length) {
        const empty = document.createElement("div");
        empty.className = "mn-board-empty";
        empty.textContent = "No tasks match the current filters.";
        board.appendChild(empty);
      } else {
        lanes.forEach(function (lane) {
          const section = document.createElement("section");
          section.className = "mn-board-platform-section";
          section.setAttribute("data-platform", lane);
          const header = document.createElement("div");
          header.className = "mn-board-platform-header";
          header.textContent = boardGroupMode === "priority" ? ("Priority: " + lane) : lane;
          section.appendChild(header);
          const columns = document.createElement("div");
          columns.className = "mn-board-platform-columns";
          if (boardGroupMode === "priority") {
            const frag = document.createDocumentFragment();
            BOARD_STATUSES.forEach(function (status) {
              const col = document.createElement("div");
              col.className = "mn-board-column";
              col.setAttribute("data-status", status);
              const headerCol = document.createElement("div");
              headerCol.className = "mn-board-column-header";
              const colItems = sortItemsForBoardPriority(lastItemsCache, lane, status);
              headerCol.innerHTML = "<span>" + escapeHtml(BOARD_STATUS_LABELS[status] || status) + "</span>" +
                '<span class="mn-board-count">' + colItems.length + "</span>";
              col.appendChild(headerCol);
              const body = document.createElement("div");
              body.className = "mn-board-column-body";
              body.setAttribute("data-board-drop", status);
              body.setAttribute("data-platform", lane);
              colItems.forEach(function (it) {
                body.appendChild(buildTaskCard(it, { readOnly: readOnly, compact: hubMode }));
              });
              if (!colItems.length) {
                const empty = document.createElement("div");
                empty.className = "mn-board-empty";
                empty.textContent = "—";
                body.appendChild(empty);
              }
              col.appendChild(body);
              frag.appendChild(col);
            });
            columns.appendChild(frag);
          } else {
            columns.appendChild(buildBoardStatusColumns(lastItemsCache, lane, readOnly));
          }
          section.appendChild(columns);
          board.appendChild(section);
        });
      }
    } else {
      board.className = "mn-board";
      if (statusBoardTemplate) board.innerHTML = statusBoardTemplate;
      BOARD_STATUSES.forEach(function (status) {
        const body = board.querySelector('[data-board-drop="' + status + '"]');
        const countEl = board.querySelector('[data-board-count="' + status + '"]');
        if (!body) return;
        body.innerHTML = "";
        const colItems = sortItemsForBoard(lastItemsCache, status);
        if (countEl) countEl.textContent = String(colItems.length);
        if (!colItems.length) {
          const empty = document.createElement("div");
          empty.className = "mn-board-empty";
          empty.textContent = status === "done" ? "No completed tasks" : status === "in_progress" ? "No tasks in progress" : "No tasks yet";
          body.appendChild(empty);
          return;
        }
        colItems.forEach(function (it) {
          body.appendChild(buildTaskCard(it, { readOnly: readOnly, compact: hubMode }));
        });
      });
    }
    wireBoardDnD();
    applyHighlightScroll();
  }

  function applyHighlightScroll() {
    const hl = new URLSearchParams(window.location.search).get("highlight");
    if (!hl) return;
    const card = document.querySelector('.mn-task-card[data-item-id="' + hl + '"]');
    const row = document.querySelector('tr[data-item-id="' + hl + '"]');
    const target = card || row;
    if (target) {
      target.classList.add("mn-highlight");
      setTimeout(function () { target.scrollIntoView({ block: "center", behavior: "smooth" }); }, 200);
    }
  }

  function wireBoardDnD() {
    if (!canEditItems()) return;
    const board = $("#mn-board");
    if (!board) return;
    if (board.getAttribute("data-dnd-wired") === "1") return;
    board.setAttribute("data-dnd-wired", "1");

    board.addEventListener("dragover", function (e) {
      const body = e.target.closest("[data-board-drop]");
      if (!body || !board.contains(body)) return;
      e.preventDefault();
      if (e.dataTransfer) e.dataTransfer.dropEffect = "move";
      const col = body.closest(".mn-board-column");
      if (col) col.classList.add("is-drag-over");
    });
    board.addEventListener("dragleave", function (e) {
      const col = e.target.closest(".mn-board-column");
      if (col && !col.contains(e.relatedTarget)) col.classList.remove("is-drag-over");
    });
    board.addEventListener("drop", function (e) {
      const body = e.target.closest("[data-board-drop]");
      if (!body || !board.contains(body)) return;
      e.preventDefault();
      const col = body.closest(".mn-board-column");
      if (col) col.classList.remove("is-drag-over");
      const targetStatus = body.getAttribute("data-board-drop");
      const targetPlatform = body.getAttribute("data-platform");
      const itemId = dragItemId || parseInt((e.dataTransfer && e.dataTransfer.getData("text/plain")) || "0", 10);
      if (!itemId || !targetStatus) return;
      handleBoardDrop(itemId, targetStatus, targetPlatform, e.target.closest(".mn-task-card"));
    });
  }

  function getColumnItemsForDrop(itemId, targetStatus, targetPlatform) {
    if (boardGroupMode === "platform" && targetPlatform) {
      return sortItemsForBoardPlatform(lastItemsCache, targetPlatform, targetStatus)
        .filter(function (it) { return it.id !== itemId; });
    }
    return sortItemsForBoard(lastItemsCache, targetStatus)
      .filter(function (it) { return it.id !== itemId; });
  }

  async function handleBoardDrop(itemId, targetStatus, targetPlatform, beforeCard) {
    const item = lastItemsCache.find(function (it) { return it.id === itemId; });
    if (!item) return;
    const colItems = getColumnItemsForDrop(itemId, targetStatus, targetPlatform);
    let insertIdx = colItems.length;
    if (beforeCard && beforeCard.getAttribute("data-item-id")) {
      const beforeId = parseInt(beforeCard.getAttribute("data-item-id"), 10);
      const idx = colItems.findIndex(function (it) { return it.id === beforeId; });
      if (idx >= 0) insertIdx = idx;
    }
    const nextPlatform = targetPlatform ? normalizePlatformLabel(targetPlatform) : normalizePlatformLabel(item.platform);
    const platformChanged = normalizePlatformLabel(item.platform) !== nextPlatform;
    colItems.splice(insertIdx, 0, Object.assign({}, item, { status: targetStatus, platform: nextPlatform }));
    try {
      if (platformChanged && item.focus_row_id) {
        const frRes = await putFocusRow(item.focus_row_id, { platform: nextPlatform, silent: true });
        if (!frRes.ok) throw new Error("Platform update failed");
      }
      await Promise.all(colItems.map(function (it, idx) {
        const payload = { sort_order: idx, silent: true };
        if (it.id === itemId) payload.status = targetStatus;
        return putActionItem(it.id, payload);
      }));
      await refreshItems();
      loadActivity();
    } catch (e) {
      console.error(e);
      alert("Could not update task order");
      await refreshItems();
    }
  }

  function setPanelSaveHint(state, msg) {
    const hint = $("#mn-panel-save-hint");
    if (!hint) return;
    hint.className = "mn-panel-save-hint";
    if (state === "saving") hint.classList.add("is-saving");
    if (state === "saved") hint.classList.add("is-saved");
    if (state === "error") hint.classList.add("is-error");
    hint.textContent = msg || "";
  }

  function openTaskPanel(item, readOnly) {
    const backdrop = $("#mn-task-panel-backdrop");
    const panel = $("#mn-task-panel");
    if (!panel) return;
    panelItemId = item.id;
    panelItem = item;
    if (window.MN) {
      window.MN._panelItemId = item.id;
      window.MN._panelItem = item;
      window.MN._panelAttendeeUserOpts = meetingAttendeeUserOpts(item);
    }
    panelReadOnly = readOnly;

    const editableBody = $("#mn-panel-editable-body");
    const readonlyBody = $("#mn-panel-readonly-body");
    if (editableBody) editableBody.classList.toggle("d-none", readOnly);
    if (readonlyBody) readonlyBody.classList.toggle("d-none", !readOnly);

    if (readOnly) {
      const body = readonlyBody || $("#mn-panel-readonly-body");
      if (body) {
        const ctaParts = splitCallToAction(item.call_to_action);
        body.innerHTML =
          "<p class=\"small text-muted mb-2\">" + escapeHtml(item.meeting_title || "") +
          (item.meeting_date ? " · " + escapeHtml(item.meeting_date) : "") + "</p>" +
          "<label class=\"mn-filter-label\">Task title</label><div class=\"mb-2\">" + formatBulletsHtml(ctaParts.title) + "</div>" +
          renderReadonlySubtasksHtml(item) +
          "<label class=\"mn-filter-label\">Expected impact</label><div class=\"mb-2\">" + formatBulletsHtml(item.expected_impact) + "</div>" +
          "<label class=\"mn-filter-label\">Challenges</label><div class=\"mb-2\">" + formatBulletsHtml(item.challenges) + "</div>" +
          "<label class=\"mn-filter-label\">Comments</label><div class=\"mb-2\">" + formatBulletsHtml(item.comments) + "</div>" +
          "<p class=\"small mb-0\"><strong>Status:</strong> " + statusBadgeHtml(item.status) + "</p>";
      }
      const openLink = $("#mn-panel-open-meeting");
      if (openLink && item.meeting_note_id) {
        openLink.href = "/meeting-notes/" + item.meeting_note_id + "?view=board&highlight=" + item.id;
        openLink.classList.remove("d-none");
      }
    } else {
      const title = $("#mn-panel-title");
      if (title) title.textContent = firstLineOfBullets(item.call_to_action);
      const sub = $("#mn-panel-subtitle");
      if (sub) sub.textContent = (item.platform || "") + (item.focus_area ? " · " + firstLineOfBullets(item.focus_area) : "");
      const setVal = function (id, val) { const el = $(id); if (el) el.value = val || ""; };
      const ctaParts = splitCallToAction(item.call_to_action);
      setVal("#mn-panel-platform", item.platform);
      setVal("#mn-panel-focus", item.focus_area);
      setVal("#mn-panel-task-title", ctaParts.title);
      setVal("#mn-panel-cta", mergeCallToAction(ctaParts.title, ctaParts.extra));
      setVal("#mn-panel-impact", item.expected_impact);
      setVal("#mn-panel-challenges", item.challenges);
      setVal("#mn-panel-comments", item.comments);
      setVal("#mn-panel-start", dateVal(item.start_date));
      setVal("#mn-panel-due", dateVal(item.due_date));
      setVal("#mn-panel-status", item.status || "open");
      setVal("#mn-panel-priority", item.priority || "medium");
      const labelHost = $("#mn-panel-labels");
      if (labelHost) {
        labelHost.innerHTML = "";
        labelHost.appendChild(buildLabelPicker(item.label_ids || [], function () {
          schedulePanelSave({ log: true });
        }));
      }
      const assignHost = $("#mn-panel-assignees");
      if (assignHost) {
        assignHost.innerHTML = "";
        panelAssigneePicker = buildAssigneePicker(item.assignee_ids, function () {
          schedulePanelSave({ log: true });
        });
        assignHost.appendChild(panelAssigneePicker);
      }
      renderPanelSubtasks(item);
      wireAutoResize(panel);
      setPanelSaveHint("", "");
    }

    if (backdrop) {
      backdrop.classList.add("is-open");
      backdrop.setAttribute("aria-hidden", "false");
    }
    panel.classList.add("is-open");
    panel.setAttribute("aria-hidden", "false");
  }

  function closeTaskPanel() {
    const backdrop = $("#mn-task-panel-backdrop");
    const panel = $("#mn-task-panel");
    if (backdrop) {
      backdrop.classList.remove("is-open");
      backdrop.setAttribute("aria-hidden", "true");
    }
    if (panel) {
      panel.classList.remove("is-open");
      panel.setAttribute("aria-hidden", "true");
    }
    panelItemId = null;
    panelItem = null;
    panelReadOnly = false;
    if (window.MN) {
      window.MN._panelItem = null;
      window.MN._panelAttendeeUserOpts = [];
    }
  }

  function renderPanelSubtasks(item) {
    const host = $("#mn-panel-subtasks");
    if (!host) return;
    host.innerHTML = "";
    const pool = meetingAttendeeUserOpts(item);
    const subtasks = (item.subtasks || []).slice().sort(function (a, b) {
      return (a.sort_order || 0) - (b.sort_order || 0) || a.id - b.id;
    });
    subtasks.forEach(function (st, idx) {
      host.appendChild(buildSubtaskRow(st, item.id, idx, subtasks.length, pool));
    });
  }

  function buildSubtaskAssigneeSelect(st, itemId, pool) {
    const sel = document.createElement("select");
    sel.className = "form-select form-select-sm mn-subtask-assignee";
    sel.title = "Assign to attendee";
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = "Assignee";
    sel.appendChild(empty);
    (pool || []).forEach(function (u) {
      const opt = document.createElement("option");
      opt.value = String(u.id);
      opt.textContent = u.label;
      if (st.assignee_user_id != null && Number(st.assignee_user_id) === Number(u.id)) {
        opt.selected = true;
      }
      sel.appendChild(opt);
    });
    sel.addEventListener("change", function () {
      const uid = sel.value ? parseInt(sel.value, 10) : null;
      updateSubtaskAssignee(st.id, uid, itemId);
    });
    return sel;
  }

  function buildSubtaskRow(st, itemId, idx, total, attendeePool) {
    const row = document.createElement("div");
    row.className = "mn-subtask-row" + (st.is_done ? " is-done" : "");
    row.setAttribute("data-subtask-id", String(st.id));

    const chk = document.createElement("input");
    chk.type = "checkbox";
    chk.className = "form-check-input mt-1";
    chk.checked = !!st.is_done;
    chk.addEventListener("change", function () {
      toggleSubtaskDone(st.id, chk.checked, itemId);
    });

    const title = document.createElement("input");
    title.type = "text";
    title.className = "mn-subtask-title";
    title.value = st.title || "";
    title.addEventListener("change", function () {
      updateSubtaskTitle(st.id, title.value, itemId);
    });

    const assigneeSel = buildSubtaskAssigneeSelect(st, itemId, attendeePool);

    const actions = document.createElement("div");
    actions.className = "mn-subtask-actions";
    if (idx > 0) {
      const up = document.createElement("button");
      up.type = "button";
      up.className = "btn btn-sm mn-btn-ghost py-0 px-1";
      up.textContent = "↑";
      up.title = "Move up";
      up.addEventListener("click", function () { reorderSubtask(itemId, st.id, -1); });
      actions.appendChild(up);
    }
    if (idx < total - 1) {
      const down = document.createElement("button");
      down.type = "button";
      down.className = "btn btn-sm mn-btn-ghost py-0 px-1";
      down.textContent = "↓";
      down.title = "Move down";
      down.addEventListener("click", function () { reorderSubtask(itemId, st.id, 1); });
      actions.appendChild(down);
    }
    const del = document.createElement("button");
    del.type = "button";
    del.className = "btn btn-sm mn-btn-ghost py-0 px-1 text-danger";
    del.textContent = "×";
    del.title = "Delete";
    del.addEventListener("click", function () { deleteSubtask(st.id, itemId); });
    actions.appendChild(del);

    row.appendChild(chk);
    row.appendChild(title);
    row.appendChild(assigneeSel);
    row.appendChild(actions);
    return row;
  }

  async function refreshPanelItem(itemId) {
    const res = await fetch(API.actionItem(itemId), { headers: { Accept: "application/json" } });
    if (!res.ok) return;
    const data = await res.json();
    const idx = lastItemsCache.findIndex(function (it) { return it.id === itemId; });
    if (idx >= 0) lastItemsCache[idx] = data;
    if (panelItemId === itemId) panelItem = data;
    if (panelItemId === itemId && !panelReadOnly) {
      const ctaParts = splitCallToAction(data.call_to_action);
      const titleEl = $("#mn-panel-task-title");
      if (titleEl) titleEl.value = ctaParts.title;
      const statusEl = $("#mn-panel-status");
      if (statusEl) statusEl.value = data.status || "open";
      renderPanelSubtasks(data);
      const title = $("#mn-panel-title");
      if (title) title.textContent = firstLineOfBullets(data.call_to_action);
    }
    if ($("#mn-view-board") && !$("#mn-view-board").classList.contains("d-none")) {
      renderBoard(lastItemsCache);
    }
    if (hubMode) loadMyTasksHub();
  }

  async function addSubtaskFromPanel() {
    if (!panelItemId || panelReadOnly) return;
    const input = $("#mn-panel-subtask-input");
    const title = input ? input.value.trim() : "";
    if (!title) return;
    setPanelSaveHint("saving", "Adding sub-task…");
    try {
      const res = await fetch(API.subtasks(panelItemId), {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ title: title }),
      });
      if (!res.ok) throw new Error("Create failed");
      if (input) input.value = "";
      setPanelSaveHint("saved", "Saved");
      await refreshPanelItem(panelItemId);
      loadActivity();
    } catch (e) {
      console.error(e);
      setPanelSaveHint("error", "Could not add sub-task");
    }
  }

  async function toggleSubtaskDone(subtaskId, isDone, itemId) {
    try {
      const res = await fetch(API.subtask(subtaskId), {
        method: "PUT",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ is_done: isDone }),
      });
      if (!res.ok) throw new Error("Update failed");
      await refreshPanelItem(itemId);
      loadActivity();
    } catch (e) {
      console.error(e);
      alert("Could not update sub-task");
      await refreshPanelItem(itemId);
    }
  }

  async function updateSubtaskAssignee(subtaskId, assigneeUserId, itemId) {
    try {
      const res = await fetch(API.subtask(subtaskId), {
        method: "PUT",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ assignee_user_id: assigneeUserId, silent: true }),
      });
      const data = await res.json().catch(function () { return {}; });
      if (!res.ok) throw new Error(data.error || "Update failed");
      const item = lastItemsCache.find(function (it) { return it.id === itemId; });
      if (item && item.subtasks) {
        const si = item.subtasks.findIndex(function (s) { return s.id === subtaskId; });
        if (si >= 0) item.subtasks[si] = Object.assign({}, item.subtasks[si], data);
        if (panelItemId === itemId) {
          renderPanelSubtasks(item);
          if (hubMode) loadMyTasksHub();
        }
      } else {
        await refreshPanelItem(itemId);
      }
    } catch (e) {
      console.error(e);
      alert(e.message || "Could not update sub-task assignee");
      await refreshPanelItem(itemId);
    }
  }

  async function updateSubtaskTitle(subtaskId, title, itemId) {
    const trimmed = (title || "").trim();
    if (!trimmed) return;
    try {
      const res = await fetch(API.subtask(subtaskId), {
        method: "PUT",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ title: trimmed }),
      });
      if (!res.ok) throw new Error("Update failed");
      await refreshPanelItem(itemId);
      loadActivity();
    } catch (e) {
      console.error(e);
      alert("Could not update sub-task");
    }
  }

  async function deleteSubtask(subtaskId, itemId) {
    if (!confirm("Delete this sub-task?")) return;
    try {
      const res = await fetch(API.subtask(subtaskId), { method: "DELETE" });
      if (!res.ok) throw new Error("Delete failed");
      await refreshPanelItem(itemId);
      loadActivity();
    } catch (e) {
      console.error(e);
      alert("Could not delete sub-task");
    }
  }

  async function reorderSubtask(itemId, subtaskId, direction) {
    const item = lastItemsCache.find(function (it) { return it.id === itemId; });
    if (!item || !item.subtasks) return;
    const ordered = item.subtasks.slice().sort(function (a, b) {
      return (a.sort_order || 0) - (b.sort_order || 0) || a.id - b.id;
    });
    const idx = ordered.findIndex(function (s) { return s.id === subtaskId; });
    if (idx < 0) return;
    const newIdx = idx + direction;
    if (newIdx < 0 || newIdx >= ordered.length) return;
    const tmp = ordered[idx];
    ordered[idx] = ordered[newIdx];
    ordered[newIdx] = tmp;
    try {
      const res = await fetch(API.subtasksReorder(itemId), {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ ordered_ids: ordered.map(function (s) { return s.id; }) }),
      });
      if (!res.ok) throw new Error("Reorder failed");
      await refreshPanelItem(itemId);
      loadActivity();
    } catch (e) {
      console.error(e);
      alert("Could not reorder sub-tasks");
    }
  }

  function collectPanelPayload() {
    const get = function (id) {
      const el = $(id);
      return el ? el.value.trim() : "";
    };
    const getBullet = function (id) {
      const el = $(id);
      return el ? normalizeBulletText(el.value) : "";
    };
    const ctaParts = splitCallToAction(getBullet("#mn-panel-cta"));
    const taskTitle = get("#mn-panel-task-title");
    return {
      platform: get("#mn-panel-platform"),
      focus_area: getBullet("#mn-panel-focus"),
      call_to_action: mergeCallToAction(taskTitle || ctaParts.title, ctaParts.extra),
      expected_impact: getBullet("#mn-panel-impact"),
      challenges: getBullet("#mn-panel-challenges"),
      comments: getBullet("#mn-panel-comments"),
      status: get("#mn-panel-status") || "open",
      priority: get("#mn-panel-priority") || "medium",
      start_date: get("#mn-panel-start") || null,
      due_date: get("#mn-panel-due") || null,
      assignee_ids: getAssigneeIdsFromPicker(panelAssigneePicker),
      label_ids: (function () {
        const el = $("#mn-task-panel .mn-label-picker");
        if (!el) return [];
        try { return JSON.parse(el.getAttribute("data-label-ids") || "[]"); } catch (e) { return []; }
      })(),
    };
  }

  function schedulePanelSave(opts) {
    if (!panelItemId || panelReadOnly) return;
    opts = opts || {};
    debounce("panel-" + panelItemId, async function () {
      setPanelSaveHint("saving", "Saving…");
      const item = lastItemsCache.find(function (it) { return it.id === panelItemId; }) || panelItem;
      if (!item || !item.focus_row_id) return;
      const p = collectPanelPayload();
      try {
        const frRes = await putFocusRow(item.focus_row_id, {
          platform: p.platform,
          focus_area: p.focus_area,
          silent: !opts.log,
        });
        if (!frRes.ok) throw new Error("Focus row save failed");
        const itemRes = await putActionItem(panelItemId, {
          call_to_action: p.call_to_action,
          expected_impact: p.expected_impact,
          challenges: p.challenges,
          comments: p.comments,
          status: p.status,
          priority: p.priority,
          start_date: p.start_date,
          due_date: p.due_date,
          assignee_ids: p.assignee_ids,
          label_ids: p.label_ids,
          silent: !opts.log,
        });
        if (!itemRes.ok) throw new Error("Item save failed");
        setPanelSaveHint("saved", "Saved");
        if (hubMode) await loadMyTasksHub();
        else await refreshItems();
        if (opts.log) loadActivity();
      } catch (e) {
        console.error(e);
        setPanelSaveHint("error", "Save failed");
      }
    });
  }

  function wireTaskPanel() {
    const closeBtns = ["#mn-panel-close", "#mn-panel-close-footer", "#mn-task-panel-backdrop"];
    closeBtns.forEach(function (sel) {
      const el = $(sel);
      if (el) el.addEventListener("click", closeTaskPanel);
    });
    $all(".mn-panel-field", $("#mn-task-panel")).forEach(function (el) {
      el.addEventListener("input", function () { schedulePanelSave(); });
      el.addEventListener("change", function () { schedulePanelSave({ log: true }); });
    });
    const saveBtn = $("#mn-panel-save");
    if (saveBtn) {
      saveBtn.addEventListener("click", function () {
        if (saveTimers["panel-" + panelItemId]) {
          clearTimeout(saveTimers["panel-" + panelItemId]);
          delete saveTimers["panel-" + panelItemId];
        }
        schedulePanelSave({ log: true });
      });
    }
    const delBtn = $("#mn-panel-delete");
    if (delBtn) {
      delBtn.addEventListener("click", async function () {
        if (!panelItemId || !confirm("Delete this action item?")) return;
        const res = await fetch(API.actionItem(panelItemId), { method: "DELETE" });
        if (!res.ok) { alert("Delete failed"); return; }
        closeTaskPanel();
        if (hubMode) await loadMyTasksHub();
        else await refreshItems();
        loadActivity();
      });
    }
    const taskTitleEl = $("#mn-panel-task-title");
    if (taskTitleEl) {
      taskTitleEl.addEventListener("input", function () { schedulePanelSave(); });
      taskTitleEl.addEventListener("change", function () { schedulePanelSave({ log: true }); });
    }
    const subAddBtn = $("#mn-panel-subtask-add");
    if (subAddBtn) subAddBtn.addEventListener("click", addSubtaskFromPanel);
    const subInput = $("#mn-panel-subtask-input");
    if (subInput) {
      subInput.addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
          e.preventDefault();
          addSubtaskFromPanel();
        }
      });
    }
  }

  async function loadMyTasksHub() {
    const overdueEl = $("#mn-my-tasks-overdue");
    const weekEl = $("#mn-my-tasks-week");
    const progressEl = $("#mn-my-tasks-progress");
    const summaryEl = $("#mn-my-tasks-summary");
    if (!hubMode || !overdueEl) return;

    function renderHubColumn(el, items, emptyMsg) {
      if (!el) return;
      el.innerHTML = "";
      if (!items.length) {
        el.innerHTML = '<p class="small text-muted mb-0">' + escapeHtml(emptyMsg) + "</p>";
        return;
      }
      items.slice(0, 8).forEach(function (it) {
        el.appendChild(buildTaskCard(it, { readOnly: !hubEditMode, compact: true }));
      });
      if (items.length > 8) {
        const more = document.createElement("p");
        more.className = "small text-muted mb-0";
        more.textContent = "+" + (items.length - 8) + " more";
        el.appendChild(more);
      }
    }

    function setHubLoading() {
      const msg = '<p class="small text-muted mb-0">Loading…</p>';
      overdueEl.innerHTML = msg;
      if (weekEl) weekEl.innerHTML = msg;
      if (progressEl) progressEl.innerHTML = msg;
    }

    function setHubError(message) {
      const msg = '<p class="small text-danger mb-0">' + escapeHtml(message) + "</p>";
      overdueEl.innerHTML = msg;
      if (weekEl) weekEl.innerHTML = msg;
      if (progressEl) progressEl.innerHTML = msg;
    }

    if (!currentUserId) {
      setHubError("Could not determine your user account. Refresh the page.");
      return;
    }

    setHubLoading();

    try {
      const res = await fetch(API.hubMyTasks, { headers: { Accept: "application/json" }, credentials: "same-origin" });
      if (!res.ok) throw new Error("Request failed (" + res.status + ")");
      const data = await res.json();
      const overdue = data.overdue || [];
      const week = data.due_this_week || [];
      const progress = data.in_progress || [];

      renderHubColumn(overdueEl, overdue, "No overdue tasks assigned to you");
      renderHubColumn(weekEl, week, "Nothing due this week");
      renderHubColumn(progressEl, progress, "No active tasks assigned to you");

      if (summaryEl) {
        summaryEl.innerHTML =
          '<span class="mn-task-chip mn-task-chip-overdue">' + overdue.length + " overdue</span>" +
          '<span class="mn-task-chip">' + week.length + " due this week</span>" +
          '<span class="mn-task-chip">' + progress.length + " active</span>";
      }
    } catch (e) {
      console.error("loadMyTasksHub", e);
      setHubError("Could not load tasks. Try refreshing the page.");
    }
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
        "<td class=\"small\"><a href=\"/meeting-notes/" + it.meeting_note_id + "?view=board&highlight=" + it.id + "\">" +
        escapeHtml(it.meeting_title || "") + "</a><div class=\"text-muted\">" + escapeHtml(it.meeting_date || "") + "</div></td>" +
        "<td class=\"small\">" + escapeHtml(it.platform || "") + "</td>" +
        "<td class=\"small\">" + formatBulletsHtml(it.focus_area) + "</td>" +
        "<td>" + formatBulletsHtml(it.call_to_action) + "</td>" +
        "<td class=\"small\">" + formatBulletsHtml(it.expected_impact) + "</td>" +
        "<td class=\"small text-nowrap\">" + (it.start_date || "—") + " / " + (it.due_date || "—") + "</td>" +
        "<td class=\"small\">" + formatBulletsHtml(it.challenges) + "</td>" +
        "<td class=\"small\">" + formatBulletsHtml(it.comments) + "</td>" +
        "<td class=\"small\">" + assigneeChipsHtml(it.assignee_names || getAssigneeLabels(it.assignee_ids)) + "</td>" +
        "<td class=\"small mn-table-priority-cell\">" + statusBadgeHtml(it.status) + " " + priorityBadgeHtml(it.priority || "medium") + "</td>" +
        "<td class=\"text-end text-nowrap\">" +
        (globalEditMode
          ? '<button type="button" class="btn btn-sm mn-btn-primary mn-btn-edit-item" data-item-id="' + it.id + '">Edit</button> '
          : "") +
        '<a class="btn btn-sm mn-btn-ghost" href="/meeting-notes/' + it.meeting_note_id + "?view=board&highlight=" + it.id + '">Open meeting</a></td>';
      tb.appendChild(tr);
      tr.setAttribute("data-priority", (it.priority || "medium").toLowerCase());
      applyStatusRowClass(tr, it.status);
      if (globalEditMode) {
        const editBtn = tr.querySelector(".mn-btn-edit-item");
        if (editBtn) {
          editBtn.addEventListener("click", function () { openTaskPanel(it, false); });
        }
      }
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
    lastItemsCache = items || [];
    if (meetingNoteId && canEditItems()) renderTableInline(lastItemsCache);
    else renderTableReadOnly(lastItemsCache);
    if ($("#mn-board")) renderBoard(lastItemsCache);
    applyHighlightScroll();
  }

  async function fetchItems() {
    const p = readFilters();
    const res = await fetch(API.items + "?" + p.toString(), { headers: { Accept: "application/json" } });
    if (!res.ok) throw new Error("Failed to load items");
    const data = await res.json();
    return data.items || [];
  }

  async function refreshTable() {
    return refreshItems();
  }

  async function refreshItems() {
    try {
      const items = await fetchItems();
      renderTable(items);
    } catch (e) {
      console.error(e);
      const tb = $("#mn-table-body");
      if (tb) {
        tb.innerHTML = '<tr><td colspan="' + (meetingNoteId ? 11 : 11) + '" class="text-danger">Could not load items.</td></tr>';
      }
      const board = $("#mn-board");
      if (board) {
        $all("[data-board-drop]", board).forEach(function (body) {
          body.innerHTML = '<div class="mn-board-empty text-danger">Could not load items.</div>';
        });
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
    else await refreshItems();
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
    const incLabelsPriority = $("#mn-pdf-include-labels-priority");
    const incSubtasks = $("#mn-pdf-include-subtasks");
    const incDiscussion = $("#mn-pdf-include-discussion");
    return {
      includeDone: incDone ? incDone.checked : true,
      includeSummary: incSummary ? incSummary.checked : true,
      groupByPlatform: groupPlatform ? groupPlatform.checked : true,
      includeLabelsPriority: incLabelsPriority ? incLabelsPriority.checked : true,
      includeSubtasks: incSubtasks ? incSubtasks.checked : true,
      includeDiscussion: incDiscussion ? incDiscussion.checked : false,
    };
  }

  async function fetchItemsForPdf(pdfOpts) {
    const p = readFilters();
    if (pdfOpts.includeDiscussion) p.set("include_comment_threads", "1");
    const res = await fetch(API.items + "?" + p.toString(), { headers: { Accept: "application/json" } });
    if (!res.ok) throw new Error("Failed to load items");
    const data = await res.json();
    return data.items || [];
  }

  function buildPdfHeaders(pdfOpts) {
    const cols = [];
    if (!meetingNoteId) cols.push("Meeting");
    cols.push("Platform", "Focus area", "Call to action", "Impact", "Start", "Due");
    if (pdfOpts.includeLabelsPriority) cols.push("Priority", "Labels");
    cols.push("Progress");
    if (pdfOpts.includeSubtasks) cols.push("Sub-tasks");
    cols.push("Challenges", "Comments");
    if (pdfOpts.includeDiscussion) cols.push("Discussion");
    cols.push("Led by", "Status");
    return [cols];
  }

  function buildPdfRowCells(it, pdfOpts) {
    const names = (it.assignee_names && it.assignee_names.length)
      ? it.assignee_names.join(", ")
      : getAssigneeLabels(it.assignee_ids).join(", ");
    const st = (it.status || "open").replace(/_/g, " ");
    let cta = linesToBulletCell(it.call_to_action);
    if (it.ai_extracted && cta) cta += " *";
    else if (it.ai_extracted) cta = "*";
    const row = [];
    if (!meetingNoteId) {
      row.push((it.meeting_title || "") + " (" + (it.meeting_date || "") + ")");
    }
    row.push(
      it.platform || "",
      linesToBulletCell(it.focus_area),
      cta,
      linesToBulletCell(it.expected_impact),
      it.start_date ? String(it.start_date).slice(0, 10) : "",
      it.due_date ? String(it.due_date).slice(0, 10) : ""
    );
    if (pdfOpts.includeLabelsPriority) {
      row.push((it.priority || "medium").replace(/_/g, " "), formatLabelsPdf(it.labels));
    }
    row.push(formatProgressPdf(it));
    if (pdfOpts.includeSubtasks) row.push(formatSubtasksPdf(it.subtasks));
    row.push(linesToBulletCell(it.challenges), linesToBulletCell(it.comments));
    if (pdfOpts.includeDiscussion) row.push(formatCommentThreadPdf(it.comment_threads));
    row.push(names, st);
    return row;
  }

  function buildPdfTableConfig(doc, headers, body, startY, logoDataUrl, pdfOpts, meta, rawItems) {
    return {
      head: headers,
      body: body,
      startY: startY,
      theme: "striped",
      styles: {
        fontSize: 7,
        cellPadding: { top: 3, right: 4, bottom: 3, left: 4 },
        overflow: "linebreak",
        textColor: [30, 41, 59],
        lineColor: [226, 232, 240],
        lineWidth: 0.2,
      },
      headStyles: {
        fillColor: [224, 242, 254],
        textColor: [3, 105, 161],
        fontStyle: "bold",
        lineColor: [125, 211, 252],
        lineWidth: 0.4,
      },
      alternateRowStyles: { fillColor: [248, 252, 255] },
      tableLineColor: [226, 232, 240],
      tableLineWidth: 0.2,
      bodyStyles: { valign: "top" },
      margin: { top: 52, left: 28, right: 28, bottom: 32 },
      didParseCell: function (data) {
        if (data.section !== "body") return;
        const row = rawItems && rawItems[data.row.index];
        if (!row) return;
        const pr = ((row.priority || "medium") + "").toLowerCase();
        const pal = TASK_PALETTES[pr] || TASK_PALETTES.medium;
        if (data.column.index === 0 || (!meetingNoteId && data.column.index === 1)) {
          const rgb = hexToRgbArray(pal.rowBg);
          if (rgb) data.cell.styles.fillColor = rgb;
        }
      },
      didDrawPage: function () {
        drawPdfPageChrome(doc, logoDataUrl, meta);
      },
    };
  }

  function hexToRgbArray(hex) {
    const s = String(hex || "").replace("#", "");
    if (!/^[0-9a-fA-F]{6}$/.test(s)) return null;
    return [parseInt(s.slice(0, 2), 16), parseInt(s.slice(2, 4), 16), parseInt(s.slice(4, 6), 16)];
  }

  function renderPdfCover(doc, logoDataUrl, pdfOpts, meta) {
    drawPdfPageChrome(doc, logoDataUrl, meta);
    const accent = [56, 189, 248];
    const primary = [3, 105, 161];
    const muted = [71, 85, 105];
    const pageW = doc.internal.pageSize.getWidth();
    let y = 84;
    const title = meta.title || "All action items";
    const meetingDate = meta.meetingDate || "";
    doc.setDrawColor(accent[0], accent[1], accent[2]);
    doc.setLineWidth(2);
    doc.line(64, y, 64, y + 54);
    doc.setFontSize(22);
    doc.setTextColor(primary[0], primary[1], primary[2]);
    doc.text(title, 76, y + 4);
    y += 22;
    doc.setFontSize(10);
    doc.setTextColor(muted[0], muted[1], muted[2]);
    doc.text("Strategic Meeting Execution Report", 76, y);
    y += 18;
    doc.setFillColor(239, 246, 255);
    doc.roundedRect(76, y - 10, 220, 18, 6, 6, "F");
    doc.setTextColor(primary[0], primary[1], primary[2]);
    doc.setFontSize(9);
    doc.text("Generated: " + new Date().toISOString().slice(0, 16).replace("T", " "), 86, y + 2);
    y += 18;
    if (meetingDate) {
      doc.setFillColor(224, 242, 254);
      doc.roundedRect(76, y - 10, 160, 18, 6, 6, "F");
      doc.setTextColor(12, 74, 110);
      doc.text("Meeting date: " + meetingDate, 86, y + 2);
      y += 12;
    }
    if (meetingNoteId) {
      const attendeeLine = formatAttendeesPdfLine();
      if (attendeeLine) {
        doc.setFontSize(9);
        doc.setTextColor(muted[0], muted[1], muted[2]);
        const attLines = doc.splitTextToSize(attendeeLine, pageW - 160);
        doc.text(attLines, 76, y + 8);
        y += attLines.length * 10 + 2;
      }
      if (pdfOpts.includeSummary && typeof MN_MEETING_SUMMARY === "string" && MN_MEETING_SUMMARY.trim()) {
        y += 10;
        doc.setTextColor(primary[0], primary[1], primary[2]);
        doc.setFontSize(11);
        doc.text("Summary", 76, y);
        y += 10;
        const sumLines = doc.splitTextToSize(MN_MEETING_SUMMARY.trim(), pageW - 160);
        doc.setFillColor(240, 249, 255);
        const summaryHeight = Math.max(28, sumLines.length * 10 + 10);
        doc.roundedRect(76, y - 9, pageW - 152, summaryHeight, 8, 8, "F");
        doc.setTextColor(muted[0], muted[1], muted[2]);
        doc.setFontSize(9);
        doc.text(sumLines, 84, y + 2);
        y += sumLines.length * 10 + 10;
      }
    }
    if (meta.hasAiItems) {
      doc.setFontSize(8);
      doc.setTextColor(8, 145, 178);
      doc.text("* Includes AI-suggested tasks", 76, y + 8);
      y += 10;
    }
    y += 14;
    doc.setDrawColor(203, 213, 225);
    doc.setLineWidth(0.6);
    doc.line(76, y, pageW - 76, y);
    return y + 10;
  }

  async function buildExportPdfDocument() {
    if (!window.jspdf || !window.jspdf.jsPDF) {
      throw new Error("PDF library not loaded.");
    }
    const pdfOpts = getPdfExportOptions();
    const logoUrl = typeof MN_PDF_LOGO_URL === "string" ? MN_PDF_LOGO_URL : "";
    let logoDataUrl = null;
    try {
      logoDataUrl = await loadPdfLogoDataUrl(logoUrl);
    } catch (e) {
      logoDataUrl = null;
    }
    let items;
    try {
      items = await fetchItemsForPdf(pdfOpts);
    } catch (e) {
      throw new Error("Could not load data for export.");
    }
    if (!pdfOpts.includeDone) {
      items = items.filter(function (it) { return (it.status || "open") !== "done"; });
    }
    if (!items.length) {
      throw new Error("No action items to export.");
    }
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF({ orientation: "landscape", unit: "pt", format: "a4" });
    const title = meetingNoteId && typeof MN_MEETING_TITLE === "string"
      ? MN_MEETING_TITLE
      : "All action items";
    const meetingDate = meetingNoteId && typeof MN_MEETING_DATE === "string" ? MN_MEETING_DATE : "";
    const meta = {
      title: title,
      meetingDate: meetingDate,
      hasAiItems: items.some(function (it) { return it.ai_extracted; }),
    };
    let y = renderPdfCover(doc, logoDataUrl, pdfOpts, meta);
    const headers = buildPdfHeaders(pdfOpts);
    const rowCells = function (it) { return buildPdfRowCells(it, pdfOpts); };

    if (meetingNoteId && pdfOpts.groupByPlatform) {
      const byPlat = {};
      items.forEach(function (it) {
        const p = it.platform || "General";
        if (!byPlat[p]) byPlat[p] = [];
        byPlat[p].push(it);
      });
      Object.keys(byPlat).sort().forEach(function (plat) {
        doc.setFillColor(224, 242, 254);
        doc.roundedRect(56, y - 9, 220, 18, 6, 6, "F");
        doc.setFontSize(9);
        doc.setTextColor(2, 132, 199);
        doc.text("PLATFORM", 66, y + 2);
        doc.setTextColor(3, 105, 161);
        doc.setFontSize(10);
        doc.text(plat, 126, y + 2);
        y += 16;
        const body = byPlat[plat].map(rowCells);
        doc.autoTable(buildPdfTableConfig(doc, headers, body, y, logoDataUrl, pdfOpts, meta, byPlat[plat]));
        y = doc.lastAutoTable.finalY + 20;
      });
    } else {
      const body = items.map(rowCells);
      doc.autoTable(buildPdfTableConfig(doc, headers, body, y, logoDataUrl, pdfOpts, meta, items));
    }
    const slug = String(title).replace(/[^\w\-]+/g, "_").slice(0, 40) || "export";
    const filename = "meeting-notes_" + slug + "_" + new Date().toISOString().slice(0, 10) + ".pdf";
    return { doc: doc, filename: filename };
  }

  async function exportTablePdf() {
    try {
      const built = await buildExportPdfDocument();
      built.doc.save(built.filename);
    } catch (e) {
      alert((e && e.message) ? e.message : "PDF export failed.");
    }
  }

  async function emailMeetingReport() {
    if (!meetingNoteId) {
      alert("Open a meeting to email a report.");
      return;
    }
    const recipientsRaw = (document.getElementById("mn-pdf-email-recipients") || {}).value || "";
    if (!recipientsRaw.trim()) {
      alert("Enter at least one recipient email.");
      return;
    }
    const subject = ((document.getElementById("mn-pdf-email-subject") || {}).value || "").trim();
    try {
      const built = await buildExportPdfDocument();
      const pdfBase64 = built.doc.output("datauristring").split(",")[1] || "";
      const res = await fetch(API.emailReport(meetingNoteId), {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({
          recipients: recipientsRaw,
          subject: subject,
          body_html: "<p>Please find attached the latest meeting report.</p>",
          body_text: "Please find attached the latest meeting report.",
          pdf_base64: pdfBase64,
          pdf_filename: built.filename,
        }),
      });
      const data = await res.json().catch(function () { return {}; });
      if (!res.ok) {
        alert(data.error || "Email send failed.");
        return;
      }
      alert("Meeting report emailed. Sent: " + (data.sent || 0) + ", Failed: " + (data.failed || 0));
    } catch (e) {
      alert("Could not send report email.");
    }
  }

  let activityFetchSeq = 0;

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
      if (!box.querySelector("#mn-activity-list")) {
        box.innerHTML = "<p class=\"text-muted mb-0\">You do not have permission to view activity.</p>";
      }
      return;
    }
    if (!meetingNoteId) {
      if (!box.querySelector("#mn-activity-list")) {
        box.innerHTML = "<p class=\"text-muted mb-0\">Open a meeting to view activity.</p>";
      }
      return;
    }
    const seq = ++activityFetchSeq;
    const actFilter = ($("#mn-activity-filter") || {}).value || "all";
    const q = "?per_page=40&coalesce=1" + (actFilter && actFilter !== "all" ? "&action=" + encodeURIComponent(actFilter) : "");
    try {
      const res = await fetch(API.activity(meetingNoteId) + q, {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });
      if (seq !== activityFetchSeq) return;
      if (res.status === 403) {
        box.innerHTML = "<p class=\"text-muted mb-0\">You do not have permission to view activity.</p>";
        return;
      }
      if (!res.ok) {
        if (!box.querySelector("#mn-activity-list")) {
          box.innerHTML = "<p class=\"text-muted mb-0\">Could not load activity (HTTP " + res.status + ").</p>";
        }
        return;
      }
      const data = await res.json();
      if (seq !== activityFetchSeq) return;
      if (Array.isArray(data.items)) {
        renderActivityRows(data.items);
      }
    } catch (e) {
      console.error("loadActivity", e);
      if (!box.querySelector("#mn-activity-list") && !box.textContent.trim()) {
        box.innerHTML = "<p class=\"text-muted mb-0\">Could not load activity.</p>";
      }
    }
  }

  function syncFilterChips() {
    const host = $("#mn-filter-chips");
    if (!host) return;

    const chips = [];
    function addChip(key, label, clearFn) {
      if (!label) return;
      chips.push({ key: key, label: label, clear: clearFn });
    }

    const platform = ($("#mn-filter-platform") || {}).value;
    if (platform) addChip("platform", "Platform: " + platform, function () { $("#mn-filter-platform").value = ""; });

    const assigneeSel = $("#mn-filter-assignee");
    const assignee = assigneeSel ? assigneeSel.value : "";
    if (assignee) {
      const opt = assigneeSel.options[assigneeSel.selectedIndex];
      addChip("assignee", "Assignee: " + (opt ? opt.text : assignee), function () { assigneeSel.value = ""; });
    }

    const status = ($("#mn-filter-status") || {}).value;
    if (status && status !== "all") {
      const labels = { open: "Open", in_progress: "In progress", done: "Done" };
      addChip("status", "Status: " + (labels[status] || status), function () { $("#mn-filter-status").value = "all"; });
    }

    const priority = ($("#mn-filter-priority") || {}).value;
    if (priority) addChip("priority", "Priority: " + priority, function () { $("#mn-filter-priority").value = ""; });

    const labelSel = $("#mn-filter-label");
    const labelId = labelSel ? labelSel.value : "";
    if (labelId) {
      const opt = labelSel.options[labelSel.selectedIndex];
      addChip("label", "Label: " + (opt ? opt.text : labelId), function () { labelSel.value = ""; });
    }

    const due = ($("#mn-filter-due") || {}).value;
    if (due) {
      const dueLabels = {
        overdue: "Overdue", this_week: "This week", this_month: "This month",
        next_month: "Next month", none: "No due date", custom: "Custom range"
      };
      let dueLabel = dueLabels[due] || due;
      if (due === "custom") {
        const ds = ($("#mn-due-start") || {}).value;
        const de = ($("#mn-due-end") || {}).value;
        if (ds || de) dueLabel = (ds || "…") + " – " + (de || "…");
      }
      addChip("due", "Due: " + dueLabel, function () {
        $("#mn-filter-due").value = "";
        if ($("#mn-due-start")) $("#mn-due-start").value = "";
        if ($("#mn-due-end")) $("#mn-due-end").value = "";
        document.querySelectorAll(".mn-due-custom").forEach(function (el) { el.classList.add("d-none"); });
      });
    }

    const search = ($("#mn-filter-search") || {}).value;
    if (search) addChip("search", "Search: " + search, function () { $("#mn-filter-search").value = ""; });

    if (!chips.length) {
      host.innerHTML = '<span class="small text-muted">No filters applied</span>';
      return;
    }

    host.innerHTML = chips.map(function (c) {
      return '<span class="mn-filter-chip" data-chip-key="' + escapeHtml(c.key) + '">' +
        escapeHtml(c.label) +
        '<button type="button" aria-label="Remove filter">&times;</button></span>';
    }).join("");

    $all(".mn-filter-chip button", host).forEach(function (btn) {
      btn.addEventListener("click", function () {
        const chip = btn.closest(".mn-filter-chip");
        const key = chip ? chip.getAttribute("data-chip-key") : "";
        const match = chips.find(function (c) { return c.key === key; });
        if (match && match.clear) match.clear();
        syncFilterChips();
        refreshItems();
        if (calendar) calendar.refetchEvents();
        if ($("#mn-view-gantt") && !$("#mn-view-gantt").classList.contains("d-none")) refreshGantt();
      });
    });
  }

  function wireFilters() {
    function onFilterChange() {
      syncFilterChips();
      refreshItems();
      if (calendar) calendar.refetchEvents();
      if ($("#mn-view-gantt") && !$("#mn-view-gantt").classList.contains("d-none")) refreshGantt();
    }

    $all(".mn-filter-ctrl").forEach(function (el) {
      el.addEventListener("change", onFilterChange);
      if (el.type === "search" || el.type === "text") {
        var t;
        el.addEventListener("input", function () {
          clearTimeout(t);
          t = setTimeout(onFilterChange, 300);
        });
      }
    });

    const clearBtn = $("#mn-filter-clear-all");
    if (clearBtn) {
      clearBtn.addEventListener("click", function () {
        if ($("#mn-filter-platform")) $("#mn-filter-platform").value = "";
        if ($("#mn-filter-assignee")) $("#mn-filter-assignee").value = "";
        if ($("#mn-filter-status")) $("#mn-filter-status").value = "all";
        if ($("#mn-filter-priority")) $("#mn-filter-priority").value = "";
        if ($("#mn-filter-label")) $("#mn-filter-label").value = "";
        if ($("#mn-filter-due")) $("#mn-filter-due").value = "";
        if ($("#mn-due-start")) $("#mn-due-start").value = "";
        if ($("#mn-due-end")) $("#mn-due-end").value = "";
        if ($("#mn-filter-search")) $("#mn-filter-search").value = "";
        document.querySelectorAll(".mn-due-custom").forEach(function (el) { el.classList.add("d-none"); });
        syncFilterChips();
        onFilterChange();
      });
    }

    const applyBtn = $("#mn-filter-apply");
    if (applyBtn) applyBtn.addEventListener("click", syncFilterChips);

    syncFilterChips();
  }

  function wireViews() {
    $all("[data-mn-view-btn]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        showView(btn.getAttribute("data-mn-view-btn"));
      });
    });
  }

  function wireBoardGroup() {
    boardGroupMode = getBoardGroupFromUrl();
    $all("[data-mn-board-group]").forEach(function (btn) {
      btn.classList.toggle("active", btn.getAttribute("data-mn-board-group") === boardGroupMode);
      btn.addEventListener("click", function () {
        setBoardGroupMode(btn.getAttribute("data-mn-board-group"));
      });
    });
    updateBoardGroupToggleVisibility(getViewFromUrl());
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
    if (hubMode) {
      wireTaskPanel();
      loadMyTasksHub();
      loadLabelsCache();
      return;
    }

    const u = new URL(window.location.href);
    if (meetingNoteId && !u.searchParams.get("view")) {
      u.searchParams.set("view", "board");
      window.history.replaceState({}, "", u.toString());
    }

    initMeetingAttendeePickers();
    wireFilters();
    wireViews();
    wireBoardGroup();
    wireGanttToolbar();
    wireTaskPanel();
    ensureStatusBoardTemplate();
    refreshItems();
    showView(getViewFromUrl());

    var sm = $("#mn-btn-save-meta");
    if (sm) sm.addEventListener("click", saveMeetingMeta);
    var ar = $("#mn-btn-add-row");
    if (ar) ar.addEventListener("click", createNewRow);
    var ni = $("#mn-btn-new-item");
    if (ni) ni.addEventListener("click", createNewRow);
    var exp = $("#mn-btn-export-pdf");
    if (exp && !document.getElementById("mnExportModal")) {
      exp.addEventListener("click", exportTablePdf);
    }

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
      refreshItems();
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
          await refreshItems();
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
        refreshItems();
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
        window.location.href = "/meeting-notes/" + data.id + "?view=board";
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
        refreshItems();
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

    const actToggle = $("#mn-activity-toggle");
    const actBody = $("#mn-activity-body");
    if (actToggle && actBody) {
      actToggle.addEventListener("click", function () {
        const hidden = actBody.classList.toggle("d-none");
        actToggle.setAttribute("aria-expanded", hidden ? "false" : "true");
      });
    }

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
      const emailExp = $("#mn-btn-email-export");
      if (emailExp) {
        emailExp.addEventListener("click", emailMeetingReport);
      }
    }
  }

  async function loadLabelsCache() {
    try {
      const res = await fetch(API.labels);
      if (res.ok) labelsCache = await res.json();
    } catch (e) {
      console.error(e);
    }
  }

  loadLabelsCache();

  window.MN = {
    API: API,
    refreshItems: refreshItems,
    openTaskPanel: openTaskPanel,
    escapeHtml: escapeHtml,
    userOpts: userOpts,
    meetingNoteId: meetingNoteId,
    meetingAttendeeUserOpts: meetingAttendeeUserOpts,
    focusRows: typeof MN_FOCUS_ROWS !== "undefined" ? MN_FOCUS_ROWS : [],
    labelsCache: function () { return labelsCache; },
    setLabelsCache: function (lbs) { labelsCache = lbs || []; },
    readFilters: readFilters,
    syncFilterChips: syncFilterChips,
    getViewFromUrl: getViewFromUrl,
    setUrlView: setUrlView,
  };
})();
