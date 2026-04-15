'use strict';

const API = '/api';
let currentSessionId = null;
let currentProvider = 'claude';
let isBusy = false;

// ── Init ──────────────────────────────────────────────────────────────────────

async function init() {
  await loadAvailableProviders();

  const sessions = await fetchJSON(`${API}/sessions`).catch(() => []);
  const savedId = localStorage.getItem('currentSessionId');

  // Restore last active session, or fall back to most recent, or create new
  const existing = savedId && sessions.find(s => s.session_id === savedId)
    ? savedId
    : sessions[0]?.session_id;

  if (existing) {
    currentSessionId = existing;
    const session = await fetchJSON(`${API}/sessions/${existing}`).catch(() => null);
    if (session) {
      clearChat();
      for (const msg of session.messages) {
        addMessage(msg.role, msg.content);
      }
      currentProvider = localStorage.getItem(`provider_${existing}`) || session.provider || currentProvider;
      document.getElementById('provider-select').value = currentProvider;
      updateProviderBadge();
      updateCaseInfo(session);
      if (session.analysis) showAnalysis(session.analysis);
    } else {
      await startNewSession();
    }
  } else {
    await startNewSession();
  }

  await loadSessionList();
}

async function loadAvailableProviders() {
  try {
    const providers = await fetchJSON(`${API}/providers`);
    const sel = document.getElementById('provider-select');
    sel.innerHTML = '';
    if (providers.length === 0) {
      sel.innerHTML = '<option value="">未配置任何 API Key</option>';
      return;
    }
    providers.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = p.name;
      sel.appendChild(opt);
    });
    currentProvider = providers[0].id;
  } catch (e) {
    console.warn('Could not load providers', e);
  }
}

// ── Session management ────────────────────────────────────────────────────────

async function startNewSession() {
  const data = await fetchJSON(`${API}/sessions/new`, {
    method: 'POST',
    body: JSON.stringify({ provider: currentProvider }),
  });
  currentSessionId = data.session_id;
  localStorage.setItem('currentSessionId', currentSessionId);
  clearChat();
  updateCaseInfo(data.session);
  updateProviderBadge();

  // Show welcome message locally (no API call needed)
  addMessage('assistant',
    '您好，欢迎使用 Mr. Burns 合规离职顾问 ⚖️\n\n' +
    '本系统帮您依法核算应得补偿：\n• 精准计算法定赔偿金\n• 识别公司方案的不足\n• 制定合理合规的谈判策略\n\n' +
    '请先告诉我：**是公司通知您离职，还是双方"友好协商"？** 公司给出的理由是什么？'
  );

  await loadSessionList();
}

async function loadSessionList() {
  const sessions = await fetchJSON(`${API}/sessions`);
  const listEl = document.getElementById('session-list');
  if (sessions.length === 0) {
    listEl.innerHTML = '<div style="padding:8px 10px;font-size:12px;color:#94a3b8">暂无历史咨询</div>';
    return;
  }
  listEl.innerHTML = sessions.map(s => `
    <div class="session-item ${s.session_id === currentSessionId ? 'active' : ''}"
         onclick="loadSession('${s.session_id}')">
      <div class="session-title">${esc(s.case_summary || '新咨询')}</div>
      <div class="session-item-footer">
        <span class="session-date">${formatDate(s.updated_at)}</span>
        <button class="btn-delete-session" onclick="deleteSession(event, '${s.session_id}')" title="删除">✕</button>
      </div>
    </div>
  `).join('');
}

async function loadSession(sessionId) {
  if (sessionId === currentSessionId) return;
  currentSessionId = sessionId;
  localStorage.setItem('currentSessionId', currentSessionId);

  const session = await fetchJSON(`${API}/sessions/${sessionId}`);
  clearChat();

  for (const msg of session.messages) {
    addMessage(msg.role, msg.content);
  }

  currentProvider = localStorage.getItem(`provider_${sessionId}`) || session.provider || 'claude';
  document.getElementById('provider-select').value = currentProvider;
  updateProviderBadge();
  updateCaseInfo(session);

  if (session.analysis) {
    showAnalysis(session.analysis);
  } else {
    document.getElementById('analysis-panel').style.display = 'none';
  }

  await loadSessionList();
}

async function deleteSession(event, sessionId) {
  event.stopPropagation();
  if (!confirm('删除这条咨询记录？')) return;

  await fetch(`${API}/sessions/${sessionId}`, { method: 'DELETE' });
  localStorage.removeItem(`provider_${sessionId}`);

  if (sessionId === currentSessionId) {
    localStorage.removeItem('currentSessionId');
    const remaining = await fetchJSON(`${API}/sessions`).catch(() => []);
    if (remaining.length > 0) {
      await loadSession(remaining[0].session_id);
    } else {
      await startNewSession();
    }
  } else {
    await loadSessionList();
  }
}

// ── Chat ──────────────────────────────────────────────────────────────────────

async function sendMessage() {
  if (isBusy) return;
  const input = document.getElementById('user-input');
  const text = input.value.trim();
  if (!text) return;

  input.value = '';
  setInputEnabled(false);
  isBusy = true;

  addMessage('user', text);
  const botEl = addTypingIndicator();

  try {
    const resp = await fetch(`${API}/sessions/${currentSessionId}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, provider: currentProvider }),
    });

    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let botText = '';
    let isFirstChunk = true;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        let payload;
        try { payload = JSON.parse(line.slice(6)); } catch { continue; }

        if (payload.type === 'text') {
          if (isFirstChunk) {
            replaceTypingWithBubble(botEl, '');
            isFirstChunk = false;
          }
          botText += payload.content;
          updateLastBotBubble(botText);

        } else if (payload.type === 'done') {
          updateCaseInfo(payload.session);
          await loadSessionList();

        } else if (payload.type === 'error') {
          replaceTypingWithBubble(botEl, `❌ 出错了：${payload.content}`);
          isFirstChunk = false;
        }
      }
    }

    if (isFirstChunk) {
      replaceTypingWithBubble(botEl, '❌ 未收到回复，请检查服务器日志');
    }

  } catch (e) {
    replaceTypingWithBubble(botEl, `❌ 请求失败：${e.message}`);
  } finally {
    isBusy = false;
    setInputEnabled(true);
    document.getElementById('user-input').focus();
  }
}

// ── Analysis ──────────────────────────────────────────────────────────────────

async function generateAnalysis() {
  if (isBusy) return;
  isBusy = true;
  const btn = document.getElementById('generate-analysis-btn');
  btn.disabled = true;
  btn.textContent = '生成中…';

  const panel = document.getElementById('analysis-panel');
  const content = document.getElementById('analysis-content');
  panel.style.display = 'flex';
  content.innerHTML = '<div class="typing-dots"><span></span><span></span><span></span></div>';

  let fullText = '';
  try {
    const resp = await fetch(`${API}/sessions/${currentSessionId}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider: currentProvider }),
    });

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let started = false;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        let payload;
        try { payload = JSON.parse(line.slice(6)); } catch { continue; }

        if (payload.type === 'text') {
          if (!started) { content.innerHTML = ''; started = true; }
          fullText += payload.content;
          content.innerHTML = mdToHtml(fullText);
        } else if (payload.type === 'done') {
          await loadSessionList();
        } else if (payload.type === 'error') {
          content.innerHTML = `<p style="color:red">❌ ${esc(payload.content)}</p>`;
        }
      }
    }
  } catch (e) {
    content.innerHTML = `<p style="color:red">❌ 请求失败：${esc(e.message)}</p>`;
  } finally {
    isBusy = false;
    btn.disabled = false;
    btn.textContent = '更新分析报告';
  }
}

function showAnalysis(text) {
  const panel = document.getElementById('analysis-panel');
  const content = document.getElementById('analysis-content');
  panel.style.display = 'flex';
  content.innerHTML = mdToHtml(text);
}

// ── DOM helpers ───────────────────────────────────────────────────────────────

function addMessage(role, text) {
  const el = document.createElement('div');
  el.className = `message ${role}`;
  el.innerHTML = `
    <div class="msg-avatar">${role === 'user' ? '👤' : '👩‍⚖️'}</div>
    <div class="msg-bubble">${esc(text)}</div>
  `;
  document.getElementById('messages').appendChild(el);
  scrollBottom();
  return el;
}

function addTypingIndicator() {
  const el = document.createElement('div');
  el.className = 'message assistant';
  el.innerHTML = `
    <div class="msg-avatar">👩‍⚖️</div>
    <div class="msg-bubble"><div class="typing-dots"><span></span><span></span><span></span></div></div>
  `;
  document.getElementById('messages').appendChild(el);
  scrollBottom();
  return el;
}

function replaceTypingWithBubble(el, text) {
  el.querySelector('.msg-bubble').textContent = text;
  scrollBottom();
}

function updateLastBotBubble(text) {
  const bubbles = document.querySelectorAll('.message.assistant .msg-bubble');
  if (bubbles.length) {
    bubbles[bubbles.length - 1].textContent = text;
    scrollBottom();
  }
}

function clearChat() {
  document.getElementById('messages').innerHTML = '';
  document.getElementById('analysis-panel').style.display = 'none';
  resetCaseInfo();
}

function scrollBottom() {
  const m = document.getElementById('messages');
  m.scrollTop = m.scrollHeight;
}

function setInputEnabled(on) {
  document.getElementById('user-input').disabled = !on;
  document.getElementById('send-btn').disabled = !on;
}

function updateProviderBadge() {
  const names = { claude: 'Claude', minimax: 'MiniMax', qwen: 'Qwen 通义' };
  document.getElementById('provider-badge').textContent =
    names[currentProvider] || currentProvider;
}

// ── Case info panel ───────────────────────────────────────────────────────────

function updateCaseInfo(session) {
  const emp = session.employee_info || {};
  const off = session.company_offer || {};

  set('i-years',  emp.years_of_service ? `${emp.years_of_service} 年` : '—');
  set('i-salary', emp.monthly_salary   ? `${fmt(emp.monthly_salary)} 元/月` : '—');
  set('i-total',  emp.salary_12month_total ? `${fmt(emp.salary_12month_total)} 元` : '—');
  set('i-leave',  emp.unused_leave_days ? `${emp.unused_leave_days} 天` : '—');
  set('i-bonus',  emp.pending_bonus    ? `${fmt(emp.pending_bonus)} 元` : '—');
  set('i-stocks', emp.unvested_stocks_desc || '—');

  set('i-offer-desc', off.offer_description || '—');
  set('i-months', off.compensation_months ? `${off.compensation_months} 个月` : '—');
  set('i-amount', off.total_amount ? `${fmt(off.total_amount)} 元` : '—');

  const summary = session.case_summary;
  const sg = document.getElementById('summary-group');
  if (summary) {
    sg.style.display = '';
    document.getElementById('i-summary').textContent = summary;
  } else {
    sg.style.display = 'none';
  }

  if (session.case_summary) {
    document.getElementById('chat-title').textContent = summary;
  }
}

function resetCaseInfo() {
  ['i-years','i-salary','i-total','i-leave','i-bonus','i-stocks',
   'i-offer-desc','i-months','i-amount'].forEach(id => set(id, '—'));
  document.getElementById('summary-group').style.display = 'none';
  document.getElementById('chat-title').textContent = '新咨询';
}

// ── Markdown renderer (lightweight) ──────────────────────────────────────────

function mdToHtml(text) {
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    // headings
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    // bold / italic
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // table rows  |…|…|
    .replace(/^\|(.+)\|$/gm, row => {
      const cells = row.slice(1, -1).split('|').map(c => c.trim());
      if (cells.every(c => /^[-:]+$/.test(c))) return '';
      return '<tr>' + cells.map(c => `<td>${c}</td>`).join('') + '</tr>';
    })
    // wrap consecutive <tr> blocks in <table>
    .replace(/(<tr>.*?<\/tr>\s*)+/gs, match => `<table>${match}</table>`)
    // horizontal rule
    .replace(/^---+$/gm, '<hr>')
    // list items
    .replace(/^(\d+)\. (.+)$/gm, '<li>$1. $2</li>')
    .replace(/^[•\-\*] (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*?<\/li>\n?)+/gs, match => `<ul>${match}</ul>`)
    // line breaks
    .replace(/\n/g, '<br>');
}

// ── Utilities ─────────────────────────────────────────────────────────────────

function esc(str) {
  return String(str ?? '')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;');
}

function fmt(n) {
  // Strip currency symbols, commas, spaces, and Chinese units before parsing
  const num = Number(String(n ?? '').replace(/[,，￥¥元万\s]/g, ''));
  return isNaN(num) ? String(n ?? '') : num.toLocaleString('zh-CN');
}

function set(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function formatDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return `${d.getMonth()+1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2,'0')}`;
}

async function fetchJSON(url, opts = {}) {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
    ...opts,
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ── Event listeners ───────────────────────────────────────────────────────────

document.getElementById('send-btn').addEventListener('click', sendMessage);

document.getElementById('user-input').addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

document.getElementById('new-session-btn').addEventListener('click', startNewSession);

document.getElementById('generate-analysis-btn').addEventListener('click', generateAnalysis);

document.getElementById('close-analysis-btn').addEventListener('click', () => {
  document.getElementById('analysis-panel').style.display = 'none';
});

document.getElementById('provider-select').addEventListener('change', e => {
  currentProvider = e.target.value;
  updateProviderBadge();
  if (currentSessionId) {
    localStorage.setItem(`provider_${currentSessionId}`, currentProvider);
  }
});

// ── Boot ──────────────────────────────────────────────────────────────────────

init();
