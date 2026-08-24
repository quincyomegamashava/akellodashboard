(function (global) {
  var DELIMS = [
    { left: '$$', right: '$$', display: true },
    { left: '\\[', right: '\\]', display: true },
    { left: '$', right: '$', display: false },
    { left: '\\(', right: '\\)', display: false }
  ];

  function prepareMathText(text) {
    var t = String(text || '');
    if (!t) return t;
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

  global.QuizMath = {
    prepareMathText: prepareMathText,
    typesetMath: typesetMath,
    whenReady: whenReady,
    watch: watch
  };
})(window);
