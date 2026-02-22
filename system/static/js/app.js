/**
 * 基于曲线相似性的分布式集群异常检测系统 - 前端SPA
 * 多页面路由、ECharts可视化、全功能交互
 */

// ==================== 全局状态 ====================
let currentUser = null;
let currentDataId = null;
let currentResult = null;
let charts = {};

// ==================== API 工具 ====================
async function api(url, options = {}) {
    const defaults = { headers: { 'Content-Type': 'application/json' } };
    if (options.body && !(options.body instanceof FormData)) {
        options.body = JSON.stringify(options.body);
    } else if (options.body instanceof FormData) {
        delete defaults.headers['Content-Type'];
    }
    const resp = await fetch(url, { ...defaults, ...options });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || '请求失败');
    return data;
}

function setStatus(type, text) {
    const dot = document.querySelector('.status-dot');
    const el = document.getElementById('statusText');
    if (dot) dot.className = 'status-dot' + (type === 'loading' ? ' loading' : '');
    if (el) el.textContent = text;
}

function showToast(msg, type = 'info') {
    const t = document.createElement('div');
    t.style.cssText = `position:fixed;top:20px;right:20px;z-index:9999;padding:12px 20px;border-radius:8px;color:#fff;font-size:13px;font-weight:500;box-shadow:0 4px 12px rgba(0,0,0,0.15);animation:fadeIn 0.3s;`;
    t.style.background = type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#3b82f6';
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 3000);
}

// ==================== 认证 ====================
async function handleLogin(e) {
    e.preventDefault();
    const username = document.getElementById('loginUsername').value;
    const password = document.getElementById('loginPassword').value;
    try {
        const data = await api('/api/auth/login', {
            method: 'POST', body: { username, password }
        });
        currentUser = data.user;
        showApp();
    } catch (err) {
        document.getElementById('loginError').textContent = err.message;
    }
}

async function checkAuth() {
    try {
        currentUser = await api('/api/auth/me');
        showApp();
    } catch (e) {
        showLogin();
    }
}

function showLogin() {
    document.getElementById('loginPage').style.display = 'flex';
    document.getElementById('appMain').style.display = 'none';
}

function showApp() {
    document.getElementById('loginPage').style.display = 'none';
    document.getElementById('appMain').style.display = 'flex';
    document.getElementById('currentUserName').textContent = currentUser.display_name || currentUser.username;
    initRouter();
    startClock();
    loadAlertBadge();
}

async function handleLogout() {
    await api('/api/auth/logout', { method: 'POST' });
    currentUser = null;
    showLogin();
}

// ==================== 路由 ====================
const pages = {
    dashboard: { title: '系统仪表盘', render: renderDashboard },
    data: { title: '数据管理', render: renderDataPage },
    detection: { title: '异常检测', render: renderDetectionPage },
    visualization: { title: '可视化分析', render: renderVisualizationPage },
    clusters: { title: '集群管理', render: renderClustersPage },
    alerts: { title: '告警管理', render: renderAlertsPage },
    users: { title: '用户管理', render: renderUsersPage },
    history: { title: '检测历史', render: renderHistoryPage },
};

function initRouter() {
    window.addEventListener('hashchange', onRoute);
    onRoute();
}

function onRoute() {
    const hash = (location.hash || '#dashboard').substring(1);
    const page = pages[hash] || pages.dashboard;
    document.querySelectorAll('.nav-item').forEach(n => {
        n.classList.toggle('active', n.dataset.page === hash);
    });
    document.getElementById('pageTitle').textContent = page.title;
    Object.values(charts).forEach(c => { try { c.dispose(); } catch(e){} });
    charts = {};
    page.render(document.getElementById('pageContent'));
}

function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('collapsed');
    document.getElementById('sidebar').classList.toggle('open');
}

function startClock() {
    const el = document.getElementById('datetime');
    function tick() {
        const d = new Date();
        el.textContent = d.getFullYear() + '-' +
            String(d.getMonth()+1).padStart(2,'0') + '-' +
            String(d.getDate()).padStart(2,'0') + ' ' +
            String(d.getHours()).padStart(2,'0') + ':' +
            String(d.getMinutes()).padStart(2,'0');
    }
    tick(); setInterval(tick, 30000);
}

async function loadAlertBadge() {
    try {
        const stats = await api('/api/alerts/stats');
        const badge = document.getElementById('alertBadge');
        if (stats.pending > 0) {
            badge.textContent = stats.pending;
            badge.style.display = 'block';
        } else {
            badge.style.display = 'none';
        }
    } catch(e) {}
}

// ==================== 仪表盘页 ====================
async function renderDashboard(container) {
    container.innerHTML = '<div class="stats-grid" id="dashStats"></div><div class="chart-row" id="dashCharts"></div><div id="dashRecent"></div>';
    try {
        const d = await api('/api/dashboard');
        document.getElementById('dashStats').innerHTML = `
            <div class="stat-card"><div class="stat-icon blue"><i class="ri-search-eye-line"></i></div><div class="stat-info"><div class="stat-value">${d.total_tasks}</div><div class="stat-label">检测任务总数</div></div></div>
            <div class="stat-card"><div class="stat-icon green"><i class="ri-check-double-line"></i></div><div class="stat-info"><div class="stat-value">${d.completed_tasks}</div><div class="stat-label">已完成任务</div></div></div>
            <div class="stat-card"><div class="stat-icon purple"><i class="ri-database-2-line"></i></div><div class="stat-info"><div class="stat-value">${d.total_datasets}</div><div class="stat-label">数据集</div></div></div>
            <div class="stat-card"><div class="stat-icon orange"><i class="ri-server-line"></i></div><div class="stat-info"><div class="stat-value">${d.active_clusters}</div><div class="stat-label">活跃集群</div></div></div>
            <div class="stat-card"><div class="stat-icon red"><i class="ri-alarm-warning-line"></i></div><div class="stat-info"><div class="stat-value">${d.pending_alerts}</div><div class="stat-label">待处理告警</div></div></div>
            <div class="stat-card"><div class="stat-icon blue"><i class="ri-team-line"></i></div><div class="stat-info"><div class="stat-value">${d.total_users}</div><div class="stat-label">系统用户</div></div></div>
        `;

        let taskHtml = '<div class="panel"><div class="panel-header"><div class="panel-title"><i class="ri-time-line"></i> 最近检测任务</div></div><div class="panel-body">';
        if (d.recent_tasks && d.recent_tasks.length > 0) {
            taskHtml += '<table class="data-table"><thead><tr><th>ID</th><th>类型</th><th>场景</th><th>状态</th><th>节点数</th><th>异常数</th><th>时间</th></tr></thead><tbody>';
            d.recent_tasks.forEach(t => {
                const statusBadge = t.status === 'completed' ? 'badge-success' : t.status === 'failed' ? 'badge-danger' : 'badge-warning';
                taskHtml += `<tr><td>#${t.task_id}</td><td>${t.task_type === 'scheduled' ? '定时巡检' : '手动检测'}</td><td>${t.scenario || '-'}</td><td><span class="badge ${statusBadge}">${t.status}</span></td><td>${t.n_nodes || '-'}</td><td>${t.n_anomaly || 0}</td><td>${t.started_at || '-'}</td></tr>`;
            });
            taskHtml += '</tbody></table>';
        } else {
            taskHtml += '<div class="empty-state"><i class="ri-inbox-line"></i><p>暂无检测记录</p></div>';
        }
        taskHtml += '</div></div>';
        document.getElementById('dashRecent').innerHTML = taskHtml;

    } catch(e) {
        container.innerHTML = '<div class="empty-state"><i class="ri-error-warning-line"></i><p>加载仪表盘失败: ' + e.message + '</p></div>';
    }
}

// ==================== 数据管理页 ====================
async function renderDataPage(container) {
    container.innerHTML = `
        <div class="panel">
            <div class="panel-header">
                <div class="panel-title"><i class="ri-upload-cloud-2-line"></i> 上传数据</div>
            </div>
            <div class="panel-body">
                <div class="upload-zone" id="uploadZone">
                    <i class="ri-file-upload-line"></i>
                    <p>拖拽文件到此处，或点击选择文件</p>
                    <p class="hint">支持 CSV、JSON 格式，最大 50MB</p>
                    <input type="file" id="fileInput" accept=".csv,.json" hidden>
                </div>
            </div>
        </div>
        <div class="panel">
            <div class="panel-header">
                <div class="panel-title"><i class="ri-cloud-line"></i> Prometheus API 数据接入</div>
                <span class="badge badge-info">常态化监控</span>
            </div>
            <div class="panel-body">
                <p style="color:#64748b;font-size:13px;margin-bottom:12px;">
                    <i class="ri-information-line"></i> 通过 Prometheus HTTP API 实时接入集群监控数据，支持 PromQL 查询表达式。
                </p>
                <div class="form-row">
                    <div class="form-group" style="flex:2;">
                        <label class="form-label">Prometheus 地址</label>
                        <input id="promUrl" class="form-input" placeholder="http://prometheus-server:9090" value="">
                    </div>
                    <div class="form-group" style="flex:2;">
                        <label class="form-label">PromQL 查询</label>
                        <input id="promQuery" class="form-input" placeholder="node_cpu_seconds_total{mode='idle'}">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">起始时间</label>
                        <input id="promStart" type="datetime-local" class="form-input">
                    </div>
                    <div class="form-group">
                        <label class="form-label">结束时间</label>
                        <input id="promEnd" type="datetime-local" class="form-input">
                    </div>
                    <div class="form-group">
                        <label class="form-label">采样步长</label>
                        <select id="promStep" class="form-select">
                            <option value="15s">15秒</option>
                            <option value="30s">30秒</option>
                            <option value="60s" selected>1分钟</option>
                            <option value="300s">5分钟</option>
                        </select>
                    </div>
                </div>
                <div style="display:flex;gap:8px;align-items:center;">
                    <button class="btn btn-primary btn-sm" onclick="loadPrometheusData()"><i class="ri-download-cloud-2-line"></i> 拉取数据</button>
                    <button class="btn btn-outline btn-sm" onclick="testPrometheusConn()"><i class="ri-link"></i> 测试连接</button>
                    <span id="promStatus" style="font-size:12px;color:#64748b;"></span>
                </div>
            </div>
        </div>
        <div class="panel">
            <div class="panel-header">
                <div class="panel-title"><i class="ri-database-2-line"></i> 数据集列表</div>
                <button class="btn btn-outline btn-sm" onclick="renderDataPage(document.getElementById('pageContent'))"><i class="ri-refresh-line"></i> 刷新</button>
            </div>
            <div class="panel-body" id="datasetList"></div>
        </div>
    `;
    const zone = document.getElementById('uploadZone');
    const input = document.getElementById('fileInput');
    zone.addEventListener('click', () => input.click());
    zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('dragover'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
    zone.addEventListener('drop', e => { e.preventDefault(); zone.classList.remove('dragover'); if(e.dataTransfer.files.length) doUpload(e.dataTransfer.files[0]); });
    input.addEventListener('change', () => { if(input.files.length) doUpload(input.files[0]); });

    const now = new Date();
    const oneHourAgo = new Date(now.getTime() - 3600000);
    const fmt = d => d.toISOString().slice(0,16);
    const promStart = document.getElementById('promStart');
    const promEnd = document.getElementById('promEnd');
    if (promStart) promStart.value = fmt(oneHourAgo);
    if (promEnd) promEnd.value = fmt(now);

    try {
        const datasets = await api('/api/datasets');
        const el = document.getElementById('datasetList');
        if (datasets.length === 0) {
            el.innerHTML = '<div class="empty-state"><i class="ri-inbox-line"></i><p>暂无数据集，请上传文件或加载演示数据</p></div>';
        } else {
            let html = '<table class="data-table"><thead><tr><th>ID</th><th>名称</th><th>来源</th><th>指标数</th><th>节点数</th><th>时间步</th><th>上传者</th><th>时间</th><th>操作</th></tr></thead><tbody>';
            datasets.forEach(ds => {
                html += `<tr><td>${ds.dataset_id}</td><td>${ds.name}</td><td><span class="badge badge-info">${ds.source}</span></td><td>${ds.n_metrics}</td><td>${ds.n_nodes}</td><td>${ds.n_timestamps}</td><td>${ds.uploaded_by || '-'}</td><td>${ds.uploaded_at || '-'}</td><td><button class="btn btn-danger btn-sm" onclick="deleteDataset(${ds.dataset_id})"><i class="ri-delete-bin-line"></i></button></td></tr>`;
            });
            html += '</tbody></table>';
            el.innerHTML = html;
        }
    } catch(e) {
        document.getElementById('datasetList').innerHTML = '<p>加载失败</p>';
    }
}

async function doUpload(file) {
    setStatus('loading', '上传中...');
    const fd = new FormData();
    fd.append('file', file);
    try {
        const data = await api('/api/upload', { method: 'POST', body: fd });
        currentDataId = data.data_id;
        showToast('数据上传成功: ' + data.filename, 'success');
        setStatus('ready', '数据已加载');
        renderDataPage(document.getElementById('pageContent'));
    } catch(e) {
        showToast('上传失败: ' + e.message, 'error');
        setStatus('ready', '就绪');
    }
}

async function deleteDataset(id) {
    if (!confirm('确定删除该数据集？')) return;
    try {
        await api('/api/datasets/' + id, { method: 'DELETE' });
        showToast('已删除', 'success');
        renderDataPage(document.getElementById('pageContent'));
    } catch(e) { showToast(e.message, 'error'); }
}

async function loadPrometheusData() {
    const url = document.getElementById('promUrl').value;
    const query = document.getElementById('promQuery').value;
    const start = document.getElementById('promStart').value;
    const end = document.getElementById('promEnd').value;
    const step = document.getElementById('promStep').value;

    if (!url || !query) {
        showToast('请填写 Prometheus 地址和 PromQL 查询', 'error');
        return;
    }

    const statusEl = document.getElementById('promStatus');
    statusEl.innerHTML = '<span style="color:#f59e0b;">拉取中...</span>';
    setStatus('loading', '拉取Prometheus数据...');

    try {
        const data = await api('/api/prometheus', {
            method: 'POST',
            body: { url, query, start, end, step }
        });
        currentDataId = data.data_id;
        statusEl.innerHTML = `<span style="color:#10b981;"><i class="ri-check-line"></i> 成功加载 ${data.n_nodes} 个节点，${data.n_timestamps} 个时间步</span>`;
        showToast('Prometheus 数据加载成功', 'success');
        setStatus('ready', '数据已加载');
        renderDataPage(document.getElementById('pageContent'));
    } catch(e) {
        statusEl.innerHTML = `<span style="color:#ef4444;"><i class="ri-close-line"></i> ${e.message}</span>`;
        showToast('Prometheus 数据拉取失败: ' + e.message, 'error');
        setStatus('ready', '就绪');
    }
}

async function testPrometheusConn() {
    const url = document.getElementById('promUrl').value;
    if (!url) { showToast('请填写 Prometheus 地址', 'error'); return; }
    const statusEl = document.getElementById('promStatus');
    statusEl.innerHTML = '<span style="color:#f59e0b;">测试连接中...</span>';
    setTimeout(() => {
        statusEl.innerHTML = '<span style="color:#f59e0b;"><i class="ri-information-line"></i> 连接测试需要后端服务支持，请确保 Prometheus 地址可访问后直接拉取数据</span>';
    }, 1000);
}

// ==================== 异常检测页 ====================
async function renderDetectionPage(container) {
    let datasetsHtml = '<option value="">-- 请选择数据集 --</option>';
    try {
        const datasets = await api('/api/datasets');
        datasets.forEach(ds => {
            const selected = currentDataId === `ds_${ds.dataset_id}` ? 'selected' : '';
            datasetsHtml += `<option value="${ds.dataset_id}" ${selected}>${ds.name} (${ds.n_nodes}节点, ${ds.n_timestamps}步, ${ds.source})</option>`;
        });
    } catch(e) {}

    container.innerHTML = `
        <div class="two-col">
            <div class="col-side">
                <div class="panel">
                    <div class="panel-header"><div class="panel-title"><i class="ri-settings-3-line"></i> 检测配置</div></div>
                    <div class="panel-body">
                        <div class="form-group">
                            <label class="form-label">数据来源</label>
                            <select id="datasetSelect" class="form-select" onchange="onDatasetSelect(this.value)">
                                ${datasetsHtml}
                            </select>
                            <div style="display:flex;gap:8px;margin-top:8px;">
                                <button class="btn btn-outline btn-sm" onclick="loadDemoData()"><i class="ri-play-circle-line"></i> 演示数据</button>
                                <button class="btn btn-outline btn-sm" onclick="location.hash='data'"><i class="ri-upload-2-line"></i> 去上传</button>
                            </div>
                            <p class="form-hint" id="dataStatus">${currentDataId ? '当前数据: ' + currentDataId : '请选择数据集或加载演示数据'}</p>
                        </div>
                        <div class="form-group">
                            <label class="form-label">检测场景</label>
                            <select id="scenarioSelect" class="form-select" onchange="onScenarioChange()">
                                <option value="auto">自动判断</option>
                                <option value="single">单指标多节点（CSAD-AT框架）</option>
                                <option value="multi">多指标多节点（双视角融合）</option>
                            </select>
                        </div>
                        <div id="singleParams">
                            <div class="form-group">
                                <label class="form-label">滑动窗口大小</label>
                                <input type="number" id="windowSize" value="60" min="5" max="500" class="form-input">
                                <p class="form-hint">建议不超过数据时间步长度的1/3</p>
                            </div>
                            <div class="form-group">
                                <label class="form-label">检测方法</label>
                                <div class="checkbox-group">
                                    <label class="checkbox-label"><input type="checkbox" value="euclidean" checked> 欧氏距离相似性</label>
                                    <label class="checkbox-label"><input type="checkbox" value="autoencoder" checked> 自编码器嵌入</label>
                                    <label class="checkbox-label"><input type="checkbox" value="dbscan" checked> DBSCAN聚类</label>
                                </div>
                            </div>
                            <div class="form-row">
                                <div class="form-group">
                                    <label class="form-label">DBSCAN eps</label>
                                    <input type="number" id="dbscanEps" value="0.5" step="0.1" class="form-input">
                                </div>
                                <div class="form-group">
                                    <label class="form-label">I-SPOT q</label>
                                    <input type="number" id="ispotQ" value="0.001" step="0.001" class="form-input">
                                </div>
                            </div>
                        </div>
                        <div id="multiParams" style="display:none;">
                            <div class="form-row">
                                <div class="form-group">
                                    <label class="form-label">数值权重</label>
                                    <input type="number" id="wNum" value="0.5" step="0.1" min="0" max="1" class="form-input">
                                </div>
                                <div class="form-group">
                                    <label class="form-label">形状权重</label>
                                    <input type="number" id="wShape" value="0.5" step="0.1" min="0" max="1" class="form-input">
                                </div>
                            </div>
                            <div class="form-group">
                                <label class="form-label">SAX字母表大小</label>
                                <input type="number" id="alphabetSize" value="7" min="3" max="20" class="form-input">
                            </div>
                        </div>
                        <button class="btn btn-primary btn-block" onclick="runDetection()" id="detectBtn" ${currentDataId ? '' : 'disabled'} style="margin-top:12px;">
                            <i class="ri-search-eye-line"></i> 开始检测
                        </button>
                    </div>
                </div>
                <div class="panel">
                    <div class="panel-header">
                        <div class="panel-title"><i class="ri-cloud-line"></i> Prometheus 实时接入</div>
                        <span class="badge badge-info">常态化监控</span>
                    </div>
                    <div class="panel-body">
                        <p style="color:#64748b;font-size:12px;margin-bottom:10px;">
                            通过 Prometheus HTTP API 实时拉取集群运行指标数据，接入后可直接执行异常检测。
                        </p>
                        <div class="form-group">
                            <label class="form-label">Prometheus 地址</label>
                            <input id="detectPromUrl" class="form-input" placeholder="http://prometheus:9090">
                        </div>
                        <div class="form-group">
                            <label class="form-label">PromQL 查询表达式</label>
                            <input id="detectPromQuery" class="form-input" placeholder="node_cpu_seconds_total{mode='idle'}">
                        </div>
                        <div class="form-row">
                            <div class="form-group">
                                <label class="form-label">时间范围</label>
                                <select id="detectPromRange" class="form-select">
                                    <option value="30">最近30分钟</option>
                                    <option value="60" selected>最近1小时</option>
                                    <option value="180">最近3小时</option>
                                    <option value="360">最近6小时</option>
                                    <option value="720">最近12小时</option>
                                    <option value="1440">最近24小时</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label class="form-label">步长</label>
                                <select id="detectPromStep" class="form-select">
                                    <option value="15s">15秒</option>
                                    <option value="60s" selected>1分钟</option>
                                    <option value="300s">5分钟</option>
                                </select>
                            </div>
                        </div>
                        <button class="btn btn-outline btn-block btn-sm" onclick="loadPromDetectionData()">
                            <i class="ri-download-cloud-2-line"></i> 拉取并加载数据
                        </button>
                        <p class="form-hint" id="promDetectStatus"></p>
                    </div>
                </div>
            </div>
            <div class="col-main">
                <div id="detectionResults">
                    <div class="panel"><div class="panel-body"><div class="empty-state"><i class="ri-bar-chart-box-line"></i><p>配置参数并点击"开始检测"查看结果</p></div></div></div>
                </div>
            </div>
        </div>
    `;
}

async function onDatasetSelect(datasetId) {
    if (!datasetId) return;
    setStatus('loading', '加载数据集...');
    const statusEl = document.getElementById('dataStatus');
    try {
        const data = await api(`/api/datasets/${datasetId}/load`, { method: 'POST' });
        currentDataId = data.data_id;
        if (statusEl) statusEl.textContent = `已加载: ${data.name} (${data.n_nodes}节点, ${data.n_timestamps}时间步)`;
        const btn = document.getElementById('detectBtn');
        if (btn) btn.disabled = false;
        showToast(`数据集 "${data.name}" 加载成功`, 'success');
        setStatus('ready', '数据已加载');
    } catch(e) {
        if (statusEl) statusEl.textContent = '加载失败: ' + e.message;
        showToast('数据集加载失败: ' + e.message, 'error');
        setStatus('ready', '就绪');
    }
}

async function loadPromDetectionData() {
    const url = document.getElementById('detectPromUrl').value;
    const query = document.getElementById('detectPromQuery').value;
    const range = parseInt(document.getElementById('detectPromRange').value);
    const step = document.getElementById('detectPromStep').value;

    if (!url || !query) {
        showToast('请填写 Prometheus 地址和 PromQL 查询', 'error');
        return;
    }

    const now = new Date();
    const start = new Date(now.getTime() - range * 60000);
    const statusEl = document.getElementById('promDetectStatus');
    statusEl.innerHTML = '<span style="color:#f59e0b;">拉取中...</span>';
    setStatus('loading', '拉取Prometheus数据...');

    try {
        const data = await api('/api/prometheus', {
            method: 'POST',
            body: { url, query, start: start.toISOString(), end: now.toISOString(), step }
        });
        currentDataId = data.data_id;
        statusEl.innerHTML = `<span style="color:#10b981;"><i class="ri-check-line"></i> 已加载 ${data.n_nodes} 节点 / ${data.n_timestamps} 时间步</span>`;
        const btn = document.getElementById('detectBtn');
        if (btn) btn.disabled = false;
        const ds = document.getElementById('dataStatus');
        if (ds) ds.textContent = `已加载Prometheus数据 (${data.n_nodes}节点, ${data.n_timestamps}步)`;
        showToast('Prometheus 数据加载成功', 'success');
        setStatus('ready', '数据已加载');
    } catch(e) {
        statusEl.innerHTML = `<span style="color:#ef4444;">${e.message}</span>`;
        showToast(e.message, 'error');
        setStatus('ready', '就绪');
    }
}

function onScenarioChange() {
    const v = document.getElementById('scenarioSelect').value;
    const sp = document.getElementById('singleParams');
    const mp = document.getElementById('multiParams');
    if (sp) sp.style.display = (v === 'multi') ? 'none' : 'block';
    if (mp) mp.style.display = (v === 'multi' || v === 'auto') ? 'block' : 'none';
    if (v === 'auto' && sp) sp.style.display = 'block';
}

async function loadDemoData() {
    setStatus('loading', '生成演示数据...');
    try {
        const data = await api('/api/demo');
        currentDataId = data.data_id;
        const ds = document.getElementById('dataStatus');
        if (ds) ds.textContent = '已加载演示数据 (15节点, 500时间步)';
        const btn = document.getElementById('detectBtn');
        if (btn) btn.disabled = false;
        const sel = document.getElementById('datasetSelect');
        if (sel) sel.value = '';
        showToast('演示数据加载成功', 'success');
        setStatus('ready', '数据已加载');
    } catch(e) {
        showToast('加载失败: ' + e.message, 'error');
        setStatus('ready', '就绪');
    }
}

async function runDetection() {
    if (!currentDataId) { showToast('请先加载数据', 'error'); return; }
    setStatus('loading', '检测中...');
    const btn = document.getElementById('detectBtn');
    if (btn) btn.disabled = true;

    const scenario = document.getElementById('scenarioSelect').value;
    const methods = [];
    document.querySelectorAll('.checkbox-group input:checked').forEach(cb => methods.push(cb.value));

    const config = {
        window_size: parseInt(document.getElementById('windowSize')?.value || 60),
        methods: methods,
        dbscan_eps: parseFloat(document.getElementById('dbscanEps')?.value || 0.5),
        ispot_q: parseFloat(document.getElementById('ispotQ')?.value || 0.001),
        w_num: parseFloat(document.getElementById('wNum')?.value || 0.5),
        w_shape: parseFloat(document.getElementById('wShape')?.value || 0.5),
        alphabet_size: parseInt(document.getElementById('alphabetSize')?.value || 7),
        threshold: 3.0,
    };

    try {
        const result = await api('/api/detect', {
            method: 'POST',
            body: { data_id: currentDataId, scenario, config }
        });
        currentResult = result;
        renderDetectionResults(result);
        setStatus('ready', '检测完成');
        showToast('检测完成，发现 ' + (result.anomaly_nodes?.length || 0) + ' 个异常节点', 'success');
    } catch(e) {
        showToast('检测失败: ' + e.message, 'error');
        setStatus('ready', '就绪');
    }
    if (btn) btn.disabled = false;
}

// ==================== 检测结果展示（重构） ====================
function renderDetectionResults(result) {
    const el = document.getElementById('detectionResults');
    if (!el) return;

    const nodeNames = result.node_names || [];
    const anomalyNodes = result.anomaly_nodes || [];
    const anomalySegments = result.anomaly_segments || [];
    const isSingle = result.scenario === 'single_metric';

    let html = '';

    // Warning
    if (result.warning) {
        html += `<div class="panel" style="border-left:4px solid #f59e0b;"><div class="panel-body" style="padding:12px;"><span style="color:#f59e0b;font-size:13px;"><i class="ri-error-warning-line"></i> ${result.warning}</span></div></div>`;
    }

    // Summary cards
    html += '<div class="result-grid">';
    html += `<div class="result-card"><div class="val">${nodeNames.length}</div><div class="lbl">监控节点</div></div>`;
    html += `<div class="result-card"><div class="val">${result.n_metrics || 1}</div><div class="lbl">监控指标</div></div>`;
    html += `<div class="result-card"><div class="val">${isSingle ? 'CSAD-AT' : '双视角融合'}</div><div class="lbl">检测框架</div></div>`;
    html += `<div class="result-card"><div class="val danger">${anomalyNodes.length}</div><div class="lbl">异常节点</div></div>`;
    html += `<div class="result-card"><div class="val danger">${anomalySegments.length}</div><div class="lbl">异常片段</div></div>`;
    html += '</div>';

    if (isSingle) {
        // 单指标场景：展示集成决策信息 + 异常片段
        if (result.ensemble) {
            const nMethods = Object.keys(result.methods || {}).length;
            html += `<div class="panel"><div class="panel-header"><div class="panel-title"><i class="ri-shield-check-line"></i> 集成决策结果</div></div><div class="panel-body">`;
            html += `<p style="color:#64748b;font-size:13px;">
                采用 <strong>${nMethods}</strong> 种检测方法（${Object.keys(result.methods || {}).join('、')}），
                经 I-SPOT 自适应阈值 + 保守集成（逻辑与）决策。
                只有所有方法同时判定异常的时间窗口才被确认为异常。
            </p>`;
            html += '</div></div>';
        }

        // 异常片段图表：每个片段显示该时间窗口的曲线
        if (anomalySegments.length > 0 && result.chart_data) {
            html += '<div class="panel"><div class="panel-header"><div class="panel-title"><i class="ri-alarm-warning-line"></i> 异常时间片段</div></div><div class="panel-body">';
            anomalySegments.forEach((seg, idx) => {
                const timeInfo = seg.start_time ? ` (${fmtTimeFull(seg.start_time)} ~ ${fmtTimeFull(seg.end_time)})` : ` (窗口 ${seg.start} ~ ${seg.end})`;
                html += `<div class="anomaly-segment-card" style="margin-bottom:16px;padding:12px;border:1px solid #e2e8f0;border-radius:8px;border-left:4px solid #ef4444;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                        <span style="font-weight:600;color:#1e293b;"><i class="ri-error-warning-fill" style="color:#ef4444;"></i> ${seg.node} ${timeInfo}</span>
                        <span class="badge badge-danger">持续 ${seg.duration || (seg.end - seg.start)} 个窗口</span>
                    </div>
                    <div id="segChart_${idx}" style="width:100%;height:200px;"></div>
                </div>`;
            });
            html += '</div></div>';
        } else if (anomalySegments.length > 0) {
            // 无chart_data时显示列表
            html += '<div class="panel"><div class="panel-header"><div class="panel-title"><i class="ri-alarm-warning-line"></i> 异常时间片段</div></div><div class="panel-body">';
            anomalySegments.forEach(seg => {
                const timeInfo = seg.start_time ? `${fmtTimeFull(seg.start_time)} ~ ${fmtTimeFull(seg.end_time)}` : `窗口 ${seg.start} ~ ${seg.end}`;
                html += `<div class="anomaly-item"><span class="node-name"><i class="ri-error-warning-fill"></i> ${seg.node}</span><span class="score-badge">${timeInfo} (${seg.duration || (seg.end - seg.start)} 窗口)</span></div>`;
            });
            html += '</div></div>';
        }

    } else {
        // 多指标场景：保留分数排名柱状图
        html += '<div class="chart-row"><div class="panel" style="flex:1;"><div class="panel-header"><div class="panel-title"><i class="ri-bar-chart-horizontal-line"></i> 融合异常分数排名</div></div><div class="panel-body"><div id="scoreChart" class="chart-container"></div></div></div></div>';
    }

    // 正常/异常总结
    if (anomalyNodes.length === 0) {
        html += '<div class="panel"><div class="panel-body" style="text-align:center;padding:24px;"><span style="color:#10b981;font-weight:600;font-size:15px;"><i class="ri-checkbox-circle-fill"></i> 所有节点正常，未检测到异常</span></div></div>';
    }

    el.innerHTML = html;

    // 渲染图表
    setTimeout(() => {
        if (isSingle && anomalySegments.length > 0 && result.chart_data) {
            renderAnomalySegmentCharts(result, anomalySegments);
        }
        if (!isSingle) {
            renderMultiMetricScoreChart(result);
        }
    }, 100);
}

/**
 * 为每个异常片段渲染独立的时间窗口曲线图
 * 只展示异常时间窗口范围内的数据，并高亮异常节点
 */
function renderAnomalySegmentCharts(result, segments) {
    if (!result.chart_data) return;
    const fm = Object.keys(result.chart_data)[0];
    if (!fm) return;
    const chartData = result.chart_data[fm];
    const allTimestamps = chartData.timestamps || [];
    const allNodes = chartData.nodes || {};
    const windowSize = result.window_size || 60;

    segments.forEach((seg, idx) => {
        const el = document.getElementById('segChart_' + idx);
        if (!el) return;

        const chart = echarts.init(el);
        charts['seg_' + idx] = chart;

        // 计算该片段在原始数据中的范围
        // seg.start / seg.end 是窗口索引，映射到原始时间需要加上 window_size-1
        const dataStart = Math.max(0, seg.start);
        const dataEnd = Math.min(allTimestamps.length, seg.end + windowSize);

        const sliceTs = allTimestamps.slice(dataStart, dataEnd);
        const anomNodeName = seg.node;

        // 构建 series：异常节点用红色粗线，其他节点用淡色细线作为对比背景
        const series = [];
        const nodeKeys = Object.keys(allNodes);

        // 先画其他节点（背景参考）
        nodeKeys.forEach(name => {
            if (name === anomNodeName) return;
            const sliceData = allNodes[name].slice(dataStart, dataEnd);
            series.push({
                name: name, type: 'line', data: sliceData,
                showSymbol: false,
                lineStyle: { width: 0.8, opacity: 0.2, color: '#94a3b8' },
                itemStyle: { color: '#94a3b8' },
                z: 1,
            });
        });

        // 再画异常节点（前景高亮）
        if (allNodes[anomNodeName]) {
            const sliceData = allNodes[anomNodeName].slice(dataStart, dataEnd);
            series.push({
                name: anomNodeName + ' (异常)', type: 'line', data: sliceData,
                showSymbol: false,
                lineStyle: { width: 2.5, color: '#ef4444' },
                itemStyle: { color: '#ef4444' },
                z: 10,
                areaStyle: { color: 'rgba(239,68,68,0.08)' },
            });
        }

        chart.setOption({
            tooltip: { trigger: 'axis', confine: true },
            legend: { show: false },
            grid: { left: 50, right: 16, top: 10, bottom: 24 },
            xAxis: {
                type: 'category',
                data: sliceTs.map(t => fmtTime(t)),
                axisLabel: { fontSize: 10 },
            },
            yAxis: { type: 'value', axisLabel: { fontSize: 10 } },
            series: series,
        }, true);

        window.addEventListener('resize', () => chart.resize());
    });
}

/**
 * 多指标场景的融合分数排名柱状图
 */
function renderMultiMetricScoreChart(result) {
    const el = document.getElementById('scoreChart');
    if (!el) return;
    const chart = echarts.init(el);
    charts.score = chart;

    const names = result.node_names || [];
    const scores = result.fused_scores || result.node_scores || [];
    const threshold = result.threshold || 3.0;
    const anomSet = new Set(result.anomaly_nodes || []);

    // 按分数排序
    const indexed = names.map((n, i) => ({ name: n, score: scores[i] || 0 }));
    indexed.sort((a, b) => b.score - a.score);

    chart.setOption({
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        grid: { left: 80, right: 40, top: 10, bottom: 20 },
        xAxis: { type: 'value', axisLabel: { fontSize: 10 } },
        yAxis: { type: 'category', data: indexed.map(d => d.name).reverse(), axisLabel: { fontSize: 10 } },
        series: [{
            type: 'bar', barMaxWidth: 18,
            data: indexed.map(d => ({
                value: d.score.toFixed(4),
                itemStyle: { color: anomSet.has(d.name) ? '#ef4444' : '#4f46e5' }
            })).reverse(),
            markLine: {
                silent: true, symbol: 'none',
                lineStyle: { color: '#ef4444', type: 'dashed', width: 2 },
                label: { formatter: 'T=' + threshold, fontSize: 10 },
                data: [{ xAxis: threshold }]
            }
        }]
    }, true);
    window.addEventListener('resize', () => chart.resize());
}

// ==================== 可视化分析页（重构：只展示异常时间片段） ====================
function renderVisualizationPage(container) {
    if (!currentResult) {
        container.innerHTML = '<div class="panel"><div class="panel-body"><div class="empty-state"><i class="ri-line-chart-line"></i><p>请先在"异常检测"页面执行检测后查看可视化结果</p></div></div></div>';
        return;
    }

    const anomalySegments = currentResult.anomaly_segments || [];
    const anomalyNodes = currentResult.anomaly_nodes || [];
    const nodeNames = currentResult.node_names || [];
    const isSingle = currentResult.scenario === 'single_metric';

    let html = '';

    // 顶部概览
    html += '<div class="result-grid">';
    html += `<div class="result-card"><div class="val">${nodeNames.length}</div><div class="lbl">总节点数</div></div>`;
    html += `<div class="result-card"><div class="val danger">${anomalyNodes.length}</div><div class="lbl">异常节点</div></div>`;
    html += `<div class="result-card"><div class="val danger">${anomalySegments.length}</div><div class="lbl">异常片段</div></div>`;
    html += `<div class="result-card"><div class="val">${isSingle ? 'CSAD-AT' : '双视角融合'}</div><div class="lbl">检测框架</div></div>`;
    html += '</div>';

    // 节点状态饼图
    html += '<div class="chart-row">';
    html += '<div class="panel" style="flex:1;"><div class="panel-header"><div class="panel-title"><i class="ri-pie-chart-line"></i> 节点状态分布</div></div><div class="panel-body"><div id="vizPie" class="chart-container-sm"></div></div></div>';

    // 异常节点列表
    html += '<div class="panel" style="flex:2;"><div class="panel-header"><div class="panel-title"><i class="ri-alarm-warning-line"></i> 异常节点清单</div></div><div class="panel-body">';
    if (anomalyNodes.length > 0) {
        // 按节点分组统计异常片段
        const nodeSegCount = {};
        anomalySegments.forEach(seg => {
            nodeSegCount[seg.node] = (nodeSegCount[seg.node] || 0) + 1;
        });
        anomalyNodes.forEach(name => {
            const segCount = nodeSegCount[name] || 0;
            html += `<div class="anomaly-item" style="margin-bottom:6px;"><span class="node-name"><i class="ri-error-warning-fill" style="color:#ef4444;"></i> ${name}</span><span class="score-badge">${segCount} 个异常片段</span></div>`;
        });
    } else {
        html += '<div style="text-align:center;padding:20px;color:#10b981;font-weight:600;"><i class="ri-checkbox-circle-fill"></i> 所有节点正常</div>';
    }
    html += '</div></div></div>';

    // 异常时间片段详情（核心可视化）
    if (anomalySegments.length > 0) {
        html += '<div class="panel"><div class="panel-header"><div class="panel-title"><i class="ri-focus-3-line"></i> 异常时间片段详细视图</div><span class="badge badge-danger">' + anomalySegments.length + ' 个片段</span></div><div class="panel-body">';

        anomalySegments.forEach((seg, idx) => {
            const timeInfo = seg.start_time
                ? `${fmtTimeFull(seg.start_time)} ~ ${fmtTimeFull(seg.end_time)}`
                : `窗口索引 ${seg.start} ~ ${seg.end}`;
            const duration = seg.duration || (seg.end - seg.start);

            html += `<div style="margin-bottom:20px;padding:14px;border:1px solid #e2e8f0;border-radius:10px;border-left:4px solid #ef4444;background:#fefefe;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                    <div>
                        <span style="font-weight:700;color:#1e293b;font-size:14px;"><i class="ri-error-warning-fill" style="color:#ef4444;margin-right:4px;"></i>${seg.node}</span>
                        <span style="color:#64748b;font-size:12px;margin-left:12px;">${timeInfo}</span>
                    </div>
                    <span class="badge badge-danger">持续 ${duration} 个窗口</span>
                </div>
                <div id="vizSegChart_${idx}" style="width:100%;height:220px;"></div>
            </div>`;
        });

        html += '</div></div>';
    } else {
        html += '<div class="panel"><div class="panel-body" style="text-align:center;padding:40px;"><i class="ri-checkbox-circle-fill" style="font-size:48px;color:#10b981;"></i><p style="margin-top:12px;font-size:16px;color:#10b981;font-weight:600;">检测结果正常，未发现异常时间片段</p></div></div>';
    }

    container.innerHTML = html;

    // 渲染图表
    setTimeout(() => {
        // 饼图
        const pieEl = document.getElementById('vizPie');
        if (pieEl) {
            const c = echarts.init(pieEl); charts.vizPie = c;
            const anom = anomalyNodes.length;
            const normal = nodeNames.length - anom;
            c.setOption({
                tooltip: { trigger: 'item' },
                series: [{ type: 'pie', radius: ['40%', '70%'],
                    data: [
                        { value: normal, name: '正常节点', itemStyle: { color: '#10b981' } },
                        { value: anom, name: '异常节点', itemStyle: { color: '#ef4444' } },
                    ],
                    label: { fontSize: 13 },
                }]
            }, true);
        }

        // 异常片段图表
        if (anomalySegments.length > 0 && currentResult.chart_data) {
            renderVizSegmentCharts(currentResult, anomalySegments);
        }
    }, 100);
}

/**
 * 可视化分析页的异常片段图表渲染
 * 每个异常片段单独一张图，仅展示该窗口范围的数据
 * 异常节点红色粗线，其他节点浅色细线作为对比
 */
function renderVizSegmentCharts(result, segments) {
    if (!result.chart_data) return;
    const fm = Object.keys(result.chart_data)[0];
    if (!fm) return;
    const chartData = result.chart_data[fm];
    const allTimestamps = chartData.timestamps || [];
    const allNodes = chartData.nodes || {};
    const windowSize = result.window_size || 60;

    segments.forEach((seg, idx) => {
        const el = document.getElementById('vizSegChart_' + idx);
        if (!el) return;

        const chart = echarts.init(el);
        charts['vizSeg_' + idx] = chart;

        // 片段在原始数据中的范围
        const dataStart = Math.max(0, seg.start);
        const dataEnd = Math.min(allTimestamps.length, seg.end + windowSize);

        const sliceTs = allTimestamps.slice(dataStart, dataEnd);
        const anomNodeName = seg.node;

        const series = [];
        const nodeKeys = Object.keys(allNodes);

        // 背景：其他节点淡色
        nodeKeys.forEach(name => {
            if (name === anomNodeName) return;
            const sliceData = allNodes[name].slice(dataStart, dataEnd);
            series.push({
                name: name, type: 'line', data: sliceData,
                showSymbol: false,
                lineStyle: { width: 0.8, opacity: 0.15, color: '#cbd5e1' },
                itemStyle: { color: '#cbd5e1' },
                z: 1,
            });
        });

        // 前景：异常节点红色高亮
        if (allNodes[anomNodeName]) {
            const sliceData = allNodes[anomNodeName].slice(dataStart, dataEnd);
            series.push({
                name: anomNodeName + ' (异常)', type: 'line', data: sliceData,
                showSymbol: false,
                lineStyle: { width: 2.5, color: '#ef4444' },
                itemStyle: { color: '#ef4444' },
                z: 10,
                areaStyle: { color: 'rgba(239,68,68,0.06)' },
            });
        }

        chart.setOption({
            tooltip: { trigger: 'axis', confine: true },
            legend: {
                data: [anomNodeName + ' (异常)'],
                bottom: 0, textStyle: { fontSize: 10 }
            },
            grid: { left: 50, right: 16, top: 10, bottom: 30 },
            xAxis: {
                type: 'category',
                data: sliceTs.map(t => fmtTime(t)),
                axisLabel: { fontSize: 10 },
            },
            yAxis: { type: 'value', axisLabel: { fontSize: 10 } },
            series: series,
            dataZoom: [{ type: 'inside' }],
        }, true);

        window.addEventListener('resize', () => chart.resize());
    });
}

// ==================== 集群管理页 ====================
async function renderClustersPage(container) {
    container.innerHTML = `
        <div class="panel">
            <div class="panel-header">
                <div class="panel-title"><i class="ri-server-line"></i> 集群列表</div>
                <button class="btn btn-primary btn-sm" onclick="showClusterModal()"><i class="ri-add-line"></i> 添加集群</button>
            </div>
            <div class="panel-body" id="clusterList"></div>
        </div>
        <div id="clusterModal"></div>
    `;
    try {
        const clusters = await api('/api/clusters');
        const el = document.getElementById('clusterList');
        if (clusters.length === 0) {
            el.innerHTML = '<div class="empty-state"><i class="ri-server-line"></i><p>暂无集群配置</p></div>';
        } else {
            let html = '<table class="data-table"><thead><tr><th>ID</th><th>集群名称</th><th>Prometheus</th><th>巡检间隔</th><th>检测场景</th><th>状态</th><th>操作</th></tr></thead><tbody>';
            clusters.forEach(c => {
                html += `<tr><td>${c.cluster_id}</td><td><strong>${c.cluster_name}</strong></td><td style="font-size:12px;">${c.prometheus_url}</td><td>${c.check_interval}分钟</td><td>${c.scenario_type}</td><td><span class="badge ${c.is_active ? 'badge-success' : 'badge-secondary'}">${c.is_active ? '运行中' : '已停用'}</span></td><td><button class="btn btn-danger btn-sm" onclick="deleteCluster(${c.cluster_id})"><i class="ri-delete-bin-line"></i></button></td></tr>`;
            });
            html += '</tbody></table>';
            el.innerHTML = html;
        }
    } catch(e) {
        document.getElementById('clusterList').innerHTML = '<p>加载失败</p>';
    }
}

function showClusterModal() {
    document.getElementById('clusterModal').innerHTML = `
        <div class="modal-overlay" onclick="if(event.target===this)this.innerHTML=''">
            <div class="modal">
                <div class="modal-header"><h3>添加集群</h3><button class="modal-close" onclick="this.closest('.modal-overlay').remove()">&times;</button></div>
                <div class="modal-body">
                    <div class="form-group"><label class="form-label">集群名称</label><input id="cName" class="form-input" placeholder="如: 生产集群A"></div>
                    <div class="form-group"><label class="form-label">Prometheus地址</label><input id="cUrl" class="form-input" placeholder="http://prometheus:9090"></div>
                    <div class="form-group"><label class="form-label">PromQL查询</label><input id="cQuery" class="form-input" placeholder="node_cpu_seconds_total"></div>
                    <div class="form-row">
                        <div class="form-group"><label class="form-label">巡检间隔(分钟)</label><input id="cInterval" type="number" value="5" class="form-input"></div>
                        <div class="form-group"><label class="form-label">检测场景</label><select id="cScenario" class="form-select"><option value="auto">自动</option><option value="single">单指标</option><option value="multi">多指标</option></select></div>
                    </div>
                </div>
                <div class="modal-footer"><button class="btn btn-outline" onclick="this.closest('.modal-overlay').remove()">取消</button><button class="btn btn-primary" onclick="createCluster()">创建</button></div>
            </div>
        </div>`;
}

async function createCluster() {
    try {
        await api('/api/clusters', { method: 'POST', body: {
            cluster_name: document.getElementById('cName').value,
            prometheus_url: document.getElementById('cUrl').value,
            promql_query: document.getElementById('cQuery').value,
            check_interval: parseInt(document.getElementById('cInterval').value),
            scenario_type: document.getElementById('cScenario').value,
        }});
        showToast('集群创建成功', 'success');
        renderClustersPage(document.getElementById('pageContent'));
    } catch(e) { showToast(e.message, 'error'); }
}

async function deleteCluster(id) {
    if (!confirm('确定删除该集群？')) return;
    try {
        await api('/api/clusters/' + id, { method: 'DELETE' });
        showToast('已删除', 'success');
        renderClustersPage(document.getElementById('pageContent'));
    } catch(e) { showToast(e.message, 'error'); }
}

// ==================== 告警管理页 ====================
async function renderAlertsPage(container) {
    container.innerHTML = `
        <div class="tabs" id="alertTabs">
            <button class="tab-btn active" onclick="switchAlertTab('logs')">告警日志</button>
            <button class="tab-btn" onclick="switchAlertTab('rules')">告警规则</button>
        </div>
        <div id="alertContent"></div>
        <div id="alertModal"></div>
    `;
    await loadAlertLogs();
}

async function switchAlertTab(tab) {
    document.querySelectorAll('#alertTabs .tab-btn').forEach((b,i) => b.classList.toggle('active', (tab==='logs'?i===0:i===1)));
    if (tab === 'logs') await loadAlertLogs();
    else await loadAlertRules();
}

async function loadAlertLogs() {
    try {
        const logs = await api('/api/alerts/logs');
        const el = document.getElementById('alertContent');
        if (logs.length === 0) {
            el.innerHTML = '<div class="panel"><div class="panel-body"><div class="empty-state"><i class="ri-alarm-warning-line"></i><p>暂无告警记录</p></div></div></div>';
        } else {
            let html = '<div class="panel"><div class="panel-body">';
            logs.forEach(l => {
                const levelClass = l.level === 'critical' ? 'critical' : l.level === 'warning' ? 'warning' : 'info';
                const levelText = l.level === 'critical' ? '严重' : l.level === 'warning' ? '警告' : '信息';
                html += `<div class="alert-item level-${levelClass}">
                    <div class="alert-icon ${levelClass}"><i class="ri-alarm-warning-${levelClass==='info'?'line':'fill'}"></i></div>
                    <div class="alert-content">
                        <div class="alert-title">${l.rule_name || '告警'} <span class="badge badge-${levelClass==='critical'?'danger':levelClass==='warning'?'warning':'info'}">${levelText}</span></div>
                        <div class="alert-meta">节点: ${l.node_name || '-'} | 分数: ${l.anomaly_score || '-'} | 时间: ${l.triggered_at || '-'} | 状态: ${l.status}</div>
                    </div>
                    ${l.status === 'pending' ? `<button class="btn btn-outline btn-sm" onclick="ackAlert(${l.log_id})">确认</button>` : ''}
                </div>`;
            });
            html += '</div></div>';
            el.innerHTML = html;
        }
    } catch(e) { document.getElementById('alertContent').innerHTML = '<p>加载失败</p>'; }
}

async function loadAlertRules() {
    try {
        const rules = await api('/api/alerts/rules');
        const el = document.getElementById('alertContent');
        let html = '<div class="panel"><div class="panel-header"><div class="panel-title"><i class="ri-list-settings-line"></i> 告警规则</div><button class="btn btn-primary btn-sm" onclick="showAlertRuleModal()"><i class="ri-add-line"></i> 新增规则</button></div><div class="panel-body">';
        if (rules.length === 0) {
            html += '<div class="empty-state"><p>暂无告警规则</p></div>';
        } else {
            html += '<table class="data-table"><thead><tr><th>ID</th><th>名称</th><th>级别</th><th>阈值</th><th>通知方式</th><th>状态</th><th>操作</th></tr></thead><tbody>';
            rules.forEach(r => {
                const lvl = r.level === 'critical' ? 'badge-danger' : r.level === 'warning' ? 'badge-warning' : 'badge-info';
                html += `<tr><td>${r.rule_id}</td><td>${r.rule_name}</td><td><span class="badge ${lvl}">${r.level}</span></td><td>${r.threshold}</td><td>${r.notify_type}</td><td><span class="badge ${r.is_active ? 'badge-success' : 'badge-secondary'}">${r.is_active ? '启用' : '停用'}</span></td><td><button class="btn btn-danger btn-sm" onclick="deleteAlertRule(${r.rule_id})"><i class="ri-delete-bin-line"></i></button></td></tr>`;
            });
            html += '</tbody></table>';
        }
        html += '</div></div>';
        el.innerHTML = html;
    } catch(e) { document.getElementById('alertContent').innerHTML = '<p>加载失败</p>'; }
}

function showAlertRuleModal() {
    document.getElementById('alertModal').innerHTML = `
        <div class="modal-overlay" onclick="if(event.target===this)this.innerHTML=''">
            <div class="modal">
                <div class="modal-header"><h3>新增告警规则</h3><button class="modal-close" onclick="this.closest('.modal-overlay').remove()">&times;</button></div>
                <div class="modal-body">
                    <div class="form-group"><label class="form-label">规则名称</label><input id="rName" class="form-input" placeholder="如: CPU高异常告警"></div>
                    <div class="form-row">
                        <div class="form-group"><label class="form-label">告警级别</label><select id="rLevel" class="form-select"><option value="info">信息</option><option value="warning">警告</option><option value="critical">严重</option></select></div>
                        <div class="form-group"><label class="form-label">阈值</label><input id="rThreshold" type="number" value="3.0" step="0.1" class="form-input"></div>
                    </div>
                    <div class="form-row">
                        <div class="form-group"><label class="form-label">通知方式</label><select id="rNotify" class="form-select"><option value="system">系统通知</option><option value="email">邮件</option><option value="webhook">Webhook</option></select></div>
                        <div class="form-group"><label class="form-label">通知目标</label><input id="rTarget" class="form-input" placeholder="邮箱或webhook地址"></div>
                    </div>
                </div>
                <div class="modal-footer"><button class="btn btn-outline" onclick="this.closest('.modal-overlay').remove()">取消</button><button class="btn btn-primary" onclick="createAlertRule()">创建</button></div>
            </div>
        </div>`;
}

async function createAlertRule() {
    try {
        await api('/api/alerts/rules', { method: 'POST', body: {
            rule_name: document.getElementById('rName').value,
            level: document.getElementById('rLevel').value,
            threshold: parseFloat(document.getElementById('rThreshold').value),
            notify_type: document.getElementById('rNotify').value,
            notify_target: document.getElementById('rTarget').value,
        }});
        showToast('规则创建成功', 'success');
        await loadAlertRules();
        document.querySelector('.modal-overlay')?.remove();
    } catch(e) { showToast(e.message, 'error'); }
}

async function deleteAlertRule(id) {
    if (!confirm('确定删除该规则？')) return;
    try {
        await api('/api/alerts/rules/' + id, { method: 'DELETE' });
        showToast('已删除', 'success');
        await loadAlertRules();
    } catch(e) { showToast(e.message, 'error'); }
}

async function ackAlert(id) {
    try {
        await api('/api/alerts/logs/' + id + '/ack', { method: 'POST' });
        showToast('已确认', 'success');
        await loadAlertLogs();
        loadAlertBadge();
    } catch(e) { showToast(e.message, 'error'); }
}

// ==================== 用户管理页 ====================
async function renderUsersPage(container) {
    container.innerHTML = `
        <div class="panel">
            <div class="panel-header">
                <div class="panel-title"><i class="ri-team-line"></i> 用户列表</div>
                <button class="btn btn-primary btn-sm" onclick="showUserModal()"><i class="ri-add-line"></i> 添加用户</button>
            </div>
            <div class="panel-body" id="userList"></div>
        </div>
        <div id="userModal"></div>
    `;
    try {
        const users = await api('/api/users');
        const el = document.getElementById('userList');
        let html = '<table class="data-table"><thead><tr><th>ID</th><th>用户名</th><th>显示名</th><th>角色</th><th>状态</th><th>最后登录</th><th>操作</th></tr></thead><tbody>';
        users.forEach(u => {
            html += `<tr><td>${u.user_id}</td><td>${u.username}</td><td>${u.display_name}</td><td><span class="badge ${u.role==='admin'?'badge-info':'badge-secondary'}">${u.role}</span></td><td><span class="badge ${u.is_active?'badge-success':'badge-danger'}">${u.is_active?'正常':'禁用'}</span></td><td>${u.last_login || '从未'}</td><td><button class="btn btn-danger btn-sm" onclick="deleteUser(${u.user_id})"><i class="ri-delete-bin-line"></i></button></td></tr>`;
        });
        html += '</tbody></table>';
        el.innerHTML = html;
    } catch(e) {
        document.getElementById('userList').innerHTML = '<div class="empty-state"><p>需要管理员权限</p></div>';
    }
}

function showUserModal() {
    document.getElementById('userModal').innerHTML = `
        <div class="modal-overlay" onclick="if(event.target===this)this.innerHTML=''">
<div class="modal">
                <div class="modal-header"><h3>添加用户</h3><button class="modal-close" onclick="this.closest('.modal-overlay').remove()">&times;</button></div>
                <div class="modal-body">
                    <div class="form-group"><label class="form-label">用户名</label><input id="uName" class="form-input"></div>
                    <div class="form-group"><label class="form-label">密码</label><input id="uPass" type="password" class="form-input"></div>
                    <div class="form-group"><label class="form-label">显示名称</label><input id="uDisplay" class="form-input"></div>
                    <div class="form-group"><label class="form-label">角色</label><select id="uRole" class="form-select"><option value="user">普通用户</option><option value="admin">管理员</option></select></div>
                </div>
                <div class="modal-footer"><button class="btn btn-outline" onclick="this.closest('.modal-overlay').remove()">取消</button><button class="btn btn-primary" onclick="createUser()">创建</button></div>
            </div>
        </div>`;
}

async function createUser() {
    try {
        await api('/api/users', { method: 'POST', body: {
            username: document.getElementById('uName').value,
            password: document.getElementById('uPass').value,
            display_name: document.getElementById('uDisplay').value,
            role: document.getElementById('uRole').value,
        }});
        showToast('用户创建成功', 'success');
        renderUsersPage(document.getElementById('pageContent'));
    } catch(e) { showToast(e.message, 'error'); }
}

async function deleteUser(id) {
    if (!confirm('确定删除该用户？')) return;
    try {
        await api('/api/users/' + id, { method: 'DELETE' });
        showToast('已删除', 'success');
        renderUsersPage(document.getElementById('pageContent'));
    } catch(e) { showToast(e.message, 'error'); }
}

// ==================== 检测历史页 ====================
async function renderHistoryPage(container) {
    container.innerHTML = `
        <div class="panel">
            <div class="panel-header">
                <div class="panel-title"><i class="ri-history-line"></i> 检测任务历史</div>
                <button class="btn btn-outline btn-sm" onclick="renderHistoryPage(document.getElementById('pageContent'))"><i class="ri-refresh-line"></i> 刷新</button>
            </div>
            <div class="panel-body" id="historyList"></div>
        </div>
    `;
    try {
        const tasks = await api('/api/detection/tasks');
        const el = document.getElementById('historyList');
        if (tasks.length === 0) {
            el.innerHTML = '<div class="empty-state"><i class="ri-history-line"></i><p>暂无检测记录</p></div>';
        } else {
            let html = '<table class="data-table"><thead><tr><th>任务ID</th><th>类型</th><th>场景</th><th>数据源</th><th>状态</th><th>节点数</th><th>异常数</th><th>最高分数</th><th>开始时间</th><th>结束时间</th></tr></thead><tbody>';
            tasks.forEach(t => {
                const sb = t.status === 'completed' ? 'badge-success' : t.status === 'failed' ? 'badge-danger' : 'badge-warning';
                html += `<tr><td>#${t.task_id}</td><td>${t.task_type === 'scheduled' ? '定时巡检' : '手动检测'}</td><td>${t.scenario || '-'}</td><td>${t.data_source || '-'}</td><td><span class="badge ${sb}">${t.status}</span></td><td>${t.n_nodes || '-'}</td><td>${t.n_anomaly || 0}</td><td>${t.max_score || '-'}</td><td>${t.started_at || '-'}</td><td>${t.finished_at || '-'}</td></tr>`;
            });
            html += '</tbody></table>';
            el.innerHTML = html;
        }
    } catch(e) {
        document.getElementById('historyList').innerHTML = '<p>加载失败</p>';
    }
}

// ==================== 工具函数 ====================
function fmtTime(t) {
    try {
        const d = new Date(t);
        if (isNaN(d.getTime())) return String(t);
        return d.getHours() + ':' + String(d.getMinutes()).padStart(2, '0');
    } catch(e) { return String(t); }
}

function fmtTimeFull(t) {
    try {
        const d = new Date(t);
        if (isNaN(d.getTime())) return String(t);
        return (d.getMonth()+1) + '/' + d.getDate() + ' ' +
            String(d.getHours()).padStart(2,'0') + ':' +
            String(d.getMinutes()).padStart(2,'0') + ':' +
            String(d.getSeconds()).padStart(2,'0');
    } catch(e) { return String(t); }
}

// ==================== 启动 ====================
document.addEventListener('DOMContentLoaded', checkAuth);
