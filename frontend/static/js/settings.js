/**
 * settings.js - Unified Settings Page Logic
 * Handles database connection and dashboard configuration.
 */

let isEditMode = false;
let currentSchema = null;
let allColumns = [];

// ============================================================================
// Initialization
// ============================================================================

document.addEventListener('DOMContentLoaded', async () => {
    // 0. Setup Theme (for ALL users, including admin)
    setupThemeButtons();

    // 1. Permission Check - Admin only sees theme
    const role = Auth.getRole();
    if (role === 'admin') {
        const sections = ['database-section', 'schema-section', 'dashboard-config-section'];
        sections.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.style.display = 'none';
        });
        return; // Admin only sees theme
    }

    // 2. Setup UI (manager-only)
    setupDbTypeButtons();
    setupExpressionBuilder();
    setupStatusIndicatorListeners(); // Helper to attach listeners

    // 2. Initial State
    updateEditableState();

    // 3. Load Data
    await loadConnectionStatus();
});

function setupThemeButtons() {
    // Highlight current theme
    const saved = localStorage.getItem('theme') || 'auto';
    document.querySelectorAll('.theme-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.theme === saved);
        btn.onclick = () => {
            document.querySelectorAll('.theme-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            Theme.set(btn.dataset.theme);
        };
    });
}

function setupStatusIndicatorListeners() {
    // Attach input/change listener to ALL editable inputs to update dots in real-time
    const inputs = document.querySelectorAll('input, select, textarea');
    inputs.forEach(input => {
        input.addEventListener('change', updateConfigStatusIndicators);
        input.addEventListener('input', updateConfigStatusIndicators);
    });
}

// ============================================================================
// Database Logic
// ============================================================================

let selectedDbType = null;

function setupDbTypeButtons() {
    document.querySelectorAll('.db-type-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            if (!isEditMode) return;

            document.querySelectorAll('.db-type-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            selectedDbType = btn.dataset.type;

            const pathInput = document.getElementById('db-path');
            if (pathInput) {
                pathInput.placeholder = selectedDbType === 'csv'
                    ? 'e.g., C:\\data\\financial_data.csv'
                    : 'e.g., C:\\data\\financial.db';
            }
        });
    });
}

async function connectDatabase() {
    const pathInput = document.getElementById('db-path');
    const path = pathInput ? pathInput.value.trim() : '';

    if (!selectedDbType) return showToast('Please select a database type', 'error');
    if (!path && (selectedDbType === 'sqlite' || selectedDbType === 'csv')) {
        return showToast('Please enter a database path', 'error');
    }

    const btn = document.getElementById('btn-connect');
    if (btn) btn.disabled = true;
    showToast('Connecting...', 'info');

    try {
        const result = await API.post('/api/database/connect', {
            db_type: selectedDbType,
            config: { path: path }
        });

        if (result.success) {
            showToast('Database connected successfully!');
            setTimeout(() => location.reload(), 1500);
        } else {
            showToast(result.message || 'Connection failed', 'error');
        }
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        if (btn) btn.disabled = !isEditMode;
    }
}

async function disconnectDatabase() {
    if (!confirm('Are you sure you want to disconnect?')) return;

    try {
        const result = await API.post('/api/database/disconnect', {});
        if (result.success) {
            showToast('Disconnected successfully');
            location.reload();
        }
    } catch (error) {
        showToast(error.message, 'error');
    }
}

async function testConnection() {
    const path = document.getElementById('db-path').value.trim();
    if (!selectedDbType) return showToast('Select DB type first', 'warning');

    try {
        const result = await API.post('/api/database/test', {
            db_type: selectedDbType,
            config: { path: path }
        });
        if (result.success) showToast('Connection test passed!', 'success');
        else showToast('Test failed: ' + result.message, 'error');
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function loadConnectionStatus() {
    try {
        const result = await API.get('/api/database/status');
        updateConnectionUI(result);
        if (result.connected) {
            await loadSchema();
            await loadSavedConfiguration();
        }
    } catch (error) {
        console.error('Status check failed:', error);
    }
}

function updateConnectionUI(status) {
    const badge = document.getElementById('connection-badge');
    const dbResult = document.getElementById('connection-result');
    const disconnectBtn = document.getElementById('btn-disconnect');
    const connectBtn = document.getElementById('btn-connect');
    const sections = ['schema-section', 'dashboard-config-section'];
    const pathInput = document.getElementById('db-path');

    if (status.connected) {
        badge.className = 'badge bg-success';
        badge.textContent = 'Connected';

        const type = status.type || status.db_type || 'Unknown';
        if (dbResult) dbResult.innerHTML = `<span class="text-success"><i class="fas fa-check-circle me-1"></i>Connected to ${type}</span>`;

        if (pathInput) {
            pathInput.value = status.db_path || status.path || '';
            pathInput.disabled = true;
        }

        if (connectBtn) connectBtn.style.display = 'none';
        if (disconnectBtn) disconnectBtn.classList.remove('d-none');
        sections.forEach(id => document.getElementById(id)?.classList.remove('d-none'));

        // Highlight type button
        selectedDbType = type;
        document.querySelectorAll('.db-type-btn').forEach(b => {
            b.style.pointerEvents = 'none';
            b.classList.toggle('active', b.dataset.type === type);
        });

    } else {
        badge.className = 'badge bg-secondary';
        badge.textContent = 'Not Connected';
        if (connectBtn) connectBtn.style.display = '';
        if (disconnectBtn) disconnectBtn.classList.add('d-none');
        sections.forEach(id => document.getElementById(id)?.classList.add('d-none'));

        if (pathInput) pathInput.disabled = false;
        document.querySelectorAll('.db-type-btn').forEach(b => b.style.pointerEvents = '');
    }
}

// ============================================================================
// Schema & Config Logic
// ============================================================================

async function loadSchema() {
    try {
        const result = await API.get('/api/database/schema');
        if (result.success && result.tables) {
            currentSchema = result.tables;
            populateColumnSelects(currentSchema);
            renderSchemaPreview(currentSchema); // Standard UI function
        }
    } catch (e) { console.error("Schema load error", e); }
}

async function saveConfiguration() {
    const config = {
        ticker_title_column: val('ticker-subtitle-col'),
        ticker_title_format: val('ticker-subtitle-format'),
        refresh_interval: parseInt(val('refresh-interval')) || 10,
        traffic_light: {
            metric1_column: val('metric1-col'),
            metric1_format: val('metric1-format'),
            metric2_column: val('metric2-col'),
            metric2_format: val('metric2-format'),
            metric3_column: val('metric3-col'),
            metric3_format: val('metric3-format'),
            expression: val('expression-input'),
            green_threshold: parseFloat(val('green-threshold')) || 0,
            red_threshold: parseFloat(val('red-threshold')) || 0
        },
        graph1: {
            graph_type: val('graph1-type'),
            x_column: val('graph1-x'),
            x_format: val('graph1-x-format'),
            y_column: val('graph1-y'),
            y_format: val('graph1-y-format'),
            title: val('graph1-title')
        },
        graph2: {
            graph_type: val('graph2-type'),
            x_column: val('graph2-x'),
            x_format: val('graph2-x-format'),
            y_column: val('graph2-y'),
            y_format: val('graph2-y-format'),
            title: val('graph2-title')
        }
    };

    try {
        const result = await API.post('/api/config/dashboard', config);
        if (result.success) {
            showToast('Configuration saved!', 'success');
            toggleEditMode();

            // Notify Analytics page to refresh graphs (via localStorage event)
            localStorage.setItem('sfa_config_updated', Date.now().toString());
        } else {
            showToast('Save failed: ' + result.message, 'error');
        }
    } catch (e) { showToast(e.message, 'error'); }
}

async function loadSavedConfiguration() {
    try {
        const result = await API.get('/api/config/dashboard');
        if (result.success && result.config) {
            const c = result.config;

            setSelectValue('ticker-subtitle-col', c.ticker_title_column);
            setSelectValue('ticker-subtitle-format', c.ticker_title_format);
            setSelectValue('refresh-interval', c.refresh_interval);

            if (c.traffic_light) {
                setSelectValue('metric1-col', c.traffic_light.metric1_column);
                setSelectValue('metric1-format', c.traffic_light.metric1_format);
                setSelectValue('metric2-col', c.traffic_light.metric2_column);
                setSelectValue('metric2-format', c.traffic_light.metric2_format);
                setSelectValue('metric3-col', c.traffic_light.metric3_column);
                setSelectValue('metric3-format', c.traffic_light.metric3_format);

                setVal('expression-input', c.traffic_light.expression);
                setVal('green-threshold', c.traffic_light.green_threshold);
                setVal('red-threshold', c.traffic_light.red_threshold);
            }

            if (c.graph1) {
                setSelectValue('graph1-type', c.graph1.graph_type);
                setSelectValue('graph1-x', c.graph1.x_column);
                setSelectValue('graph1-x-format', c.graph1.x_format);
                setSelectValue('graph1-y', c.graph1.y_column);
                setSelectValue('graph1-y-format', c.graph1.y_format);
                setVal('graph1-title', c.graph1.title);
            }

            if (c.graph2) {
                setSelectValue('graph2-type', c.graph2.graph_type);
                setSelectValue('graph2-x', c.graph2.x_column);
                setSelectValue('graph2-x-format', c.graph2.x_format);
                setSelectValue('graph2-y', c.graph2.y_column);
                setSelectValue('graph2-y-format', c.graph2.y_format);
                setVal('graph2-title', c.graph2.title);
            }

            updateConfigStatusIndicators();
        }
    } catch (e) { console.error("Load config error", e); }
}

// ============================================================================
// UI Helpers
// ============================================================================

function val(id) {
    const el = document.getElementById(id);
    return el ? el.value : '';
}

function setVal(id, value) {
    const el = document.getElementById(id);
    if (el) el.value = value ?? '';
}

function toggleEditMode() {
    isEditMode = !isEditMode;
    const btn = document.getElementById('edit-mode-btn');
    const body = document.body;

    if (isEditMode) {
        body.classList.add('edit-mode-active');
        if (btn) {
            btn.innerHTML = '<i class="fas fa-unlock me-1"></i>Editing';
            btn.classList.replace('btn-outline-warning', 'btn-warning');
        }
    } else {
        body.classList.remove('edit-mode-active');
        if (btn) {
            btn.innerHTML = '<i class="fas fa-lock me-1"></i>Edit Mode';
            btn.classList.replace('btn-warning', 'btn-outline-warning');
        }
    }
    updateEditableState();
}

function updateEditableState() {
    const editableIds = [
        'db-path', 'btn-test', 'btn-connect', 'btn-disconnect',
        'metric1-col', 'metric1-format', 'metric2-col', 'metric2-format', 'metric3-col', 'metric3-format',
        'expression-input', 'green-threshold', 'red-threshold',
        'graph1-type', 'graph1-x', 'graph1-x-format', 'graph1-y', 'graph1-y-format', 'graph1-title',
        'graph2-type', 'graph2-x', 'graph2-x-format', 'graph2-y', 'graph2-y-format', 'graph2-title',
        'btn-save-config', 'ticker-subtitle-col', 'ticker-subtitle-format', 'refresh-interval'
    ];

    editableIds.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.disabled = !isEditMode;
    });

    // DB Type buttons
    document.querySelectorAll('.db-type-btn').forEach(btn => {
        // Only toggle visual lock if not connected
        if (!document.getElementById('connection-badge').classList.contains('bg-success')) {
            btn.classList.toggle('edit-locked', !isEditMode);
        }
    });
}

function showToast(msg, type = 'success') {
    const existing = document.getElementById('toast-notification');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.id = 'toast-notification';
    toast.className = `toast-notification text-white p-3 rounded shadow status-${type}`;
    // Simple inline styles for certainty
    toast.style.position = 'fixed';
    toast.style.bottom = '30px';
    toast.style.left = '50%';
    toast.style.transform = 'translateX(-50%)';
    toast.style.zIndex = '9999';
    toast.style.backgroundColor = type === 'success' ? '#009d63' : '#dc3545';
    toast.innerHTML = `<i class="fas fa-${type === 'success' ? 'check' : 'exclamation'}-circle me-2"></i>${msg}`;

    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

// Re-implement Render functions for Schema
function renderSchemaPreview(tables) {
    const tabDiv = document.getElementById('table-tabs');
    const contentDiv = document.getElementById('schema-content');
    if (!tabDiv || !contentDiv) return;

    tabDiv.innerHTML = '';
    contentDiv.innerHTML = '';

    Object.entries(tables).forEach(([name, info], idx) => {
        const btn = document.createElement('button');
        btn.className = `btn btn-sm ${idx === 0 ? 'btn-primary' : 'btn-outline-secondary'}`;
        btn.textContent = name;
        btn.onclick = () => {
            document.querySelectorAll('#table-tabs .btn').forEach(b => {
                b.classList.replace('btn-primary', 'btn-outline-secondary');
            });
            btn.classList.replace('btn-outline-secondary', 'btn-primary');
            renderTableColumns(name, Array.isArray(info) ? info : info.columns);
        };
        tabDiv.appendChild(btn);
        if (idx === 0) renderTableColumns(name, Array.isArray(info) ? info : info.columns);
    });
}

function renderTableColumns(name, columns) {
    const content = document.getElementById('schema-content');
    let html = `<h5 class="mb-3 border-bottom pb-2">${name}</h5><div class="row">`;
    (columns || []).forEach(col => {
        html += `<div class="col-md-4 mb-2"><div class="p-2 border rounded bg-light">
                   <small class="d-block text-muted">${col.type}</small><strong>${col.name}</strong>
                 </div></div>`;
    });
    html += '</div>';
    content.innerHTML = html;
}

function populateColumnSelects(tables) {
    allColumns = [];
    const ids = [
        'metric1-col', 'metric2-col', 'metric3-col', 'ticker-subtitle-col',
        'graph1-x', 'graph1-y', 'graph2-x', 'graph2-y'
    ];

    const optionsHtml = ['<option value="">Select column...</option>'];

    Object.entries(tables).forEach(([table, info]) => {
        const cols = Array.isArray(info) ? info : info.columns;
        optionsHtml.push(`<optgroup label="${table}">`);
        cols.forEach(col => {
            allColumns.push({ name: col.name, table: table });
            optionsHtml.push(`<option value="${table}.${col.name}">${col.name}</option>`);
        });
        optionsHtml.push(`</optgroup>`);
    });

    const fullHtml = optionsHtml.join('');
    ids.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = fullHtml;
    });

    updateExpressionBuilderColumns();
}

function updateExpressionBuilderColumns() {
    const container = document.getElementById('expression-columns');
    const input = document.getElementById('expression-input');
    if (!container) return;

    container.innerHTML = '';
    allColumns.forEach(col => {
        const btn = document.createElement('button');
        btn.className = 'btn btn-sm btn-outline-secondary m-1';
        btn.textContent = col.name;
        btn.onclick = () => {
            if (input && !input.disabled) {
                input.value += col.name;
                updateConfigStatusIndicators();
            }
        };
        container.appendChild(btn);
    });
}

function setupExpressionBuilder() {
    const input = document.getElementById('expression-input');
    document.querySelectorAll('.operator-btn').forEach(btn => {
        btn.onclick = () => {
            if (input && !input.disabled) {
                input.value += ' ' + btn.dataset.op + ' ';
                updateConfigStatusIndicators();
            }
        };
    });
}

function updateConfigStatusIndicators() {
    // Traffic Light
    const m1 = val('metric1-col'), m2 = val('metric2-col'), expr = val('expression-input');
    const hasTraffic = (m1 || m2) && expr;
    setDot('traffic-light-status', hasTraffic);

    // Graph 1
    const g1 = val('graph1-type') && val('graph1-x') && val('graph1-y');
    setDot('graph1-status', g1);

    // Graph 2
    const g2 = val('graph2-type') && val('graph2-x') && val('graph2-y');
    setDot('graph2-status', g2);
}

function setDot(id, active) {
    const el = document.getElementById(id);
    if (el) {
        el.className = `status-indicator ${active ? 'configured' : 'unconfigured'}`;
        el.title = active ? 'Configured' : 'Not configured';
    }
}

// Helper for fuzzy matching selects
function setSelectValue(id, value) {
    const select = document.getElementById(id);
    if (!select || !value) return;

    // Try exact
    select.value = value;
    if (select.value == value) return;

    // Try fuzzy match
    const str = String(value).toLowerCase();
    for (let opt of select.options) {
        if (opt.value.toLowerCase().includes(str) || str.endsWith(opt.text.toLowerCase())) {
            select.value = opt.value;
            return;
        }
    }
}
