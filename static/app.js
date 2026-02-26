/* ═══════════════════════════════════════════════════════════════
   Notification Prioritization Engine — Frontend Logic
   ═══════════════════════════════════════════════════════════════ */

let llmFailureMode = false;
let lastResults = null;

// ─── Initialization ────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    loadRules();
    loadTestEvents();
});

// ─── Toast Notifications ───────────────────────────────────────
function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast toast-${type} show`;
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// ─── Load Test Events ──────────────────────────────────────────
async function loadTestEvents() {
    try {
        const res = await fetch('/api/test-events');
        const data = await res.json();
        const events = data.test_events || [];
        document.getElementById('eventsEditor').value = JSON.stringify(events, null, 2);
        showToast(`Loaded ${events.length} test events`, 'success');
    } catch (err) {
        showToast('Failed to load test events', 'error');
    }
}

// ─── Load Stress Test ──────────────────────────────────────────
async function loadStressTest() {
    try {
        const res = await fetch('/api/test-events');
        const data = await res.json();
        const events = data.stress_test_events || [];
        document.getElementById('eventsEditor').value = JSON.stringify(events, null, 2);
        showToast(`Loaded ${events.length} stress test events`, 'warning');
    } catch (err) {
        showToast('Failed to load stress test events', 'error');
    }
}

// ─── Load Rules ────────────────────────────────────────────────
async function loadRules() {
    try {
        const res = await fetch('/api/rules');
        const data = await res.json();
        document.getElementById('rulesEditor').value = JSON.stringify(data, null, 2);
    } catch (err) {
        showToast('Failed to load rules', 'error');
    }
}

// ─── Save Rules ────────────────────────────────────────────────
async function saveRules() {
    const editor = document.getElementById('rulesEditor');
    try {
        const rules = JSON.parse(editor.value);
        const res = await fetch('/api/rules', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(rules),
        });
        const data = await res.json();
        if (res.ok) {
            showToast('✅ Rules saved & reloaded', 'success');
        } else {
            showToast(`Error: ${data.error}`, 'error');
        }
    } catch (err) {
        showToast(`Invalid JSON: ${err.message}`, 'error');
    }
}

// ─── Toggle LLM Failure ───────────────────────────────────────
async function toggleLLMFailure() {
    llmFailureMode = !llmFailureMode;
    const btn = document.getElementById('llmToggle');
    const statusDot = document.querySelector('.status-dot');
    const statusText = document.querySelector('.status-indicator span:last-child');

    try {
        const res = await fetch('/api/simulate-failure', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: llmFailureMode }),
        });
        const data = await res.json();

        if (llmFailureMode) {
            btn.classList.add('active');
            statusDot.classList.remove('active');
            statusDot.classList.add('failure');
            statusText.textContent = 'LLM Failure Mode';
            showToast('⚠️ LLM failure simulation ENABLED — using fallback rules', 'warning');
        } else {
            btn.classList.remove('active');
            statusDot.classList.remove('failure');
            statusDot.classList.add('active');
            statusText.textContent = 'Engine Ready';
            showToast('✅ LLM failure simulation DISABLED', 'success');
        }
    } catch (err) {
        showToast('Failed to toggle LLM failure mode', 'error');
    }
}

// ─── Process Events ────────────────────────────────────────────
async function processEvents() {
    const editor = document.getElementById('eventsEditor');
    const btn = document.getElementById('processBtn');

    let events;
    try {
        events = JSON.parse(editor.value);
        if (!Array.isArray(events)) events = [events];
    } catch (err) {
        showToast(`Invalid JSON: ${err.message}`, 'error');
        return;
    }

    btn.classList.add('loading');
    btn.disabled = true;

    try {
        const res = await fetch('/api/process', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ events }),
        });

        const data = await res.json();

        if (!res.ok) {
            showToast(`Error: ${data.error}`, 'error');
            return;
        }

        lastResults = data;
        renderResults(data);
        showToast(`Processed ${data.summary.total} events`, 'success');
    } catch (err) {
        showToast(`Request failed: ${err.message}`, 'error');
    } finally {
        btn.classList.remove('loading');
        btn.disabled = false;
    }
}

// ─── Render Results ────────────────────────────────────────────
function renderResults(data) {
    const { results, logs, summary } = data;

    // Show summary cards
    const cards = document.getElementById('summaryCards');
    cards.style.display = 'grid';
    animateCounter('countNow', summary.now);
    animateCounter('countLater', summary.later);
    animateCounter('countNever', summary.never);
    animateCounter('countTotal', summary.total);

    // Build results table
    const tbody = document.getElementById('resultsBody');
    tbody.innerHTML = '';

    results.forEach((r, i) => {
        const ev = r.input_event;
        const decision = r.decision;
        const badgeClass = `badge-${decision.toLowerCase()}`;

        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td style="color: var(--text-muted); font-weight: 600;">${i + 1}</td>
            <td class="user-cell">${ev.user_id || '—'}</td>
            <td class="type-cell">${ev.event_type || '—'}</td>
            <td class="message-cell" title="${escapeHtml(ev.message || '')}">${escapeHtml(ev.message || '—')}</td>
            <td><span class="badge ${badgeClass}">${decision}</span></td>
            <td><span class="code-tag">${r.explanation_code || '—'}</span></td>
            <td class="scheduled-cell">${r.scheduled_time ? formatTime(r.scheduled_time) : '—'}</td>
            <td style="color: var(--accent-primary); font-family: var(--font-mono); font-size: 0.75rem;">${r.matched_rule_id || '—'}</td>
        `;
        tbody.appendChild(tr);
    });

    document.getElementById('resultsPanel').style.display = 'flex';

    // Build logs
    document.getElementById('logOutput').textContent = JSON.stringify(logs, null, 2);
    document.getElementById('logsPanel').style.display = 'flex';

    // Scroll to results
    document.getElementById('summaryCards').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ─── Animate Counter ───────────────────────────────────────────
function animateCounter(elementId, target) {
    const el = document.getElementById(elementId);
    const duration = 600;
    const start = parseInt(el.textContent) || 0;
    const startTime = performance.now();

    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        // Ease out cubic
        const eased = 1 - Math.pow(1 - progress, 3);
        el.textContent = Math.round(start + (target - start) * eased);
        if (progress < 1) requestAnimationFrame(update);
    }

    requestAnimationFrame(update);
}

// ─── Export JSON ───────────────────────────────────────────────
function exportJSON() {
    if (!lastResults) {
        showToast('No results to export', 'warning');
        return;
    }

    const blob = new Blob([JSON.stringify(lastResults, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'notification_decisions.json';
    a.click();
    URL.revokeObjectURL(url);
    showToast('📦 JSON exported', 'success');
}

// ─── Utilities ─────────────────────────────────────────────────
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatTime(isoString) {
    if (!isoString || isoString === 'null') return '—';
    try {
        const d = new Date(isoString);
        return d.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            hour12: false,
        }) + ' ' + d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    } catch {
        return isoString;
    }
}
