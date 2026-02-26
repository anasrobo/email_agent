/* ═══════════════════════════════════════════════════════════════
   Notification Prioritization Engine — Live Dashboard Script
   ═══════════════════════════════════════════════════════════════ */

const REFRESH_INTERVAL = 5000;
let allNotifications = [];
let currentFilter    = 'ALL';

// ─── Preset Templates ──────────────────────────────────────────
const PRESETS = {
    otp: {
        sender:  'security@bank.com',
        subject: 'Your OTP is 445566',
        body:    'Use OTP 445566 to complete your login. Valid for 5 minutes. Do not share this with anyone.',
    },
    server: {
        sender:  'alerts@monitoring.io',
        subject: 'URGENT: Server is down — zone-A',
        body:    'Critical alert: server srv-42 in zone-A is unreachable. Uptime check failed at 19:45 IST. Please investigate immediately.',
    },
    meeting: {
        sender:  'manager@company.com',
        subject: 'Team Meeting — Sprint Planning on Friday',
        body:    'Hi team, we have a sprint planning meeting on Friday at 3:00 PM in Room 4B. Agenda: review Q1 backlog and assign tasks for next sprint. Please come prepared.',
    },
    zoom: {
        sender:  'noreply@zoom.us',
        subject: 'Meeting Invite: Product Review — Wednesday at 11 AM',
        body:    'You are invited to the Product Review meeting on Wednesday at 11:00 AM IST. Join via Zoom: https://zoom.us/j/123456789. Topic: Q1 product roadmap discussion.',
    },
    reminder: {
        sender:  'hr@company.com',
        subject: 'Reminder: Submit your timesheet by EOD',
        body:    'This is a reminder to submit your timesheet for this week. Deadline: today by 6:00 PM.',
    },
    promo: {
        sender:  'deals@shopnow.com',
        subject: 'Flat 70% OFF — Summer Sale ends tonight!',
        body:    'Hurry! Our biggest sale of the year ends at midnight. Shop now and save on electronics, clothing, and more. Use code SUMMER70 for extra discount.',
    },
};

function loadPreset(key) {
    const p = PRESETS[key];
    if (!p) return;
    document.getElementById('sim-sender').value  = p.sender;
    document.getElementById('sim-subject').value = p.subject;
    document.getElementById('sim-body').value    = p.body;
}

// ─── Filter ───────────────────────────────────────────────────
function setFilter(filter, btn) {
    currentFilter = filter;
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    renderCards(allNotifications);
}

function applyFilter(notifications) {
    if (currentFilter === 'ALL') return notifications;
    if (currentFilter === 'MEETING') return notifications.filter(n => n.is_meeting);
    return notifications.filter(n => n.decision === currentFilter);
}

// ─── Stats ───────────────────────────────────────────────────
function updateStats(notifications) {
    const total = notifications.length;
    const now   = notifications.filter(n => n.decision === 'NOW').length;
    const later = notifications.filter(n => n.decision === 'LATER').length;
    const never = notifications.filter(n => n.decision === 'NEVER').length;

    setNum('cnt-total', total);
    setNum('cnt-now',   now);
    setNum('cnt-later', later);
    setNum('cnt-never', never);
}

function setNum(id, val) {
    document.getElementById(id).textContent = val;
}

// ─── Card Builder ─────────────────────────────────────────────
function escapeHtml(s) {
    const d = document.createElement('div');
    d.textContent = s || '';
    return d.innerHTML;
}

function formatTime(iso) {
    if (!iso) return '—';
    try {
        const d = new Date(iso);
        return d.toLocaleString('en-IN', {
            hour: '2-digit', minute: '2-digit',
            day: 'numeric', month: 'short', year: 'numeric',
            hour12: true
        });
    } catch { return iso; }
}

function buildDecisionMeta(n) {
    const map = {
        NOW:   { label: '🔴 VERY IMPORTANT',   cls: 'now'   },
        LATER: { label: '🟡 IMPORTANT / LATER', cls: 'later' },
        NEVER: { label: '⚪ IGNORE',            cls: 'never' },
    };
    return map[n.decision] || { label: n.decision, cls: 'never' };
}

function buildMeetingBlock(n) {
    if (!n.is_meeting) return '';
    const m = n;
    const hasMeetingData = m.meeting_time || m.meeting_date || m.meeting_location || m.meeting_topic;

    let rows = '';
    if (m.meeting_time) {
        rows += `<div class="meeting-detail">
            <span class="md-label">⏰ Time</span>
            <span class="md-value">${escapeHtml(m.meeting_time)}</span>
        </div>`;
    }
    if (m.meeting_date) {
        rows += `<div class="meeting-detail">
            <span class="md-label">📅 Date</span>
            <span class="md-value">${escapeHtml(m.meeting_date)}</span>
        </div>`;
    }
    if (m.meeting_location) {
        const loc = m.meeting_location;
        const isLink = loc.startsWith('http');
        const locHtml = isLink
            ? `<a href="${escapeHtml(loc)}" target="_blank" style="color:var(--meeting)">${escapeHtml(loc)}</a>`
            : escapeHtml(loc);
        rows += `<div class="meeting-detail">
            <span class="md-label">📍 Location</span>
            <span class="md-value">${locHtml}</span>
        </div>`;
    }
    if (m.meeting_topic) {
        rows += `<div class="meeting-detail meeting-topic-row">
            <span class="md-label">📝 Topic / Agenda</span>
            <span class="md-value">${escapeHtml(m.meeting_topic)}</span>
        </div>`;
    }

    if (!hasMeetingData) {
        rows = `<span style="color:var(--meeting);opacity:.7;font-size:.8rem;">
            Meeting detected — no structured time/location found in body.
        </span>`;
    }

    return `<div class="meeting-block">
        <div class="meeting-block-header">
            <span>📅</span>
            <span>Meeting Details</span>
        </div>
        <div class="meeting-grid">
            ${rows}
        </div>
    </div>`;
}

function buildCard(n, idx) {
    const dm = buildDecisionMeta(n);
    const cardId = `card-${idx}`;
    const hasBody = n.body_preview && n.body_preview.trim().length > 10;

    const bodyToggle = hasBody ? `
        <button class="body-preview-toggle" onclick="toggleBody('${cardId}')">
            Show email body ▾
        </button>
        <div class="body-preview-text" id="${cardId}-body">
${escapeHtml(n.body_preview)}
        </div>
    ` : '';

    return `
    <div class="notif-card ${dm.cls}">
        <div class="card-header">
            <div class="card-subject">${escapeHtml(n.subject)}</div>
            <span class="badge ${dm.cls}">${dm.label}</span>
        </div>
        <div class="card-meta">
            <span>📧 ${escapeHtml(n.sender)}</span>
            <span>🕐 ${formatTime(n.time)}</span>
            ${n.decision === 'LATER' ? `<span style="color:var(--later);">Decision: LATER (Deferred)</span>` : ''}
            ${n.decision === 'NOW'   ? `<span style="color:var(--now);">Decision: SEND NOW</span>` : ''}
            ${n.decision === 'NEVER' ? `<span style="color:var(--never);">Decision: SUPPRESSED</span>` : ''}
        </div>
        <div class="card-reason">
            <strong>Reason:</strong> ${escapeHtml(n.reason)}
        </div>
        ${buildMeetingBlock(n)}
        ${bodyToggle}
    </div>`;
}

function toggleBody(cardId) {
    const el   = document.getElementById(`${cardId}-body`);
    const btn  = el.previousElementSibling;
    const open = el.style.display === 'block';
    el.style.display = open ? 'none' : 'block';
    btn.textContent  = open ? 'Show email body ▾' : 'Hide email body ▴';
}

// ─── Render Cards ─────────────────────────────────────────────
function renderCards(notifications) {
    const container = document.getElementById('cards-container');
    const filtered  = applyFilter(notifications);

    if (filtered.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">📭</div>
                <h3>${currentFilter === 'ALL' ? 'No emails processed yet' : 'No emails in this category'}</h3>
                <p>Use the Simulate panel above, or configure Gmail credentials to see live emails.</p>
            </div>`;
        return;
    }

    container.innerHTML = filtered
        .map((n, i) => buildCard(n, i))
        .join('');
}

// ─── Fetch & Refresh ─────────────────────────────────────────
function fetchAndRender() {
    fetch('/api/notifications')
        .then(r => r.json())
        .then(notifications => {
            allNotifications = notifications;
            updateStats(notifications);
            renderCards(notifications);
            document.getElementById('refresh-status').textContent =
                `Last updated: ${new Date().toLocaleTimeString()}`;
        })
        .catch(err => {
            console.error('Fetch error:', err);
            document.getElementById('refresh-status').textContent = 'Connection error';
        });
}

// ─── Simulate Email ───────────────────────────────────────────
function simulateEmail() {
    const sender  = document.getElementById('sim-sender').value.trim();
    const subject = document.getElementById('sim-subject').value.trim();
    const body    = document.getElementById('sim-body').value.trim();
    const btn     = document.getElementById('sim-btn');

    if (!subject) {
        alert('Please enter a subject.');
        return;
    }

    btn.textContent = '…';
    btn.disabled = true;

    fetch('/api/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sender, subject, body }),
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            fetchAndRender();
        } else {
            alert('Simulation failed: ' + JSON.stringify(data));
        }
    })
    .catch(err => {
        console.error('Simulation error:', err);
        alert('Request failed. See console for details.');
    })
    .finally(() => {
        btn.textContent = '▶ Send';
        btn.disabled = false;
    });
}

// ─── Boot ─────────────────────────────────────────────────────
fetchAndRender();
setInterval(fetchAndRender, REFRESH_INTERVAL);
