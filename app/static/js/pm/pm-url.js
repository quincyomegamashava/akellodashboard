/** Deep-link sync for project management (?project=&tab=&task=). */
window.pmSyncUrl = function(state) {
  const params = new URLSearchParams(window.location.search);
  if (state.project) params.set('project', String(state.project));
  else params.delete('project');
  if (state.tab && state.tab !== 'board') params.set('tab', state.tab);
  else params.delete('tab');
  if (state.task) params.set('task', String(state.task));
  else params.delete('task');
  const qs = params.toString();
  const next = window.location.pathname + (qs ? `?${qs}` : '');
  if (next !== window.location.pathname + window.location.search) {
    history.replaceState(null, '', next);
  }
};

window.pmReadUrlState = function() {
  const params = new URLSearchParams(window.location.search);
  return {
    project: params.get('project') || null,
    tab: params.get('tab') || 'board',
    task: params.get('task') || null,
  };
};

window.pmRecentProjectsKey = 'pm_recent_projects';

window.pmPushRecentProject = function(projectId) {
  if (!projectId) return;
  try {
    const key = window.pmRecentProjectsKey;
    let list = JSON.parse(localStorage.getItem(key) || '[]');
    list = [String(projectId), ...list.filter((id) => String(id) !== String(projectId))].slice(0, 8);
    localStorage.setItem(key, JSON.stringify(list));
  } catch (e) { /* ignore */ }
};

window.pmGetRecentProjects = function() {
  try {
    return JSON.parse(localStorage.getItem(window.pmRecentProjectsKey) || '[]');
  } catch (e) {
    return [];
  }
};
