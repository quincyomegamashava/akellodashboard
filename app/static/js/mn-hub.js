/**
 * Hub-specific hooks (my work dashboard). Core logic lives in meeting_notes.js;
 * analytics and templates are in mn-extensions.js.
 */
(function () {
  const VALID_HUB_TABS = ["tasks", "meetings", "new"];

  function tabFromHash() {
    const raw = (window.location.hash || "").replace(/^#/, "").toLowerCase();
    if (raw === "meetings" || raw === "mn-meetings-section") return "meetings";
    if (raw === "new" || raw === "new-meeting") return "new";
    if (raw === "tasks") return "tasks";
    const params = new URLSearchParams(window.location.search);
    if (params.get("q")) return "meetings";
    return "tasks";
  }

  function initHubTabs() {
    const tablist = document.getElementById("mn-hub-tabs");
    if (!tablist) return;

    function showTab(name) {
      if (VALID_HUB_TABS.indexOf(name) < 0) name = "tasks";
      tablist.querySelectorAll("[data-mn-hub-tab]").forEach(function (btn) {
        const on = btn.getAttribute("data-mn-hub-tab") === name;
        btn.classList.toggle("active", on);
        btn.setAttribute("aria-selected", on ? "true" : "false");
      });
      VALID_HUB_TABS.forEach(function (key) {
        const pane = document.getElementById("mn-hub-tab-" + key);
        if (pane) pane.classList.toggle("d-none", key !== name);
      });
      document.querySelectorAll(".mn-subnav-link").forEach(function (link) {
        const href = link.getAttribute("href") || "";
        if (name === "meetings" && href.indexOf("#meetings") >= 0) {
          link.classList.add("active");
        } else if (name === "tasks" && href.indexOf("#tasks") >= 0) {
          link.classList.add("active");
        } else if (href.indexOf("#meetings") >= 0 || href.indexOf("#tasks") >= 0) {
          link.classList.remove("active");
        }
      });
      if (window.location.hash !== "#" + name) {
        history.replaceState(null, "", window.location.pathname + window.location.search + "#" + name);
      }
    }

    tablist.querySelectorAll("[data-mn-hub-tab]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        showTab(btn.getAttribute("data-mn-hub-tab"));
      });
    });

    window.addEventListener("hashchange", function () {
      showTab(tabFromHash());
    });

    showTab(tabFromHash());
    window.MN_showHubTab = showTab;
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (typeof MN_HUB_MODE === "undefined" || !MN_HUB_MODE) return;
    initHubTabs();
    document.querySelectorAll(".mn-hub-nav a").forEach(function (link) {
      if (link.getAttribute("href") === window.location.pathname) {
        link.classList.add("active");
      }
    });
  });
})();
