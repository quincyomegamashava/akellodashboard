/** Baseline save/compare for Gantt. */
(function() {
  const API = window.PM_API_BASE || '/api';
  window.pmActiveBaseline = null;
  window.pmProjectBaselines = [];

  window.pmLoadBaselines = async function(projectId) {
    if (!projectId) return [];
    window.pmProjectBaselines = await pmApiGET(`${API}/projects/${projectId}/baselines`);
    return window.pmProjectBaselines;
  };

  window.pmSaveBaseline = async function(projectId, name) {
    return pmApiPOST(`${API}/projects/${projectId}/baselines`, { name: name || undefined });
  };

  window.pmSetActiveBaseline = function(baseline) {
    window.pmActiveBaseline = baseline;
  };

  window.pmBaselineVarianceClass = function(taskId, taskEndIso) {
    const b = window.pmActiveBaseline;
    if (!b || !b.snapshot || !b.snapshot.tasks) return '';
    const row = b.snapshot.tasks.find((t) => String(t.task_id) === String(taskId));
    if (!row || !row.end_date) return 'baseline-none';
    if (!taskEndIso) return '';
    const baseEnd = new Date(row.end_date.slice(0, 10));
    const curEnd = new Date(String(taskEndIso).slice(0, 10));
    if (curEnd <= baseEnd) return 'baseline-ok';
    return 'baseline-late';
  };

  window.pmWireBaselineControls = function(projectId, onChange) {
    const saveBtn = document.getElementById('pmBaselineSaveBtn');
    const sel = document.getElementById('pmBaselineSelect');
    if (saveBtn) {
      saveBtn.onclick = async () => {
        const name = prompt('Baseline name:', `Baseline ${new Date().toISOString().slice(0, 10)}`);
        if (!name) return;
        await pmSaveBaseline(projectId, name.trim());
        await pmLoadBaselines(projectId);
        if (sel) pmPopulateBaselineSelect(sel);
        if (typeof onChange === 'function') onChange();
      };
    }
    if (sel) {
      pmPopulateBaselineSelect(sel);
      sel.onchange = () => {
        const id = sel.value;
        if (!id) { window.pmActiveBaseline = null; }
        else {
          const b = (window.pmProjectBaselines || []).find((x) => String(x.id) === String(id));
          window.pmActiveBaseline = b || null;
        }
        if (typeof onChange === 'function') onChange();
        pmRenderBaselineLegend();
      };
    }
  };

  window.pmPopulateBaselineSelect = function(sel) {
    if (!sel) return;
    const prev = sel.value;
    sel.innerHTML = '<option value="">Compare to baseline…</option>';
    (window.pmProjectBaselines || []).forEach((b) => {
      sel.appendChild(new Option(b.name + (b.created_at ? ' (' + b.created_at.slice(0, 10) + ')' : ''), String(b.id)));
    });
    if (prev) sel.value = prev;
    pmRenderBaselineLegend();
  };

  window.pmRenderBaselineLegend = function() {
    let el = document.getElementById('pmBaselineLegend');
    if (!el) {
      const host = document.getElementById('pmBaselineSelect');
      if (!host || !host.parentElement) return;
      el = document.createElement('div');
      el.id = 'pmBaselineLegend';
      el.className = 'text-xs text-zinc-600 flex flex-wrap gap-3 mt-1';
      host.parentElement.appendChild(el);
    }
    if (!window.pmActiveBaseline) {
      el.classList.add('hidden');
      return;
    }
    el.classList.remove('hidden');
    el.innerHTML = `
      <span><span class="inline-block w-3 h-3 rounded bg-emerald-400 align-middle mr-1"></span> On/before baseline due</span>
      <span><span class="inline-block w-3 h-3 rounded bg-red-400 align-middle mr-1"></span> Late vs baseline</span>
      <span><span class="inline-block w-3 h-3 rounded bg-zinc-300 align-middle mr-1"></span> No baseline date</span>`;
  };
})();
