/**
 * Hub-specific hooks (my work dashboard). Core logic lives in meeting_notes.js;
 * analytics and templates are in mn-extensions.js.
 */
(function () {
  document.addEventListener("DOMContentLoaded", function () {
    if (typeof MN_HUB_MODE === "undefined" || !MN_HUB_MODE) return;
    document.querySelectorAll(".mn-hub-nav a").forEach(function (link) {
      if (link.getAttribute("href") === window.location.pathname) {
        link.classList.add("active");
      }
    });
  });
})();
