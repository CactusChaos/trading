// --- Editor Templates ---
const templates = {
    mean_reversion: `import numpy as np

def model(prices, volumes):
    """
    Mean Reversion Strategy
    Buys when price drops below the recent moving average by 5%.
    Sells when price goes above recent moving average by 5%.
    """
    period = 20
    signals = np.zeros(len(prices))
    
    # Calculate Simple Moving Average (SMA)
    # Use convolve for fast moving average calculation
    weights = np.ones(period) / period
    sma = np.convolve(prices, weights, mode='full')[:len(prices)]
    
    for i in range(period, len(prices)):
        current_price = prices[i]
        avg_price = sma[i-1]
        
        # If current price is 5% lower than SMA -> Buy
        if current_price < avg_price * 0.95:
            signals[i] = 1 # BUY
        # If current price is 5% higher than SMA -> Sell
        elif current_price > avg_price * 1.05:
            signals[i] = -1 # SELL
            
    return signals
`,
    sma_crossover: `import numpy as np

def model(prices, volumes):
    """
    SMA Crossover Strategy
    Fast SMA crosses above Slow SMA -> Buy
    Fast SMA crosses below Slow SMA -> Sell
    """
    fast_period = 10
    slow_period = 50
    signals = np.zeros(len(prices))
    
    if len(prices) < slow_period:
        return signals
        
    fast_sma = np.convolve(prices, np.ones(fast_period)/fast_period, mode='full')[:len(prices)]
    slow_sma = np.convolve(prices, np.ones(slow_period)/slow_period, mode='full')[:len(prices)]
    
    for i in range(slow_period, len(prices)):
        # Bullish crossover
        if fast_sma[i-1] <= slow_sma[i-1] and fast_sma[i] > slow_sma[i]:
            signals[i] = 1
        # Bearish crossover
        elif fast_sma[i-1] >= slow_sma[i-1] and fast_sma[i] < slow_sma[i]:
            signals[i] = -1
            
    return signals
`,
    blank: `import numpy as np

def model(prices, volumes):
    signals = np.zeros(len(prices))
    # Write your logic here
    # signals[i] = 1 (Buy), -1 (Sell), 0 (Hold)
    return signals
`
};

// --- Globals ---
let editor = null;
let currentProjectId = null;
let currentMarketData = null; // For new project modal

// --- Init ---
document.addEventListener('DOMContentLoaded', () => {
    editor = CodeMirror.fromTextArea(document.getElementById('codeEditor'), {
        mode: 'python',
        theme: 'material-ocean',
        lineNumbers: true,
        indentUnit: 4
    });
    loadTemplate();
    fetchProjects();
});

function loadTemplate() {
    const val = document.getElementById('modelTemplate').value;
    editor.setValue(templates[val] || templates.blank);
}

function showView(viewId) {
    document.querySelectorAll('.view').forEach(v => v.classList.add('hidden', 'active'));
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.getElementById(viewId + 'View').classList.remove('hidden');
    document.getElementById(viewId + 'View').classList.add('active');
    
    if(viewId === 'dashboard') fetchProjects();
    if(viewId === 'cache') refreshCache();
}

function toggleFetchMode() {
    const mode = document.getElementById('fetchMode').value;
    document.getElementById('autoInfoDiv').classList.toggle('hidden', mode !== 'auto');
    document.getElementById('periodDiv').classList.toggle('hidden', mode !== 'period');
    document.getElementById('recentBlocksDiv').classList.toggle('hidden', mode !== 'recent');
    document.getElementById('rangeBlocksDiv').classList.toggle('hidden', mode !== 'range');
}

function togglePeriodCustom() {
    const val = document.getElementById('periodSelect').value;
    document.getElementById('periodCustom').classList.toggle('hidden', val !== 'custom');
}

// --- Cache Manager ---

function fmtBytes(b) {
    if(b < 1024) return b + ' B';
    if(b < 1024*1024) return (b/1024).toFixed(1) + ' KB';
    return (b/1024/1024).toFixed(2) + ' MB';
}

function fmtAge(ts) {
    const secs = Math.floor(Date.now()/1000 - ts);
    if(secs < 60) return secs + 's ago';
    if(secs < 3600) return Math.floor(secs/60) + 'm ago';
    if(secs < 86400) return Math.floor(secs/3600) + 'h ago';
    return Math.floor(secs/86400) + 'd ago';
}

async function refreshCache() {
    const tbody = document.getElementById('cacheTableBody');
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#888;">Loading...</td></tr>';
    const res = await fetch('/api/cache/');
    const data = await res.json();
    
    document.getElementById('cacheTotalSize').innerText =
        `${data.count} entries · ${data.total_size_mb} MB total`;
    
    tbody.innerHTML = '';
    if(data.entries.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#888;">No cached downloads yet.</td></tr>';
        return;
    }
    data.entries.forEach(e => {
        const sb = e.start_block ? `${e.start_block}` : 'latest';
        const eb = e.end_block ? `${e.end_block}` : (e.blocks ? `−${e.blocks}blks` : '?');
        const range = e.start_block ? `${sb} → ${eb}` : eb;
        tbody.innerHTML += `<tr>
            <td style="font-family:monospace;font-size:0.75rem;">${e.token_id.substring(0,12)}…</td>
            <td style="font-size:0.8rem;">${range}</td>
            <td>${e.row_count.toLocaleString()}</td>
            <td>${fmtBytes(e.file_size_bytes)}</td>
            <td>${fmtAge(e.created_at)}</td>
            <td>${fmtAge(e.last_accessed)}</td>
            <td><button class="btn" style="padding:0.2rem 0.6rem;font-size:0.75rem;background:var(--danger);" onclick="deleteCacheEntry('${e.cache_id}')">Delete</button></td>
        </tr>`;
    });
}

async function deleteCacheEntry(cacheId) {
    if(!confirm('Delete this cache entry?')) return;
    await fetch(`/api/cache/${cacheId}`, { method: 'DELETE' });
    refreshCache();
}

async function clearAllCache() {
    if(!confirm('Clear ALL cached downloads? This cannot be undone.')) return;
    await fetch('/api/cache/', { method: 'DELETE' });
    refreshCache();
}

// --- API Calls & UI Updates ---

async function fetchProjects() {
    const res = await fetch('/api/projects/');
    const projects = await res.json();
    const grid = document.getElementById('projectsGrid');
    grid.innerHTML = '';
    
    projects.forEach(p => {
        const card = document.createElement('div');
        card.className = 'project-card glass-panel';
        card.onclick = () => openProject(p.id);
        
        let tokensText = p.token_id ? `Token: ${p.token_id.substring(0,8)}...` : '';
        
        card.innerHTML = `
            <h3>${p.name}</h3>
            <p>${p.market_slug || 'Unknown Market'}</p>
            <span class="badge" style="width:fit-content">${tokensText}</span>
        `;
        grid.appendChild(card);
    });
}

function openNewProjectModal() {
    document.getElementById('newProjectModal').classList.remove('hidden');
    document.getElementById('newProjName').value = '';
    document.getElementById('marketSearch').value = '';
    document.getElementById('searchResults').innerHTML = '';
    document.getElementById('searchResults').classList.add('hidden');
    document.getElementById('selectedMarketInfo').classList.add('hidden');
    document.getElementById('btnCreateProj').disabled = true;
    currentMarketData = null;
}

function closeModal(id) {
    document.getElementById(id).classList.add('hidden');
}

async function searchMarket() {
    const q = document.getElementById('marketSearch').value;
    if(!q) return;
    
    const resBox = document.getElementById('searchResults');
    resBox.innerHTML = 'Searching...';
    resBox.classList.remove('hidden');
    
    const res = await fetch(`/api/markets/search?q=${q}`);
    const data = await res.json();
    
    resBox.innerHTML = '';
    
    if(data.length === 0) {
        resBox.innerHTML = '<div style="padding:1rem;color:#888;">No results found</div>';
        return;
    }
    
    data.slice(0, 10).forEach(m => {
        const div = document.createElement('div');
        div.className = 'search-item';
        div.innerHTML = `<div class="m-title">${m.title || m.question}</div><div class="m-slug">${m.slug}</div>`;
        div.onclick = () => selectMarketForProject(m.slug);
        resBox.appendChild(div);
    });
}

async function selectMarketForProject(slug) {
    document.getElementById('searchResults').classList.add('hidden');
    const res = await fetch(`/api/markets/${slug}`);
    if(!res.ok) return alert('Failed to fetch market details');
    
    currentMarketData = await res.json();
    
    document.getElementById('selectedMarketInfo').classList.remove('hidden');
    document.getElementById('selMarketName').innerText = currentMarketData.question;
    
    const selToken = document.getElementById('selMarketToken');
    selToken.innerHTML = '';
    
    let tokens = [];
    let outcomes = [];
    try {
        tokens = JSON.parse(currentMarketData.clobTokenIds || '[]');
        outcomes = JSON.parse(currentMarketData.outcomes || '[]');
    } catch(e) {}
    
    if(tokens.length > 0) {
        tokens.forEach((tk, idx) => {
            const opt = document.createElement('option');
            opt.value = tk;
            opt.innerText = outcomes[idx] || tk.substring(0,8)+'...';
            selToken.appendChild(opt);
        });
    }
    
    document.getElementById('btnCreateProj').disabled = false;
    if(document.getElementById('newProjName').value === '') {
        document.getElementById('newProjName').value = currentMarketData.question;
    }
}

async function createProject() {
    const name = document.getElementById('newProjName').value;
    const tokenId = document.getElementById('selMarketToken').value;
    
    const res = await fetch('/api/projects/', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            name: name,
            market_slug: currentMarketData.slug,
            token_id: tokenId
        })
    });
    
    if(res.ok) {
        closeModal('newProjectModal');
        const p = await res.json();
        openProject(p.id);
    }
}

async function openProject(id) {
    currentProjectId = id;
    const res = await fetch(`/api/projects/${id}`);
    const p = await res.json();
    
    document.getElementById('projectTitle').innerText = p.name;
    document.getElementById('projectMarket').innerText = p.market_slug;
    document.getElementById('projectToken').innerText = 'Token: ' + p.token_id.substring(0,8) + '...';
    
    // Clear results
    document.getElementById('resultsSection').classList.add('hidden');
    
    renderAttempts(p.attempts);
    renderComments(p.comments);
    
    showView('project');
    
    // Refresh editor to fix sizing
    setTimeout(() => editor.refresh(), 50);
}

function renderAttempts(attempts) {
    const list = document.getElementById('attemptsList');
    list.innerHTML = '';
    
    const sorted = attempts.sort((a,b) => new Date(b.created_at) - new Date(a.created_at));
    
    sorted.forEach(a => {
        const div = document.createElement('div');
        div.className = 'attempt-item';
        
        let statsHtml = '';
        if(a.status === 'completed' && a.results) {
            let color = a.results.total_return_pct >= 0 ? 'var(--success)' : 'var(--danger)';
            statsHtml = `<div class="stats" style="color:${color}">Ret: ${a.results.total_return_pct.toFixed(2)}% | Sharpe: ${a.results.sharpe_ratio.toFixed(2)}</div>`;
        } else if (a.status === 'failed') {
            statsHtml = `<div class="stats" style="color:var(--danger)">Failed</div>`;
        }
        
        div.innerHTML = `<h4>${a.name}</h4>${statsHtml}`;
        div.onclick = () => loadAttempt(a);
        list.appendChild(div);
    });
}

function loadAttempt(a) {
    editor.setValue(a.model_code);
    document.getElementById('attemptName').value = a.name + ' (Copy)';
    
    if(a.results && a.status === 'completed') {
        displayResults(a.results);
    } else {
        document.getElementById('resultsSection').classList.add('hidden');
    }
}

function displayResults(data) {
    document.getElementById('resultsSection').classList.remove('hidden');
    
    const retEl = document.getElementById('resReturn');
    retEl.innerText = data.total_return_pct.toFixed(2) + '%';
    retEl.className = 'val ' + (data.total_return_pct >= 0 ? 'positive' : 'negative');
    
    document.getElementById('resSharpe').innerText = data.sharpe_ratio.toFixed(2);
    document.getElementById('resDrawdown').innerText = data.max_drawdown_pct.toFixed(2) + '%';
    document.getElementById('resTrades').innerText = data.trades;
    
    document.getElementById('resChart').src = 'data:image/png;base64,' + data.chart_base64;
    
    const tbody = document.getElementById('tradeLogBody');
    tbody.innerHTML = '';
    (data.trade_log || []).forEach(t => {
        tbody.innerHTML += `<tr>
            <td>${t.step}</td>
            <td style="color:${t.type==='BUY'?'var(--success)':'var(--danger)'}">${t.type}</td>
            <td>$${t.price.toFixed(3)}</td>
            <td>${t.position.toFixed(2)}</td>
            <td>$${t.equity.toFixed(2)}</td>
        </tr>`;
    });
}

async function runBacktest() {
    const btn = document.getElementById('runBtn');
    const statusMsg = document.getElementById('runStatus');
    
    btn.innerText = 'Running...';
    btn.disabled = true;
    statusMsg.innerText = "Downloading trades via poly-trade-scan and executing model...";
    statusMsg.classList.remove('hidden');
    document.getElementById('resultsSection').classList.add('hidden');
    
    const payload = {
        name: document.getElementById('attemptName').value || 'Untitled',
        model_code: editor.getValue()
    };
    
    // 1. Create Attempt
    let res = await fetch(`/api/projects/${currentProjectId}/attempts`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    });
    
    if(!res.ok) {
        statusMsg.innerText = "Failed to create attempt.";
        btn.innerText = 'Run Backtest ⚡';
        btn.disabled = false;
        return;
    }
    
    const attempt = await res.json();
    
    // 2. Run Attempt
    let runPayload = {
        initial_capital: parseFloat(document.getElementById('initCapital').value) || 100.0,
    };
    
    const mode = document.getElementById('fetchMode')?.value || 'auto';
    if(mode === 'auto') {
        runPayload.auto_range = true;
    } else if(mode === 'period') {
        let periodVal = document.getElementById('periodSelect').value;
        if(periodVal === 'custom') {
            periodVal = document.getElementById('periodCustom').value;
        }
        runPayload.period_hours = parseFloat(periodVal) || 24;
    } else if(mode === 'recent') {
        runPayload.blocks_to_fetch = parseInt(document.getElementById('blocksFetch').value) || 5000;
    } else {
        const startB = document.getElementById('startBlock').value;
        const endB = document.getElementById('endBlock').value;
        if(startB) runPayload.start_block = parseInt(startB);
        if(endB) runPayload.end_block = parseInt(endB);
    }
    
    res = await fetch(`/api/attempts/${attempt.id}/run`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(runPayload)
    });
    
    let updatedAttempt;
    try {
        updatedAttempt = await res.json();
    } catch(e) {
        updatedAttempt = { detail: "Failed to parse server response." };
    }
    
    btn.innerText = 'Run Backtest ⚡';
    btn.disabled = false;
    
    if(!res.ok) {
        statusMsg.innerText = "Error: " + (updatedAttempt.detail || "Server request failed");
        return;
    }
    
    if(updatedAttempt.status === 'completed') {
        statusMsg.innerText = "Backtest completed!";
        displayResults(updatedAttempt.results);
    } else {
        statusMsg.innerText = "Error: " + (updatedAttempt.results?.error || "Unknown error");
    }
    
    // Reload Project to update attempts list
    openProject(currentProjectId);
}

// --- Comments ---
function renderComments(comments) {
    const list = document.getElementById('commentsList');
    list.innerHTML = '';
    comments.forEach(c => {
        const d = new Date(c.created_at).toLocaleString();
        list.innerHTML += `<div class="comment-item">
            <div><span class="author">${c.author}</span><span class="date">${d}</span></div>
            <div class="body">${c.body}</div>
        </div>`;
    });
}

async function submitComment() {
    const author = document.getElementById('commentAuthor').value;
    const body = document.getElementById('commentBody').value;
    
    if(!author || !body) return;
    
    await fetch(`/api/projects/${currentProjectId}/comments`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ author, body })
    });
    
    document.getElementById('commentBody').value = '';
    // Refresh project
    openProject(currentProjectId);
}
