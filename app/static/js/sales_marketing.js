(function () {
  const API = {
    stakeholders: "/sales-marketing/api/stakeholders",
    stakeholdersExport: "/sales-marketing/api/stakeholders/export",
    events: "/sales-marketing/api/events",
    roadmap: "/sales-marketing/api/events/roadmap",
    interest: "/sales-marketing/api/interest-options",
    campaigns: "/sales-marketing/api/campaigns",
    send: "/sales-marketing/api/campaigns/send",
    stats: "/sales-marketing/api/stakeholders/stats",
    previewCount: "/sales-marketing/api/stakeholders/preview-count",
    bulkStatus: "/sales-marketing/api/stakeholders/bulk-status",
    campaign: function (id) { return "/sales-marketing/api/campaigns/" + id; },
    event: function (id) { return "/sales-marketing/api/events/" + id; },
    stakeholder: function (id) { return "/sales-marketing/api/stakeholders/" + id; },
    interestOpt: function (id) { return "/sales-marketing/api/interest-options/" + id; },
  };

  const page = window.SM_PAGE || "stakeholders";

  function pageUserOpts() {
    if (Array.isArray(window.SM_USER_OPTS)) return window.SM_USER_OPTS;
    try {
      if (typeof SM_USER_OPTS !== "undefined" && Array.isArray(SM_USER_OPTS)) return SM_USER_OPTS;
    } catch (e) { /* SM_USER_OPTS not in scope */ }
    return [];
  }

  function pageProvinces() {
    if (Array.isArray(window.SM_PROVINCES)) return window.SM_PROVINCES;
    try {
      if (typeof SM_PROVINCES !== "undefined" && Array.isArray(SM_PROVINCES)) return SM_PROVINCES;
    } catch (e) { /* SM_PROVINCES not in scope */ }
    return [];
  }

  let userOpts = pageUserOpts().slice();
  const provinces = pageProvinces();

  async function ensureUserOpts() {
    if (userOpts.length) return userOpts;
    try {
      const data = await fetchJson("/sales-marketing/api/users");
      userOpts = Array.isArray(data) ? data : [];
    } catch (e) {
      userOpts = [];
    }
    return userOpts;
  }
  let currentPage = 1;
  let selectedLeadIds = new Set();
  let editingLeadId = null;
  let editingEventId = null;
  let selectedAttendeeIds = new Set();
  let interestOptionsCache = [];
  let eventsCache = [];

  function $(id) { return document.getElementById(id); }
  function esc(s) {
    const d = document.createElement("div");
    d.textContent = s || "";
    return d.innerHTML;
  }

  async function fetchJson(url, opts) {
    const res = await fetch(url, Object.assign({ headers: { Accept: "application/json" } }, opts || {}));
    const data = await res.json().catch(function () { return {}; });
    if (!res.ok) throw new Error(data.error || "Request failed");
    return data;
  }

  function $all(sel, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  }

  function buildAttendeePicker(container, initialSelected) {
    if (!container) return;
    selectedAttendeeIds = new Set((initialSelected || []).map(Number).filter(Boolean));
    container.innerHTML = "";

    let selectedIds = Array.from(selectedAttendeeIds);

    function normId(v) {
      return parseInt(v, 10) || 0;
    }

    function findUser(uid) {
      const id = normId(uid);
      return userOpts.find(function (o) { return normId(o.id) === id; });
    }

    const chipsEl = document.createElement("div");
    chipsEl.className = "sm-user-chips";

    const input = document.createElement("input");
    input.type = "text";
    input.className = "sm-user-input";
    input.placeholder = "Type name or department…";
    input.autocomplete = "off";

    const list = document.createElement("div");
    list.className = "sm-user-suggestions";

    let activeIdx = -1;

    function syncSelected() {
      selectedAttendeeIds = new Set(selectedIds);
    }

    function userLabel(u) {
      return u.label + (u.department ? " (" + u.department + ")" : "");
    }

    function renderChips() {
      chipsEl.innerHTML = "";
      selectedIds.forEach(function (uid) {
        const u = findUser(uid);
        if (!u) return;
        const chip = document.createElement("span");
        chip.className = "sm-user-chip";
        chip.textContent = u.label;
        const rm = document.createElement("button");
        rm.type = "button";
        rm.className = "sm-user-chip-remove";
        rm.innerHTML = "&times;";
        rm.setAttribute("aria-label", "Remove " + u.label);
        rm.addEventListener("click", function (e) {
          e.preventDefault();
          selectedIds = selectedIds.filter(function (id) { return id !== uid; });
          syncSelected();
          renderChips();
        });
        chip.appendChild(rm);
        chipsEl.appendChild(chip);
      });
    }

    function filteredUsers(q) {
      const qq = (q || "").trim().toLowerCase();
      if (!qq) {
        return userOpts.filter(function (u) { return selectedIds.indexOf(normId(u.id)) < 0; }).slice(0, 8);
      }
      return userOpts.filter(function (u) {
        if (selectedIds.indexOf(normId(u.id)) >= 0) return false;
        return u.label.toLowerCase().indexOf(qq) >= 0 ||
          (u.department || "").toLowerCase().indexOf(qq) >= 0;
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
      matches.forEach(function (u) {
        const item = document.createElement("div");
        item.className = "sm-user-suggestion";
        item.textContent = userLabel(u);
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
      const id = normId(uid);
      if (!id || selectedIds.indexOf(id) >= 0) return;
      selectedIds.push(id);
      syncSelected();
      input.value = "";
      renderChips();
      closeList();
    }

    input.addEventListener("input", openList);
    input.addEventListener("focus", openList);
    input.addEventListener("blur", function () {
      setTimeout(closeList, 150);
    });
    input.addEventListener("keydown", function (e) {
      const items = $all(".sm-user-suggestion", list);
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
    container.appendChild(chipsEl);
    container.appendChild(input);
    container.appendChild(list);
  }

  function renderAttendeeChips(names) {
    if (!names || !names.length) return '<span class="text-muted small">No staff assigned</span>';
    return names.map(function (n) { return '<span class="sm-attendee-chip">' + esc(n) + "</span>"; }).join("");
  }

  function eventCardHtml(ev) {
    return '<div class="sm-event-card timeline-' + esc(ev.timeline_status) + '">' +
      '<div class="sm-event-card-title">' + esc(ev.name) + '</div>' +
      '<div class="sm-event-card-meta">' + esc(ev.start_date) + " → " + esc(ev.end_date) +
      (ev.location ? " · " + esc(ev.location) : "") +
      ' · <span class="badge bg-light text-dark">' + esc(ev.timeline_status) + "</span>" +
      " · " + (ev.lead_count || 0) + ' <a href="/sales-marketing/?event_id=' + ev.id + '" class="sm-lead-link">leads</a></div>' +
      '<div class="sm-attendee-chips">' + renderAttendeeChips(ev.attendee_names) + "</div>" +
      (page === "events" ? '<button type="button" class="btn btn-sm btn-link p-0 mt-1 sm-edit-event" data-id="' + ev.id + '">Edit</button>' : "") +
      "</div>";
  }

  // --- Stakeholders page ---
  async function loadInterestOptions() {
    interestOptionsCache = await fetchJson(API.interest);
    const sel = $("sm-filter-interest");
    if (sel) {
      const cur = sel.value;
      sel.innerHTML = '<option value="">All interests</option>';
      interestOptionsCache.forEach(function (o) {
        if (!o.is_active) return;
        const opt = document.createElement("option");
        opt.value = String(o.id);
        opt.textContent = o.label;
        sel.appendChild(opt);
      });
      if (cur) sel.value = cur;
    }
  }

  async function loadEventsForFilter() {
    eventsCache = await fetchJson(API.events + "?timeline=all");
    const sel = $("sm-filter-event");
    if (sel) {
      const cur = sel.value;
      sel.innerHTML = '<option value="">All events</option>';
      eventsCache.forEach(function (e) {
        const opt = document.createElement("option");
        opt.value = String(e.id);
        opt.textContent = e.name;
        sel.appendChild(opt);
      });
      if (cur) sel.value = cur;
    }
  }

  function filterParams() {
    const p = new URLSearchParams();
    p.set("page", String(currentPage));
    const s = ($("sm-search") || {}).value;
    if (s) p.set("search", s);
    const ev = ($("sm-filter-event") || {}).value;
    if (ev) p.set("event_id", ev);
    const prov = ($("sm-filter-province") || {}).value;
    if (prov) p.set("province", prov);
    const io = ($("sm-filter-interest") || {}).value;
    if (io) p.set("interest_option_id", io);
    const st = ($("sm-filter-status") || {}).value;
    if (st) p.set("status", st);
    if (($("sm-filter-consent") || {}).checked) p.set("consent_only", "1");
    if (($("sm-filter-dup") || {}).checked) p.set("duplicates_only", "1");
    return p;
  }

  function filterParamsObject() {
    const p = filterParams();
    return {
      event_id: p.get("event_id") || null,
      province: p.get("province") || null,
      interest_option_id: p.get("interest_option_id") || null,
      search: p.get("search") || null,
      status: p.get("status") || null,
      duplicates_only: p.get("duplicates_only") === "1",
    };
  }

  async function loadLeads() {
    const body = $("sm-leads-body");
    if (!body) return;
    body.innerHTML = '<tr><td colspan="9" class="text-muted">Loading…</td></tr>';
    try {
      const data = await fetchJson(API.stakeholders + "?" + filterParams().toString());
      body.innerHTML = "";
      if (!data.items.length) {
        body.innerHTML = '<tr><td colspan="9" class="text-muted">No leads found.</td></tr>';
      }
      data.items.forEach(function (it) {
        const tr = document.createElement("tr");
        if (it.is_duplicate_flag) tr.classList.add("table-warning");
        tr.innerHTML =
          '<td><input type="checkbox" class="sm-lead-chk" data-id="' + it.id + '"' +
          (selectedLeadIds.has(it.id) ? " checked" : "") + " /></td>" +
          '<td><button type="button" class="btn btn-sm btn-link p-0 sm-view-lead" data-id="' + it.id + '">' + esc(it.full_name) + "</button>" +
          (it.is_duplicate_flag && !it.duplicate_dismissed ? ' <span class="sm-badge-dup">dup</span>' : "") + "</td>" +
          "<td>" + esc(it.email) + "</td>" +
          '<td><span class="sm-status-pill sm-status-' + esc(it.follow_up_status || "new") + '">' + esc(it.follow_up_status || "new") + "</span></td>" +
          "<td>" + esc(it.event_name || "—") + "</td>" +
          "<td>" + esc(it.interest_label) + "</td>" +
          "<td>" + esc(it.province) + "</td>" +
          "<td>" + esc((it.submitted_at || "").slice(0, 16).replace("T", " ")) + "</td>" +
          '<td><button type="button" class="btn btn-sm btn-link sm-edit-lead" data-id="' + it.id + '">Edit</button></td>';
        body.appendChild(tr);
      });
      const info = $("sm-pagination-info");
      if (info) info.textContent = "Page " + data.page + " of " + Math.max(1, data.pages) + " (" + data.total + " total)";
      body.querySelectorAll(".sm-lead-chk").forEach(function (c) {
        c.addEventListener("change", function () {
          const id = parseInt(c.getAttribute("data-id"), 10);
          if (c.checked) selectedLeadIds.add(id);
          else selectedLeadIds.delete(id);
        });
      });
      body.querySelectorAll(".sm-edit-lead").forEach(function (btn) {
        btn.addEventListener("click", function () { openLeadModal(parseInt(btn.getAttribute("data-id"), 10)); });
      });
      body.querySelectorAll(".sm-view-lead").forEach(function (btn) {
        btn.addEventListener("click", function () {
          if (window.smOpenLeadDrawer) window.smOpenLeadDrawer(parseInt(btn.getAttribute("data-id"), 10));
        });
      });
      if (window.smOnLeadsLoaded) window.smOnLeadsLoaded(data);
    } catch (e) {
      body.innerHTML = '<tr><td colspan="9" class="text-danger">' + esc(e.message) + "</td></tr>";
    }
  }

  function leadFormHtml(data) {
    data = data || {};
    let evOpts = '<option value="">—</option>';
    eventsCache.forEach(function (e) {
      evOpts += '<option value="' + e.id + '"' + (data.event_id === e.id ? " selected" : "") + ">" + esc(e.name) + "</option>";
    });
    let intOpts = "";
    interestOptionsCache.forEach(function (o) {
      intOpts += '<option value="' + o.id + '"' + (data.interest_option_id === o.id ? " selected" : "") + ">" + esc(o.label) + "</option>";
    });
    let provOpts = '<option value="">—</option>';
    provinces.forEach(function (p) {
      provOpts += '<option value="' + esc(p) + '"' + (data.province === p ? " selected" : "") + ">" + esc(p) + "</option>";
    });
    return '<div class="row g-2">' +
      '<div class="col-md-6"><label class="form-label">Full name</label><input class="form-control form-control-sm" id="lf-name" value="' + esc(data.full_name || "") + '" /></div>' +
      '<div class="col-md-6"><label class="form-label">Email</label><input class="form-control form-control-sm" id="lf-email" value="' + esc(data.email || "") + '" /></div>' +
      '<div class="col-md-6"><label class="form-label">Mobile</label><input class="form-control form-control-sm" id="lf-mobile" value="' + esc(data.mobile || "") + '" /></div>' +
      '<div class="col-md-6"><label class="form-label">Occupation</label><input class="form-control form-control-sm" id="lf-occupation" value="' + esc(data.occupation || "") + '" /></div>' +
      '<div class="col-md-6"><label class="form-label">Province</label><select class="form-select form-select-sm" id="lf-province">' + provOpts + "</select></div>" +
      '<div class="col-md-6"><label class="form-label">School</label><input class="form-control form-control-sm" id="lf-school" value="' + esc(data.school_name || "") + '" /></div>' +
      '<div class="col-md-6"><label class="form-label">Event</label><select class="form-select form-select-sm" id="lf-event">' + evOpts + "</select></div>" +
      '<div class="col-md-6"><label class="form-label">Interest</label><select class="form-select form-select-sm" id="lf-interest">' + intOpts + "</select></div>" +
      '<div class="col-md-6"><label class="form-label">Follow-up status</label><select class="form-select form-select-sm" id="lf-status">' +
      ["new", "contacted", "qualified", "closed"].map(function (s) {
        return '<option value="' + s + '"' + ((data.follow_up_status || "new") === s ? " selected" : "") + ">" + s + "</option>";
      }).join("") + "</select></div>" +
      '<div class="col-12"><label class="form-check"><input type="checkbox" class="form-check-input" id="lf-consent"' + (data.consent_marketing ? " checked" : "") + " /> Marketing consent</label></div>" +
      '<div class="col-12"><label class="form-label">Comments</label><textarea class="form-control form-control-sm" id="lf-comments" rows="2">' + esc(data.comments || "") + "</textarea></div>" +
      "</div>";
  }

  async function openLeadModal(id) {
    editingLeadId = id || null;
    const host = $("sm-lead-form-host");
    const title = $("sm-lead-modal-title");
    if (!host) return;
    if (title) title.textContent = id ? "Edit lead" : "Add lead";
    let data = {};
    if (id) {
      data = await fetchJson(API.stakeholder(id));
    }
    host.innerHTML = leadFormHtml(data);
    new bootstrap.Modal($("smLeadModal")).show();
  }

  async function saveLead() {
    const payload = {
      full_name: ($("lf-name") || {}).value,
      email: ($("lf-email") || {}).value,
      mobile: ($("lf-mobile") || {}).value,
      occupation: ($("lf-occupation") || {}).value,
      province: ($("lf-province") || {}).value,
      school_name: ($("lf-school") || {}).value,
      event_id: ($("lf-event") || {}).value || null,
      interest_option_id: ($("lf-interest") || {}).value || null,
      follow_up_status: ($("lf-status") || {}).value || "new",
      consent_marketing: ($("lf-consent") || {}).checked,
      comments: ($("lf-comments") || {}).value,
    };
    try {
      if (editingLeadId) {
        await fetchJson(API.stakeholder(editingLeadId), { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      } else {
        await fetchJson(API.stakeholders, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      }
      bootstrap.Modal.getInstance($("smLeadModal")).hide();
      loadLeads();
    } catch (e) { alert(e.message); }
  }

  function wireStakeholders() {
    const qs = new URLSearchParams(window.location.search);
    const evQ = qs.get("event_id");
    if (evQ && $("sm-filter-event")) $("sm-filter-event").value = evQ;
    loadInterestOptions().then(loadEventsForFilter).then(loadLeads);
    ["sm-search", "sm-filter-event", "sm-filter-province", "sm-filter-interest", "sm-filter-consent", "sm-filter-status", "sm-filter-dup"].forEach(function (id) {
      const el = $(id);
      if (el) el.addEventListener("change", function () { currentPage = 1; loadLeads(); });
      if (el && el.type === "search") el.addEventListener("input", function () { currentPage = 1; loadLeads(); });
    });
    const refresh = $("sm-btn-refresh");
    if (refresh) refresh.addEventListener("click", loadLeads);
    const exp = $("sm-btn-export");
    if (exp) exp.addEventListener("click", function () {
      window.location.href = API.stakeholdersExport + "?" + filterParams().toString();
    });
    const prev = $("sm-prev");
    if (prev) prev.addEventListener("click", function () { if (currentPage > 1) { currentPage--; loadLeads(); } });
    const next = $("sm-next");
    if (next) next.addEventListener("click", function () { currentPage++; loadLeads(); });
    const chkAll = $("sm-chk-all");
    if (chkAll) chkAll.addEventListener("change", function () {
      document.querySelectorAll(".sm-lead-chk").forEach(function (c) {
        c.checked = chkAll.checked;
        const id = parseInt(c.getAttribute("data-id"), 10);
        if (chkAll.checked) selectedLeadIds.add(id);
        else selectedLeadIds.delete(id);
      });
    });
    const addBtn = $("sm-btn-add");
    if (addBtn) addBtn.addEventListener("click", function () { openLeadModal(null); });
    const saveLeadBtn = $("sm-lead-save");
    if (saveLeadBtn) saveLeadBtn.addEventListener("click", saveLead);
    const emailBtn = $("sm-btn-email");
    if (emailBtn) emailBtn.addEventListener("click", function () {
      if (!selectedLeadIds.size) { alert("Select at least one lead."); return; }
      const cnt = $("sm-email-count");
      if (cnt) cnt.textContent = selectedLeadIds.size + " recipient(s) with consent will be emailed.";
      new bootstrap.Modal($("smEmailModal")).show();
    });
    const sendBtn = $("sm-email-send");
    if (sendBtn) sendBtn.addEventListener("click", async function () {
      try {
        const data = await fetchJson(API.send, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            stakeholder_ids: Array.from(selectedLeadIds),
            subject: ($("sm-email-subject") || {}).value,
            body_html: ($("sm-email-body") || {}).value,
          }),
        });
        alert("Sent " + data.sent + " of " + data.total);
        bootstrap.Modal.getInstance($("smEmailModal")).hide();
      } catch (e) { alert(e.message); }
    });
  }

  // --- Events page ---
  async function loadEventsList() {
    const host = $("sm-events-list");
    if (!host) return;
    host.innerHTML = '<p class="text-muted">Loading…</p>';
    try {
      const events = await fetchJson(API.events + "?timeline=all");
      eventsCache = events;
      host.innerHTML = events.length ? events.map(eventCardHtml).join("") :
        '<div class="sm-empty-guide"><h2 class="h6">No events yet</h2><p class="small text-muted mb-0">Create your first event, assign attending staff, then share the connect link or QR code at the stand.</p></div>';
      host.querySelectorAll(".sm-edit-event").forEach(function (btn) {
        btn.addEventListener("click", function () { openEventModal(parseInt(btn.getAttribute("data-id"), 10)); });
      });
    } catch (e) { host.innerHTML = '<p class="text-danger">' + esc(e.message) + "</p>"; }
  }

  async function openEventModal(id) {
    editingEventId = id || null;
    const delBtn = $("sm-event-delete");
    if (delBtn) delBtn.classList.toggle("d-none", !id);
    const qrBtn = $("sm-event-qr");
    if (qrBtn) qrBtn.classList.toggle("d-none", !id);
    const title = $("sm-event-modal-title");
    if (title) title.textContent = id ? "Edit event" : "New event";
    const ev = id ? eventsCache.find(function (e) { return e.id === id; }) : {};
    if ($("sm-event-id")) $("sm-event-id").value = id || "";
    if ($("sm-event-name")) $("sm-event-name").value = (ev && ev.name) || "";
    if ($("sm-event-start")) $("sm-event-start").value = (ev && ev.start_date) || "";
    if ($("sm-event-end")) $("sm-event-end").value = (ev && ev.end_date) || "";
    if ($("sm-event-location")) $("sm-event-location").value = (ev && ev.location) || "";
    if ($("sm-event-status")) $("sm-event-status").value = (ev && ev.status) || "active";
    if ($("sm-event-notes")) $("sm-event-notes").value = (ev && ev.notes) || "";
    await ensureUserOpts();
    buildAttendeePicker($("sm-attendee-picker"), ev && ev.attendee_ids);
    new bootstrap.Modal($("smEventModal")).show();
  }

  async function saveEvent() {
    const payload = {
      name: ($("sm-event-name") || {}).value,
      start_date: ($("sm-event-start") || {}).value,
      end_date: ($("sm-event-end") || {}).value,
      location: ($("sm-event-location") || {}).value,
      status: ($("sm-event-status") || {}).value,
      notes: ($("sm-event-notes") || {}).value,
      attendee_ids: Array.from(selectedAttendeeIds),
    };
    try {
      if (editingEventId) {
        await fetchJson(API.event(editingEventId), { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      } else {
        await fetchJson(API.events, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      }
      bootstrap.Modal.getInstance($("smEventModal")).hide();
      loadEventsList();
    } catch (e) { alert(e.message); }
  }

  function wireEvents() {
    loadEventsList();
    const newBtn = $("sm-new-event");
    if (newBtn) newBtn.addEventListener("click", function () { openEventModal(null); });
    const saveBtn = $("sm-event-save");
    if (saveBtn) saveBtn.addEventListener("click", saveEvent);
    const delBtn = $("sm-event-delete");
    if (delBtn) delBtn.addEventListener("click", async function () {
      if (!editingEventId || !confirm("Delete this event?")) return;
      await fetchJson(API.event(editingEventId), { method: "DELETE" });
      bootstrap.Modal.getInstance($("smEventModal")).hide();
      loadEventsList();
    });
    const qrBtn = $("sm-event-qr");
    if (qrBtn) qrBtn.addEventListener("click", function () {
      if (window.smShowEventQr) window.smShowEventQr(editingEventId);
    });
  }

  // --- Roadmap ---
  async function loadRoadmap() {
    const host = $("sm-roadmap-host");
    if (!host) return;
    host.innerHTML = '<p class="text-muted">Loading…</p>';
    const p = new URLSearchParams();
    const tl = ($("sm-roadmap-timeline") || {}).value;
    if (tl) p.set("timeline", tl);
    if (($("sm-roadmap-mine") || {}).checked) p.set("my_events", "1");
    const loc = ($("sm-roadmap-location") || {}).value;
    if (loc) p.set("location", loc);
    try {
      const grouped = await fetchJson(API.roadmap + "?" + p.toString());
      const sections = [
        { key: "ongoing", title: "Happening now", color: "#16a34a" },
        { key: "upcoming", title: "Upcoming", color: "#00407d" },
        { key: "past", title: "Past", color: "#94a3b8" },
        { key: "cancelled", title: "Cancelled", color: "#dc2626" },
      ];
      let html = "";
      sections.forEach(function (sec) {
        const items = grouped[sec.key] || [];
        if (tl !== "all" && tl !== sec.key) return;
        html += '<div class="sm-roadmap-section"><h3 style="color:' + sec.color + '">' + sec.title + " (" + items.length + ")</h3>";
        html += items.length ? items.map(eventCardHtml).join("") : '<p class="text-muted small">None</p>';
        html += "</div>";
      });
      host.innerHTML = html || '<p class="text-muted">No events match filters.</p>';
    } catch (e) { host.innerHTML = '<p class="text-danger">' + esc(e.message) + "</p>"; }
  }

  function wireRoadmap() {
    loadRoadmap();
    ["sm-roadmap-timeline", "sm-roadmap-mine", "sm-roadmap-location"].forEach(function (id) {
      const el = $(id);
      if (el) el.addEventListener("change", loadRoadmap);
      if (el && el.type === "search") el.addEventListener("input", loadRoadmap);
    });
    const ref = $("sm-roadmap-refresh");
    if (ref) ref.addEventListener("click", loadRoadmap);
  }

  // --- Settings ---
  async function loadSettings() {
    const list = $("sm-interest-list");
    if (!list) return;
    const opts = await fetchJson(API.interest);
    list.innerHTML = "";
    opts.forEach(function (o) {
      const li = document.createElement("li");
      li.className = "list-group-item d-flex justify-content-between align-items-center";
      li.innerHTML = '<span>' + esc(o.label) + (o.is_active ? "" : ' <span class="badge bg-secondary">inactive</span>') + "</span>" +
        '<div><button class="btn btn-sm btn-link sm-toggle-interest" data-id="' + o.id + '" data-active="' + o.is_active + '">' +
        (o.is_active ? "Deactivate" : "Activate") + '</button></div>';
      list.appendChild(li);
    });
    list.querySelectorAll(".sm-toggle-interest").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        const id = btn.getAttribute("data-id");
        const active = btn.getAttribute("data-active") === "true";
        await fetchJson(API.interestOpt(id), { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ is_active: !active }) });
        loadSettings();
      });
    });
  }

  function wireSettings() {
    loadSettings();
    const add = $("sm-add-interest");
    if (add) add.addEventListener("click", async function () {
      const label = ($("sm-new-interest") || {}).value;
      if (!label.trim()) return;
      await fetchJson(API.interest, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ label: label.trim() }) });
      $("sm-new-interest").value = "";
      loadSettings();
    });
  }

  // --- Campaigns ---
  async function loadCampaigns() {
    const body = $("sm-campaigns-body");
    if (!body) return;
    const items = await fetchJson(API.campaigns);
    body.innerHTML = items.length ? items.map(function (c) {
      return "<tr><td>" + esc(c.subject) + "</td><td>" + c.recipient_count + "</td><td>" + esc(c.status) +
        "</td><td>" + esc((c.sent_at || c.created_at || "").slice(0, 16).replace("T", " ")) +
        '</td><td><button type="button" class="btn btn-sm btn-link sm-campaign-detail" data-id="' + c.id + '">Details</button></td></tr>';
    }).join("") : '<tr><td colspan="5" class="text-muted">No campaigns yet. Compose above or send from Stakeholders.</td></tr>';
    body.querySelectorAll(".sm-campaign-detail").forEach(function (btn) {
      btn.addEventListener("click", function () {
        if (window.smOpenCampaignDetail) window.smOpenCampaignDetail(parseInt(btn.getAttribute("data-id"), 10));
      });
    });
  }

  function wireCampaigns() { loadCampaigns(); }

  document.addEventListener("DOMContentLoaded", function () {
    if (page === "stakeholders") wireStakeholders();
    if (page === "events") wireEvents();
    if (page === "roadmap") wireRoadmap();
    if (page === "settings") wireSettings();
    if (page === "campaigns") wireCampaigns();
  });

  window.smSalesMarketing = {
    API: API,
    fetchJson: fetchJson,
    esc: esc,
    $: $,
    filterParams: filterParams,
    filterParamsObject: filterParamsObject,
    loadLeads: loadLeads,
    selectedLeadIds: function () { return selectedLeadIds; },
    openLeadModal: openLeadModal,
    getEventsCache: function () { return eventsCache; },
    getEditingEventId: function () { return editingEventId; },
  };
})();
