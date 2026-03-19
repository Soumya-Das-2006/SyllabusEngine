/* ══════════════════════════════════════════════
   SyllabusEngine — main.js
   ══════════════════════════════════════════════ */

/* ── Global layout + nav ── */
document.addEventListener('DOMContentLoaded', () => {
  const toggle = document.getElementById('nav-toggle');
  const nav    = document.getElementById('main-nav');

  // Mobile nav toggle
  if (toggle && nav) {
    toggle.addEventListener('click', () => {
      const isOpen = nav.classList.toggle('nav-open');
      toggle.classList.toggle('is-open', isOpen);
      toggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    });
  }

  // Auto-dismiss flashes
  document.querySelectorAll('.flash').forEach(el => {
    setTimeout(() => el.remove(), 5000);
  });

  // Low data mode banner
  if (localStorage.getItem('low_data_mode') === '1') {
    const banner = document.getElementById('low-data-banner');
    if (banner) banner.removeAttribute('hidden');
  }

  // Close dropdowns / notification panel on outside click
  document.addEventListener('click', e => {
    document.querySelectorAll('.nav-dropdown.open').forEach(d => {
      if (!d.contains(e.target)) d.classList.remove('open');
    });
    const bell  = document.getElementById('notif-bell');
    const panel = document.getElementById('notif-panel');
    if (panel && bell && !bell.contains(e.target)) {
      panel.classList.remove('open');
      bell.setAttribute('aria-expanded', 'false');
    }
  });
});

// Dropdown toggle
function toggleDropdown(id) {
  const d = document.getElementById(id);
  if (!d) return;
  d.classList.toggle('open');
}

/* ── Low data mode toggle ── */
function setLowData(enabled) {
  fetch('/offline/set-mode', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled: !!enabled })
  }).then(r => r.json()).then(() => {
    localStorage.setItem('low_data_mode', enabled ? '1' : '0');
    const banner = document.getElementById('low-data-banner');
    if (banner) {
      if (enabled) banner.removeAttribute('hidden');
      else banner.setAttribute('hidden', 'hidden');
    }
  }).catch(() => {
    localStorage.setItem('low_data_mode', enabled ? '1' : '0');
    const banner = document.getElementById('low-data-banner');
    if (banner) {
      if (enabled) banner.removeAttribute('hidden');
      else banner.setAttribute('hidden', 'hidden');
    }
  });
}

/* ── Generic AJAX helper ── */
function apiPost(url, data) {
  return fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  }).then(r => r.json());
}

/* ── Confirm-delete helper ── */
function confirmDelete(url, msg) {
  if (!confirm(msg || 'Are you sure?')) return;
  apiPost(url, {}).then(d => {
    if (d.ok) location.reload();
  });
}

/* ── Password visibility toggle ── */
function togglePasswordVisibility(fieldId) {
  const field = document.getElementById(fieldId);
  if (!field) return;
  const toggle = field.parentElement.querySelector('.password-toggle');
  if (!toggle) return;

  if (field.type === 'password') {
    field.type = 'text';
    toggle.textContent = 'Hide';
    toggle.title = 'Hide password';
  } else {
    field.type = 'password';
    toggle.textContent = 'Show';
    toggle.title = 'Show password';
  }
}

/* ── Dark mode ── */
function toggleDark() {
  fetch('/profile/toggle-dark', { method: 'POST' })
    .then(r => r.json())
    .then(d => {
      document.documentElement.setAttribute('data-theme', d.dark ? 'dark' : 'light');
      location.reload();
    });
}

/* ── Notifications ── */
function toggleNotifDropdown() {
  const bell  = document.getElementById('notif-bell');
  const panel = document.getElementById('notif-panel');
  if (!bell || !panel) return;
  const isOpen = panel.classList.toggle('open');
  bell.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
  if (isOpen) loadNotifications();
}

function loadNotifications() {
  fetch('/notifications/api')
    .then(r => r.json())
    .then(items => {
      const list = document.getElementById('notif-list-items');
      if (!list) return;
      if (!items.length) {
        list.innerHTML = '<div class="notif-empty">No unread notifications</div>';
        return;
      }
      list.innerHTML = items.map(n => (
        '<div class="notif-item" onclick="openNotif(' + n.id + ',\'' + (n.link || '') + '\')">'
        + '<div class="notif-title">' + escHtml(n.title) + '</div>'
        + (n.message ? '<div class="notif-body">' + escHtml(n.message) + '</div>' : '')
        + '<div class="notif-time">' + n.time + '</div>'
        + '</div>'
      )).join('');
    }).catch(() => {});
}

function openNotif(id, link) {
  fetch('/notifications/mark-read/' + id, { method: 'POST' });
  const badge = document.getElementById('notif-badge');
  if (badge) {
    const current = parseInt(badge.textContent, 10) - 1;
    if (current <= 0) badge.remove();
    else badge.textContent = String(current);
  }
  const panel = document.getElementById('notif-panel');
  if (panel) panel.classList.remove('open');
  const bell = document.getElementById('notif-bell');
  if (bell) bell.setAttribute('aria-expanded', 'false');
  if (link) window.location = link;
}

function markAllRead(e) {
  if (e && e.stopPropagation) e.stopPropagation();
  fetch('/notifications/mark-all-read', { method: 'POST' })
    .then(() => {
      const badge = document.getElementById('notif-badge');
      if (badge) badge.remove();
      document.querySelectorAll('.notif-item').forEach(el => {
        el.style.opacity = '.6';
      });
    });
}

function escHtml(t) {
  return String(t)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}
