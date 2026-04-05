/* DUT Project Hub — main.js */

// ── Notifications ─────────────────────────────────────────────────────────────
async function loadNotifications() {
  try {
    const res = await fetch('/notifications/api/recent');
    if (!res.ok) return;
    const notifs = await res.json();
    const badge = document.getElementById('notifBadge');
    const list  = document.getElementById('notifList');
    const empty = document.getElementById('notifEmpty');

    if (notifs.length > 0) {
      badge.textContent = notifs.length;
      badge.classList.remove('d-none');
      if (empty) empty.remove();

      // Colour-code the dot by notification type
      const dotColor = {
        'info':    '#3b82f6',
        'success': '#10b981',
        'warning': '#f59e0b',   // amber — used for task-due reminders
        'danger':  '#ef4444',
      };

      list.innerHTML = notifs.map(n => {
        const color = dotColor[n.type] || dotColor['info'];
        const isWarning = n.type === 'warning';
        return `
          <form action="/notifications/${n.id}/read" method="post" style="margin:0">
            <button type="submit"
                    class="notif-item unread w-100 border-0 text-start bg-transparent"
                    style="${isWarning ? 'background:#fffbeb!important' : ''}">
              <span class="notif-dot mt-1" style="background:${color}"></span>
              <div>
                <div style="font-size:.82rem;font-weight:600;color:#1a2035">
                  ${isWarning ? '⏰ ' : ''}${escHtml(n.title)}
                </div>
                <div style="font-size:.78rem;color:#6b7280">${escHtml(n.message)}</div>
                <div style="font-size:.72rem;color:#9ca3af;margin-top:2px">${n.created_at}</div>
              </div>
            </button>
          </form>
        `;
      }).join('');
    } else {
      badge.classList.add('d-none');
    }
  } catch (e) {}
}

function escHtml(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// Poll every 60s
if (document.getElementById('notifBtn')) {
  loadNotifications();
  setInterval(loadNotifications, 60000);
}

// ── Auto-dismiss alerts ───────────────────────────────────────────────────────
document.querySelectorAll('.alert').forEach(el => {
  setTimeout(() => {
    const bs = bootstrap.Alert.getOrCreateInstance(el);
    bs.close();
  }, 5000);
});

// ── Confirm Delete ────────────────────────────────────────────────────────────
document.querySelectorAll('[data-confirm]').forEach(el => {
  el.addEventListener('click', function(e) {
    if (!confirm(this.dataset.confirm || 'Are you sure?')) {
      e.preventDefault();
    }
  });
});

// ── Progress Animation ────────────────────────────────────────────────────────
document.querySelectorAll('.progress-bar').forEach(bar => {
  const target = bar.getAttribute('aria-valuenow');
  bar.style.width = '0%';
  setTimeout(() => {
    bar.style.transition = 'width 0.8s ease';
    bar.style.width = target + '%';
  }, 200);
});

// ── Character Counter for Textareas ──────────────────────────────────────────
document.querySelectorAll('textarea[maxlength]').forEach(ta => {
  const max = ta.getAttribute('maxlength');
  const counter = document.createElement('small');
  counter.className = 'text-muted d-block text-end mt-1';
  counter.textContent = `0 / ${max}`;
  ta.parentNode.insertBefore(counter, ta.nextSibling);
  ta.addEventListener('input', () => {
    counter.textContent = `${ta.value.length} / ${max}`;
  });
});

// ── Tooltip Init ──────────────────────────────────────────────────────────────
document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => {
  new bootstrap.Tooltip(el);
});

// ── Search debounce ───────────────────────────────────────────────────────────
let searchTimeout;
const searchInput = document.getElementById('projectSearch');
if (searchInput) {
  searchInput.addEventListener('input', function() {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      const form = this.closest('form');
      if (form) form.submit();
    }, 500);
  });
}

// ── Collapsible Milestones ────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Sync chevron rotation with Bootstrap collapse state
  document.querySelectorAll('[data-bs-toggle="collapse"][data-bs-target^="#milestoneBody"]').forEach(header => {
    const targetId = header.getAttribute('data-bs-target');
    const body     = document.querySelector(targetId);
    const chevron  = header.querySelector('.milestone-chevron');
    if (!body || !chevron) return;

    // Set initial chevron state from aria-expanded
    const isOpen = header.getAttribute('aria-expanded') !== 'false';
    chevron.style.transform = isOpen ? 'rotate(0deg)' : 'rotate(-90deg)';

    body.addEventListener('show.bs.collapse',  () => { chevron.style.transform = 'rotate(0deg)'; });
    body.addEventListener('hide.bs.collapse',  () => { chevron.style.transform = 'rotate(-90deg)'; });
  });

  // "Expand All" / "Collapse All" buttons (if present)
  const btnExpandAll   = document.getElementById('expandAllMilestones');
  const btnCollapseAll = document.getElementById('collapseAllMilestones');

  if (btnExpandAll) {
    btnExpandAll.addEventListener('click', () => {
      document.querySelectorAll('[id^="milestoneBody"]').forEach(el => {
        bootstrap.Collapse.getOrCreateInstance(el).show();
      });
    });
  }
  if (btnCollapseAll) {
    btnCollapseAll.addEventListener('click', () => {
      document.querySelectorAll('[id^="milestoneBody"]').forEach(el => {
        bootstrap.Collapse.getOrCreateInstance(el).hide();
      });
    });
  }
});
