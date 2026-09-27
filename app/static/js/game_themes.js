/**
 * Game portal visual themes — car race, tug of war, solo survival.
 * Expects a mount element and updates from leaderboard / timer state.
 */
(function (global) {
  "use strict";

  const CAR_COLORS = [
    "#2563eb", "#ea580c", "#16a34a", "#db2777",
    "#0891b2", "#ca8a04", "#7c3aed", "#dc2626",
  ];

  function esc(text) {
    return String(text == null ? "" : text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function firstName(row) {
    const n = (row.firstname || row.username || "Racer").trim();
    return n.split(/\s+/)[0] || "Racer";
  }

  function progressFraction(row, totalItems) {
    const total = Math.max(1, Number(totalItems) || Number(row.total_items) || 1);
    if (row.finished) {
      const place = Math.max(1, Number(row.place) || 1);
      // Finished players stay near the finish; better place slightly ahead
      return Math.min(1, 0.92 + (1 / (place + 4)));
    }
    return Math.max(0, Math.min(0.9, (Number(row.progress) || 0) / total));
  }

  function ensureRaceShell(mount, theme) {
    if (!mount) return;
    if (mount.dataset.theme === theme && mount.querySelector(".theme-inner")) return;
    // Dispose previous 3D scene when switching themes
    if (mount._tug3d) {
      try { mount._tug3d.dispose(); } catch (_) { /* ignore */ }
      mount._tug3d = null;
    }
    mount.dataset.theme = theme || "car";
    if (theme === "tug_of_war") {
      const use3d = global.GameThemes3D && global.GameThemes3D.available && global.GameThemes3D.available();
      mount.innerHTML = `
        <div class="theme-stage theme-inner">
          <div class="theme-stage-header">
            <span><i class="fas fa-people-arrows mr-1"></i> Tug of War${use3d ? " · 3D" : ""}</span>
            <span class="theme-chip-you" id="tugYouChip" style="display:none;"></span>
          </div>
          <div class="tug-banners tug-banners-overlay">
            <span class="team1">Team 1 · <span id="tugScore1">0</span></span>
            <span class="team2">Team 2 · <span id="tugScore2">0</span></span>
          </div>
          <div class="tug-arena${use3d ? " tug-arena-3d" : ""}" id="tugArena">
            ${use3d ? '<div id="tug3dMount" class="theme-3d-mount"></div>' : `
            <div class="tug-midline"></div>
            <div class="tug-team left" id="tugTeam1">
              <div class="tug-kid"><div class="head"></div><div class="body"></div><div class="legs"><span></span><span></span></div></div>
              <div class="tug-kid"><div class="head"></div><div class="body"></div><div class="legs"><span></span><span></span></div></div>
            </div>
            <div class="tug-team right" id="tugTeam2">
              <div class="tug-kid"><div class="head"></div><div class="body"></div><div class="legs"><span></span><span></span></div></div>
              <div class="tug-kid"><div class="head"></div><div class="body"></div><div class="legs"><span></span><span></span></div></div>
            </div>
            <div class="tug-rope-wrap">
              <div class="tug-rope" id="tugRope"><div class="tug-knot"></div></div>
            </div>`}
          </div>
        </div>`;
      if (use3d) {
        const el = mount.querySelector("#tug3dMount");
        try {
          mount._tug3d = global.GameThemes3D.mountTug(el);
          if (!mount._tug3d) throw new Error("mountTug returned null");
        } catch (err) {
          console.warn("Tug 3D failed, using 2D", err);
          mount._tug3d = null;
          const arena = mount.querySelector("#tugArena");
          if (arena) {
            arena.classList.remove("tug-arena-3d");
            arena.innerHTML = `
            <div class="tug-midline"></div>
            <div class="tug-team left" id="tugTeam1">
              <div class="tug-kid"><div class="head"></div><div class="body"></div><div class="legs"><span></span><span></span></div></div>
              <div class="tug-kid"><div class="head"></div><div class="body"></div><div class="legs"><span></span><span></span></div></div>
            </div>
            <div class="tug-team right" id="tugTeam2">
              <div class="tug-kid"><div class="head"></div><div class="body"></div><div class="legs"><span></span><span></span></div></div>
              <div class="tug-kid"><div class="head"></div><div class="body"></div><div class="legs"><span></span><span></span></div></div>
            </div>
            <div class="tug-rope-wrap">
              <div class="tug-rope" id="tugRope"><div class="tug-knot"></div></div>
            </div>`;
          }
        }
      }
    } else {
      mount.innerHTML = `
        <div class="theme-stage theme-inner">
          <div class="theme-stage-header">
            <span><i class="fas fa-car-side mr-1"></i> Car Race</span>
            <span class="theme-chip-you" id="carYouChip" style="display:none;"></span>
          </div>
          <div class="car-track" id="carTrack">
            <div class="car-finish" title="Finish"></div>
            <div id="carLanes"></div>
          </div>
        </div>`;
    }
  }

  function renderCarRace(mount, leaderboard, opts) {
    opts = opts || {};
    ensureRaceShell(mount, "car");
    const lanes = mount.querySelector("#carLanes");
    if (!lanes) return;
    const meId = opts.meUserId != null ? Number(opts.meUserId) : null;
    const board = Array.isArray(leaderboard) ? leaderboard.slice(0, 8) : [];
    const totalItems = opts.totalItems || (board[0] && board[0].total_items) || 1;
    const track = mount.querySelector("#carTrack");
    const trackWidth = track ? Math.max(120, track.clientWidth - 80) : 280;

    lanes.innerHTML = board
      .map((row, i) => {
        const frac = progressFraction(row, totalItems);
        const px = Math.round(frac * trackWidth);
        const color = CAR_COLORS[i % CAR_COLORS.length];
        const isMe = meId != null && Number(row.user_id) === meId;
        const top = 18 + i * 16;
        return `
          <div class="car-lane" style="top:${top}px;">
            <div class="car-sprite${isMe ? " is-me" : ""}" style="transform:translateX(${px}px);">
              <div class="car-body" style="background:${color};"></div>
              <div class="car-label">${esc(firstName(row))}</div>
            </div>
          </div>`;
      })
      .join("");

    const chip = mount.querySelector("#carYouChip");
    if (chip && meId != null) {
      chip.style.display = "inline-flex";
      chip.textContent = "You are racing";
    }
  }

  function renderTugOfWar(mount, leaderboard, opts) {
    opts = opts || {};
    ensureRaceShell(mount, "tug_of_war");
    const board = Array.isArray(leaderboard) ? leaderboard : [];
    let t1 = 0;
    let t2 = 0;
    board.forEach((row) => {
      const prog = Number(row.progress) || 0;
      if (Number(row.team) === 2) t2 += prog;
      else t1 += prog;
    });
    const score1 = mount.querySelector("#tugScore1");
    const score2 = mount.querySelector("#tugScore2");
    if (score1) score1.textContent = String(t1);
    if (score2) score2.textContent = String(t2);

    const maxSide = Math.max(t1, t2, 1);
    const bias = ((t1 - t2) / (maxSide * 2)) * 40;

    if (mount._tug3d && mount._tug3d.setBias) {
      mount._tug3d.setBias(bias);
    } else {
      const rope = mount.querySelector("#tugRope");
      const team1El = mount.querySelector("#tugTeam1");
      const team2El = mount.querySelector("#tugTeam2");
      if (rope) rope.style.transform = `translateX(${bias}%)`;
      if (team1El) team1El.style.transform = `translateX(${bias * 0.35}%)`;
      if (team2El) team2El.style.transform = `translateX(${bias * 0.35}%)`;
    }

    const chip = mount.querySelector("#tugYouChip");
    const myTeam = opts.myTeam;
    if (chip && myTeam) {
      chip.style.display = "inline-flex";
      chip.textContent = `You: Team ${myTeam}`;
      chip.style.background = myTeam === 2 ? "#ffedd5" : "#e0f2fe";
      chip.style.color = myTeam === 2 ? "#c2410c" : "#0369a1";
    }
  }

  function updateRaceTheme(mount, race, leaderboard) {
    if (!mount || !race) return;
    const theme = race.visual_theme === "tug_of_war" ? "tug_of_war" : "car";
    const board = leaderboard || race.leaderboard || [];
    const me = race.me || {};
    const opts = {
      meUserId: me.user_id,
      myTeam: me.team,
      totalItems: (race.items && race.items.length) || (race.mix && race.mix.total_items) || 1,
    };
    if (theme === "tug_of_war") renderTugOfWar(mount, board, opts);
    else renderCarRace(mount, board, opts);
  }

  /* ---- Solo survival ---- */

  function ensureSurvivalShell(mount, theme) {
    if (!mount) return;
    const t = theme === "balloon" || theme === "rocket" ? theme : "swim";
    if (mount.dataset.soloTheme === t && mount.querySelector(".survival-inner")) return;
    if (mount._swim3d) {
      try { mount._swim3d.dispose(); } catch (_) { /* ignore */ }
      mount._swim3d = null;
    }
    mount.dataset.soloTheme = t;
    const useSwim3d = t === "swim" && global.GameThemes3D && global.GameThemes3D.available && global.GameThemes3D.available();
    let stageInner = "";
    if (t === "balloon") {
      stageInner = `
        <div class="survival-stage balloon">
          <div class="survival-actor balloon-actor" id="survivalActor">
            <div class="balloon-ball"></div>
            <div class="string"></div>
          </div>
        </div>`;
    } else if (t === "rocket") {
      stageInner = `
        <div class="survival-stage rocket">
          <div class="survival-actor rocket-actor" id="survivalActor">
            <div class="r-body"></div>
            <div class="flame"></div>
          </div>
        </div>`;
    } else if (useSwim3d) {
      stageInner = `<div class="survival-stage swim swim-3d" id="swim3dMount"></div>`;
    } else {
      stageInner = `
        <div class="survival-stage swim">
          <div class="shore"></div>
          <div class="survival-actor swimmer swimming" id="survivalActor">
            <div class="s-head"></div>
            <div class="s-body"></div>
          </div>
        </div>`;
    }
    mount.innerHTML = `
      <div class="survival-panel survival-inner">
        <div class="survival-timer">
          <div class="label">Time left</div>
          <div class="clock" id="survivalClock">--:--</div>
        </div>
        ${stageInner}
        <div class="survival-status" id="survivalStatus">Keep going — finish before time runs out!</div>
      </div>`;
    if (useSwim3d) {
      const el = mount.querySelector("#swim3dMount");
      try {
        mount._swim3d = global.GameThemes3D.mountSwim(el);
        if (!mount._swim3d) throw new Error("mountSwim returned null");
      } catch (err) {
        console.warn("Swim 3D failed, using 2D", err);
        mount._swim3d = null;
        const stage = mount.querySelector("#swim3dMount") || mount.querySelector(".survival-stage");
        if (stage) {
          stage.classList.remove("swim-3d");
          stage.innerHTML = `
          <div class="shore"></div>
          <div class="survival-actor swimmer swimming" id="survivalActor">
            <div class="s-head"></div>
            <div class="s-body"></div>
          </div>`;
        }
      }
    }
  }

  function formatClock(seconds) {
    const s = Math.max(0, Math.floor(seconds));
    const m = Math.floor(s / 60);
    const r = s % 60;
    return `${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
  }

  function setSurvivalProgress(mount, theme, elapsedFrac, scoreFrac) {
    const pressure = Math.max(0, Math.min(1, elapsedFrac || 0));
    const boost = Math.max(0, Math.min(1, scoreFrac || 0)) * 0.35;
    const pos = Math.max(0, Math.min(0.92, pressure * 0.55 + boost));
    const t = theme === "balloon" || theme === "rocket" ? theme : "swim";
    if (t === "swim" && mount && mount._swim3d && mount._swim3d.setProgress) {
      mount._swim3d.setProgress(pos);
      return;
    }
    const actor = mount && mount.querySelector("#survivalActor");
    if (!actor) return;
    if (t === "swim") {
      actor.style.left = `${8 + pos * 70}%`;
      actor.style.top = `${42 - boost * 10}%`;
    } else if (t === "balloon") {
      actor.style.bottom = `${12 + pos * 70}%`;
    } else {
      actor.style.bottom = `${10 + pos * 65}%`;
    }
  }

  function setSurvivalClock(mount, remaining, total) {
    const clock = mount && mount.querySelector("#survivalClock");
    if (!clock) return;
    clock.textContent = formatClock(remaining);
    clock.classList.remove("warn", "danger");
    if (total > 0 && remaining <= total * 0.15) clock.classList.add("danger");
    else if (total > 0 && remaining <= total * 0.35) clock.classList.add("warn");
  }

  function setSurvivalOutcome(mount, theme, outcome) {
    const t = theme === "balloon" || theme === "rocket" ? theme : "swim";
    const status = mount && mount.querySelector("#survivalStatus");
    if (t === "swim" && mount && mount._swim3d && mount._swim3d.setOutcome) {
      mount._swim3d.setOutcome(outcome === "win" ? "win" : outcome === "fail" ? "fail" : "playing");
      if (status) {
        if (outcome === "win") {
          status.className = "survival-status win";
          status.textContent = "You reached the shore!";
        } else if (outcome === "fail") {
          status.className = "survival-status fail";
          status.textContent = "Oh no — you drowned! Time's up.";
        } else {
          status.className = "survival-status";
          status.textContent = "Keep going — finish before time runs out!";
        }
      }
      return;
    }
    const actor = mount && mount.querySelector("#survivalActor");
    if (!actor) return;
    actor.classList.remove("drowning", "safe", "popped", "crashed", "orbit", "swimming");
    if (outcome === "win") {
      if (t === "swim") actor.classList.add("safe");
      else if (t === "balloon") actor.style.bottom = "78%";
      else actor.classList.add("orbit");
      if (status) {
        status.className = "survival-status win";
        status.textContent =
          t === "swim" ? "You reached the shore!" :
          t === "balloon" ? "You floated to safety!" :
          "Liftoff success!";
      }
    } else if (outcome === "fail") {
      if (t === "swim") actor.classList.add("drowning");
      else if (t === "balloon") actor.classList.add("popped");
      else actor.classList.add("crashed");
      if (status) {
        status.className = "survival-status fail";
        status.textContent =
          t === "swim" ? "Oh no — you drowned! Time's up." :
          t === "balloon" ? "Pop! The balloon burst — time's up." :
          "Crash landing — time's up.";
      }
    } else {
      if (t === "swim") actor.classList.add("swimming");
      if (status) {
        status.className = "survival-status";
        status.textContent = "Keep going — finish before time runs out!";
      }
    }
  }

  global.GameThemes = {
    updateRaceTheme,
    ensureRaceShell,
    ensureSurvivalShell,
    setSurvivalProgress,
    setSurvivalClock,
    setSurvivalOutcome,
    formatClock,
  };
})(typeof window !== "undefined" ? window : globalThis);
