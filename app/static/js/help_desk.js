/* Help Desk support hub client */
(function (global) {
  const HD = {};
  const BASE = '/help-desk';

  function csrfToken() {
    const m = document.querySelector('meta[name="csrf-token"]');
    if (m) return m.getAttribute('content');
    const input = document.querySelector('input[name="csrf_token"]');
    return input ? input.value : '';
  }

  async function api(path, opts) {
    opts = opts || {};
    const headers = Object.assign({}, opts.headers || {});
    if (!(opts.body instanceof FormData)) {
      headers['Content-Type'] = headers['Content-Type'] || 'application/json';
    }
    const token = csrfToken();
    if (token) headers['X-CSRFToken'] = token;
    const res = await fetch(BASE + path, Object.assign({}, opts, { headers, credentials: 'same-origin' }));
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || res.statusText || 'Request failed');
    return data;
  }

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function fmtDate(iso) {
    if (!iso) return '—';
    try {
      const d = new Date(iso);
      return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch (e) {
      return iso;
    }
  }

  function priorityBadge(p) {
    p = (p || 'normal').toLowerCase();
    return `<span class="hd-badge hd-badge-${esc(p)}">${esc(p)}</span>`;
  }

  function sourceBadge(s) {
    s = (s || 'internal').toLowerCase();
    const cls = s === 'email' ? 'hd-badge-email' : 'hd-badge-internal';
    return `<span class="hd-badge ${cls}">${esc(s)}</span>`;
  }

  function statusBadge(s) {
    return `<span class="hd-badge hd-badge-status">${esc(s || '')}</span>`;
  }

  function ticketRow(t, cols) {
    cols = cols || 'inbox';
    const breach = t.sla_breached ? ' <span class="hd-badge hd-badge-breach">SLA</span>' : '';
    const assignees = (t.assignees || []).map((a) => a.display_name || a.username).join(', ') || '—';
    if (cols === 'mine') {
      return `<tr class="hd-row" data-id="${t.id}">
        <td><div class="hd-ticket-title">${esc(t.title)}</div><div class="hd-ticket-sub">#${t.id}${breach}</div></td>
        <td>${statusBadge(t.status)}</td>
        <td>${priorityBadge(t.priority)}</td>
        <td>${esc(t.category)}</td>
        <td>${fmtDate(t.timestamp)}</td>
      </tr>`;
    }
    if (cols === 'email') {
      return `<tr class="hd-row" data-id="${t.id}">
        <td><div class="hd-ticket-title">${esc(t.title)}</div></td>
        <td>${esc(t.requester_email || '—')}</td>
        <td>${statusBadge(t.status)}</td>
        <td>${priorityBadge(t.priority)}</td>
        <td>${fmtDate(t.timestamp)}</td>
      </tr>`;
    }
    return `<tr class="hd-row" data-id="${t.id}">
      <td><div class="hd-ticket-title">${esc(t.title)}</div><div class="hd-ticket-sub">#${t.id}${breach}</div></td>
      <td>${statusBadge(t.status)}</td>
      <td>${priorityBadge(t.priority)}</td>
      <td>${esc(t.category)}</td>
      <td>${sourceBadge(t.source)}</td>
      <td>${esc(assignees)}</td>
      <td>${fmtDate(t.timestamp)}</td>
    </tr>`;
  }

  function bindRows(tbody) {
    if (!tbody) return;
    tbody.addEventListener('click', (e) => {
      const tr = e.target.closest('tr.hd-row');
      if (tr && tr.dataset.id) window.location.href = BASE + '/' + tr.dataset.id;
    });
  }

  /* ---- New ticket modal ---- */
  let newModal;
  function openNewTicket() {
    const el = document.getElementById('hd-new-ticket-modal');
    if (!el) return;
    if (window.bootstrap && bootstrap.Modal) {
      newModal = bootstrap.Modal.getOrCreateInstance(el);
      newModal.show();
    } else {
      el.classList.add('show');
      el.style.display = 'block';
    }
  }

  function wireNewTicket() {
    const btn = document.getElementById('hd-new-ticket-btn');
    const mob = document.getElementById('hd-mobile-new');
    if (btn) btn.addEventListener('click', openNewTicket);
    if (mob) mob.addEventListener('click', openNewTicket);

    const titleEl = document.getElementById('hd-new-title');
    let suggestTimer;
    if (titleEl) {
      titleEl.addEventListener('input', () => {
        clearTimeout(suggestTimer);
        suggestTimer = setTimeout(async () => {
          const q = titleEl.value.trim();
          const box = document.getElementById('hd-kb-suggestions');
          const list = document.getElementById('hd-kb-suggestions-list');
          if (!box || !list) return;
          if (q.length < 3) {
            box.classList.add('d-none');
            return;
          }
          try {
            const data = await api('/api/articles?q=' + encodeURIComponent(q));
            const arts = data.articles || [];
            if (!arts.length) {
              box.classList.add('d-none');
              return;
            }
            list.innerHTML = arts
              .slice(0, 5)
              .map((a) => `<li><a href="${BASE}/kb/${esc(a.slug)}" target="_blank">${esc(a.title)}</a></li>`)
              .join('');
            box.classList.remove('d-none');
          } catch (e) {
            box.classList.add('d-none');
          }
        }, 300);
      });
    }

    const submit = document.getElementById('hd-new-submit');
    if (submit) {
      submit.addEventListener('click', async () => {
        const err = document.getElementById('hd-new-error');
        const title = (document.getElementById('hd-new-title') || {}).value || '';
        const description = (document.getElementById('hd-new-desc') || {}).value || '';
        const priority = (document.getElementById('hd-new-priority') || {}).value || 'normal';
        const category = (document.getElementById('hd-new-category') || {}).value || 'general';
        const query_type = (document.getElementById('hd-new-type') || {}).value || 'self';
        if (err) {
          err.classList.add('d-none');
          err.textContent = '';
        }
        try {
          const payload = { title, description, priority, category, query_type };
          const data = await api('/api/tickets', { method: 'POST', body: JSON.stringify(payload) });
          const filesInput = document.getElementById('hd-new-files');
          if (filesInput && filesInput.files && filesInput.files.length && data.ticket) {
            const fd = new FormData();
            Array.from(filesInput.files).forEach((f) => fd.append('files', f));
            await api('/api/tickets/' + data.ticket.id + '/attachments', { method: 'POST', body: fd, headers: {} });
          }
          window.location.href = BASE + '/' + data.ticket.id;
        } catch (e) {
          if (err) {
            err.textContent = e.message;
            err.classList.remove('d-none');
          }
        }
      });
    }
  }

  /* ---- Inbox ---- */
  HD.initInbox = async function () {
    wireNewTicket();
    bindRows(document.getElementById('hd-inbox-body'));
    try {
      const stats = await api('/api/stats');
      const strip = document.getElementById('hd-inbox-stats');
      if (strip) {
        strip.innerHTML = [
          ['Open', (stats.unresolved || 0)],
          ['Resolved', stats.resolved || 0],
          ['SLA breach', stats.sla_breached_open || 0],
        ]
          .map(([l, v]) => `<div class="hd-stat-chip"><strong>${v}</strong>${l}</div>`)
          .join('');
      }
    } catch (e) {}

    async function load() {
      const params = new URLSearchParams();
      const q = document.getElementById('hd-filter-q');
      const st = document.getElementById('hd-filter-status');
      const pr = document.getElementById('hd-filter-priority');
      const cat = document.getElementById('hd-filter-category');
      const src = document.getElementById('hd-filter-source');
      if (q && q.value) params.set('q', q.value);
      if (st && st.value) params.set('status', st.value);
      if (pr && pr.value) params.set('priority', pr.value);
      if (cat && cat.value) params.set('category', cat.value);
      if (src && src.value) params.set('source', src.value);
      const body = document.getElementById('hd-inbox-body');
      try {
        const data = await api('/api/tickets?' + params.toString());
        const tickets = data.tickets || [];
        body.innerHTML = tickets.length
          ? tickets.map((t) => ticketRow(t)).join('')
          : '<tr><td colspan="7" class="hd-muted text-center py-4">No tickets match.</td></tr>';
      } catch (e) {
        body.innerHTML = `<tr><td colspan="7" class="text-danger text-center py-4">${esc(e.message)}</td></tr>`;
      }
    }

    ['hd-filter-q', 'hd-filter-status', 'hd-filter-priority', 'hd-filter-category', 'hd-filter-source'].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.addEventListener(id === 'hd-filter-q' ? 'input' : 'change', () => load());
    });
    load();
  };

  HD.initMyTickets = async function () {
    wireNewTicket();
    const body = document.getElementById('hd-my-body');
    bindRows(body);
    try {
      const data = await api('/api/tickets?mine=1');
      const tickets = data.tickets || [];
      body.innerHTML = tickets.length
        ? tickets.map((t) => ticketRow(t, 'mine')).join('')
        : '<tr><td colspan="5" class="hd-muted text-center py-4">You have no tickets yet.</td></tr>';
    } catch (e) {
      body.innerHTML = `<tr><td colspan="5" class="text-danger text-center py-4">${esc(e.message)}</td></tr>`;
    }
  };

  HD.initEmail = async function () {
    wireNewTicket();
    const body = document.getElementById('hd-email-body');
    bindRows(body);
    async function load() {
      try {
        const data = await api('/api/tickets?source=email');
        const tickets = data.tickets || [];
        body.innerHTML = tickets.length
          ? tickets.map((t) => ticketRow(t, 'email')).join('')
          : '<tr><td colspan="5" class="hd-muted text-center py-4">No email tickets yet.</td></tr>';
      } catch (e) {
        body.innerHTML = `<tr><td colspan="5" class="text-danger text-center py-4">${esc(e.message)}</td></tr>`;
      }
    }
    const sync = document.getElementById('hd-email-sync');
    if (sync) {
      sync.addEventListener('click', async () => {
        const st = document.getElementById('hd-email-status');
        if (st) st.textContent = 'Syncing…';
        try {
          const r = await api('/api/email/sync', { method: 'POST', body: '{}' });
          if (st) st.textContent = `Created ${r.created || 0} ticket(s).` + (r.warning ? ' ' + r.warning : '');
          load();
        } catch (e) {
          if (st) st.textContent = e.message;
        }
      });
    }
    load();
  };

  /* ---- Detail ---- */
  let detailState = { ticket: null, assigneeIds: [], watcherIds: [] };

  function renderThread(ticket) {
    const el = document.getElementById('hd-thread');
    if (!el) return;
    const msgs = ticket.messages || [];
    if (!msgs.length) {
      el.innerHTML = `<div class="hd-msg"><div class="hd-msg-body">${esc(ticket.description)}</div></div>`;
      return;
    }
    el.innerHTML = msgs
      .map((m) => {
        const who = (m.author && (m.author.display_name || m.author.username)) || m.author_name || 'System';
        const cls = m.is_internal ? 'hd-msg hd-msg-internal' : 'hd-msg';
        const tag = m.is_internal ? ' · Internal' : '';
        const atts = (m.attachments || [])
          .map((a) => `<div><a href="${esc(a.path)}" target="_blank">${esc(a.filename)}</a></div>`)
          .join('');
        return `<div class="${cls}">
          <div class="hd-msg-meta">${esc(who)}${tag} · ${fmtDate(m.created_at)}</div>
          <div class="hd-msg-body">${esc(m.body)}</div>
          ${atts}
        </div>`;
      })
      .join('');
    el.scrollTop = el.scrollHeight;
  }

  function renderPeople(containerId, people, removable, onRemove) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = (people || [])
      .map((p) => {
        const name = p.display_name || p.username;
        const btn = removable
          ? `<button type="button" data-id="${p.id}" aria-label="Remove">&times;</button>`
          : '';
        return `<span class="hd-chip">${esc(name)}${btn}</span>`;
      })
      .join('') || '<span class="hd-muted small">None</span>';
    if (removable) {
      el.querySelectorAll('button[data-id]').forEach((b) => {
        b.addEventListener('click', () => onRemove(parseInt(b.dataset.id, 10)));
      });
    }
  }

  function renderSla(ticket) {
    const box = document.getElementById('hd-sla-box');
    if (!box) return;
    let html = '<label class="form-label">SLA</label>';
    if (ticket.sla_breached) html += '<div class="hd-badge hd-badge-breach mb-1">Breached</div>';
    html += `<div class="small hd-muted">First response due: ${fmtDate(ticket.sla_first_response_due)}</div>`;
    html += `<div class="small hd-muted">Resolve due: ${fmtDate(ticket.sla_resolve_due)}</div>`;
    if (ticket.first_response_at) html += `<div class="small">First response: ${fmtDate(ticket.first_response_at)}</div>`;
    box.innerHTML = html;
  }

  function renderAttachments(ticket) {
    const box = document.getElementById('hd-attachments-box');
    if (!box) return;
    const atts = ticket.attachments || [];
    let html = '<label class="form-label">Attachments</label>';
    if (ticket.image_path && !atts.length) {
      html += `<div><a href="${esc(ticket.image_path)}" target="_blank">Legacy image</a></div>`;
    }
    html += atts.map((a) => `<div><a href="${esc(a.path)}" target="_blank">${esc(a.filename)}</a></div>`).join('')
      || '<div class="hd-muted small">None</div>';
    box.innerHTML = html;
  }

  async function refreshDetail(id) {
    const data = await api('/api/tickets/' + id);
    const t = data.ticket;
    detailState.ticket = t;
    detailState.assigneeIds = (t.assignees || []).map((a) => a.id);
    detailState.watcherIds = (t.watchers || []).map((w) => w.id);
    const title = document.getElementById('hd-detail-title');
    if (title) title.textContent = t.title;
    const meta = document.getElementById('hd-detail-meta');
    if (meta) {
      meta.innerHTML =
        statusBadge(t.status) +
        priorityBadge(t.priority) +
        sourceBadge(t.source) +
        `<span class="hd-badge hd-badge-status">${esc(t.category)}</span>` +
        (t.sla_breached ? '<span class="hd-badge hd-badge-breach">SLA breached</span>' : '');
    }
    renderThread(t);
    renderSla(t);
    renderAttachments(t);
    const canEdit = !!document.getElementById('hd-side-status') && !document.getElementById('hd-side-status').disabled;
    renderPeople('hd-assignees', t.assignees, canEdit, async (uid) => {
      detailState.assigneeIds = detailState.assigneeIds.filter((x) => x !== uid);
      await api('/api/tickets/' + id, {
        method: 'PATCH',
        body: JSON.stringify({ assignee_ids: detailState.assigneeIds }),
      });
      refreshDetail(id);
    });
    renderPeople('hd-watchers', t.watchers, canEdit, async (uid) => {
      detailState.watcherIds = detailState.watcherIds.filter((x) => x !== uid);
      await api('/api/tickets/' + id, {
        method: 'PATCH',
        body: JSON.stringify({ watcher_ids: detailState.watcherIds }),
      });
      refreshDetail(id);
    });
  }

  function wireUserSearch(inputId, resultsId, onPick) {
    const input = document.getElementById(inputId);
    const results = document.getElementById(resultsId);
    if (!input || !results) return;
    let timer;
    input.addEventListener('input', () => {
      clearTimeout(timer);
      timer = setTimeout(async () => {
        const q = input.value.trim();
        if (q.length < 2) {
          results.innerHTML = '';
          return;
        }
        try {
          const data = await api('/api/users?q=' + encodeURIComponent(q));
          results.innerHTML = (data.users || [])
            .map(
              (u) =>
                `<button type="button" data-id="${u.id}">${esc(u.display_name || u.username)} <span class="hd-muted">@${esc(u.username)}</span></button>`
            )
            .join('');
          results.querySelectorAll('button').forEach((b) => {
            b.addEventListener('click', () => {
              onPick(parseInt(b.dataset.id, 10));
              input.value = '';
              results.innerHTML = '';
            });
          });
        } catch (e) {
          results.innerHTML = '';
        }
      }, 250);
    });
  }

  HD.initDetail = async function (queryId) {
    wireNewTicket();
    try {
      await refreshDetail(queryId);
    } catch (e) {
      console.error(e);
    }

    // Macros
    try {
      const macros = await api('/api/macros');
      const sel = document.getElementById('hd-macro-select');
      if (sel) {
        (macros.macros || []).forEach((m) => {
          const opt = document.createElement('option');
          opt.value = m.id;
          opt.textContent = m.title;
          opt.dataset.body = m.body;
          sel.appendChild(opt);
        });
        sel.addEventListener('change', () => {
          const opt = sel.options[sel.selectedIndex];
          const ta = document.getElementById('hd-reply-body');
          if (opt && opt.dataset.body && ta) {
            ta.value = (ta.value ? ta.value + '\n\n' : '') + opt.dataset.body;
          }
          sel.selectedIndex = 0;
        });
      }
    } catch (e) {}

    ['hd-side-status', 'hd-side-priority', 'hd-side-category'].forEach((id) => {
      const el = document.getElementById(id);
      if (!el || el.disabled) return;
      el.addEventListener('change', async () => {
        const payload = {};
        if (id === 'hd-side-status') payload.status = el.value;
        if (id === 'hd-side-priority') payload.priority = el.value;
        if (id === 'hd-side-category') payload.category = el.value;
        await api('/api/tickets/' + queryId, { method: 'PATCH', body: JSON.stringify(payload) });
        await refreshDetail(queryId);
        if (payload.status === 'Resolved') {
          if (confirm('Ticket resolved. Leave a CSAT rating?')) {
            window.location.href = BASE + '/csat/' + queryId;
          }
        }
      });
    });

    wireUserSearch('hd-assign-search', 'hd-assign-results', async (uid) => {
      if (!detailState.assigneeIds.includes(uid)) detailState.assigneeIds.push(uid);
      await api('/api/tickets/' + queryId, {
        method: 'PATCH',
        body: JSON.stringify({ assignee_ids: detailState.assigneeIds }),
      });
      refreshDetail(queryId);
    });
    wireUserSearch('hd-watch-search', 'hd-watch-results', async (uid) => {
      if (!detailState.watcherIds.includes(uid)) detailState.watcherIds.push(uid);
      await api('/api/tickets/' + queryId, {
        method: 'PATCH',
        body: JSON.stringify({ watcher_ids: detailState.watcherIds }),
      });
      refreshDetail(queryId);
    });

    const send = document.getElementById('hd-reply-send');
    if (send) {
      send.addEventListener('click', async () => {
        const body = (document.getElementById('hd-reply-body') || {}).value || '';
        const is_internal = !!(document.getElementById('hd-internal-note') || {}).checked;
        if (!body.trim()) return;
        await api('/api/tickets/' + queryId + '/messages', {
          method: 'POST',
          body: JSON.stringify({ body, is_internal }),
        });
        const filesInput = document.getElementById('hd-reply-files');
        if (filesInput && filesInput.files && filesInput.files.length) {
          const fd = new FormData();
          Array.from(filesInput.files).forEach((f) => fd.append('files', f));
          await api('/api/tickets/' + queryId + '/attachments', { method: 'POST', body: fd, headers: {} });
          filesInput.value = '';
        }
        document.getElementById('hd-reply-body').value = '';
        await refreshDetail(queryId);
      });
    }
  };

  /* ---- KB ---- */
  HD.initKb = async function () {
    wireNewTicket();
    const list = document.getElementById('hd-kb-list');
    async function load(q) {
      try {
        const params = new URLSearchParams();
        if (q) params.set('q', q);
        if (document.getElementById('hd-kb-new')) params.set('all', '1');
        const qs = params.toString();
        const data = await api('/api/articles' + (qs ? '?' + qs : ''));
        const arts = data.articles || [];
        list.innerHTML = arts.length
          ? arts
              .map(
                (a) => `<a class="hd-kb-card" href="${BASE}/kb/${esc(a.slug)}">
              <h3>${esc(a.title)}${a.published ? '' : ' <span class="hd-badge">draft</span>'}</h3>
              <div class="hd-muted small">${esc(a.tags || '')}</div>
            </a>`
              )
              .join('')
          : '<p class="hd-muted">No articles found.</p>';
      } catch (e) {
        list.innerHTML = `<p class="text-danger">${esc(e.message)}</p>`;
      }
    }
    const search = document.getElementById('hd-kb-search');
    if (search) {
      let t;
      search.addEventListener('input', () => {
        clearTimeout(t);
        t = setTimeout(() => load(search.value.trim()), 250);
      });
    }
    load('');

    const neu = document.getElementById('hd-kb-new');
    if (neu) {
      neu.addEventListener('click', () => {
        document.getElementById('hd-kb-id').value = '';
        document.getElementById('hd-kb-title').value = '';
        document.getElementById('hd-kb-body').value = '';
        document.getElementById('hd-kb-tags').value = '';
        document.getElementById('hd-kb-published').checked = false;
        const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('hd-kb-modal'));
        modal.show();
      });
    }
    const save = document.getElementById('hd-kb-save');
    if (save) {
      save.addEventListener('click', async () => {
        const payload = {
          title: document.getElementById('hd-kb-title').value,
          body: document.getElementById('hd-kb-body').value,
          tags: document.getElementById('hd-kb-tags').value,
          published: document.getElementById('hd-kb-published').checked,
        };
        const id = document.getElementById('hd-kb-id').value;
        if (id) await api('/api/articles/' + id, { method: 'PUT', body: JSON.stringify(payload) });
        else await api('/api/articles', { method: 'POST', body: JSON.stringify(payload) });
        bootstrap.Modal.getOrCreateInstance(document.getElementById('hd-kb-modal')).hide();
        load(search ? search.value.trim() : '');
      });
    }
  };

  /* ---- Reports ---- */
  HD.initReports = async function () {
    wireNewTicket();
    try {
      const s = await api('/api/stats');
      const box = document.getElementById('hd-report-stats');
      if (box) {
        const items = [
          ['Total', s.total],
          ['Resolved', s.resolved],
          ['Open', s.unresolved],
          ['Success %', s.success_rate],
          ['Avg resolve (h)', s.avg_resolution_hours ?? '—'],
          ['SLA met %', s.sla_met_percent ?? '—'],
          ['CSAT avg', s.csat_average ?? '—'],
          ['Email', s.email_count],
        ];
        box.innerHTML = items
          .map(([l, v]) => `<div class="hd-report-stat"><div class="label">${l}</div><div class="value">${v}</div></div>`)
          .join('');
      }
      if (global.Chart) {
        const vol = s.volume_7d || [];
        new Chart(document.getElementById('hd-chart-volume'), {
          type: 'line',
          data: {
            labels: vol.map((v) => v.date),
            datasets: [{ label: 'Tickets', data: vol.map((v) => v.count), borderColor: '#0f766e', tension: 0.3 }],
          },
          options: { plugins: { legend: { display: false } } },
        });
        const cats = s.by_category || [];
        new Chart(document.getElementById('hd-chart-category'), {
          type: 'doughnut',
          data: {
            labels: cats.map((c) => c.category),
            datasets: [{ data: cats.map((c) => c.count), backgroundColor: ['#0f766e', '#14b8a6', '#5eead4', '#99f6e4', '#ccfbf1'] }],
          },
        });
      }
    } catch (e) {
      console.error(e);
    }
  };

  /* ---- Settings ---- */
  HD.initSettings = async function () {
    wireNewTicket();

    // SLA
    try {
      const { policy } = await api('/api/sla');
      const form = document.getElementById('hd-sla-form');
      form.innerHTML = ['urgent', 'high', 'normal']
        .map((p) => {
          const r = policy[p] || {};
          return `<div class="row g-2 align-items-end mb-2">
            <div class="col-3"><strong>${p}</strong></div>
            <div class="col-4"><label class="small">First response</label>
              <input type="number" class="form-control form-control-sm" data-sla="${p}" data-field="first_response_hours" value="${r.first_response_hours || ''}"></div>
            <div class="col-4"><label class="small">Resolve</label>
              <input type="number" class="form-control form-control-sm" data-sla="${p}" data-field="resolve_hours" value="${r.resolve_hours || ''}"></div>
          </div>`;
        })
        .join('');
      document.getElementById('hd-sla-save').addEventListener('click', async () => {
        const next = {};
        form.querySelectorAll('[data-sla]').forEach((inp) => {
          const p = inp.dataset.sla;
          next[p] = next[p] || {};
          next[p][inp.dataset.field] = parseFloat(inp.value) || 0;
        });
        await api('/api/sla', { method: 'PUT', body: JSON.stringify({ policy: next }) });
        alert('SLA saved');
      });
    } catch (e) {}

    async function loadMacros() {
      const data = await api('/api/macros');
      const list = document.getElementById('hd-macros-list');
      list.innerHTML = (data.macros || [])
        .map(
          (m) => `<div class="d-flex justify-content-between align-items-start border-bottom py-2">
          <div><strong>${esc(m.title)}</strong><div class="small hd-muted">${esc((m.body || '').slice(0, 120))}</div></div>
          <button type="button" class="btn btn-sm btn-outline-danger" data-del-macro="${m.id}">Delete</button>
        </div>`
        )
        .join('') || '<p class="hd-muted small">No macros yet.</p>';
      list.querySelectorAll('[data-del-macro]').forEach((b) => {
        b.addEventListener('click', async () => {
          await api('/api/macros/' + b.dataset.delMacro, { method: 'DELETE' });
          loadMacros();
        });
      });
    }
    document.getElementById('hd-macro-add').addEventListener('click', async () => {
      const title = prompt('Macro title');
      if (!title) return;
      const body = prompt('Macro body');
      if (!body) return;
      await api('/api/macros', { method: 'POST', body: JSON.stringify({ title, body }) });
      loadMacros();
    });
    loadMacros().catch(() => {});

    async function loadTeams() {
      const data = await api('/api/teams');
      const list = document.getElementById('hd-teams-list');
      list.innerHTML = (data.teams || [])
        .map(
          (t) => `<div class="border-bottom py-2">
          <strong>${esc(t.name)}</strong>
          <div class="small hd-muted">${(t.members || []).map((m) => m.display_name || m.username).join(', ') || 'No members'}</div>
        </div>`
        )
        .join('') || '<p class="hd-muted small">No teams yet.</p>';
    }
    document.getElementById('hd-team-add').addEventListener('click', async () => {
      const name = prompt('Team name');
      if (!name) return;
      await api('/api/teams', { method: 'POST', body: JSON.stringify({ name }) });
      loadTeams();
    });
    loadTeams().catch(() => {});

    document.getElementById('hd-migrate-legacy').addEventListener('click', async () => {
      const st = document.getElementById('hd-migrate-status');
      st.textContent = 'Migrating…';
      try {
        const r = await api('/api/email/migrate-legacy', { method: 'POST', body: '{}' });
        st.textContent = `Migrated ${r.migrated || 0} ticket(s).`;
      } catch (e) {
        st.textContent = e.message;
      }
    });
  };

  global.HD = HD;
})(window);
