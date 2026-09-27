(function (global) {
  var DELIMS = [
    { left: '$$', right: '$$', display: true },
    { left: '\\[', right: '\\]', display: true },
    { left: '$', right: '$', display: false },
    { left: '\\(', right: '\\)', display: false }
  ];

  function escapeTex(s) {
    return String(s || '').replace(/[\\{}$&#^_~]/g, '');
  }

  /** Fix UTF-8 text that was mis-decoded as Windows-1252 / Latin-1 (e.g. â€" Ã—). */
  function fixTextEncoding(text) {
    var t = String(text || '');
    if (!t) return t;
    if (t.indexOf('\u00c3') < 0 && t.indexOf('\u00e2') < 0 && t.indexOf('\u00c2') < 0) return t;

    // Prefer round-trip when bytes are recoverable (handles â€" / Ã— etc.)
    try {
      if (typeof TextEncoder !== 'undefined' && typeof TextDecoder !== 'undefined') {
        var bytes = new Uint8Array(t.length);
        var ok = true;
        for (var i = 0; i < t.length; i++) {
          var c = t.charCodeAt(i);
          // Map common CP1252 extras back to bytes
          if (c === 0x20ac) c = 0x80;      // €
          else if (c === 0x201a) c = 0x82; // ‚
          else if (c === 0x0192) c = 0x83; // ƒ
          else if (c === 0x201e) c = 0x84; // „
          else if (c === 0x2026) c = 0x85; // …
          else if (c === 0x2020) c = 0x86; // †
          else if (c === 0x2021) c = 0x87; // ‡
          else if (c === 0x02c6) c = 0x88; // ˆ
          else if (c === 0x2030) c = 0x89; // ‰
          else if (c === 0x0160) c = 0x8a; // Š
          else if (c === 0x2039) c = 0x8b; // ‹
          else if (c === 0x0152) c = 0x8c; // Œ
          else if (c === 0x017d) c = 0x8e; // Ž
          else if (c === 0x2018) c = 0x91; // ‘
          else if (c === 0x2019) c = 0x92; // ’
          else if (c === 0x201c) c = 0x93; // “
          else if (c === 0x201d) c = 0x94; // ”
          else if (c === 0x2022) c = 0x95; // •
          else if (c === 0x2013) c = 0x96; // –
          else if (c === 0x2014) c = 0x97; // —
          else if (c === 0x02dc) c = 0x98; // ˜
          else if (c === 0x2122) c = 0x99; // ™
          else if (c === 0x0161) c = 0x9a; // š
          else if (c === 0x203a) c = 0x9b; // ›
          else if (c === 0x0153) c = 0x9c; // œ
          else if (c === 0x017e) c = 0x9e; // ž
          else if (c === 0x0178) c = 0x9f; // Ÿ
          if (c > 255) { ok = false; break; }
          bytes[i] = c;
        }
        if (ok) {
          var decoded = new TextDecoder('utf-8', { fatal: true }).decode(bytes);
          if (decoded && decoded.indexOf('\ufffd') < 0) t = decoded;
        }
      }
    } catch (_) { /* keep t */ }

    // Explicit fallbacks for common math / punctuation mojibake
    var pairs = [
      ['â€"', '\u2013'], ['â€“', '\u2013'], ['â€”', '\u2014'], ['âˆ’', '\u2212'],
      ['Ã—', '\u00d7'], ['Ã·', '\u00f7'], ['Â±', '\u00b1'],
      ['â€™', "'"], ['â€˜', "'"], ['â€œ', '"'], ['â€', '"'],
      ['â€¦', '\u2026'], ['Â°', '\u00b0'], ['Â ', ' '],
    ];
    for (var p = 0; p < pairs.length; p++) {
      if (t.indexOf(pairs[p][0]) >= 0) t = t.split(pairs[p][0]).join(pairs[p][1]);
    }
    // Stray Â before punctuation/symbols
    t = t.replace(/\u00c2(?=[\u00a0-\u00ff])/g, '');
    return t;
  }

  function fraToTex(inner) {
    var raw = String(inner || '').trim();
    if (!raw) return '';
    // mixed number: 2 1/8
    var mixed = raw.match(/^(-?\d+)\s+(\d+)\s*\/\s*(\d+)$/);
    if (mixed) {
      return escapeTex(mixed[1]) + '\\,\\frac{' + escapeTex(mixed[2]) + '}{' + escapeTex(mixed[3]) + '}';
    }
    // simple fraction: 1/8 or -3/4
    var simple = raw.match(/^(-?\d+)\s*\/\s*(-?\d+)$/);
    if (simple) {
      return '\\frac{' + escapeTex(simple[1]) + '}{' + escapeTex(simple[2]) + '}';
    }
    // already tex-ish
    if (raw.indexOf('\\') >= 0) return raw;
    return escapeTex(raw);
  }

  function prepareMathText(text) {
    var t = fixTextEncoding(String(text || ''));
    if (!t) return t;

    // Normalize fancy dashes
    t = t.replace(/[\u2013\u2014\u2212]/g, '-');

    // Equation-like prompts: 7 - (5 × 1) + 1 = _
    var looksLikeEq = /[=_]/.test(t) && /\d/.test(t) && /[\u00d7\u00f7+\-*\/()]/.test(t)
      && t.length < 120 && (t.match(/[A-Za-z]/g) || []).length < 12;
    if (looksLikeEq && t.indexOf('$') < 0) {
      var eq = t
        .replace(/\u00d7/g, '\\times')
        .replace(/\u00f7/g, '\\div')
        .replace(/_/g, '\\_');
      t = '$' + eq + '$';
    }

    // Unescape common entity forms of <fra>
    t = t.replace(/&lt;\s*\/?\s*fra\s*&gt;/gi, function (m) {
      return m.toLowerCase().indexOf('/') >= 0 ? '</fra>' : '<fra>';
    });

    // Custom bank markup: <fra>1/8</fra> or <fra>2 1/8</fra>
    t = t.replace(/<\s*fra\s*>\s*([^<]*?)\s*<\s*\/\s*fra\s*>/gi, function (_, inner) {
      var tex = fraToTex(inner);
      return tex ? ('$' + tex + '$') : '';
    });

    // Bare leftover opening tags (broken markup)
    t = t.replace(/<\s*\/?\s*fra\s*>/gi, '');

    // Bare mixed numbers in prose: 2 1/8
    t = t.replace(/(^|[^\d$\\])(-?\d+)\s+(\d+)\s*\/\s*(\d+)(?!\d)/g, function (_, pre, w, n, d) {
      return pre + '$' + escapeTex(w) + '\\,\\frac{' + escapeTex(n) + '}{' + escapeTex(d) + '}$';
    });

    if (t.indexOf('$') >= 0 || t.indexOf('\\(') >= 0 || t.indexOf('\\[') >= 0) return t;
    t = t.replace(/\\frac\s*\{[^{}]*\}\s*\{[^{}]*\}/g, function (m) { return '$' + m + '$'; });
    t = t.replace(/\\sqrt\s*(?:\[[^\]]*\])?\s*\{[^{}]*\}/g, function (m) { return '$' + m + '$'; });
    t = t.replace(/\\(?:times|div|pm|cdot|leq|geq|neq|pi)\b/g, function (m) { return '$' + m + '$'; });
    return t;
  }

  function prepareMathInTree(root) {
    if (!root) return;
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
    var nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(function (node) {
      if (!node.nodeValue || !node.parentElement) return;
      var tag = node.parentElement.tagName;
      if (/^(SCRIPT|STYLE|TEXTAREA|CODE|PRE)$/.test(tag)) return;
      if (node.parentElement.closest && node.parentElement.closest('.katex')) return;
      var next = prepareMathText(node.nodeValue);
      if (next !== node.nodeValue) node.nodeValue = next;
    });
  }

  function typesetMath(root) {
    if (!global.renderMathInElement) return;
    var el = root || document.body;
    prepareMathInTree(el);
    global.renderMathInElement(el, {
      delimiters: DELIMS,
      throwOnError: false,
      ignoredTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code']
    });
  }

  /** Set element text and render math (safe for prompts / answer buttons). */
  function setMathText(el, text) {
    if (!el) return;
    el.textContent = prepareMathText(text);
    whenReady(function () { typesetMath(el); });
  }

  function whenReady(cb) {
    if (global.renderMathInElement) { cb(); return; }
    var n = 0;
    var t = setInterval(function () {
      n += 1;
      if (global.renderMathInElement) { clearInterval(t); cb(); }
      else if (n > 80) clearInterval(t);
    }, 80);
  }

  function watch(root) {
    if (!root) return;
    whenReady(function () {
      typesetMath(root);
      if (root.dataset.mathWatch === '1') return;
      root.dataset.mathWatch = '1';
      var obs = new MutationObserver(function (mutations) {
        var relevant = mutations.some(function (m) {
          var n = m.target;
          if (n.nodeType === 3) n = n.parentElement;
          return !(n && n.closest && n.closest('.katex'));
        });
        if (!relevant) return;
        if (root._mathTimer) clearTimeout(root._mathTimer);
        root._mathTimer = setTimeout(function () { typesetMath(root); }, 50);
      });
      obs.observe(root, { childList: true, subtree: true, characterData: true });
    });
  }

  function ensureAssets(cb) {
    whenReady(function () {
      if (typeof cb === 'function') cb();
    });
    if (global.renderMathInElement) return;

    if (!document.getElementById('quiz-math-katex-css')) {
      var css = document.createElement('link');
      css.id = 'quiz-math-katex-css';
      css.rel = 'stylesheet';
      css.href = 'https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css';
      document.head.appendChild(css);
    }

    function addScript(src, id, onload) {
      if (document.getElementById(id)) {
        if (onload) onload();
        return;
      }
      var s = document.createElement('script');
      s.id = id;
      s.src = src;
      s.async = true;
      s.onload = onload || null;
      document.head.appendChild(s);
    }

    addScript('https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js', 'quiz-math-katex-js', function () {
      addScript(
        'https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js',
        'quiz-math-katex-auto',
        function () {
          if (typeof cb === 'function') cb();
        }
      );
    });
  }

  global.QuizMath = {
    prepareMathText: prepareMathText,
    fixTextEncoding: fixTextEncoding,
    typesetMath: typesetMath,
    setMathText: setMathText,
    whenReady: whenReady,
    watch: watch,
    ensureAssets: ensureAssets
  };
})(window);
