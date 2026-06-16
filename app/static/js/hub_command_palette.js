/**
 * Shared hub command palette — context-aware search and commands.
 */
(function () {
  function $(sel) { return document.querySelector(sel); }

  function pageContext() {
    const p = window.location.pathname;
    if (p.indexOf("/meeting-notes") === 0) return "meeting_notes";
    if (p.indexOf("/sales-marketing") === 0) return "sales_marketing";
    return "hub";
  }

  async function runCommand(query) {
    const ctx = pageContext();
    const q = (query || "").trim();
    if (!q) return;

    if (ctx === "meeting_notes" && window.MN_MEETING_ID) {
      const res = await fetch("/meeting-notes/api/hub/command", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q, meeting_id: window.MN_MEETING_ID }),
      });
      const data = await res.json();
      if (data.url) { window.location.href = data.url; return; }
      if (data.summary) { alert(data.summary); return; }
    }

    if (ctx === "sales_marketing") {
      if (/export/i.test(q)) {
        const btn = document.getElementById("sm-btn-export");
        if (btn) btn.click();
        return;
      }
      if (/stand/i.test(q)) {
        const m = window.location.pathname.match(/events\/(\d+)/);
        if (m) window.location.href = "/sales-marketing/events/" + m[1] + "/stand";
        return;
      }
    }

    const palette = document.getElementById("mn-command-palette");
    if (palette && window.bootstrap) {
      const input = palette.querySelector("input");
      if (input) { input.value = q; input.dispatchEvent(new Event("input", { bubbles: true })); }
      new bootstrap.Modal(palette).show();
    }
  }

  document.addEventListener("keydown", function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key === "k") {
      const palette = document.getElementById("mn-command-palette");
      if (palette && window.bootstrap) {
        e.preventDefault();
        new bootstrap.Modal(palette).show();
      }
    }
  });

  window.hubRunCommand = runCommand;

  document.addEventListener("DOMContentLoaded", function () {
    if (localStorage.getItem("hub_dark_mode") === "1") {
      document.body.classList.add("hub-dark-mode");
    }
    if (localStorage.getItem("hub_density") === "compact") {
      document.body.setAttribute("data-density", "compact");
    }
  });

  window.hubToggleDarkMode = function () {
    document.body.classList.toggle("hub-dark-mode");
    localStorage.setItem("hub_dark_mode", document.body.classList.contains("hub-dark-mode") ? "1" : "0");
  };

  window.hubToggleDensity = function () {
    const compact = document.body.getAttribute("data-density") === "compact";
    document.body.setAttribute("data-density", compact ? "comfortable" : "compact");
    localStorage.setItem("hub_density", compact ? "comfortable" : "compact");
  };
})();
