/** @mention autocomplete in task comments. */
(function() {
  let _members = [];
  let _menu = null;

  function esc(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;');
  }

  function closeMenu() {
    if (_menu) {
      _menu.remove();
      _menu = null;
    }
  }

  function insertMention(input, username) {
    const val = input.value;
    const pos = input.selectionStart || val.length;
    const before = val.slice(0, pos);
    const m = before.match(/@([\w.-]*)$/);
    if (!m) return;
    const start = before.length - m[0].length;
    const after = val.slice(pos);
    input.value = val.slice(0, start) + '@' + username + ' ' + after;
    const caret = start + username.length + 2;
    input.setSelectionRange(caret, caret);
    input.focus();
    closeMenu();
  }

  function showMenu(input, query) {
    closeMenu();
    const q = (query || '').toLowerCase();
    const matches = _members.filter((m) => {
      const name = (m.name || m.username || '').toLowerCase();
      return !q || name.includes(q);
    }).slice(0, 8);
    if (!matches.length) return;
    _menu = document.createElement('div');
    _menu.className = 'absolute z-50 bg-white border border-zinc-200 rounded-lg shadow-lg text-sm max-h-40 overflow-y-auto';
    const rect = input.getBoundingClientRect();
    _menu.style.left = rect.left + 'px';
    _menu.style.top = (rect.bottom + 4) + 'px';
    _menu.style.minWidth = Math.max(rect.width, 160) + 'px';
    matches.forEach((m) => {
      const name = m.name || m.username;
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'block w-full text-left px-3 py-1.5 hover:bg-indigo-50';
      btn.textContent = name;
      btn.onclick = () => insertMention(input, name);
      _menu.appendChild(btn);
    });
    document.body.appendChild(_menu);
  }

  window.pmWireCommentMentions = function(input, getProjectId) {
    if (!input) return;
    input.addEventListener('input', async () => {
      const val = input.value;
      const pos = input.selectionStart || val.length;
      const before = val.slice(0, pos);
      const m = before.match(/@([\w.-]*)$/);
      if (!m) {
        closeMenu();
        return;
      }
      const pid = typeof getProjectId === 'function' ? getProjectId() : getProjectId;
      if (!pid) return;
      if (typeof getProjectMembers === 'function') {
        _members = await getProjectMembers(pid);
      }
      showMenu(input, m[1]);
    });
    input.addEventListener('blur', () => setTimeout(closeMenu, 150));
    document.addEventListener('click', (e) => {
      if (_menu && !e.target.closest('#pm-task-comment-input') && !_menu.contains(e.target)) closeMenu();
    });
  };
})();
