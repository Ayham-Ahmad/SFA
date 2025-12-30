/**
 * manager_dashboard.js - Dashboard with traffic light and company metrics
 */

let isDbConnected = false;
let pollTimer = null;

// ============================================================================
// Initialization
// ============================================================================

document.addEventListener('DOMContentLoaded', async () => {
    // Initial check
    const connected = await checkDatabaseConnection();
    if (connected) {
        startPolling();
    } else {
        showDatabaseRequired();
    }
});

// ============================================================================
// Database Connection
// ============================================================================

async function checkDatabaseConnection() {
    try {
        const data = await API.get('/api/database/status');
        isDbConnected = data.connected === true;

        const statusEl = document.getElementById('connection-status');
        if (statusEl && isDbConnected) {
            statusEl.innerHTML = '<i class="fas fa-circle me-1"></i>LIVE';
            statusEl.className = 'text-success small fw-bold';
        }
        return isDbConnected;
    } catch (error) {
        console.error('Failed to check DB connection:', error);
        return false;
    }
}

function showDatabaseRequired() {
    const container = document.getElementById('live-feed-content');
    const statusEl = document.getElementById('connection-status');

    if (statusEl) {
        statusEl.innerHTML = '<i class="fas fa-database me-1"></i>NOT CONNECTED';
        statusEl.className = 'text-warning small fw-bold';
    }

    if (container) {
        container.innerHTML = `
            <div class="py-5">
                <i class="fas fa-database fa-4x text-muted mb-4"></i>
                <h4 class="text-muted">No Database Connected</h4>
                <p class="text-secondary mb-4">Connect your database to view financial data.</p>
                <a href="/settings" class="btn btn-success btn-lg">
                    <i class="fas fa-plug me-2"></i>Connect Database
                </a>
            </div>
        `;
    }
}

// ============================================================================
// Live Data Polling
// ============================================================================

async function startPolling() {
    await fetchLiveData();
}

async function fetchLiveData() {
    if (!Auth.getToken()) {
        window.location.href = '/login';
        return;
    }

    try {
        const data = await API.get('/api/manager/live-data');

        if (data.error) {
            showError(data.error);
        } else if (data.data && data.data.length > 0) {
            // Show the last item
            const lastItem = data.data[data.data.length - 1];
            displayCompany(lastItem, data.subtitle_column);
        } else {
            const container = document.getElementById('live-feed-content');
            container.innerHTML = `<div class="py-5 text-muted">Waiting for data...</div>`;
        }

        // Schedule next poll based on config
        const refreshInterval = (data.refresh_interval || 10) * 1000;
        if (pollTimer) clearTimeout(pollTimer);
        pollTimer = setTimeout(fetchLiveData, refreshInterval);

    } catch (error) {
        // If 401, API.js redirects. Else show error
        showError("Network error or server offline");
        // Retry slower on error
        pollTimer = setTimeout(fetchLiveData, 60000);
    }
}

function displayCompany(company, subtitleLabel = null) {
    const container = document.getElementById('live-feed-content');
    if (!container) return;

    const isProfit = company.is_profit;
    let statusColor = 'text-warning'; // Default neutral/error
    if (isProfit === true) statusColor = 'text-success';
    if (isProfit === false) statusColor = 'text-danger';

    // Determine subtitle text
    let subtitleText = "PERIOD:";
    let subtitleValue = company.period || '';

    if (company.subtitle_value) {
        subtitleValue = company.subtitle_value;
        if (subtitleLabel) {
            const parts = subtitleLabel.split('.');
            subtitleText = (parts.length > 1 ? parts[1] : parts[0]).toUpperCase() + ":";
        }
    }

    const html = `
        <div>
            <div style="min-height: 120px; display: flex; align-items: center; justify-content: center; flex-direction: column;">
                <h1 class="display-4 fw-bold mb-1 text-truncate" style="max-width: 90%;" title="${company.name}">${company.name}</h1>
                <p class="text-secondary fs-5 mb-0 text-truncate" style="max-width: 90%;" title="${subtitleText} ${subtitleValue}">
                    ${subtitleText} <span class="fw-bold">${subtitleValue}</span>
                </p>
            </div>

            <div class="my-4 d-flex justify-content-center">
                <div class="traffic-light-container position-relative d-flex flex-row justify-content-center align-items-center gap-4 bg-dark p-4 rounded-pill shadow-lg" 
                     style="border: 1px solid #334155;">
                    <div class="light red ${isProfit === false ? 'active' : ''}" style="width: 80px; height: 80px;"></div>
                    <div class="light yellow ${isProfit === null ? 'active' : ''}" style="width: 80px; height: 80px;"></div>
                    <div class="light green ${isProfit === true ? 'active' : ''}" style="width: 80px; height: 80px;"></div>


                </div>
            </div>


            <div class="row justify-content-center mt-5">
                <div class="col-md-3 border-end border-secondary">
                    <div class="text-info small text-uppercase fw-bold mb-2">${company.metric1_label || 'Metric 1'}</div>
                    <div class="h2 fw-bold">${company.metric1}</div>
                </div>
                <div class="col-md-3 border-end border-secondary">
                    <div class="text-info small text-uppercase fw-bold mb-2">${company.metric2_label || 'Metric 2'}</div>
                    <div class="h2 fw-bold ${statusColor}">${company.metric2}</div>
                </div>
                <div class="col-md-3">
                    <div class="text-info small text-uppercase fw-bold mb-2">${company.metric3_label || 'Metric 3'}</div>
                    <div class="h2 fw-bold ${statusColor}">
                        ${company.metric3}
                    </div>
                </div>
            </div>
            
            <div class="mt-4 d-flex justify-content-center align-items-center gap-2">
                <div class="badge bg-secondary bg-opacity-25 px-3 py-2 text-body">
                    STATUS: <span class="${statusColor}">${company.status}</span>
                </div>
                
                <!-- Calculator Tooltip -->
                <div class="calc-tooltip-btn position-relative" style="cursor: pointer;">
                     <i class="fas fa-calculator text-secondary" style="font-size: 1.2rem;"></i>
                     <div class="calc-tooltip-content shadow-lg">
                        <div class="fw-bold text-info mb-2 border-bottom pb-1" style="border-color: var(--border-color) !important;">Traffic Light Logic</div>
                        
                        <div class="calc-tooltip-row">
                            <span class="text-muted">Expr:</span>
                            <code class="small" style="word-break: break-all; color: var(--text-color);">${company.expression || '-'}</code>
                        </div>

                        ${renderVars(company.calc_details?.vars)}

                        <div class="calc-tooltip-row mt-2 pt-1" style="border-top: 1px solid var(--border-color);">
                            <span class="text-muted">Result:</span>
                            <span class="fw-bold ${statusColor}">${formatNumber(company.calc_details?.result)}</span>
                        </div>
                        
                        <div class="d-flex justify-content-between mt-2 pt-2 small" style="border-top: 1px solid var(--border-color);">
                             <div class="text-danger" title="Red Threshold"><i class="fas fa-arrow-down"></i> &lt; ${company.calc_details?.red ?? '-'}</div>
                             <div class="text-success" title="Green Threshold"><i class="fas fa-arrow-up"></i> &ge; ${company.calc_details?.green ?? '-'}</div>
                        </div>
                     </div>
                </div>
            </div>
        </div>
    `;

    container.innerHTML = html;
}

function showError(msg) {
    const el = document.getElementById('connection-status');
    if (el) {
        el.innerHTML = '<i class="fas fa-exclamation-triangle me-1"></i>ERROR';
        el.className = 'text-danger small fw-bold';
    }
    console.error('Dashboard error:', msg);
}


function renderVars(vars) {
    if (!vars || Object.keys(vars).length === 0) {
        return '<div class="text-muted text-center small my-2">No variables tracked</div>';
    }
    let html = '';
    for (const [key, val] of Object.entries(vars)) {
        html += `
            <div class="calc-tooltip-row">
                <span class="text-muted small">${key}:</span>
                <span class="small" style="color: var(--text-color);">${formatNumber(val)}</span>
            </div>`;
    }
    return html;
}

function formatNumber(num) {
    if (num === null || num === undefined || isNaN(num)) return '-';
    if (typeof num !== 'number') return num;

    // Format large numbers
    if (Math.abs(num) >= 1e9) return (num / 1e9).toFixed(2) + 'B';
    if (Math.abs(num) >= 1e6) return (num / 1e6).toFixed(2) + 'M';
    if (Math.abs(num) >= 1e3) return (num / 1e3).toFixed(2) + 'k';
    return num.toFixed(2);
}
