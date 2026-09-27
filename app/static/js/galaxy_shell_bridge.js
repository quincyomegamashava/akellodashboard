/**
 * Bridge: load GK + AI questions into galaxy shells, checkpoint progress, submit scores.
 * Expects window.GALAXY = { shell, subject, userId } from parent iframe or URL query.
 */
(function () {
  "use strict";

  const LOCAL_FALLBACK = [
    { prompt: "What helps you learn best?", options: ["Practise a little every day", "Never try", "Skip reading", "Guess forever"], correctIndex: 0, explain: "Practice wins!", source: "fallback" },
    { prompt: "If an answer is wrong, you should…", options: ["Learn and try the next one", "Quit immediately", "Close your eyes", "Delete the quiz"], correctIndex: 0, explain: "Keep going!", source: "fallback" },
    { prompt: "True or false: practice helps you improve.", options: ["True", "False", "Never", "Only on Mondays"], correctIndex: 0, explain: "True!", source: "fallback" },
    { prompt: "Multiple-choice questions have…", options: ["Several options and one best answer", "No options", "Only pictures", "Only music"], correctIndex: 0, explain: "Pick the best option.", source: "fallback" },
    { prompt: "When the timer is running, you should…", options: ["Stay calm and think", "Panic and freeze", "Leave the page", "Ignore the question"], correctIndex: 0, explain: "Stay calm.", source: "fallback" },
    { prompt: "A streak means…", options: ["Several correct answers in a row", "You lost", "The game crashed", "Time stopped"], correctIndex: 0, explain: "Keep the streak!", source: "fallback" },
    { prompt: "Reading the question carefully helps you…", options: ["Pick a better answer", "Waste time only", "Skip learning", "Lose points always"], correctIndex: 0, explain: "Read first.", source: "fallback" },
    { prompt: "After a quiz round you can…", options: ["Try again and improve", "Never play again", "Forget everything", "Break the timer"], correctIndex: 0, explain: "Rematch!", source: "fallback" },
    { prompt: "Which is a healthy study habit?", options: ["Short focused practice", "No sleep before tests", "Never review mistakes", "Only copy friends"], correctIndex: 0, explain: "Focus helps.", source: "fallback" },
    { prompt: "In Quiz Galaxy, correct answers…", options: ["Help you progress", "Delete your account", "Stop the sun", "Turn off sound forever"], correctIndex: 0, explain: "Progress!", source: "fallback" },
    { prompt: "The best time to answer is…", options: ["When you understand the question", "Without reading", "After the timer ends", "Never"], correctIndex: 0, explain: "Understand first.", source: "fallback" },
    { prompt: "Teamwork in learning means…", options: ["Helping each other improve", "Giving up together", "Hiding answers always", "Ignoring friends"], correctIndex: 0, explain: "Help each other.", source: "fallback" },
  ];

  let questionsReady = false;
  let loadPromise = null;

  function readQueryConfig() {
    try {
      const q = new URLSearchParams(window.location.search || "");
      const userId = q.get("user_id");
      const shell = q.get("shell");
      if (!userId || !shell) return null;
      return {
        userId: Number(userId),
        shell,
        subject: q.get("subject") || "",
        shellGameId: q.get("shell_game_id") ? Number(q.get("shell_game_id")) : null,
      };
    } catch (_) {
      return null;
    }
  }

  function cfg() {
    if (window.GALAXY && window.GALAXY.userId && window.GALAXY.shell) return window.GALAXY;
    try {
      if (window.parent && window.parent !== window && window.parent.GALAXY && window.parent.GALAXY.userId) {
        window.GALAXY = window.parent.GALAXY;
        return window.GALAXY;
      }
    } catch (_) { /* cross-origin */ }
    const fromQuery = readQueryConfig();
    if (fromQuery) {
      window.GALAXY = Object.assign({}, window.GALAXY || {}, fromQuery);
      return window.GALAXY;
    }
    return window.GALAXY || {};
  }

  function shuffleChoices(choices, answerIdx) {
    const n = choices.length;
    const order = [];
    for (let i = 0; i < n; i++) order.push(i);
    for (let i = n - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      const tmp = order[i];
      order[i] = order[j];
      order[j] = tmp;
    }
    let ans = typeof answerIdx === "number" ? answerIdx : 0;
    if (ans < 0 || ans >= n) ans = 0;
    return {
      choices: order.map((i) => choices[i]),
      answer: order.indexOf(ans),
    };
  }

  function toShellQuestion(q, opts) {
    if (!q || typeof q !== "object") return null;
    let choices = q.options || q.choices || [];
    if (typeof choices === "string") {
      try { choices = JSON.parse(choices); } catch (_) { choices = String(choices).split("|"); }
    }
    if (!Array.isArray(choices)) choices = [];
    choices = choices.map((c) => String(c)).filter(Boolean);
    const prompt = String(q.prompt || q.q || "").trim();
    if (!prompt || choices.length < 2) return null;
    let answer = 0;
    if (typeof q.correctIndex === "number") answer = q.correctIndex;
    else if (typeof q.answer === "number") answer = q.answer;
    if (answer < 0 || answer >= choices.length) answer = 0;
    // Shuffle client fallbacks; server packs already shuffled
    if (opts && opts.shuffle) {
      const shuffled = shuffleChoices(choices, answer);
      choices = shuffled.choices;
      answer = shuffled.answer;
    }
    return {
      q: prompt,
      choices: choices,
      answer: answer,
      explain: q.explain || "",
      prompt: prompt,
      options: choices,
      correctIndex: answer,
      id: q.id,
      source: q.source || "",
    };
  }

  function setQuestions(rawList, opts) {
    const seen = new Set();
    const qs = [];
    (rawList || []).forEach((raw) => {
      const q = toShellQuestion(raw, opts);
      if (!q) return;
      const key = questionKey(q);
      if (!key || seen.has(key)) return;
      seen.add(key);
      qs.push(q);
    });
    window.GALAXY_QUESTIONS = qs;
    questionsReady = qs.length > 0;
    return qs;
  }

  function questionKey(q) {
    if (!q || typeof q !== "object") return "";
    if (q.id != null && String(q.id).trim()) return "id:" + String(q.id).trim();
    const p = String(q.q || q.prompt || "").toLowerCase().replace(/\s+/g, " ").trim();
    return p ? "p:" + p.slice(0, 180) : "";
  }

  function shuffleInPlace(arr) {
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      const t = arr[i];
      arr[i] = arr[j];
      arr[j] = t;
    }
    return arr;
  }

  /**
   * Deal the next unique question for this round.
   * Does not reshuffle already-seen prompts within the same playState.
   * Returns null when every bank question has been asked once this round.
   */
  function takeNextQuestion(playState) {
    if (!playState || typeof playState !== "object") return null;
    if (!(playState.seenKeys instanceof Set)) {
      playState.seenKeys = new Set(Array.isArray(playState.seenKeys) ? playState.seenKeys : []);
    }
    const refill = () => {
      const unused = quizBank().filter((q) => {
        const k = questionKey(q);
        return k && !playState.seenKeys.has(k);
      });
      playState.deck = shuffleInPlace(unused.slice());
    };
    if (!Array.isArray(playState.deck) || playState.deck.length === 0) refill();
    while (playState.deck.length) {
      const q = playState.deck.pop();
      const k = questionKey(q);
      if (!k || playState.seenKeys.has(k)) continue;
      playState.seenKeys.add(k);
      return q;
    }
    return null;
  }

  function resetDealState(playState) {
    if (!playState || typeof playState !== "object") return playState;
    playState.seenKeys = new Set();
    playState.deck = [];
    return playState;
  }

  function quizBank() {
    return Array.isArray(window.GALAXY_QUESTIONS) ? window.GALAXY_QUESTIONS : [];
  }

  function setStartEnabled(enabled, label) {
    document.querySelectorAll("#start-btn, .start-btn, [data-galaxy-start]").forEach((btn) => {
      // Animal race: keep disabled until both questions AND animal are ready
      if (enabled && document.getElementById("animal-picker") && !window.__galaxyAnimalPicked) {
        btn.disabled = true;
      } else {
        btn.disabled = !enabled;
      }
      if (label && btn.id === "start-btn") {
        if (!btn.getAttribute("data-label")) btn.setAttribute("data-label", btn.textContent);
        btn.textContent = label;
      }
    });
  }

  async function loadQuestions(opts) {
    const g = cfg();
    if (!g.userId || !g.shell) {
      console.warn("GALAXY config missing userId/shell", g);
      return setQuestions(LOCAL_FALLBACK, { shuffle: true });
    }
    const params = new URLSearchParams({
      user_id: String(g.userId),
      shell: g.shell,
      subject: g.subject || "",
      limit: "24",
    });
    if (opts && opts.fresh) params.set("fresh", "1");
    if (opts && opts.level) params.set("level", String(opts.level));
    try {
      const r = await fetch("/api/galaxy/questions?" + params.toString(), { credentials: "same-origin" });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || "Failed to load questions");
      let qs = setQuestions(data.questions || []);
      window.GALAXY_META = {
        level: data.level,
        difficulty: data.difficulty,
        subject: data.subject,
        resume: !!data.resume,
        sources: data.sources || {},
      };
      window.GALAXY_RESUME = data.resume ? (data.session || null) : null;
      if (!qs.length) qs = setQuestions(LOCAL_FALLBACK, { shuffle: true });
      return qs;
    } catch (err) {
      console.error("loadQuestions failed", err);
      window.GALAXY_META = { level: 1, difficulty: "medium", subject: g.subject || "", resume: false, sources: { fallback_used: true } };
      window.GALAXY_RESUME = null;
      return setQuestions(LOCAL_FALLBACK, { shuffle: true });
    }
  }

  function ensureQuestions() {
    if (quizBank().length) return Promise.resolve(quizBank());
    if (loadPromise) return loadPromise;
    loadPromise = loadQuestions({ fresh: true }).finally(() => { loadPromise = null; });
    return loadPromise;
  }

  async function checkpoint(state) {
    const g = cfg();
    if (!g.userId || !g.shell || !state) return null;
    const body = {
      user_id: Number(g.userId),
      shell: g.shell,
      subject: g.subject || "",
      asked: state.asked || 0,
      playerCorrect: state.playerCorrect || 0,
      rivalCorrect: state.rivalCorrect || 0,
      playerStep: state.playerStep || state.playerSnowballs || state.playerPopped || 0,
      rivalStep: state.rivalStep || state.rivalSnowballs || state.rivalPopped || 0,
      streak: state.streak || 0,
      secondsLeft: state.secondsLeft,
      deck: Array.isArray(state.deck)
        ? state.deck.map((q) => toShellQuestion(q)).filter(Boolean).map((q) => ({
            id: q.id,
            prompt: q.q,
            options: q.choices,
            correctIndex: q.answer,
            explain: q.explain || "",
            source: q.source || "",
          }))
        : [],
      questions: quizBank().map((q) => ({
        id: q.id,
        prompt: q.q || q.prompt,
        options: q.choices || q.options,
        correctIndex: typeof q.answer === "number" ? q.answer : q.correctIndex,
        explain: q.explain || "",
        source: q.source || "",
      })),
    };
    try {
      const r = await fetch("/api/galaxy/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        credentials: "same-origin",
      });
      return await r.json();
    } catch (err) {
      console.warn("galaxy checkpoint failed", err);
      return null;
    }
  }

  async function submitRound(score, maxScore) {
    const g = cfg();
    const r = await fetch("/api/galaxy/complete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: Number(g.userId),
        shell: g.shell,
        subject: g.subject || "",
        score: Number(score),
        max_score: Number(maxScore),
      }),
      credentials: "same-origin",
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || "Score submit failed");
    window.GALAXY_RESUME = null;
    if (data && data.progress) {
      window.__galaxyLastProgress = Object.assign({}, data.progress, {
        passed: data.passed,
        played_level: data.played_level,
        next_level: data.next_level,
      });
      window.GALAXY_META = Object.assign({}, window.GALAXY_META || {}, {
        level: data.progress.level,
        difficulty: data.progress.difficulty,
        coaching: data.progress.coaching_blurb,
        passed: data.passed,
        played_level: data.played_level,
        next_level: data.next_level,
      });
      try {
        document.dispatchEvent(new CustomEvent("galaxy-progress-updated", { detail: window.__galaxyLastProgress }));
      } catch (_) { /* ignore */ }
    }
    return data;
  }

  window.GalaxyShell = {
    loadQuestions,
    ensureQuestions,
    submitRound,
    checkpoint,
    quizBank,
    cfg,
    setQuestions,
    setStartEnabled,
    takeNextQuestion,
    resetDealState,
    questionKey,
    isReady: function () { return quizBank().length > 0; },
  };

  // Animal picker must not unlock Start until questions are ready
  document.addEventListener("click", (e) => {
    const animalBtn = e.target.closest && e.target.closest(".animal-btn");
    if (!animalBtn) return;
    window.__galaxyAnimalPicked = true;
    if (questionsReady || quizBank().length) {
      const start = document.getElementById("start-btn");
      if (start) start.disabled = false;
    }
  }, true);

  // Block Start if bank empty; load then re-click
  document.addEventListener("click", async (e) => {
    const btn = e.target.closest && e.target.closest("#start-btn, .start-btn, [data-galaxy-start]");
    if (!btn) return;
    if (quizBank().length) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    const status = document.getElementById("galaxyLoadStatus");
    if (status) status.textContent = "Loading questions…";
    btn.disabled = true;
    const qs = await ensureQuestions();
    if (!qs.length) setQuestions(LOCAL_FALLBACK, { shuffle: true });
    btn.disabled = false;
    if (status) status.textContent = quizBank().length + " questions ready";
    // Fire a fresh click now that bank is ready
    btn.click();
  }, true);

  document.addEventListener("DOMContentLoaded", async () => {
    setStartEnabled(false);
    const status = document.getElementById("galaxyLoadStatus");
    try {
      if (status) status.textContent = "Loading your quizzes…";
      cfg();
      const qs = await ensureQuestions();
      const meta = window.GALAXY_META || {};
      const src = meta.sources || {};
      if (status) {
        const bits = [
          "Level " + (meta.level || 1),
          meta.difficulty || "medium",
          qs.length + " questions ready",
        ];
        if (src.general_knowledge_count) bits.push(src.general_knowledge_count + " GK");
        if (src.ai_count) bits.push(src.ai_count + " AI");
        if (src.fallback_used || qs.some((q) => q.source === "fallback")) bits.push("practice set");
        if (meta.resume) bits.push("continue saved run");
        status.textContent = bits.join(" · ");
      }
      const label = meta.resume ? "Continue" : null;
      setStartEnabled(qs.length > 0, label);
      if (window.GalaxyUX && GalaxyUX.markReady) GalaxyUX.markReady(qs.length > 0);
      document.dispatchEvent(new CustomEvent("galaxy-questions-ready", {
        detail: { count: qs.length, resume: !!meta.resume },
      }));
    } catch (err) {
      console.error(err);
      setQuestions(LOCAL_FALLBACK, { shuffle: true });
      if (status) status.textContent = "Using practice questions · " + quizBank().length + " ready";
      setStartEnabled(true);
      if (window.GalaxyUX && GalaxyUX.markReady) GalaxyUX.markReady(true);
    }
  });
})();
