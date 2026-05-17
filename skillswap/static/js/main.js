/* filepath: skillswap/static/js/main.js */

/* ── Theme toggle ─────────────────────────────────────────────────────────── */
(function () {
  const html = document.documentElement;
  const icon = document.getElementById('themeIcon');
  const btn  = document.getElementById('themeToggle');
  const saved = localStorage.getItem('ss-theme') || 'light';
  html.setAttribute('data-bs-theme', saved);
  if (icon) icon.className = saved === 'dark' ? 'bi bi-sun-fill' : 'bi bi-moon-stars-fill';
  if (btn) {
    btn.addEventListener('click', () => {
      const next = html.getAttribute('data-bs-theme') === 'dark' ? 'light' : 'dark';
      html.setAttribute('data-bs-theme', next);
      localStorage.setItem('ss-theme', next);
      if (icon) icon.className = next === 'dark' ? 'bi bi-sun-fill' : 'bi bi-moon-stars-fill';
    });
  }
})();

/* ── Bootstrap toast auto-show ───────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.toast').forEach(el => {
    new bootstrap.Toast(el, { delay: 4500 }).show();
  });
});

/* ── Mobile filter sidebar toggle ────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  const btn  = document.getElementById('filterToggleBtn');
  const body = document.getElementById('filterSidebarBody');
  if (btn && body) {
    btn.addEventListener('click', () => {
      body.classList.toggle('open');
      const isOpen = body.classList.contains('open');
      btn.innerHTML = isOpen
        ? '<i class="bi bi-funnel-fill"></i> Фільтри ▲'
        : '<i class="bi bi-funnel"></i> Фільтри ▼';
    });
  }
});

/* ── CSRF helper for fetch() ─────────────────────────────────────────────── */
function getCsrfToken() {
  return document.querySelector('input[name="csrf_token"]')?.value || '';
}

/* ── Skill autocomplete ───────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.skill-autocomplete').forEach(input => {
    const list = document.getElementById(input.getAttribute('list'));
    if (!list) return;
    let timer = null;
    input.addEventListener('input', () => {
      clearTimeout(timer);
      const q = input.value.trim();
      if (q.length < 1) { list.innerHTML = ''; return; }
      timer = setTimeout(async () => {
        try {
          const resp = await fetch(`/api/skills/autocomplete?q=${encodeURIComponent(q)}`);
          const data = await resp.json();
          list.innerHTML = data
            .map(s => `<option value="${s.title}">${s.title}${s.category ? ' · ' + s.category : ''}</option>`)
            .join('');
        } catch (_) {}
      }, 220);
    });
  });
});

/* ── Real-time notification push via Socket.IO ───────────────────────────── */
(function () {
  if (typeof io === 'undefined') return;
  try {
    const sock = io({ transports: ['websocket', 'polling'] });
    sock.on('notification', function (data) {
      // Show toast
      const container = document.querySelector('.toast-container')
        || (() => {
          const d = document.createElement('div');
          d.className = 'toast-container position-fixed bottom-0 end-0 p-3';
          d.style.zIndex = '1100';
          document.body.appendChild(d);
          return d;
        })();
      const toastEl = document.createElement('div');
      toastEl.className = 'toast align-items-center text-bg-primary border-0 show';
      toastEl.setAttribute('data-bs-autohide', 'true');
      toastEl.setAttribute('data-bs-delay', '5000');
      toastEl.innerHTML = `
        <div class="d-flex">
          <div class="toast-body fw-semibold">🔔 ${data.title}${data.body ? '<br><small>' + data.body + '</small>' : ''}</div>
          <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>`;
      container.appendChild(toastEl);
      new bootstrap.Toast(toastEl, { delay: 5000 }).show();

      // Update bell counter
      const badge = document.querySelector('.bi-bell-fill')
        ?.closest('a')?.querySelector('.badge');
      if (badge) {
        const n = parseInt(badge.textContent) || 0;
        badge.textContent = n + 1;
        badge.style.display = '';
      }
    });
  } catch (_) {}
})();
