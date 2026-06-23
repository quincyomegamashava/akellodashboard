/** Collaboration: mentions highlight, activity polling. */
(function() {
  const API = window.PM_API_BASE || '/api';
  let pmActivityPollTimer = null;

  window.pmFormatCommentBody = function(body) {
    if (!body) return '';
    const esc = body.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return esc.replace(/@([A-Za-z0-9_.-]+)/g, '<span class="pm-mention font-semibold text-indigo-700">@$1</span>');
  };

  window.pmStartActivityPoll = function(projectId, callback, intervalMs) {
    pmStopActivityPoll();
    if (!projectId) return;
    let since = new Date().toISOString();
    pmActivityPollTimer = setInterval(async () => {
      try {
        const acts = await pmApiGET(`${API}/projects/${projectId}/activities?since=${encodeURIComponent(since)}`);
        if (acts && acts.length && typeof callback === 'function') callback(acts);
        since = new Date().toISOString();
      } catch (e) { /* ignore */ }
    }, intervalMs || 30000);
  };

  window.pmStopActivityPoll = function() {
    if (pmActivityPollTimer) {
      clearInterval(pmActivityPollTimer);
      pmActivityPollTimer = null;
    }
  };

  window.pmSubscribeProject = async function(projectId, on) {
    if (on) await pmApiPOST(`${API}/projects/${projectId}/subscribe`, {});
    else await pmApiDELETE(`${API}/projects/${projectId}/subscribe`);
  };
})();
