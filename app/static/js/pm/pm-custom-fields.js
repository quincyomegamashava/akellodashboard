/** Custom fields UI for task modal. */
(function() {
  const API = window.PM_API_BASE || '/api';

  window.pmProjectCustomFields = [];

  window.pmLoadCustomFields = async function(projectId) {
    if (!projectId) return [];
    window.pmProjectCustomFields = await pmApiGET(`${API}/projects/${projectId}/custom-fields`);
    return window.pmProjectCustomFields;
  };

  window.pmRenderCustomFieldsForm = function(container, task, projectId) {
    if (!container) return;
    const fields = window.pmProjectCustomFields || [];
    const values = task?.custom_fields || {};
    if (!fields.length) {
      container.innerHTML = '';
      return null;
    }
    container.innerHTML = fields.map((f) => {
      const val = values[String(f.id)] || values[f.id] || '';
      const id = `pm-cf-${f.id}`;
      if (f.field_type === 'select') {
        const opts = (f.options || []).map((o) =>
          `<option value="${o}"${String(val) === String(o) ? ' selected' : ''}>${o}</option>`
        ).join('');
        return `<label class="text-xs text-zinc-600">${f.name}<select id="${id}" class="w-full border rounded px-2 py-1 text-sm mt-0.5" data-cf-id="${f.id}"><option value="">—</option>${opts}</select></label>`;
      }
      if (f.field_type === 'date') {
        return `<label class="text-xs text-zinc-600">${f.name}<input type="date" id="${id}" value="${val ? String(val).slice(0, 10) : ''}" class="w-full border rounded px-2 py-1 text-sm mt-0.5" data-cf-id="${f.id}" /></label>`;
      }
      if (f.field_type === 'number') {
        return `<label class="text-xs text-zinc-600">${f.name}<input type="number" id="${id}" value="${val}" class="w-full border rounded px-2 py-1 text-sm mt-0.5" data-cf-id="${f.id}" /></label>`;
      }
      return `<label class="text-xs text-zinc-600">${f.name}<input type="text" id="${id}" value="${val}" class="w-full border rounded px-2 py-1 text-sm mt-0.5" data-cf-id="${f.id}" /></label>`;
    }).join('');
    return {
      collect() {
        const out = {};
        container.querySelectorAll('[data-cf-id]').forEach((el) => {
          out[el.dataset.cfId] = el.value;
        });
        return out;
      },
    };
  };
})();
