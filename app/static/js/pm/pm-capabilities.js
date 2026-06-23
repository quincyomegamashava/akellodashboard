/** Project role capabilities from board API payload. */
(function() {
  window.pmProjectCapabilities = {
    can_edit_tasks: true,
    can_manage_project: false,
    can_comment: true,
    role: 'contributor',
  };

  window.pmCanEditTasks = function() {
    return window.pmProjectCapabilities?.can_edit_tasks !== false;
  };

  window.pmCanManageProject = function() {
    return !!window.pmProjectCapabilities?.can_manage_project;
  };

  window.pmCanComment = function() {
    return window.pmProjectCapabilities?.can_comment !== false;
  };

  window.pmApplyProjectCapabilities = function(data) {
    const caps = {
      can_edit_tasks: data?.can_edit_tasks !== false,
      can_manage_project: !!data?.can_manage_project,
      can_comment: data?.can_comment !== false,
      role: data?.current_user_role || 'contributor',
    };
    window.pmProjectCapabilities = caps;

    const badge = document.getElementById('pmReadOnlyBadge');
    if (badge) {
      badge.classList.toggle('hidden', caps.can_edit_tasks);
    }

    ['pmBulkToggleBtn', 'pmSaveViewBtn', 'pmManageLabelsBtn'].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.classList.toggle('hidden', !caps.can_edit_tasks);
    });

    const baselineSave = document.getElementById('pmBaselineSaveBtn');
    if (baselineSave) baselineSave.classList.toggle('hidden', !caps.can_manage_project);

    const editProj = document.getElementById('editProjectBtn');
    const delProj = document.getElementById('deleteProjectBtn');
    if (editProj) editProj.classList.toggle('hidden', !caps.can_manage_project);
    if (delProj) delProj.classList.toggle('hidden', !caps.can_manage_project);
  };
})();
