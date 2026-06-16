/**
 * Meeting Notes roadmap: decisions, meeting mode, scorecard, carry-forward suggestions, collab.
 */
(function () {
  const API = window.MN_API;
  const MN = window.MN;
  if (!API) return;

  function $(id) { return document.getElementById(id); }

  function meetingId() {
    return window.MN_MEETING_ID || window.MN_MEETING_NOTE_ID;
  }

  async function loadDecisions() {
    const host = $("mn-decisions-list");
    if (!host || !meetingId()) return;
    try {
      const rows = await fetch(API.decisions ? API.decisions(meetingId()) : "/meeting-notes/api/meetings/" + meetingId() + "/decisions").then(function (r) { return r.json(); });
      if (!rows.length) {
        host.innerHTML = "<p class=\"text-muted small\">No decisions recorded yet.</p>";
        return;
      }
      host.innerHTML = rows.map(function (d) {
        return "<div class=\"hub-card p-2 mb-2\"><div class=\"small fw-semibold\">" + (d.owner_name || "Team") + "</div><div>" + escapeHtml(d.body) + "</div></div>";
      }).join("");
    } catch (e) {
      host.innerHTML = "<p class=\"text-danger small\">Could not load decisions.</p>";
    }
  }

  function escapeHtml(s) {
    return String(s || "").replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  async function loadCarrySuggestions() {
    const banner = $("mn-carry-suggestions");
    if (!banner || !meetingId()) return;
    try {
      const data = await fetch("/meeting-notes/api/meetings/" + meetingId() + "/carry-forward/suggestions").then(function (r) { return r.json(); });
      const items = data.suggestions || [];
      if (!items.length) { banner.classList.add("d-none"); return; }
      banner.classList.remove("d-none");
      banner.innerHTML = "<strong class=\"small\">Suggested carry-forward</strong> (" + items.length + " open items from prior meeting) " +
        "<button type=\"button\" class=\"btn btn-sm btn-outline-primary ms-2\" id=\"mn-carry-suggestions-go\">Review</button>";
      const go = $("mn-carry-suggestions-go");
      if (go) go.addEventListener("click", function () {
        const modal = document.getElementById("mnCarryForwardModal");
        if (modal && window.bootstrap) new bootstrap.Modal(modal).show();
      });
    } catch (e) { banner.classList.add("d-none"); }
  }

  function initMeetingMode() {
    const btn = $("mn-btn-meeting-mode");
    const shell = $("mn-page-detail");
    if (!btn || !shell) return;
    const key = "mn_meeting_mode_" + meetingId();
    function apply(on) {
      shell.classList.toggle("mn-meeting-mode", on);
      sessionStorage.setItem(key, on ? "1" : "0");
      btn.classList.toggle("active", on);
    }
    apply(sessionStorage.getItem(key) === "1");
    btn.addEventListener("click", function () {
      apply(!shell.classList.contains("mn-meeting-mode"));
    });
  }

  function initPresence() {
    if (!meetingId() || typeof io === "undefined") return;
    try {
      const socket = io("/meeting-notes");
      socket.emit("presence_join", { meeting_id: meetingId(), username: window.MN_CURRENT_USER || "User" });
      socket.on("presence_update", function (data) {
        const el = $("mn-presence-avatars");
        if (!el || !data.users) return;
        el.innerHTML = data.users.map(function (u) {
          return "<span class=\"badge bg-secondary\" title=\"" + escapeHtml(u) + "\">" + escapeHtml(u.slice(0, 2).toUpperCase()) + "</span>";
        }).join(" ");
      });
    } catch (e) { /* ignore */ }
  }

  async function loadExtendedAnalytics() {
    const el = $("mn-hub-analytics");
    if (!el || !window.MN_HUB_MODE) return;
    try {
      const data = await fetch("/meeting-notes/api/hub/analytics/extended").then(function (r) { return r.json(); });
      let html =
        "<span class=\"mn-analytics-chip\">" + (data.completion_rate || 0) + "% complete</span>" +
        "<span class=\"mn-analytics-chip\">" + (data.overdue_items || 0) + " overdue</span>";
      (data.per_user || []).slice(0, 3).forEach(function (u) {
        html += "<span class=\"mn-analytics-chip\" title=\"Avg days late\">" + escapeHtml(u.name) + ": " + u.completion_rate + "%</span>";
      });
      el.innerHTML = html;
    } catch (e) { /* fallback handled by mn-extensions */ }
  }

  function initDecisionsTab() {
    document.querySelectorAll("[data-mn-detail-tab]").forEach(function (tab) {
      tab.addEventListener("click", function () {
        const t = tab.getAttribute("data-mn-detail-tab");
        document.querySelectorAll(".mn-detail-tab-pane").forEach(function (p) {
          p.classList.toggle("d-none", p.id !== "mn-tab-" + t);
        });
        document.querySelectorAll("[data-mn-detail-tab]").forEach(function (b) {
          b.classList.toggle("active", b === tab);
        });
        if (t === "decisions") loadDecisions();
      });
    });
    const addBtn = $("mn-decision-add");
    if (addBtn) addBtn.addEventListener("click", async function () {
      const input = $("mn-decision-input");
      const body = (input && input.value || "").trim();
      if (!body) return;
      await fetch("/meeting-notes/api/meetings/" + meetingId() + "/decisions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ body: body }),
      });
      if (input) input.value = "";
      loadDecisions();
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (meetingId()) {
      loadDecisions();
      loadCarrySuggestions();
      initMeetingMode();
      initPresence();
      initDecisionsTab();
    }
    if (window.MN_HUB_MODE) loadExtendedAnalytics();
  });

  window.MN_API = window.MN_API || {};
  window.MN_API.decisions = function (mid) { return "/meeting-notes/api/meetings/" + mid + "/decisions"; };
})();
