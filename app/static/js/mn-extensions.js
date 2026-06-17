/**
 * Meeting notes extensions: command palette, saved views, AI, quick capture, analytics, realtime.
 */
(function () {
  const API = window.MN_API || (window.MN && window.MN.API);
  if (!API) return;

  function $(sel, root) { return (root || document).querySelector(sel); }
  function escapeHtml(s) {
    const d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML;
  }

  /* --- Command palette (Ctrl+K) --- */
  function initCommandPalette() {
    const modal = $("#mn-command-palette");
    const input = $("#mn-cmd-input");
    const results = $("#mn-cmd-results");
    if (!modal || !input || !results) return;

    let items = [];

    function openPalette() {
      input.value = "";
      results.innerHTML = "";
      if (window.bootstrap) bootstrap.Modal.getOrCreateInstance(modal).show();
      setTimeout(function () { input.focus(); }, 200);
      search("");
    }

    function search(q) {
      const qq = (q || "").trim().toLowerCase();
      Promise.all([
        fetch(API.meetingsSearch + "?q=" + encodeURIComponent(qq) + "&limit=15").then(function (r) { return r.json(); }),
        fetch(API.items + "?q=" + encodeURIComponent(qq)).then(function (r) { return r.json(); }).catch(function () { return { items: [] }; }),
      ]).then(function (pair) {
        const meetings = pair[0] || [];
        const actionItems = (pair[1].items || []).slice(0, 10);
        items = [];
        meetings.forEach(function (m) {
          items.push({ type: "meeting", label: m.title, sub: m.meeting_date, href: "/meeting-notes/" + m.id + "?view=board" });
        });
        actionItems.forEach(function (it) {
          items.push({
            type: "task",
            label: (it.call_to_action || "").split("\n")[0],
            sub: (it.meeting_title || "") + " · " + (it.status || ""),
            href: "/meeting-notes/" + it.meeting_note_id + "?view=board&highlight=" + it.id,
          });
        });
        if (window.MN && window.MN.meetingNoteId && qq.indexOf("extract") >= 0) {
          items.unshift({ type: "action", label: "Extract tasks from notes (AI)", action: "ai-extract" });
        }
        renderResults();
      });
    }

    function renderResults() {
      results.innerHTML = "";
      if (!items.length) {
        results.innerHTML = '<p class="small text-muted mb-0 px-2">No results</p>';
        return;
      }
      items.forEach(function (it, idx) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "mn-cmd-item" + (idx === 0 ? " active" : "");
        btn.innerHTML = "<strong>" + escapeHtml(it.label) + "</strong>" +
          (it.sub ? '<span class="small text-muted d-block">' + escapeHtml(it.sub) + "</span>" : "");
        btn.addEventListener("click", function () { runItem(it); });
        results.appendChild(btn);
      });
    }

    function runItem(it) {
      if (it.action === "ai-extract") {
        if (window.bootstrap) bootstrap.Modal.getOrCreateInstance(modal).hide();
        const aiBtn = $("#mn-btn-ai-extract");
        if (aiBtn) aiBtn.click();
        return;
      }
      if (it.href) window.location.href = it.href;
    }

    input.addEventListener("input", function () { search(input.value); });
    document.addEventListener("keydown", function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        openPalette();
      }
      if (e.key === "/" && !e.target.matches("input, textarea, select")) {
        e.preventDefault();
        openPalette();
      }
    });
  }

  /* --- Saved views --- */
  function initSavedViews() {
    const sel = $("#mn-saved-view-select");
    const saveBtn = $("#mn-saved-view-save");
    if (!sel) return;

    function applyView(view) {
      const f = view.filters_json || {};
      const set = function (id, val) { const el = $(id); if (el && val != null) el.value = val; };
      set("#mn-filter-platform", f.platform || "");
      set("#mn-filter-assignee", f.assignee_user_id || "");
      set("#mn-filter-status", f.status || "all");
      set("#mn-filter-due", f.due_preset || "");
      set("#mn-filter-priority", f.priority || "");
      set("#mn-filter-label", f.label_id || "");
      set("#mn-filter-search", f.q || "");
      if (window.MN && window.MN.setUrlView && view.view_mode) window.MN.setUrlView(view.view_mode);
      if (window.MN && window.MN.refreshItems) window.MN.refreshItems();
    }

    function loadViews() {
      fetch(API.savedViews).then(function (r) { return r.json(); }).then(function (views) {
        sel.innerHTML = '<option value="">Saved views…</option>';
        views.forEach(function (v) {
          const opt = document.createElement("option");
          opt.value = String(v.id);
          opt.textContent = v.name + (v.is_default ? " ★" : "");
          opt._view = v;
          sel.appendChild(opt);
        });
      });
    }

    sel.addEventListener("change", function () {
      const opt = sel.options[sel.selectedIndex];
      if (opt && opt._view) applyView(opt._view);
    });

    if (saveBtn) {
      saveBtn.addEventListener("click", async function () {
        const name = prompt("Name for this view:");
        if (!name) return;
        const f = {};
        const g = function (id, key) { const el = $(id); if (el && el.value) f[key] = el.value; };
        g("#mn-filter-platform", "platform");
        g("#mn-filter-assignee", "assignee_user_id");
        g("#mn-filter-status", "status");
        g("#mn-filter-due", "due_preset");
        g("#mn-filter-priority", "priority");
        g("#mn-filter-label", "label_id");
        g("#mn-filter-search", "q");
        const viewMode = window.MN && window.MN.getViewFromUrl ? window.MN.getViewFromUrl() : "board";
        await fetch(API.savedViews, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: name, filters_json: f, view_mode: viewMode }),
        });
        loadViews();
      });
    }
    loadViews();
  }

  /* --- Hub analytics --- */
  function initHubAnalytics() {
    const el = $("#mn-hub-analytics");
    if (!el) return;
    fetch(API.hubAnalytics).then(function (r) { return r.json(); }).then(function (data) {
      el.innerHTML =
        '<span class="mn-analytics-chip">' + (data.completion_rate || 0) + "% complete</span>" +
        '<span class="mn-analytics-chip">' + (data.overdue_items || 0) + " overdue</span>" +
        '<span class="mn-analytics-chip">' + (data.total_items || 0) + " total tasks</span>";
    }).catch(function () {});
  }

  /* --- AI extract modal --- */
  function initAiExtract() {
    const btn = $("#mn-btn-ai-extract");
    const modal = $("#mnAiExtractModal");
    const tbody = $("#mn-ai-tasks-body");
    const decisionsBody = $("#mn-ai-decisions-body");
    const applyBtn = $("#mn-btn-ai-apply");
    const summarizeBtn = $("#mn-btn-ai-summarize");
    const meetingId = window.MN && window.MN.meetingNoteId;
    if (!btn || !modal || !meetingId) return;

    let preview = null;

    btn.addEventListener("click", async function () {
      btn.disabled = true;
      const notes = (window.easyMDE ? window.easyMDE.value() : "") ||
        ($("#mn-meta-summary") || {}).value ||
        (typeof MN_MEETING_SUMMARY === "string" ? MN_MEETING_SUMMARY : "");
      try {
        const res = await fetch(API.aiExtract(meetingId), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ notes_text: notes }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Extract failed");
        preview = data.preview || {};
        tbody.innerHTML = "";
        (preview.action_items || []).forEach(function (row, idx) {
          const tr = document.createElement("tr");
          tr.innerHTML =
            '<td><input type="checkbox" class="mn-ai-pick" data-idx="' + idx + '" checked /></td>' +
            '<td><input class="form-control form-control-sm" value="' + escapeHtml(row.title) + '" data-field="title" data-idx="' + idx + '" /></td>' +
            '<td><select class="form-select form-select-sm" data-field="priority" data-idx="' + idx + '">' +
            ["low", "medium", "high", "urgent"].map(function (p) {
              return '<option value="' + p + '"' + (row.priority === p ? " selected" : "") + ">" + p + "</option>";
            }).join("") + "</select></td>" +
            '<td><input type="date" class="form-control form-control-sm" value="' + escapeHtml(row.due_date || "") + '" data-field="due_date" data-idx="' + idx + '" /></td>' +
            '<td class="small text-muted">' + escapeHtml(row.assignee_hint || "") + "</td>";
          tbody.appendChild(tr);
        });
        if (decisionsBody) {
          decisionsBody.innerHTML = "";
          const decList = preview.decisions || [];
          if (!decList.length) {
            const tr = document.createElement("tr");
            tr.innerHTML = '<td colspan="3" class="small text-muted">No decisions suggested — add notes and try again.</td>';
            decisionsBody.appendChild(tr);
          }
          decList.forEach(function (row, idx) {
            const text = typeof row === "string" ? row : (row.body || row.title || "");
            const excerpt = typeof row === "object" ? (row.source_excerpt || "") : "";
            const tr = document.createElement("tr");
            tr.innerHTML =
              '<td><input type="checkbox" class="mn-ai-dec-pick" data-idx="' + idx + '" checked /></td>' +
              '<td><input class="form-control form-control-sm mn-ai-dec-body" value="' + escapeHtml(text) + '" data-idx="' + idx + '" /></td>' +
              '<td class="small text-muted">' + escapeHtml(excerpt) + "</td>";
            decisionsBody.appendChild(tr);
          });
        }
        if (window.bootstrap) bootstrap.Modal.getOrCreateInstance(modal).show();
      } catch (e) {
        alert(e.message || String(e));
      }
      btn.disabled = false;
    });

    async function runSummarize() {
      const notes = ($("#mn-meta-summary") || {}).value || (window.easyMDE ? window.easyMDE.value() : "");
      const res = await fetch(API.aiSummarize(meetingId), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ notes_text: notes }),
      });
      const data = await res.json();
      if (!res.ok) { alert(data.error || "Failed"); return; }
      const ta = $("#mn-meta-summary");
      if (ta) ta.value = data.summary || "";
      if (window.easyMDE) window.easyMDE.value(data.summary || "");
    }
    const summarizeModalBtn = $("#mn-btn-ai-summarize-modal");
    if (summarizeModalBtn) summarizeModalBtn.addEventListener("click", runSummarize);
    if (summarizeBtn) summarizeBtn.addEventListener("click", runSummarize);

    if (applyBtn) {
      applyBtn.addEventListener("click", async function () {
        const focusSel = $("#mn-ai-focus-row");
        const focusRowId = focusSel ? parseInt(focusSel.value, 10) : null;
        const rows = [];
        $all(".mn-ai-pick:checked", tbody).forEach(function (chk) {
          const idx = parseInt(chk.getAttribute("data-idx"), 10);
          const src = (preview.action_items || [])[idx] || {};
          const tr = chk.closest("tr");
          const titleIn = tr.querySelector('[data-field="title"]');
          const prIn = tr.querySelector('[data-field="priority"]');
          const dueIn = tr.querySelector('[data-field="due_date"]');
          rows.push({
            title: titleIn ? titleIn.value : src.title,
            priority: prIn ? prIn.value : src.priority,
            due_date: dueIn ? dueIn.value : src.due_date,
            assignee_id: src.assignee_id,
            source_excerpt: src.source_excerpt,
            subtasks: src.subtasks || [],
          });
        });
        const decisionRows = [];
        if (decisionsBody) {
          $all(".mn-ai-dec-pick:checked", decisionsBody).forEach(function (chk) {
            const idx = parseInt(chk.getAttribute("data-idx"), 10);
            const src = (preview.decisions || [])[idx];
            const tr = chk.closest("tr");
            const bodyIn = tr ? tr.querySelector(".mn-ai-dec-body") : null;
            const body = bodyIn ? bodyIn.value : (typeof src === "string" ? src : (src && src.body) || "");
            if (!body || !String(body).trim()) return;
            decisionRows.push({
              body: String(body).trim(),
              source_excerpt: typeof src === "object" ? (src.source_excerpt || "") : "",
            });
          });
        }
        if (rows.length && !focusRowId) { alert("Select a focus row for action items"); return; }
        const res = await fetch(API.aiApply(meetingId), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            focus_row_id: focusRowId,
            items: rows,
            decisions: decisionRows,
            apply_summary: preview.summary || "",
          }),
        });
        const data = await res.json();
        if (!res.ok) { alert(data.error || "Apply failed"); return; }
        if (window.bootstrap) bootstrap.Modal.getOrCreateInstance(modal).hide();
        if (window.MN && window.MN.refreshItems) window.MN.refreshItems();
        if (window.MN_loadDecisions) window.MN_loadDecisions();
        if (preview.summary) {
          const ta = $("#mn-meta-summary");
          if (ta) ta.value = preview.summary;
          if (window.easyMDE) window.easyMDE.value(preview.summary);
        }
      });
    }
  }

  function $all(sel, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  }

  /* --- Quick capture --- */
  function parseQuickCapture(text) {
    const out = { title: text, assignee_ids: [], due_date: null, platform: "", priority: "medium" };
    let t = text;
    const userOpts = (window.MN && window.MN.userOpts) || [];
    const atMatch = t.match(/@([^\s#@!]+(?:\s+[^\s#@!]+)?)/);
    if (atMatch) {
      const hint = atMatch[1].toLowerCase();
      const u = userOpts.find(function (o) { return o.label.toLowerCase().indexOf(hint) >= 0; });
      if (u) out.assignee_ids = [u.id];
      t = t.replace(atMatch[0], "").trim();
    }
    const hashMatch = t.match(/#([^\s@!]+)/);
    if (hashMatch) {
      out.platform = hashMatch[1];
      t = t.replace(hashMatch[0], "").trim();
    }
    const prMatch = t.match(/!(\w+)/);
    if (prMatch && ["low", "medium", "high", "urgent"].indexOf(prMatch[1].toLowerCase()) >= 0) {
      out.priority = prMatch[1].toLowerCase();
      t = t.replace(prMatch[0], "").trim();
    }
    const dueMatch = t.match(/\bdue\s+(\d{4}-\d{2}-\d{2}|\w+)/i);
    if (dueMatch) {
      const d = dueMatch[1];
      if (/^\d{4}-\d{2}-\d{2}$/.test(d)) out.due_date = d;
      t = t.replace(dueMatch[0], "").trim();
    }
    out.title = t.trim();
    return out;
  }

  function initQuickCapture() {
    const bar = $("#mn-quick-capture");
    const input = $("#mn-quick-capture-input");
    const go = $("#mn-quick-capture-go");
    const meetingId = window.MN && window.MN.meetingNoteId;
    if (!bar || !input || !meetingId) return;

    async function submit() {
      const raw = (input.value || "").trim();
      if (!raw) return;
      if (/^(>>|decision:)/i.test(raw)) {
        const body = raw.replace(/^(>>|decision:)\s*/i, "").trim();
        if (!body) return;
        try {
          if (window.MN_createDecision) {
            await window.MN_createDecision(body);
          } else {
            const res = await fetch("/meeting-notes/api/meetings/" + meetingId + "/decisions", {
              method: "POST",
              credentials: "same-origin",
              headers: { "Content-Type": "application/json", Accept: "application/json" },
              body: JSON.stringify({ body: body }),
            });
            if (!res.ok) throw new Error("Failed");
            if (window.MN_loadDecisions) await window.MN_loadDecisions();
          }
          input.value = "";
        } catch (e) {
          alert("Could not save decision");
        }
        return;
      }
      const parsed = parseQuickCapture(raw);
      let focusRows = (window.MN && window.MN.focusRows) || [];
      let rowId = focusRows.length ? focusRows[0].id : null;
      if (!rowId) {
        const frRes = await fetch(API.focusRow(meetingId), {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify({ platform: parsed.platform || "General", focus_area: "Quick capture" }),
        });
        const fr = await frRes.json();
        rowId = fr.id;
      }
      const itemRes = await fetch(API.createItem(rowId), {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          call_to_action: parsed.title,
          priority: parsed.priority,
          due_date: parsed.due_date,
          assignee_ids: parsed.assignee_ids,
        }),
      });
      if (!itemRes.ok) throw new Error("Could not create task");
      input.value = "";
      if (window.MN && window.MN.refreshItems) window.MN.refreshItems();
    }

    window.MN_submitQuickCapture = async function (text, options) {
      options = options || {};
      const raw = (text || "").trim();
      if (!raw) return;
      if (/^(>>|decision:)/i.test(raw)) {
        const body = raw.replace(/^(>>|decision:)\s*/i, "").trim();
        if (!body) return;
        if (window.MN_createDecision) await window.MN_createDecision(body);
        return;
      }
      const parsed = parseQuickCapture(raw);
      let focusRows = (window.MN && window.MN.focusRows) || [];
      let rowId = options.focusRowId || null;
      if (!rowId && parsed.platform) {
        const match = focusRows.find(function (r) {
          return (r.platform || "").toLowerCase() === parsed.platform.toLowerCase();
        });
        if (match) rowId = match.id;
      }
      if (!rowId) rowId = focusRows.length ? focusRows[0].id : null;
      if (!rowId) {
        const frRes = await fetch(API.focusRow(meetingId), {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify({ platform: parsed.platform || "General", focus_area: "Quick capture" }),
        });
        const fr = await frRes.json();
        rowId = fr.id;
      }
      const itemRes = await fetch(API.createItem(rowId), {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          call_to_action: parsed.title,
          priority: parsed.priority,
          due_date: parsed.due_date,
          assignee_ids: parsed.assignee_ids,
        }),
      });
      if (!itemRes.ok) throw new Error("Could not create task");
      if (window.MN && window.MN.refreshItems) await window.MN.refreshItems();
    };

    if (go) go.addEventListener("click", submit);
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter") { e.preventDefault(); submit(); }
    });
  }

  /* --- Markdown editor --- */
  function initMarkdownEditor() {
    const ta = $("#mn-meta-summary");
    if (!ta || typeof EasyMDE === "undefined") return;
    window.easyMDE = new EasyMDE({
      element: ta,
      spellChecker: false,
      minHeight: "140px",
      toolbar: ["bold", "italic", "heading", "|", "unordered-list", "ordered-list", "|", "preview"],
    });
  }

  /* --- Templates on hub --- */
  function initTemplates() {
    const sel = $("#mn-template-select");
    const selMobile = $("#mn-template-select-mobile");
    const selMobileTab = $("#mn-template-select-mobile-tab");
    const btn = $("#mn-template-create");
    if (!sel && !selMobile && !selMobileTab) return;
    fetch(API.templates).then(function (r) { return r.json(); }).then(function (rows) {
      rows.forEach(function (t) {
        [sel, selMobile, selMobileTab].forEach(function (target) {
          if (!target) return;
          const opt = document.createElement("option");
          opt.value = String(t.id);
          opt.textContent = t.name;
          target.appendChild(opt);
        });
      });
    });
    if (btn) {
      btn.addEventListener("click", async function () {
        const tid = parseInt(sel.value, 10);
        if (!tid) return;
        const res = await fetch(API.templateCreateMeeting(tid), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ meeting_date: new Date().toISOString().slice(0, 10) }),
        });
        const data = await res.json();
        if (res.ok) window.location.href = "/meeting-notes/" + data.id + "?view=board";
      });
    }
  }

  /* --- Labels filter populate --- */
  function initLabelFilter() {
    const sel = $("#mn-filter-label");
    if (!sel) return;
    fetch(API.labels).then(function (r) { return r.json(); }).then(function (lbs) {
      if (window.MN && window.MN.setLabelsCache) window.MN.setLabelsCache(lbs);
      lbs.forEach(function (lb) {
        const opt = document.createElement("option");
        opt.value = String(lb.id);
        opt.textContent = lb.name;
        sel.appendChild(opt);
      });
    });
  }

  /* --- SocketIO realtime --- */
  function initRealtime() {
    const meetingId = window.MN && window.MN.meetingNoteId;
    if (!meetingId || typeof io === "undefined") return;
    try {
      const socket = io("/meeting-notes");
      socket.emit("join_meeting", { meeting_id: meetingId });
      socket.on("item_updated", function () {
        if (window.MN && window.MN.refreshItems) window.MN.refreshItems();
      });
    } catch (e) {
      console.warn("Meeting notes realtime unavailable", e);
    }
  }

  /* --- Item comments --- */
  function formatCommentBody(body) {
    const safe = escapeHtml(body || "");
    return safe.replace(/@([A-Za-z0-9_.\s-]+)/g, '<span class="mn-mention">@$1</span>');
  }

  function mentionLabelForUser(u) {
    return (u && u.label) ? u.label : "";
  }

  function initMentionAutocomplete(input) {
    if (!input || input.getAttribute("data-mn-mention-wired")) return;
    input.setAttribute("data-mn-mention-wired", "1");

    const wrap = document.createElement("div");
    wrap.className = "mn-mention-wrap";
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);

    const list = document.createElement("div");
    list.className = "mn-mention-suggestions";
    wrap.appendChild(list);

    let mentionStart = -1;
    let activeIdx = -1;

    function attendeePool() {
      if (window.MN && window.MN._panelAttendeeUserOpts && window.MN._panelAttendeeUserOpts.length) {
        return window.MN._panelAttendeeUserOpts;
      }
      if (window.MN && window.MN.meetingAttendeeUserOpts && window.MN._panelItem) {
        return window.MN.meetingAttendeeUserOpts(window.MN._panelItem);
      }
      return window.MN && window.MN.userOpts ? window.MN.userOpts : [];
    }

    function closeList() {
      list.classList.remove("is-open");
      list.innerHTML = "";
      activeIdx = -1;
      mentionStart = -1;
    }

    function insertMention(u) {
      const label = mentionLabelForUser(u);
      if (!label || mentionStart < 0) return;
      const before = input.value.slice(0, mentionStart);
      const after = input.value.slice(input.selectionStart || input.value.length);
      const mention = "@" + label;
      input.value = before + mention + (after && !/^\s/.test(after) ? " " : "") + after;
      const caret = (before + mention + " ").length;
      input.setSelectionRange(caret, caret);
      closeList();
      input.focus();
    }

    function openList(query) {
      const qq = (query || "").trim().toLowerCase();
      const pool = attendeePool();
      const matches = pool.filter(function (u) {
        const label = mentionLabelForUser(u).toLowerCase();
        const uname = (u.username || "").toLowerCase();
        return !qq || label.indexOf(qq) >= 0 || uname.indexOf(qq) >= 0;
      }).slice(0, 8);
      list.innerHTML = "";
      if (!matches.length) {
        closeList();
        return;
      }
      matches.forEach(function (u, i) {
        const item = document.createElement("button");
        item.type = "button";
        item.className = "mn-mention-suggestion";
        item.textContent = mentionLabelForUser(u);
        item.addEventListener("mousedown", function (e) {
          e.preventDefault();
          insertMention(u);
        });
        list.appendChild(item);
      });
      list.classList.add("is-open");
      activeIdx = 0;
      const items = list.querySelectorAll(".mn-mention-suggestion");
      if (items[0]) items[0].classList.add("is-active");
    }

    function syncMentionState() {
      const val = input.value;
      const pos = input.selectionStart || 0;
      const slice = val.slice(0, pos);
      const at = slice.lastIndexOf("@");
      if (at < 0) {
        closeList();
        return;
      }
      const between = slice.slice(at + 1);
      if (/\s/.test(between)) {
        closeList();
        return;
      }
      mentionStart = at;
      openList(between);
    }

    input.addEventListener("input", syncMentionState);
    input.addEventListener("keydown", function (e) {
      const items = list.querySelectorAll(".mn-mention-suggestion");
      if (!list.classList.contains("is-open") || !items.length) return;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        activeIdx = Math.min(activeIdx + 1, items.length - 1);
        items.forEach(function (el, i) { el.classList.toggle("is-active", i === activeIdx); });
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        activeIdx = Math.max(activeIdx - 1, 0);
        items.forEach(function (el, i) { el.classList.toggle("is-active", i === activeIdx); });
      } else if (e.key === "Enter" && activeIdx >= 0) {
        e.preventDefault();
        const pool = attendeePool();
        const qq = input.value.slice(mentionStart + 1, input.selectionStart || input.value.length).trim().toLowerCase();
        const matches = pool.filter(function (u) {
          const label = mentionLabelForUser(u).toLowerCase();
          const uname = (u.username || "").toLowerCase();
          return !qq || label.indexOf(qq) >= 0 || uname.indexOf(qq) >= 0;
        }).slice(0, 8);
        if (matches[activeIdx]) insertMention(matches[activeIdx]);
      } else if (e.key === "Escape") {
        closeList();
      }
    });
    input.addEventListener("blur", function () {
      setTimeout(closeList, 150);
    });
  }

  function loadCommentsForPanel() {
    const host = $("#mn-panel-comments-thread");
    const itemId = window.MN && window.MN._panelItemId;
    if (!host || !itemId) return;
    fetch(API.itemComments(itemId)).then(function (r) { return r.json(); }).then(function (rows) {
      host.innerHTML = rows.map(function (c) {
        return '<div class="mn-comment"><strong>' + escapeHtml(c.author_name) + '</strong> ' +
          '<span class="text-muted small">' + escapeHtml(c.created_at || "") + '</span><p class="mb-1">' +
          formatCommentBody(c.body) + "</p></div>";
      }).join("") || '<p class="text-muted small mb-0">No comments yet.</p>';
    });
  }

  function initComments() {
    const commentInput = $("#mn-panel-comment-input");
    if (commentInput) initMentionAutocomplete(commentInput);

    const addBtn = $("#mn-panel-comment-add");
    if (addBtn) {
      addBtn.addEventListener("click", async function () {
        const input = $("#mn-panel-comment-input");
        const body = input ? input.value.trim() : "";
        const itemId = window.MN && window.MN._panelItemId;
        if (!body || !itemId) return;
        await fetch(API.itemComments(itemId), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ body: body }),
        });
        if (input) input.value = "";
        loadCommentsForPanel();
      });
    }
    const origOpen = window.MN && window.MN.openTaskPanel;
    if (origOpen) {
      window.MN.openTaskPanel = function (item, readOnly) {
        origOpen(item, readOnly);
        if (!readOnly) {
          setTimeout(function () {
            loadCommentsForPanel();
            const inp = $("#mn-panel-comment-input");
            if (inp) initMentionAutocomplete(inp);
          }, 100);
        }
      };
    }
  }

  /* --- Keyboard view shortcuts --- */
  function initKeyboardShortcuts() {
    document.addEventListener("keydown", function (e) {
      if (e.target.matches("input, textarea, select")) return;
      if (e.key === "1") clickView("board");
      if (e.key === "2") clickView("table");
      if (e.key === "3") clickView("calendar");
      if (e.key === "4") clickView("gantt");
    });
    function clickView(v) {
      const btn = document.querySelector('[data-mn-view-btn="' + v + '"]');
      if (btn) btn.click();
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    initCommandPalette();
    initSavedViews();
    initHubAnalytics();
    initAiExtract();
    initQuickCapture();
    initMarkdownEditor();
    initTemplates();
    initLabelFilter();
    initRealtime();
    initComments();
    initKeyboardShortcuts();
  });
})();
