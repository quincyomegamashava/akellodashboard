/**
 * Shared Quiz Galaxy in-game UX: ready state, Continue/New, pause/exit,
 * keyboard, explain, power-ups, SFX, rival gate, end-screen teaching.
 * Load after galaxy_shell_bridge.js
 */
(function () {
  "use strict";

  const MUTE_KEY = "galaxyMute";
  const state = {
    paused: false,
    questionShown: false,
    fiftyUsed: false,
    freezeUsed: false,
    freezeUntil: 0,
    missed: [],
    coaching: null,
    ready: false,
  };

  function muted() {
    return localStorage.getItem(MUTE_KEY) === "1";
  }

  function setMuted(v) {
    localStorage.setItem(MUTE_KEY, v ? "1" : "0");
    const btn = document.getElementById("galaxy-mute-btn");
    if (btn) btn.textContent = v ? "Unmute" : "Mute";
  }

  /** Tiny WebAudio beeps — no asset files required */
  function beep(freq, dur, type) {
    if (muted()) return;
    try {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) return;
      if (!window.__galaxyAudioCtx) window.__galaxyAudioCtx = new Ctx();
      const ctx = window.__galaxyAudioCtx;
      const o = ctx.createOscillator();
      const g = ctx.createGain();
      o.type = type || "sine";
      o.frequency.value = freq;
      g.gain.value = 0.04;
      o.connect(g);
      g.connect(ctx.destination);
      o.start();
      g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + dur);
      o.stop(ctx.currentTime + dur);
    } catch (_) { /* ignore */ }
  }

  const sfx = {
    correct() { beep(660, 0.12, "triangle"); setTimeout(() => beep(880, 0.1, "triangle"), 80); },
    wrong() { beep(220, 0.18, "sawtooth"); },
    tick() { beep(440, 0.04, "square"); },
    power() { beep(520, 0.08); setTimeout(() => beep(720, 0.1), 60); },
    click() { beep(380, 0.05); },
  };

  function injectStyles() {
    if (document.getElementById("galaxy-ux-css")) return;
    const css = document.createElement("style");
    css.id = "galaxy-ux-css";
    css.textContent = `
      #galaxy-ready-pill {
        display:inline-flex; align-items:center; gap:6px; margin:10px 0 4px;
        padding:6px 12px; border-radius:999px; font:800 0.78rem Nunito,sans-serif;
        background:#e2e8f0; color:#64748b;
      }
      #galaxy-ready-pill.ready { background:#dcfce7; color:#166534; }
      #galaxy-ready-pill.loading { background:#fef3c7; color:#92400e; }
      #galaxy-start-actions { display:flex; flex-direction:column; gap:8px; margin-top:10px; }
      #galaxy-start-actions .btn-secondary {
        font-family:inherit; font-weight:800; font-size:1rem; border:0; border-radius:14px;
        padding:12px 18px; cursor:pointer; background:#e2e8f0; color:#1a2744;
      }
      #galaxy-start-actions .btn-secondary:disabled { opacity:.5; cursor:not-allowed; }
      #galaxy-toolbar {
        position:fixed; top:10px; left:10px; z-index:60; display:flex; flex-wrap:wrap; gap:6px;
      }
      #galaxy-toolbar button, #galaxy-powerups button {
        font:800 0.72rem Nunito,sans-serif; border:0; border-radius:999px; padding:8px 12px;
        cursor:pointer; background:rgba(255,252,245,.94); color:#1a2744;
        box-shadow:0 3px 10px rgba(0,0,0,.15);
      }
      #galaxy-powerups { display:flex; gap:6px; margin-top:8px; justify-content:center; flex-wrap:wrap; }
      #galaxy-powerups button:disabled { opacity:.4; cursor:not-allowed; }
      #galaxy-diff-chip {
        display:inline-block; margin-left:6px; padding:3px 8px; border-radius:999px;
        font:800 0.68rem Nunito,sans-serif; background:#e0e7ff; color:#3730a3; text-transform:capitalize;
      }
      .question, #question {
        overflow-wrap:anywhere; word-break:break-word; max-width:100%; line-height:1.35;
      }
      .question .katex, #question .katex, #answers .katex, #galaxy-explain .katex {
        font-size: 1.05em; line-height: 1.2;
      }
      #answers .answer-btn .katex, #answers button .katex {
        font-size: 1.08em;
      }
      .answer-btn:focus-visible, #answers button:focus-visible {
        outline:3px solid #2563eb; outline-offset:2px;
      }
      #galaxy-explain {
        margin-top:8px; padding:8px 10px; border-radius:12px; background:#fff7ed; color:#9a3412;
        font:700 0.88rem Nunito,sans-serif; display:none;
      }
      #galaxy-explain.show { display:block; }
      #galaxy-pause-overlay {
        position:fixed; inset:0; z-index:80; display:none; align-items:center; justify-content:center;
        background:rgba(7,20,40,.72); padding:16px;
      }
      #galaxy-pause-overlay.open { display:flex; }
      #galaxy-pause-overlay .card {
        width:min(380px,100%); background:#fffdf8; color:#1a2744; border-radius:18px;
        padding:22px 20px; box-shadow:0 20px 50px rgba(0,0,0,.35); text-align:center;
      }
      #galaxy-pause-overlay h2 { font-family:'Baloo 2',cursive,sans-serif; margin-bottom:8px; }
      #galaxy-pause-overlay .row { display:flex; flex-direction:column; gap:8px; margin-top:14px; }
      #galaxy-pause-overlay button {
        font:800 0.95rem Nunito,sans-serif; border:0; border-radius:14px; padding:12px 16px; cursor:pointer;
      }
      #galaxy-pause-overlay .primary { background:#2f8f56; color:#fff; }
      #galaxy-pause-overlay .ghost { background:#e2e8f0; color:#1a2744; }
      #galaxy-end-extra { margin-top:12px; text-align:left; }
      #galaxy-end-extra .coach {
        background:#ecfdf5; color:#065f46; padding:10px 12px; border-radius:12px;
        font:700 0.9rem Nunito,sans-serif; margin-bottom:10px;
      }
      #galaxy-end-extra .missed-title { font:800 0.75rem Nunito,sans-serif; color:#64748b; text-transform:uppercase; letter-spacing:.04em; }
      #galaxy-end-extra ul { list-style:none; margin:6px 0 10px; padding:0; max-height:120px; overflow:auto; }
      #galaxy-end-extra li { font:700 0.82rem Nunito,sans-serif; padding:6px 0; border-bottom:1px solid #eef2f7; color:#334155; }
      #galaxy-end-extra .end-actions { display:flex; flex-direction:column; gap:8px; }
      #galaxy-end-extra a, #galaxy-end-extra button.linkish {
        display:block; text-align:center; text-decoration:none; font:800 0.9rem Nunito,sans-serif;
        padding:10px 14px; border-radius:12px; background:#e0e7ff; color:#312e81; border:0; cursor:pointer;
      }
      #galaxy-end-extra button.linkish.primary {
        background:linear-gradient(180deg,#34d399,#059669); color:#fff;
        box-shadow:0 4px 12px rgba(5,150,105,.28);
      }
      #galaxy-end-extra button.linkish.secondary {
        background:#fff; color:#1a2744; border:2px solid #cbd5e1;
      }
      #galaxy-end-extra .level-result {
        text-align:center; font:800 1.05rem 'Baloo 2',cursive,sans-serif; margin-bottom:8px;
      }
      #galaxy-end-extra .level-result.passed { color:#047857; }
      #galaxy-end-extra .level-result.failed { color:#b45309; }
      #galaxy-rival-wait {
        font:800 0.75rem Nunito,sans-serif; color:#92400e; background:#fef3c7;
        padding:4px 10px; border-radius:999px; display:none;
      }
      #galaxy-rival-wait.show { display:inline-block; }
      .galaxy-key-hint { font:700 0.72rem Nunito,sans-serif; color:#64748b; margin-top:6px; }
    `;
    document.head.appendChild(css);
  }

  function ensureExplainEl() {
    let el = document.getElementById("galaxy-explain");
    if (el) return el;
    const feedback = document.getElementById("feedback");
    el = document.createElement("div");
    el.id = "galaxy-explain";
    el.setAttribute("role", "status");
    el.setAttribute("aria-live", "polite");
    if (feedback && feedback.parentNode) feedback.parentNode.insertBefore(el, feedback.nextSibling);
    else {
      const panel = document.getElementById("quiz-panel");
      if (panel) panel.appendChild(el);
    }
    return el;
  }

  function enhanceStartCard() {
    const overlay = document.getElementById("start-overlay");
    const card = overlay && overlay.querySelector(".card");
    const startBtn = document.getElementById("start-btn");
    if (!card || !startBtn) return;

    let pill = document.getElementById("galaxy-ready-pill");
    if (!pill) {
      pill = document.createElement("div");
      pill.id = "galaxy-ready-pill";
      pill.className = "loading";
      pill.textContent = "Loading quizzes…";
      startBtn.parentNode.insertBefore(pill, startBtn);
    }

    let actions = document.getElementById("galaxy-start-actions");
    if (!actions) {
      actions = document.createElement("div");
      actions.id = "galaxy-start-actions";
      startBtn.parentNode.insertBefore(actions, startBtn);
      actions.appendChild(startBtn);
      const freshBtn = document.createElement("button");
      freshBtn.type = "button";
      freshBtn.className = "btn-secondary";
      freshBtn.id = "galaxy-fresh-btn";
      freshBtn.textContent = "Start fresh";
      freshBtn.disabled = true;
      freshBtn.addEventListener("click", async () => {
        sfx.click();
        freshBtn.disabled = true;
        startBtn.disabled = true;
        pill.className = "loading";
        pill.textContent = "Loading a new set…";
        window.GALAXY_RESUME = null;
        if (window.GalaxyShell && GalaxyShell.loadQuestions) {
          await GalaxyShell.loadQuestions({ fresh: true });
        }
        markReady(true);
        startBtn.click();
      });
      actions.appendChild(freshBtn);
    }

    if (!card.querySelector(".galaxy-key-hint")) {
      const hint = document.createElement("p");
      hint.className = "galaxy-key-hint muted";
      hint.textContent = "Tip: press 1–4 to answer · Esc to pause";
      card.appendChild(hint);
    }
  }

  function markReady(ready) {
    state.ready = !!ready;
    const pill = document.getElementById("galaxy-ready-pill");
    const startBtn = document.getElementById("start-btn");
    const freshBtn = document.getElementById("galaxy-fresh-btn");
    const meta = window.GALAXY_META || {};
    const count = (window.GALAXY_QUESTIONS || []).length;
    if (pill) {
      if (ready && count) {
        pill.className = "ready";
        pill.textContent = meta.resume
          ? `Ready · Continue saved run · ${count} questions`
          : `Ready · ${count} questions · Lv ${meta.level || 1} · ${meta.difficulty || "medium"}`;
      } else {
        pill.className = "loading";
        pill.textContent = "Loading quizzes…";
      }
    }
    if (startBtn) {
      const animalGate = document.getElementById("animal-picker") && !window.__galaxyAnimalPicked;
      startBtn.disabled = !ready || animalGate;
      if (meta.resume && ready) {
        if (!startBtn.getAttribute("data-label")) startBtn.setAttribute("data-label", startBtn.textContent);
        startBtn.textContent = "Continue";
      } else if (startBtn.getAttribute("data-label")) {
        startBtn.textContent = startBtn.getAttribute("data-label");
      }
    }
    if (freshBtn) freshBtn.disabled = !ready;
  }

  function injectToolbar() {
    if (document.getElementById("galaxy-toolbar")) return;
    const bar = document.createElement("div");
    bar.id = "galaxy-toolbar";
    bar.innerHTML = `
      <button type="button" id="galaxy-pause-btn" hidden>Pause</button>
      <button type="button" id="galaxy-mute-btn">${muted() ? "Unmute" : "Mute"}</button>
      <span id="galaxy-rival-wait">Rival waiting for Q1…</span>
    `;
    document.body.appendChild(bar);
    document.getElementById("galaxy-mute-btn").addEventListener("click", () => {
      setMuted(!muted());
      sfx.click();
    });
    document.getElementById("galaxy-pause-btn").addEventListener("click", () => togglePause(true));
  }

  function injectPauseOverlay() {
    if (document.getElementById("galaxy-pause-overlay")) return;
    const el = document.createElement("div");
    el.id = "galaxy-pause-overlay";
    el.innerHTML = `
      <div class="card" role="dialog" aria-modal="true" aria-labelledby="galaxy-pause-title">
        <h2 id="galaxy-pause-title">Paused</h2>
        <p>Your progress is saved. Rival scoring is frozen.</p>
        <div class="row">
          <button type="button" class="primary" id="galaxy-resume-btn">Resume</button>
          <button type="button" class="ghost" id="galaxy-exit-btn">Save & exit to Galaxy</button>
        </div>
      </div>`;
    document.body.appendChild(el);
    document.getElementById("galaxy-resume-btn").addEventListener("click", () => togglePause(false));
    document.getElementById("galaxy-exit-btn").addEventListener("click", async () => {
      try {
        if (window.GalaxyShell && GalaxyShell.checkpoint && window.__galaxyPlayState) {
          await GalaxyShell.checkpoint(window.__galaxyPlayState);
        }
      } catch (_) { /* ignore */ }
      window.location.href = "/quiz-galaxy";
    });
  }

  function injectPowerups() {
    const panel = document.getElementById("quiz-panel");
    if (!panel || document.getElementById("galaxy-powerups")) return;
    const wrap = document.createElement("div");
    wrap.id = "galaxy-powerups";
    wrap.innerHTML = `
      <button type="button" id="galaxy-fifty-btn" title="Remove two wrong answers">50/50</button>
      <button type="button" id="galaxy-freeze-btn" title="Freeze rival for 5 seconds">Freeze +5s</button>
    `;
    panel.appendChild(wrap);
    document.getElementById("galaxy-fifty-btn").addEventListener("click", useFiftyFifty);
    document.getElementById("galaxy-freeze-btn").addEventListener("click", useFreeze);
  }

  function injectDiffChip() {
    const hud = document.getElementById("hud");
    if (!hud || document.getElementById("galaxy-diff-chip")) return;
    const chip = document.createElement("span");
    chip.id = "galaxy-diff-chip";
    const meta = window.GALAXY_META || {};
    chip.textContent = `Lv ${meta.level || 1} · ${meta.difficulty || "medium"}`;
    hud.appendChild(chip);
  }

  function refreshDiffChip() {
    const chip = document.getElementById("galaxy-diff-chip");
    const meta = window.GALAXY_META || {};
    if (chip) chip.textContent = `Lv ${meta.level || 1} · ${meta.difficulty || "medium"}`;
  }

  function togglePause(force) {
    state.paused = typeof force === "boolean" ? force : !state.paused;
    const ov = document.getElementById("galaxy-pause-overlay");
    if (ov) ov.classList.toggle("open", state.paused);
    const btn = document.getElementById("galaxy-pause-btn");
    if (btn) btn.hidden = state.paused;
    if (state.paused) sfx.click();
  }

  function onRoundStart(playState) {
    window.__galaxyPlayState = playState;
    state.paused = false;
    state.questionShown = false;
    state.fiftyUsed = false;
    state.freezeUsed = false;
    state.freezeUntil = 0;
    state.missed = [];
    const pauseBtn = document.getElementById("galaxy-pause-btn");
    if (pauseBtn) pauseBtn.hidden = false;
    const fifty = document.getElementById("galaxy-fifty-btn");
    const freeze = document.getElementById("galaxy-freeze-btn");
    if (fifty) fifty.disabled = false;
    if (freeze) freeze.disabled = false;
    const wait = document.getElementById("galaxy-rival-wait");
    if (wait) wait.classList.add("show");
    refreshDiffChip();
    const ov = document.getElementById("galaxy-pause-overlay");
    if (ov) ov.classList.remove("open");
  }

  function typesetQuizMath() {
    if (!window.QuizMath || !window.QuizMath.typesetMath) return;
    const roots = [
      document.getElementById("question"),
      document.querySelector(".question"),
      document.getElementById("answers"),
      document.getElementById("galaxy-explain"),
    ];
    roots.forEach((el) => {
      if (el) window.QuizMath.typesetMath(el);
    });
  }

  function bootQuizMath() {
    function start() {
      if (!window.QuizMath) return;
      window.QuizMath.ensureAssets(function () {
        const watchRoots = [
          document.getElementById("question"),
          document.querySelector(".question"),
          document.getElementById("answers"),
          document.getElementById("galaxy-explain"),
        ].filter(Boolean);
        watchRoots.forEach((root) => window.QuizMath.watch(root));
        typesetQuizMath();
      });
    }
    if (window.QuizMath) {
      start();
      return;
    }
    if (document.getElementById("galaxy-quiz-math-js")) {
      const t = setInterval(function () {
        if (window.QuizMath) {
          clearInterval(t);
          start();
        }
      }, 50);
      return;
    }
    const s = document.createElement("script");
    s.id = "galaxy-quiz-math-js";
    s.src = "/static/js/quiz_math.js?v=3";
    s.async = true;
    s.onload = start;
    document.head.appendChild(s);
  }

  function onQuestionShown(current) {
    state.questionShown = true;
    const wait = document.getElementById("galaxy-rival-wait");
    if (wait) wait.classList.remove("show");
    const explain = ensureExplainEl();
    explain.classList.remove("show");
    explain.textContent = "";
    const qEl = document.getElementById("question");
    if (qEl) {
      qEl.setAttribute("tabindex", "-1");
      qEl.setAttribute("aria-live", "polite");
    }
    // Reset 50/50 visibility for new question
    document.querySelectorAll("#answers .answer-btn, #answers button").forEach((b) => {
      b.style.display = "";
      b.hidden = false;
    });
    // Convert <fra> / TeX in prompt + answers (shells set textContent first)
    requestAnimationFrame(function () {
      typesetQuizMath();
      setTimeout(typesetQuizMath, 80);
    });
    if (current && current.q) {
      // keep focus away from buttons until learner acts
    }
  }

  function afterAnswer({ correct, explain, prompt, choices, answerIndex }) {
    if (correct) sfx.correct();
    else {
      sfx.wrong();
      state.missed.push({
        prompt: prompt || "",
        choices: choices || [],
        answerIndex: answerIndex,
        explain: explain || "",
      });
      const el = ensureExplainEl();
      if (explain) {
        if (window.QuizMath && window.QuizMath.setMathText) {
          window.QuizMath.setMathText(el, "Why: " + explain);
        } else {
          el.textContent = "Why: " + explain;
        }
        el.classList.add("show");
        typesetQuizMath();
      } else {
        el.classList.remove("show");
      }
    }
    try {
      sessionStorage.setItem("galaxyMissedLast", JSON.stringify(state.missed.slice(-12)));
    } catch (_) { /* ignore */ }
  }

  function rivalMayScore() {
    if (state.paused) return false;
    if (!state.questionShown) return false;
    if (Date.now() < state.freezeUntil) return false;
    return true;
  }

  function timerMayTick() {
    return !state.paused;
  }

  function useFiftyFifty() {
    if (state.fiftyUsed || state.paused) return;
    const buttons = [...document.querySelectorAll("#answers .answer-btn, #answers button")];
    if (buttons.length < 3) return;
    const play = window.__galaxyPlayState;
    const current = play && play.current;
    const correct = current ? current.answer : 0;
    const wrongIdx = buttons.map((_, i) => i).filter((i) => i !== correct);
    // hide two wrong
    wrongIdx.sort(() => Math.random() - 0.5).slice(0, 2).forEach((i) => {
      if (buttons[i]) {
        buttons[i].style.display = "none";
        buttons[i].hidden = true;
      }
    });
    state.fiftyUsed = true;
    const btn = document.getElementById("galaxy-fifty-btn");
    if (btn) btn.disabled = true;
    sfx.power();
  }

  function useFreeze() {
    if (state.freezeUsed || state.paused) return;
    state.freezeUsed = true;
    state.freezeUntil = Date.now() + 5000;
    const btn = document.getElementById("galaxy-freeze-btn");
    if (btn) btn.disabled = true;
    const wait = document.getElementById("galaxy-rival-wait");
    if (wait) {
      wait.textContent = "Rival frozen 5s…";
      wait.classList.add("show");
      setTimeout(() => {
        if (Date.now() >= state.freezeUntil) {
          wait.classList.remove("show");
          wait.textContent = "Rival waiting for Q1…";
        }
      }, 5100);
    }
    sfx.power();
  }

  function hideEndShowStart() {
    document.getElementById("end-overlay")?.classList.add("hidden");
    const gameover = document.getElementById("gameover-panel");
    if (gameover) gameover.style.display = "none";
    const startOverlay = document.getElementById("start-overlay");
    if (startOverlay) startOverlay.classList.remove("hidden");
    const overlay = document.getElementById("overlay");
    const startPanel = document.getElementById("start-panel");
    if (overlay) overlay.classList.remove("hidden");
    if (startPanel) startPanel.style.display = "block";
  }

  function triggerRoundStart() {
    const start = document.getElementById("start-btn");
    markReady(true);
    if (start) {
      start.disabled = false;
      start.click();
      return true;
    }
    try { document.dispatchEvent(new CustomEvent("galaxy-force-start")); } catch (_) { /* ignore */ }
    return false;
  }

  function escapeHtml(s) {
    return String(s || "").replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );
  }

  async function startLevelRun(opts) {
    const level = (opts && opts.level) || null;
    const label = (opts && opts.label) || (level ? ("level " + level) : "round");
    window.GALAXY_RESUME = null;
    sessionStorage.removeItem("galaxyReviewPack");
    if (window.GalaxyShell && GalaxyShell.loadQuestions) {
      const loadOpts = { fresh: true };
      if (level) loadOpts.level = level;
      await GalaxyShell.loadQuestions(loadOpts);
    }
    if (window.__galaxyPlayState && window.GalaxyShell && GalaxyShell.resetDealState) {
      GalaxyShell.resetDealState(window.__galaxyPlayState);
    }
    hideEndShowStart();
    const start = document.getElementById("start-btn");
    if (start) start.textContent = "Start " + label;
    markReady(true);
    refreshDiffChip();
    setTimeout(() => triggerRoundStart(), 40);
  }

  function enhanceEndScreen(payload) {
    const endCard =
      document.querySelector("#end-overlay .card") ||
      document.querySelector("#gameover-panel .card") ||
      document.querySelector("#gameover-panel") ||
      document.querySelector("#end-overlay");
    if (!endCard) return;
    let extra = document.getElementById("galaxy-end-extra");
    if (!extra) {
      extra = document.createElement("div");
      extra.id = "galaxy-end-extra";
      const replay = document.getElementById("replay-btn") || document.getElementById("retry-btn");
      if (replay && replay.parentNode) replay.parentNode.insertBefore(extra, replay);
      else endCard.appendChild(extra);
    }

    const progress = (payload && payload.progress) || window.__galaxyLastProgress || {};
    const meta = window.GALAXY_META || {};
    const coach = (payload && payload.coaching) || state.coaching || progress.coaching_blurb || meta.coaching || "";
    const missed = (payload && payload.missed) || state.missed || [];

    const nextLevel = Number(
      progress.next_level != null ? progress.next_level
        : (progress.level != null ? progress.level
          : (meta.next_level != null ? meta.next_level : meta.level))
    ) || 1;
    let playedLevel = Number(
      progress.played_level != null ? progress.played_level : meta.played_level
    );
    if (!playedLevel || playedLevel < 1) {
      playedLevel = nextLevel;
    }
    const passed = progress.passed === true || meta.passed === true || nextLevel > playedLevel;
    if (passed && playedLevel >= nextLevel) {
      playedLevel = Math.max(1, nextLevel - 1);
    }
    const difficulty = progress.difficulty || meta.difficulty || "medium";

    // Candy Crush: hide native replay if present — we provide clearer CTAs
    const nativeReplay = document.getElementById("replay-btn") || document.getElementById("retry-btn");
    if (nativeReplay) {
      nativeReplay.style.display = "none";
    }

    const resultTitle = passed
      ? ("Level " + playedLevel + " cleared!")
      : ("Keep practising Level " + playedLevel);
    const resultClass = passed ? "passed" : "failed";

    extra.innerHTML = `
      <div class="level-result ${resultClass}">${escapeHtml(resultTitle)}</div>
      <div class="coach">${escapeHtml(difficulty)}${coach ? " — " + escapeHtml(coach) : ""}</div>
      ${missed.length ? `<div class="missed-title">Review misses</div><ul>${missed.slice(0, 5).map((m) =>
        `<li>${escapeHtml((m.prompt || "").slice(0, 120))}${m.explain ? " — " + escapeHtml(m.explain) : ""}</li>`
      ).join("")}</ul>` : ""}
      <div class="end-actions">
        ${passed
          ? `<button type="button" class="linkish primary" id="galaxy-next-level-btn">Play next level (${nextLevel})</button>
             <button type="button" class="linkish secondary" id="galaxy-replay-level-btn">Play Level ${playedLevel} again</button>`
          : `<button type="button" class="linkish primary" id="galaxy-replay-level-btn">Play Level ${playedLevel} again</button>`}
        <button type="button" class="linkish" id="galaxy-review-btn" ${missed.length ? "" : "disabled"}>Practice ${Math.min(5, missed.length || 0)} you missed</button>
        <a href="/quiz-galaxy">Back to Quiz Galaxy</a>
      </div>
    `;
    if (window.QuizMath && window.QuizMath.typesetMath) {
      window.QuizMath.typesetMath(extra);
    }
    refreshDiffChip();

    const reviewBtn = document.getElementById("galaxy-review-btn");
    if (reviewBtn) {
      reviewBtn.onclick = () => {
        if (!missed.length) return;
        try {
          const pack = missed.slice(0, 8).map((m) => ({
            prompt: m.prompt,
            options: m.choices && m.choices.length ? m.choices : ["Try again", "Skip", "Ask a teacher", "Review notes"],
            correctIndex: typeof m.answerIndex === "number" ? m.answerIndex : 0,
            explain: m.explain || "Review this one carefully.",
            source: "review",
            id: "review-" + Math.random().toString(36).slice(2, 8),
          }));
          sessionStorage.setItem("galaxyReviewPack", JSON.stringify(pack));
          if (window.GalaxyShell && GalaxyShell.setQuestions) GalaxyShell.setQuestions(pack);
          else window.GALAXY_QUESTIONS = pack;
          window.GALAXY_RESUME = null;
          if (window.__galaxyPlayState && window.GalaxyShell && GalaxyShell.resetDealState) {
            GalaxyShell.resetDealState(window.__galaxyPlayState);
          }
          hideEndShowStart();
          const start = document.getElementById("start-btn");
          if (start) start.textContent = "Start review";
          markReady(true);
          setTimeout(() => triggerRoundStart(), 30);
        } catch (err) { console.warn("review start failed", err); }
      };
    }

    const nextBtn = document.getElementById("galaxy-next-level-btn");
    if (nextBtn) {
      nextBtn.onclick = async () => {
        nextBtn.disabled = true;
        nextBtn.textContent = "Loading level " + nextLevel + "…";
        try {
          await startLevelRun({ level: nextLevel, label: "level " + nextLevel });
        } catch (err) {
          console.warn("next level failed", err);
          nextBtn.disabled = false;
          nextBtn.textContent = "Play next level (" + nextLevel + ")";
        }
      };
    }

    const replayBtn = document.getElementById("galaxy-replay-level-btn");
    if (replayBtn) {
      replayBtn.onclick = async () => {
        replayBtn.disabled = true;
        replayBtn.textContent = "Loading Level " + playedLevel + "…";
        try {
          await startLevelRun({ level: playedLevel, label: "level " + playedLevel });
        } catch (err) {
          console.warn("replay level failed", err);
          replayBtn.disabled = false;
          replayBtn.textContent = "Play Level " + playedLevel + " again";
        }
      };
    }
  }

  function bindKeyboard() {
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        const playing = window.__galaxyPlayState && window.__galaxyPlayState.playing;
        if (playing) {
          e.preventDefault();
          togglePause(!state.paused);
        }
        return;
      }
      if (state.paused) return;
      const playing = window.__galaxyPlayState && window.__galaxyPlayState.playing;
      if (!playing || window.__galaxyPlayState.locked) return;
      const map = { "1": 0, "2": 1, "3": 2, "4": 3 };
      if (e.key in map) {
        const buttons = [...document.querySelectorAll("#answers .answer-btn:not([hidden]), #answers button:not([hidden])")]
          .filter((b) => b.style.display !== "none" && !b.disabled);
        // Map physical 1-4 to visible buttons by original index when possible
        const all = [...document.querySelectorAll("#answers .answer-btn, #answers button")];
        const target = all[map[e.key]];
        if (target && !target.disabled && target.style.display !== "none" && !target.hidden) {
          e.preventDefault();
          target.click();
        } else if (buttons[map[e.key]]) {
          e.preventDefault();
          buttons[map[e.key]].click();
        }
      }
    });
  }

  // Hook GalaxyShell start enable
  function patchBridge() {
    document.addEventListener("galaxy-questions-ready", (ev) => {
      markReady((ev.detail && ev.detail.count) > 0 || (window.GALAXY_QUESTIONS || []).length > 0);
      refreshDiffChip();
    });
  }

  function init() {
    injectStyles();
    enhanceStartCard();
    injectToolbar();
    injectPauseOverlay();
    injectPowerups();
    injectDiffChip();
    ensureExplainEl();
    bindKeyboard();
    patchBridge();
    bootQuizMath();
    document.addEventListener("galaxy-progress-updated", () => refreshDiffChip());
    markReady((window.GALAXY_QUESTIONS || []).length > 0);
  }

  window.GalaxyUX = {
    init,
    markReady,
    onRoundStart,
    onQuestionShown,
    afterAnswer,
    rivalMayScore,
    timerMayTick,
    isPaused: () => state.paused,
    togglePause,
    enhanceEndScreen,
    setCoaching(text) { state.coaching = text; },
    getMissed: () => state.missed.slice(),
    typesetQuizMath,
    sfx,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
