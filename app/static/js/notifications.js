/**
 * Notification system — includes PM deep links.
 */
document.addEventListener('DOMContentLoaded', function () {
    loadNotificationCount();
    setInterval(loadNotificationCount, 30000);

    document.addEventListener('click', function (e) {
        const container = document.getElementById('notificationBadgeContainer');
        const dropdown = document.getElementById('notificationsDropdown');
        if (container && !container.contains(e.target) && dropdown && !dropdown.classList.contains('hidden')) {
            dropdown.classList.add('hidden');
            window.notificationDropdownOpen = false;
        }
    });

    window.toggleNotificationsDropdown = toggleNotificationsDropdown;
    window.markNotificationRead = markNotificationRead;
});

let notificationDropdownOpen = false;
window.notificationDropdownOpen = false;

function pmNotificationIcon(type) {
    if (type === 'pm_assignment') return 'user-plus';
    if (type === 'pm_mention') return 'at';
    if (type === 'pm_comment') return 'comment';
    if (type === 'pm_due_soon') return 'clock-o';
    if (type && type.startsWith('sm_')) return 'bullhorn';
    if (type && type.startsWith('meeting_')) return 'clipboard-list';
    if (type === 'assignment') return 'user-plus';
    if (type === 'resolution') return 'check-circle';
    return 'bell';
}

function pmNotificationHref(notif) {
    const t = notif.notification_type || '';
    if (t.startsWith('pm_') && notif.pm_project_id && notif.task_id) {
        return `/projectmanagement?project=${notif.pm_project_id}&task=${notif.task_id}`;
    }
    if (notif.query_id) return `/help-desk?query=${notif.query_id}`;
    return null;
}

async function loadNotificationCount() {
    try {
        const response = await fetch('/api/notifications/unread-count');
        const data = await response.json();
        if (data.success) {
            const badge = document.getElementById('notificationCountBadge');
            if (badge) {
                if (data.count > 0) {
                    badge.textContent = data.count > 99 ? '99+' : data.count;
                    badge.style.display = 'flex';
                } else {
                    badge.style.display = 'none';
                }
            }
        }
    } catch (error) {
        console.error('Error loading notification count:', error);
    }
}

async function loadNotifications() {
    try {
        const listDiv = document.getElementById('notificationsList');
        if (!listDiv) return;

        listDiv.innerHTML = '<div class="px-4 py-8 text-center text-slate-500"><i class="fa fa-spinner fa-spin"></i> Loading...</div>';

        const response = await fetch('/api/notifications');
        const data = await response.json();

        if (!response.ok || !data.success) {
            listDiv.innerHTML = '<div class="px-4 py-8 text-center text-red-500">Error loading notifications</div>';
            return;
        }

        const notifications = data.notifications || [];
        if (notifications.length === 0) {
            listDiv.innerHTML = '<div class="px-4 py-8 text-center text-slate-500">No notifications</div>';
        } else {
            listDiv.innerHTML = notifications.map(notif => {
                const href = pmNotificationHref(notif);
                const icon = pmNotificationIcon(notif.notification_type);
                const click = href
                    ? `onclick="handleNotificationClick(${notif.id}, '${href.replace(/'/g, "\\'")}')"`
                    : `onclick="markNotificationRead(${notif.id})"`;
                return `
        <div class="px-4 py-3 hover:bg-slate-50 border-b border-slate-100 cursor-pointer ${notif.read ? '' : 'bg-blue-50'}" ${click}>
          <div class="flex items-start gap-3">
            <div class="flex-shrink-0 mt-1">
              <i class="fa fa-${icon} text-indigo-600"></i>
            </div>
            <div class="flex-grow min-w-0">
              <p class="text-sm text-slate-900 ${notif.read ? '' : 'font-semibold'}">${escapeHtml(notif.message)}</p>
              <p class="text-xs text-slate-500 mt-1">${new Date(notif.created_at).toLocaleString()}</p>
            </div>
            ${!notif.read ? '<div class="flex-shrink-0 w-2 h-2 bg-blue-500 rounded-full mt-2"></div>' : ''}
          </div>
        </div>`;
            }).join('');
        }
    } catch (error) {
        console.error('Error loading notifications:', error);
        const listDiv = document.getElementById('notificationsList');
        if (listDiv) listDiv.innerHTML = '<div class="px-4 py-8 text-center text-red-500">Error loading notifications</div>';
    }
}

async function handleNotificationClick(notificationId, href) {
    try {
        await fetch(`/api/notifications/${notificationId}/read`, { method: 'PATCH' });
        loadNotificationCount();
        if (href) window.location.href = href;
    } catch (error) {
        console.error('Error handling notification click:', error);
    }
}

function toggleNotificationsDropdown() {
    const dropdown = document.getElementById('notificationsDropdown');
    if (!dropdown) return;

    window.notificationDropdownOpen = !window.notificationDropdownOpen;

    if (window.notificationDropdownOpen) {
        dropdown.classList.remove('hidden');
        loadNotifications();
    } else {
        dropdown.classList.add('hidden');
    }
}

async function markNotificationRead(notificationId) {
    try {
        const response = await fetch(`/api/notifications/${notificationId}/read`, {
            method: 'PATCH'
        });
        if (response.ok) {
            loadNotificationCount();
            loadNotifications();
        }
    } catch (error) {
        console.error('Error marking notification as read:', error);
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

window.handleNotificationClick = handleNotificationClick;
