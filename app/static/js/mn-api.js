/**
 * Meeting notes API paths (loaded before meeting_notes.js if needed).
 * The main bundle also assigns window.MN_API.
 */
window.MN_API = window.MN_API || {
  items: "/meeting-notes/api/action-items",
  labels: "/meeting-notes/api/labels",
  savedViews: "/meeting-notes/api/saved-views",
  meetingsSearch: "/meeting-notes/api/meetings/search",
  hubAnalytics: "/meeting-notes/api/hub/analytics",
  hubMyTasks: "/meeting-notes/api/hub/my-tasks",
};
