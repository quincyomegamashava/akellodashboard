/**
 * Meeting notes mobile UX: bottom nav, detail tabs, board dots, bottom-sheet panel.
 */
(function () {
  function $(sel, root) { return (root || document).querySelector(sel); }
  function $all(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  function initBottomNav() {
    const path = window.location.pathname;
    const search = window.location.search;
    $all(".mn-bottom-nav-item[data-mn-nav]").forEach(function (el) {
      const nav = el.getAttribute("data-mn-nav");
      let active = false;
      if (nav === "home" && path.match(/\/meeting-notes\/?$/)) active = true;
      if (nav === "tasks" && path.indexOf("/all-items") >= 0) active = true;
      el.classList.toggle("active", active);
    });

    const newBtn = $(".mn-bottom-nav-item[data-mn-nav='new']");
    if (newBtn) {
      newBtn.addEventListener("click", function () {
        if (path.match(/\/meeting-notes\/?$/)) {
          const sheet = document.getElementById("mn-new-meeting-sheet");
          if (sheet && window.bootstrap) {
            bootstrap.Offcanvas.getOrCreateInstance(sheet).show();
            return;
          }
        }
        if (typeof MN_MEETING_NOTE_ID === "number" && MN_MEETING_NOTE_ID) {
          const qc = $("#mn-quick-capture-input");
          if (qc) { qc.focus(); qc.scrollIntoView({ behavior: "smooth", block: "center" }); }
          return;
        }
        window.location.href = "/meeting-notes/";
      });
    }
  }

  function initDetailTabs() {
    const tabs = $("#mn-detail-tabs");
    if (!tabs) return;
    const panes = {
      tasks: $("#mn-detail-pane-tasks"),
      filters: $("#mn-detail-pane-filters"),
    };
    const KEY = "mn-detail-tab";
    let active = sessionStorage.getItem(KEY) || "tasks";
    if (active !== "tasks" && active !== "filters") active = "tasks";

    function showTab(name) {
      active = name;
      sessionStorage.setItem(KEY, name);
      $all("[data-mn-detail-tab]", tabs).forEach(function (btn) {
        btn.classList.toggle("active", btn.getAttribute("data-mn-detail-tab") === name);
      });
      Object.keys(panes).forEach(function (key) {
        if (panes[key]) panes[key].classList.toggle("d-none", key !== name);
      });
      if (name === "filters") {
        const sheet = document.getElementById("mn-filter-sheet");
        if (sheet && window.bootstrap) bootstrap.Offcanvas.getOrCreateInstance(sheet).show();
      }
    }

    $all("[data-mn-detail-tab]", tabs).forEach(function (btn) {
      btn.addEventListener("click", function () {
        showTab(btn.getAttribute("data-mn-detail-tab"));
      });
    });

    const filterSheet = document.getElementById("mn-filter-sheet");
    if (filterSheet) {
      filterSheet.addEventListener("hidden.bs.offcanvas", function () {
        if (active === "filters") showTab("tasks");
      });
    }

    showTab(active);
  }

  function initBoardDots() {
    const board = $("#mn-board");
    const dotsHost = $("#mn-board-dots");
    if (!board || !dotsHost) return;

    function updateDots() {
      const cols = $all(".mn-board-column", board);
      if (!cols.length || window.innerWidth > 767) {
        dotsHost.innerHTML = "";
        if (dotsHost.classList) dotsHost.classList.add("d-none");
        return;
      }
      if (dotsHost.classList) dotsHost.classList.remove("d-none");
      dotsHost.innerHTML = cols.map(function (_, i) {
        return '<span class="mn-board-dot' + (i === 0 ? " active" : "") + '" data-idx="' + i + '"></span>';
      }).join("");

      const observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting && entry.intersectionRatio > 0.5) {
            const idx = cols.indexOf(entry.target);
            $all(".mn-board-dot", dotsHost).forEach(function (d, i) {
              d.classList.toggle("active", i === idx);
            });
          }
        });
      }, { root: board, threshold: 0.55 });

      cols.forEach(function (col) { observer.observe(col); });

      $all(".mn-board-dot", dotsHost).forEach(function (dot) {
        dot.addEventListener("click", function () {
          const idx = parseInt(dot.getAttribute("data-idx"), 10);
          if (cols[idx]) cols[idx].scrollIntoView({ behavior: "smooth", inline: "start", block: "nearest" });
        });
      });
    }

    const mo = new MutationObserver(updateDots);
    mo.observe(board, { childList: true, subtree: true });
    window.addEventListener("resize", updateDots);
    updateDots();
  }

  function initOverflowMenu() {
    const toggle = $("#mn-overflow-toggle");
    const menu = $("#mn-overflow-menu");
    if (!toggle || !menu) return;
    toggle.addEventListener("click", function (e) {
      e.stopPropagation();
      menu.classList.toggle("show");
    });
    document.addEventListener("click", function () { menu.classList.remove("show"); });
    menu.addEventListener("click", function (e) { e.stopPropagation(); });
  }

  function initHubCarousel() {
    const track = $("#mn-my-tasks-track");
    if (!track) return;
    const dots = $("#mn-my-tasks-dots");
    const slides = $all(".mn-my-tasks-slide", track);
    if (!slides.length || !dots) return;

    dots.innerHTML = slides.map(function (_, i) {
      return '<button type="button" class="mn-carousel-dot' + (i === 0 ? " active" : "") + '" data-idx="' + i + '" aria-label="Slide ' + (i + 1) + '"></button>';
    }).join("");

    const observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting && entry.intersectionRatio > 0.6) {
          const idx = slides.indexOf(entry.target);
          $all(".mn-carousel-dot", dots).forEach(function (d, i) {
            d.classList.toggle("active", i === idx);
          });
        }
      });
    }, { root: track, threshold: 0.6 });

    slides.forEach(function (s) { observer.observe(s); });

    $all(".mn-carousel-dot", dots).forEach(function (dot) {
      dot.addEventListener("click", function () {
        const idx = parseInt(dot.getAttribute("data-idx"), 10);
        if (slides[idx]) slides[idx].scrollIntoView({ behavior: "smooth", inline: "start" });
      });
    });
  }

  function initMobileTableHint() {
    const hint = $("#mn-mobile-table-hint");
    const tableView = $("#mn-view-table");
    if (!hint || !tableView) return;
    function sync() {
      const isMobile = window.innerWidth < 768;
      const tableVisible = tableView && !tableView.classList.contains("d-none");
      hint.classList.toggle("d-none", !(isMobile && tableVisible));
    }
    window.addEventListener("resize", sync);
    sync();
    const observer = new MutationObserver(sync);
    observer.observe(tableView, { attributes: true, attributeFilter: ["class"] });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initBottomNav();
    initDetailTabs();
    initBoardDots();
    initOverflowMenu();
    initHubCarousel();
    initMobileTableHint();
  });
})();
