/**
 * Sales & Marketing roadmap UI: kanban, saved views, funnel, map helpers.
 */
(function () {
  const sm = window.smSalesMarketing;
  if (!sm) return;

  const STAGES = ["new", "contacted", "qualified", "closed"];
  const STAGE_LABELS = { new: "New", contacted: "Contacted", qualified: "Qualified", closed: "Closed" };

  function $(id) { return document.getElementById(id); }

  function esc(s) {
    return sm.esc ? sm.esc(s) : String(s || "").replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  let kanbanLeads = [];
  let viewMode = localStorage.getItem("sm_view_mode") || "table";

  function setViewMode(mode) {
    viewMode = mode;
    localStorage.setItem("sm_view_mode", mode);
    const tableWrap = document.querySelector(".table-responsive");
    const board = $("sm-kanban-board");
    document.querySelectorAll("[data-sm-view]").forEach(function (btn) {
      btn.classList.toggle("active", btn.getAttribute("data-sm-view") === mode);
    });
    if (tableWrap) tableWrap.classList.toggle("d-none", mode === "board");
    if (board) board.classList.toggle("d-none", mode !== "board");
    if (mode === "board") renderKanban();
  }

  function renderKanban() {
    const host = $("sm-kanban-board");
    if (!host) return;
    host.innerHTML = "";
    const cols = document.createElement("div");
    cols.className = "hub-kanban";
    STAGES.forEach(function (stage) {
      const col = document.createElement("div");
      col.className = "hub-kanban-col";
      col.dataset.stage = stage;
      const items = kanbanLeads.filter(function (l) { return (l.follow_up_status || "new") === stage; });
      col.innerHTML = "<h4>" + esc(STAGE_LABELS[stage]) + " <span class=\"text-muted\">(" + items.length + ")</span></h4>";
      const list = document.createElement("div");
      list.className = "sm-kanban-list";
      items.forEach(function (lead) {
        const card = document.createElement("div");
        card.className = "hub-kanban-card";
        card.draggable = true;
        card.dataset.leadId = lead.id;
        card.innerHTML =
          "<div class=\"fw-semibold small\">" + esc(lead.full_name) + "</div>" +
          "<div class=\"text-muted\" style=\"font-size:0.7rem;\">" + esc(lead.event_name || lead.province || "") + "</div>" +
          (lead.is_duplicate_flag && !lead.duplicate_dismissed ? "<span class=\"sm-badge-dup\">Dup</span> " : "") +
          (lead.consent_marketing ? "<span class=\"badge bg-success\" style=\"font-size:0.65rem;\">Consent</span>" : "");
        card.addEventListener("dragstart", function (e) {
          e.dataTransfer.setData("text/plain", String(lead.id));
          card.classList.add("dragging");
        });
        card.addEventListener("dragend", function () { card.classList.remove("dragging"); });
        card.addEventListener("click", function () {
          if (window.smOpenLeadDrawer) window.smOpenLeadDrawer(lead.id);
        });
        list.appendChild(card);
      });
      col.addEventListener("dragover", function (e) { e.preventDefault(); col.classList.add("hub-kanban-drop-target"); });
      col.addEventListener("dragleave", function () { col.classList.remove("hub-kanban-drop-target"); });
      col.addEventListener("drop", async function (e) {
        e.preventDefault();
        col.classList.remove("hub-kanban-drop-target");
        const id = parseInt(e.dataTransfer.getData("text/plain"), 10);
        if (!id) return;
        await sm.fetchJson(sm.API.stakeholder(id), {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ follow_up_status: stage }),
        });
        sm.loadLeads();
      });
      col.appendChild(list);
      cols.appendChild(col);
    });
    host.appendChild(cols);
  }

  async function loadFunnel() {
    const el = $("sm-funnel-chart");
    if (!el) return;
    try {
      const data = await sm.fetchJson("/sales-marketing/api/stakeholders/funnel?period=30");
      let html = "<div class=\"d-flex flex-wrap gap-2 align-items-end\">";
      STAGES.forEach(function (st) {
        const n = (data.by_stage || {})[st] || 0;
        const h = Math.max(20, Math.min(120, n * 8));
        html += "<div class=\"text-center\"><div style=\"height:" + h + "px;width:3rem;background:#00407d;border-radius:4px;margin:0 auto;\"></div><div class=\"small mt-1\">" + esc(STAGE_LABELS[st]) + "</div><strong>" + n + "</strong></div>";
      });
      html += "</div>";
      if ((data.anomalies || []).length) {
        html += "<div class=\"mt-2\">";
        data.anomalies.forEach(function (a) {
          html += "<span class=\"hub-analytics-chip text-warning\">" + esc(a.message) + "</span>";
        });
        html += "</div>";
      }
      el.innerHTML = html;
    } catch (e) { el.innerHTML = ""; }
  }

  async function initSavedViews() {
    const sel = $("sm-saved-view-select");
    if (!sel) return;
    try {
      const views = await sm.fetchJson("/sales-marketing/api/saved-views");
      sel.innerHTML = "<option value=\"\">Saved views…</option>";
      views.forEach(function (v) {
        const opt = document.createElement("option");
        opt.value = v.id;
        opt.textContent = v.name + (v.is_default ? " ★" : "");
        opt.dataset.filters = JSON.stringify(v.filters_json || {});
        opt.dataset.viewMode = v.view_mode || "table";
        sel.appendChild(opt);
      });
    } catch (e) { /* ignore */ }
    sel.addEventListener("change", function () {
      const opt = sel.options[sel.selectedIndex];
      if (!opt || !opt.dataset.filters) return;
      try {
        const f = JSON.parse(opt.dataset.filters);
        if (f.search && $("sm-search")) $("sm-search").value = f.search;
        if (f.status && $("sm-filter-status")) $("sm-filter-status").value = f.status;
        if (f.province && $("sm-filter-province")) $("sm-filter-province").value = f.province;
        if (opt.dataset.viewMode) setViewMode(opt.dataset.viewMode);
        sm.loadLeads();
      } catch (err) { /* ignore */ }
    });
    const saveBtn = $("sm-saved-view-save");
    if (saveBtn) saveBtn.addEventListener("click", async function () {
      const name = prompt("View name:");
      if (!name) return;
      await sm.fetchJson("/sales-marketing/api/saved-views", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name,
          filters_json: sm.filterParamsObject ? sm.filterParamsObject() : {},
          view_mode: viewMode,
        }),
      });
      initSavedViews();
    });
  }

  window.smOnLeadsLoaded = function (data) {
    kanbanLeads = (data && data.items) ? data.items : (Array.isArray(data) ? data : []);
    if (viewMode === "board") renderKanban();
    if (typeof window.smOnLeadsLoadedBase === "function") window.smOnLeadsLoadedBase(data);
  };

  function initStakeholdersPage() {
    if (window.SM_PAGE !== "stakeholders") return;
    document.querySelectorAll("[data-sm-view]").forEach(function (btn) {
      btn.addEventListener("click", function () { setViewMode(btn.getAttribute("data-sm-view")); });
    });
    setViewMode(viewMode);
    loadFunnel();
    initSavedViews();
  }

  function initMapPage() {
    if (window.SM_PAGE !== "map") return;
    const host = $("sm-map-host");
    if (!host) return;
    sm.fetchJson("/sales-marketing/api/stakeholders/by-province?period=all").then(function (rows) {
      const max = Math.max.apply(null, rows.map(function (r) { return r.count; }).concat([1]));
      let html = "<div class=\"row g-2\">";
      rows.sort(function (a, b) { return b.count - a.count; });
      rows.forEach(function (r) {
        const pct = Math.round((r.count / max) * 100);
        html += "<div class=\"col-md-4 col-6\"><a href=\"/sales-marketing/?province=" + encodeURIComponent(r.province) + "\" class=\"text-decoration-none\">" +
          "<div class=\"hub-card p-2\"><div class=\"d-flex justify-content-between\"><strong class=\"small\">" + esc(r.province) + "</strong><span>" + r.count + "</span></div>" +
          "<div class=\"progress mt-1\" style=\"height:6px;\"><div class=\"progress-bar\" style=\"width:" + pct + "%;background:#00407d;\"></div></div>" +
          "<div class=\"text-muted\" style=\"font-size:0.7rem;\">" + r.with_consent + " with consent</div></div></a></div>";
      });
      html += "</div>";
      host.innerHTML = html;
    });
  }

  function initStandMode() {
    if (window.SM_PAGE !== "stand") return;
    const eventId = window.SM_STAND_EVENT_ID;
    if (!eventId) return;
    async function tick() {
      try {
        const s = await sm.fetchJson("/sales-marketing/api/stakeholders/stats?event_id=" + eventId);
        if ($("sm-stand-count")) $("sm-stand-count").textContent = s.total_leads || 0;
        const ticker = $("sm-stand-ticker");
        if (ticker && s.latest_leads) {
          ticker.innerHTML = s.latest_leads.map(function (l) {
            return "<div class=\"small\">" + esc(l.full_name) + " · " + esc((l.submitted_at || "").slice(11, 16)) + "</div>";
          }).join("");
        }
      } catch (e) { /* ignore */ }
    }
    tick();
    setInterval(tick, 10000);
  }

  function initEventDashboard() {
    if (window.SM_PAGE !== "event_dashboard") return;
    const eventId = window.SM_EVENT_DASHBOARD_ID;
    if (!eventId) return;
    sm.fetchJson("/sales-marketing/api/events/" + eventId + "/roi").then(function (d) {
      const host = $("sm-roi-host");
      if (!host) return;
      host.innerHTML =
        "<div class=\"hub-stat-row mb-3\">" +
        "<div class=\"hub-stat-card\"><div class=\"hub-stat-val\">" + d.total_leads + "</div><div class=\"hub-stat-lbl\">Leads</div></div>" +
        "<div class=\"hub-stat-card\"><div class=\"hub-stat-val\">" + d.consent_rate + "%</div><div class=\"hub-stat-lbl\">Consent</div></div>" +
        "<div class=\"hub-stat-card\"><div class=\"hub-stat-val\">" + (d.cost_per_lead != null ? d.cost_per_lead : "—") + "</div><div class=\"hub-stat-lbl\">Cost/lead</div></div>" +
        "</div>" +
        "<a class=\"btn btn-sm btn-primary me-2\" href=\"/sales-marketing/events/" + eventId + "/stand\">Stand mode</a>" +
        "<a class=\"btn btn-sm btn-outline-primary\" href=\"/sales-marketing/campaigns\">Send campaign</a>";
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initStakeholdersPage();
    initMapPage();
    initStandMode();
    initEventDashboard();
  });
})();
