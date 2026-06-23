/** Cross-project workload view. */
(function() {
  const API = window.PM_API_BASE || '/api';

  function esc(s) {
    if (!s) return '';
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  window.pmRenderWorkloadPage = async function(mount) {
    if (!mount) return;
    mount.innerHTML = 'Loading workload…';
    try {
      const rows = await pmApiGET(`${API}/pm/workload`);
      if (!rows || !rows.length) {
        mount.innerHTML = '<p class="text-zinc-500 italic">No open tasks across your projects.</p>';
        return;
      }
      mount.innerHTML = `
        <div class="overflow-x-auto rounded-xl border border-zinc-200 bg-white">
          <table class="min-w-full text-sm">
            <thead class="bg-zinc-50 text-left text-zinc-600">
              <tr>
                <th class="px-3 py-2">Person</th>
                <th class="px-3 py-2">Open</th>
                <th class="px-3 py-2">Overdue</th>
                <th class="px-3 py-2">Blocked</th>
                <th class="px-3 py-2">Projects</th>
                <th class="px-3 py-2">Sample tasks</th>
              </tr>
            </thead>
            <tbody>
              ${rows.map((r) => `
                <tr class="border-t border-zinc-100 align-top">
                  <td class="px-3 py-2 font-medium">${esc(r.user_name)}</td>
                  <td class="px-3 py-2">${r.open_count}</td>
                  <td class="px-3 py-2 text-red-700">${r.overdue_count}</td>
                  <td class="px-3 py-2 text-amber-700">${r.blocked_count}</td>
                  <td class="px-3 py-2 text-xs text-zinc-600">
                    ${(r.projects || []).map((p) => `${esc(p.project_name)} (${p.open} open)`).join('<br>') || '—'}
                  </td>
                  <td class="px-3 py-2 text-xs">
                    ${(r.sample_tasks || []).map((t) =>
                      `<a class="text-indigo-600 hover:underline block" href="/projectmanagement?project=${t.project_id}&task=${t.task_id}">${esc(t.title)}</a>`
                    ).join('') || '—'}
                  </td>
                </tr>`).join('')}
            </tbody>
          </table>
        </div>`;
    } catch (e) {
      mount.innerHTML = '<p class="text-red-500">Failed to load workload.</p>';
    }
  };
})();
