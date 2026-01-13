/**
 * settings.js - Unified Settings Page Logic
 * Handles database connection and dashboard configuration.
 */

let isEditMode = false;
let currentSchema = null;
let allColumns = [];
let hasUnsavedChanges = false; // Track if user has modified config without saving
let pendingNavigationUrl = null; // Store URL to navigate to after handling unsaved changes

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

    // 4. Load Data
    await loadConnectionStatus();
    await loadUploadedFiles();

    // 5. Setup unsaved changes warning
    setupUnsavedChangesWarning();

    // Initial status check (will show red dots if elements exist)
    updateConfigStatusIndicators();


    // 5. Check for connection success flag
    if (sessionStorage.getItem('connection_success')) {
        showToast('Database connected successfully!');
        sessionStorage.removeItem('connection_success');
    }
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

/**
 * Setup unsaved changes warning
 * Warns user if they try to navigate away with unsaved config changes
 */
function setupUnsavedChangesWarning() {
    // Track changes on all config inputs in dashboard section
    const configSection = document.getElementById('dashboard-config-section');
    if (configSection) {
        configSection.addEventListener('change', () => {
            if (isEditMode) {
                hasUnsavedChanges = true;
            }
        });
        configSection.addEventListener('input', () => {
            if (isEditMode) {
                hasUnsavedChanges = true;
            }
        });
    }

    // Expression builder changes
    const expressionInput = document.getElementById('expression-input');
    if (expressionInput) {
        const observer = new MutationObserver(() => {
            if (isEditMode) hasUnsavedChanges = true;
        });
        observer.observe(expressionInput, { characterData: true, childList: true, subtree: true });
    }

    // Warn before leaving page
    window.addEventListener('beforeunload', (e) => {
        if (hasUnsavedChanges && isEditMode) {
            e.preventDefault();
            e.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
            return e.returnValue;
        }
    });



    // Also warn when clicking sidebar links
    document.querySelectorAll('.list-group-item').forEach(link => {
        link.addEventListener('click', (e) => {
            if (hasUnsavedChanges && isEditMode) {
                e.preventDefault();
                e.stopPropagation();

                // Store destination
                pendingNavigationUrl = link.getAttribute('href');

                // Show custom modal
                const modal = new bootstrap.Modal(document.getElementById('unsavedChangesModal'));
                modal.show();
            }
        });
    });
}

// Handler for "Discard & Leave"
function handleDiscardAndLeave() {
    if (!pendingNavigationUrl) return;

    // Close modal
    const modal = bootstrap.Modal.getInstance(document.getElementById('unsavedChangesModal'));
    modal.hide();

    // Special case: Exit Edit Mode
    if (pendingNavigationUrl === 'EXIT_EDIT_MODE') {
        hasUnsavedChanges = false;
        // Revert UI changes
        loadSavedConfiguration().then(() => {
            // Turn off edit mode (bypasses check since flag is false)
            if (isEditMode) toggleEditMode();
        });
        pendingNavigationUrl = null;
        return;
    }

    hasUnsavedChanges = false;
    window.location.href = pendingNavigationUrl;
}

// Handler for "Save & Leave"
async function handleSaveAndLeave() {
    const modalEl = document.getElementById('unsavedChangesModal');
    const modal = bootstrap.Modal.getInstance(modalEl);

    // Close modal first
    modal.hide();

    // Call save
    await saveConfiguration();

    // Check if save was successful (flag reset)
    if (!hasUnsavedChanges && pendingNavigationUrl) {
        // If simply exiting edit mode, we are done (saveConfiguration already toggles mode)
        if (pendingNavigationUrl !== 'EXIT_EDIT_MODE') {
            window.location.href = pendingNavigationUrl;
        }
        pendingNavigationUrl = null;
    }
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
            sessionStorage.setItem('connection_success', 'true');
            location.reload();
        } else {
            showToast(result.message || 'Connection failed', 'error');
        }
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        if (btn) btn.disabled = !isEditMode;
    }
}

async function uploadDataset() {
    const fileInput = document.getElementById('upload-file');
    if (!fileInput.files.length) return;

    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append('file', file);

    const progress = document.getElementById('upload-progress');
    const label = document.getElementById('upload-label');
    
    if (progress) progress.classList.remove('d-none');
    if (label) label.classList.add('disabled');

    try {
        const response = await fetch('/api/upload/dataset', {
            method: 'POST',
            body: formData,
            headers: {
                'Authorization': `Bearer ${Auth.getToken()}`
            }
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast('File uploaded successfully!');
            await loadUploadedFiles();
            // Automatically put the path in the input
            const pathInput = document.getElementById('db-path');
            if (pathInput) {
                pathInput.value = result.path;
                // Trigger change to enable Connect button
                if (isEditMode) {
                    document.getElementById('btn-connect').disabled = false;
                    document.getElementById('btn-test').disabled = false;
                }
            }
        } else {
            showToast(result.detail || 'Upload failed', 'error');
        }
    } catch (e) {
        showToast(e.message, 'error');
    } finally {
        if (progress) progress.classList.add('d-none');
        if (label) label.classList.remove('disabled');
        fileInput.value = ''; // Reset input
    }
}

async function loadUploadedFiles() {
    const list = document.getElementById('uploaded-files-list');
    if (!list) return;

    try {
        const result = await API.get('/api/upload/list');
        if (result.files && result.files.length > 0) {
            list.innerHTML = result.files.map(f => `
                <div class="d-flex justify-content-between align-items-center mb-2 p-2 rounded bg-white shadow-sm border">
                    <div class="text-truncate me-2" title="${f.name}">
                        <i class="fas ${f.name.endsWith('.csv') ? 'fa-file-csv' : 'fa-database'} me-2 text-primary"></i>
                        <span>${f.name}</span>
                    </div>
                    <button class="btn btn-sm btn-outline-primary py-0 px-2" onclick="useUploadedFile('${f.path.replace(/\\/g, '\\\\')}')">
                        Use
                    </button>
                </div>
            `).join('');
        } else {
            list.innerHTML = '<div class="text-center py-2">No uploaded files yet</div>';
        }
    } catch (e) {
        console.error('Failed to load uploaded files:', e);
    }
}

function useUploadedFile(path) {
    const pathInput = document.getElementById('db-path');
    if (pathInput) {
        pathInput.value = path;
        showToast('Path updated to uploaded file');
        if (isEditMode) {
            document.getElementById('btn-connect').disabled = false;
            document.getElementById('btn-test').disabled = false;
        }
    }
}

function disconnectDatabase() {
    // Reset checkbox and button when opening modal
    const checkbox = document.getElementById('confirmDeleteCheck');
    const btn = document.getElementById('confirmDisconnectBtn');
    if (checkbox) checkbox.checked = false;
    if (btn) btn.disabled = true;

    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('disconnectModal'));
    modal.show();
}

function updateDisconnectButton() {
    const checkbox = document.getElementById('confirmDeleteCheck');
    const btn = document.getElementById('confirmDisconnectBtn');
    if (checkbox && btn) {
        btn.disabled = !checkbox.checked;
    }
}

async function confirmDisconnect() {
    // Hide modal first
    bootstrap.Modal.getInstance(document.getElementById('disconnectModal')).hide();

    try {
        const result = await API.post('/api/database/disconnect', { delete_all_data: true });
        if (result.success) {
            showToast('Disconnected and data cleared successfully');
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

        if (pathInput) pathInput.disabled = !isEditMode;  // Respect edit mode
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
        ticker_title_secondary_column: val('ticker-subtitle-secondary'),
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
            x_secondary_column: val('graph1-x-secondary'),
            x_format: val('graph1-x-format'),
            y_column: val('graph1-y'),
            y_format: val('graph1-y-format'),
            title: val('graph1-title'),
            data_range_mode: val('graph1-range-mode'),
            data_range_limit: parseInt(val('graph1-range-limit')) || 12
        },
        graph2: {
            graph_type: val('graph2-type'),
            x_column: val('graph2-x'),
            x_secondary_column: val('graph2-x-secondary'),
            x_format: val('graph2-x-format'),
            y_column: val('graph2-y'),
            y_format: val('graph2-y-format'),
            title: val('graph2-title'),
            data_range_mode: val('graph2-range-mode'),
            data_range_limit: parseInt(val('graph2-range-limit')) || 12
        }
    };

    try {
        const result = await API.post('/api/config/dashboard', config);
        if (result.success) {
            showToast('Configuration saved!', 'success');
            hasUnsavedChanges = false; // Reset unsaved changes flag
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
            setSelectValue('ticker-subtitle-secondary', c.ticker_title_secondary_column);
            setSelectValue('ticker-subtitle-format', c.ticker_title_format);
            setSelectValue('refresh-interval', c.refresh_interval);

            if (c.traffic_light) {
                setSelectValue('metric1-col', c.traffic_light.metric1_column);
                setSelectValue('metric1-format', c.traffic_light.metric1_format);
                setSelectValue('metric2-col', c.traffic_light.metric2_column);
                setSelectValue('metric2-format', c.traffic_light.metric2_format);
                setSelectValue('metric3-col', c.traffic_light.metric3_column);
                setSelectValue('metric3-format', c.traffic_light.metric3_format);

                document.getElementById('expression-input').value = c.traffic_light.expression || '';
                document.getElementById('green-threshold').value = c.traffic_light.green_threshold;
                document.getElementById('red-threshold').value = c.traffic_light.red_threshold;
            }

            if (c.graph1) {
                setSelectValue('graph1-type', c.graph1.graph_type);
                setSelectValue('graph1-x', c.graph1.x_column);
                setSelectValue('graph1-x-secondary', c.graph1.x_secondary_column);
                setSelectValue('graph1-x-format', c.graph1.x_format);
                setSelectValue('graph1-y', c.graph1.y_column);
                setSelectValue('graph1-y-format', c.graph1.y_format);
                document.getElementById('graph1-title').value = c.graph1.title || '';

                setSelectValue('graph1-range-mode', c.graph1.data_range_mode || 'all');
                document.getElementById('graph1-range-limit').value = c.graph1.data_range_limit || 12;
                toggleRangeLimitInput('graph1');
            }

            if (c.graph2) {
                setSelectValue('graph2-type', c.graph2.graph_type);
                setSelectValue('graph2-x', c.graph2.x_column);
                setSelectValue('graph2-x-secondary', c.graph2.x_secondary_column);
                setSelectValue('graph2-x-format', c.graph2.x_format);
                setSelectValue('graph2-y', c.graph2.y_column);
                setSelectValue('graph2-y-format', c.graph2.y_format);
                document.getElementById('graph2-title').value = c.graph2.title || '';

                setSelectValue('graph2-range-mode', c.graph2.data_range_mode || 'all');
                document.getElementById('graph2-range-limit').value = c.graph2.data_range_limit || 12;
                toggleRangeLimitInput('graph2');
            }

            updateConfigStatusIndicators();
        }
        // Force update regardless of config presence to show red dots for empty config
        updateConfigStatusIndicators();
    } catch (e) {
        console.error('Config load error', e);
        // Ensure dots are updated even on error (will show red)
        updateConfigStatusIndicators();
    }
}

function toggleRangeLimitInput(graphId) {
    const mode = document.getElementById(`${graphId}-range-mode`).value;
    const limitInput = document.getElementById(`${graphId}-range-limit`);
    if (limitInput) {
        limitInput.style.display = mode === 'last_n' ? 'block' : 'none';
        // Auto-focus if switching to last_n in edit mode
        if (mode === 'last_n' && isEditMode) limitInput.focus();
    }
    updateConfigStatusIndicators();
}

// Add listeners for range mode changing
document.addEventListener('DOMContentLoaded', () => {
    ['graph1', 'graph2'].forEach(id => {
        const sel = document.getElementById(`${id}-range-mode`);
        if (sel) sel.addEventListener('change', () => toggleRangeLimitInput(id));
    });
});


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
    // If trying to turn OFF edit mode and there are unsaved changes
    if (isEditMode && hasUnsavedChanges) {
        pendingNavigationUrl = 'EXIT_EDIT_MODE';
        const modal = new bootstrap.Modal(document.getElementById('unsavedChangesModal'));
        modal.show();
        return;
    }

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
    const isConnected = document.getElementById('connection-badge').classList.contains('bg-success');

    // Config IDs always controlled by Edit Mode
    const configIds = [
        'btn-disconnect',
        'metric1-col', 'metric1-format', 'metric2-col', 'metric2-format', 'metric3-col', 'metric3-format',
        'expression-input', 'green-threshold', 'red-threshold',
        'graph1-type', 'graph1-x', 'graph1-x-secondary', 'graph1-x-format', 'graph1-y', 'graph1-y-format', 'graph1-title', 'graph1-range-mode', 'graph1-range-limit',
        'graph2-type', 'graph2-x', 'graph2-x-secondary', 'graph2-x-format', 'graph2-y', 'graph2-y-format', 'graph2-title', 'graph2-range-mode', 'graph2-range-limit',
        'btn-save-config', 'ticker-subtitle-col', 'ticker-subtitle-secondary', 'ticker-subtitle-format', 'refresh-interval'
    ];

    configIds.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.disabled = !isEditMode;
    });

    // Connection IDs: Only enabled if Edit Mode is ON AND NOT Connected
    // This blocks changing path/type if already connected
    const connectionIds = ['db-path', 'btn-test', 'btn-connect'];
    connectionIds.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            if (isConnected) {
                el.disabled = true;
            } else {
                el.disabled = !isEditMode;
            }
        }
    });

    // DB Type buttons logic
    document.querySelectorAll('.db-type-btn').forEach(btn => {
        if (isConnected) {
            // If connected, always locked regadless of edit mode
            btn.classList.add('edit-locked');
            btn.style.pointerEvents = 'none';
        } else {
            // If not connected, lock follows edit mode
            btn.classList.toggle('edit-locked', !isEditMode);
            btn.style.pointerEvents = isEditMode ? '' : 'none';
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
        'ticker-subtitle-secondary', 'graph1-x', 'graph1-x-secondary', 'graph1-y',
        'graph2-x', 'graph2-x-secondary', 'graph2-y'
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

function clearExpression() {
    const input = document.getElementById('expression-input');
    if (input && !input.disabled) {
        input.value = '';
        updateConfigStatusIndicators();
    }
}

function updateConfigStatusIndicators() {
    // Dashboard Settings
    const subtitle = val('ticker-subtitle-col');
    setDot('dashboard-status', subtitle);

    // Traffic Light
    const m1 = val('metric1-col'), m2 = val('metric2-col'), m3 = val('metric3-col');
    const expr = val('expression-input');
    const hasTraffic = (m1 || m2 || m3) && expr;
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
        el.className = `status-dot ${active ? 'configured' : 'unconfigured'}`;
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
