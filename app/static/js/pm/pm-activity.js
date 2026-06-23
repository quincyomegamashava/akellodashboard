/** Project activity feed tab. */
(function() {
  const API = window.PM_API_BASE || '/api';
  let _lastActors = [];

  window.pmLoadProjectActivities = async function(projectId, filters) {
    if (!projectId) return [];
    const params = new URLSearchParams();
    const f = filters || {};
    if (f.since) params.set('since', f.since);
    const q = params.toString();
    return pmApiGET(`${API}/projects/${projectId}/activities${q ? '?' + q : ''}`);
  };

  window.pmPopulateActivityActorFilter = function(actorSel, acts) {
    if (!actorSel) return;
    const names = [...new Set((acts || []).map((a) => a.actor_name).filter(Boolean))].sort();
    _lastActors = names;
    const prev = actorSel.value;
    actorSel.innerHTML = '<option value="">All actors</option>';
    names.forEach((n) => actorSel.appendChild(new Option(n, n)));
    if (prev && names.includes(prev)) actorSel.value = prev;
  };

  window.pmRenderActivityPanel = async function(mount, projectId, filters) {
    if (!mount || !projectId) return;
    mount.innerHTML = '<p class="text-sm text-zinc-500 p-4">Loading activity…</p>';
    try {
      const acts = await pmLoadProjectActivities(projectId, filters);
      const actorSel = document.getElementById('pmActivityFilterActor');
      if (actorSel && (!filters || !filters.actor)) {
        pmPopulateActivityActorFilter(actorSel, acts);
      }
      let rows = acts || [];
      if (filters && filters.actor) {
        rows = rows.filter((a) => (a.actor_name || '') === filters.actor);
      }
      if (filters && filters.action) {
        rows = rows.filter((a) => (a.action || '') === filters.action);
      }
      if (!rows.length) {
        mount.innerHTML = '<p class="text-sm text-zinc-500 p-4 italic">No activity recorded.</p>';
        return;
      }
      mount.innerHTML = `
        <div class="space-y-2 p-4 max-h-[min(70vh,100%)] overflow-y-auto">
          ${rows.map((a) => `
            <div class="border border-zinc-100 rounded-lg px-3 py-2 bg-white text-sm">
              <div class="text-xs text-zinc-500">${escapeHtml(a.actor_name || 'System')} · ${a.created_at ? new Date(a.created_at).toLocaleString() : ''}</div>
              <div><span class="font-medium text-zinc-800">${escapeHtml(a.action || '')}</span>${a.detail ? `: ${escapeHtml(a.detail)}` : ''}</div>
            </div>`).join('')}
        </div>`;
    } catch (e) {
      mount.innerHTML = '<p class="text-sm text-red-500 p-4">Failed to load activity.</p>';
    }
  };

  function escapeHtml(s) {
    if (!s) return '';
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  window.pmWireActivityTab = function(getProjectId) {
    const actorSel = document.getElementById('pmActivityFilterActor');
    const actionSel = document.getElementById('pmActivityFilterAction');
    const mount = document.getElementById('pmActivityFeed');
    const refresh = () => {
      const pid = typeof getProjectId === 'function' ? getProjectId() : getProjectId;
      if (!pid || !mount) return;
      pmRenderActivityPanel(mount, pid, {
        actor: actorSel ? actorSel.value : '',
        action: actionSel ? actionSel.value : '',
      });
    };
    if (actorSel) actorSel.onchange = refresh;
    if (actionSel) actionSel.onchange = refresh;
    return refresh;
  };
})();
