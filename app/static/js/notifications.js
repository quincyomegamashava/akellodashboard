// Notification system
document.addEventListener('DOMContentLoaded', function () {
    loadNotificationCount();
    // Refresh every 30 seconds
    setInterval(loadNotificationCount, 30000);

    // Close dropdown when clicking outside
    document.addEventListener('click', function (e) {
        const container = document.getElementById('notificationBadgeContainer');
        const dropdown = document.getElementById('notificationsDropdown');
        if (container && !container.contains(e.target) && dropdown && !dropdown.classList.contains('hidden')) {
            dropdown.classList.add('hidden');
            window.notificationDropdownOpen = false;
        }
    });

    // Attach toggle function to global scope so onclick works
    window.toggleNotificationsDropdown = toggleNotificationsDropdown;
    window.markNotificationRead = markNotificationRead;
});

let notificationDropdownOpen = false;
window.notificationDropdownOpen = false;

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
            listDiv.innerHTML = notifications.map(notif => `
        <div class="px-4 py-3 hover:bg-slate-50 border-b border-slate-100 cursor-pointer ${notif.read ? '' : 'bg-blue-50'}" 
             onclick="markNotificationRead(${notif.id})">
          <div class="flex items-start gap-3">
            <div class="flex-shrink-0 mt-1">
              <i class="fa fa-${notif.notification_type === 'assignment' ? 'user-plus' : notif.notification_type && notif.notification_type.startsWith('sm_') ? 'bullhorn' : notif.notification_type && notif.notification_type.startsWith('meeting_') ? 'clipboard-list' : 'check-circle'} text-indigo-600"></i>
            </div>
            <div class="flex-grow min-w-0">
              <p class="text-sm text-slate-900 ${notif.read ? '' : 'font-semibold'}">${escapeHtml(notif.message)}</p>
              <p class="text-xs text-slate-500 mt-1">${new Date(notif.created_at).toLocaleString()}</p>
            </div>
            ${!notif.read ? '<div class="flex-shrink-0 w-2 h-2 bg-blue-500 rounded-full mt-2"></div>' : ''}
          </div>
        </div>
      `).join('');
        }
    } catch (error) {
        console.error('Error loading notifications:', error);
        const listDiv = document.getElementById('notificationsList');
        if (listDiv) listDiv.innerHTML = '<div class="px-4 py-8 text-center text-red-500">Error loading notifications</div>';
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
