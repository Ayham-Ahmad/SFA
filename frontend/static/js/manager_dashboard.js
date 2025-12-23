let currentDataQueue = [];
let queueIndex = 0;
let rotationInterval;

async function fetchLiveData() {
    const token = localStorage.getItem('token');
    if (!token) {
        window.location.href = '/login';
        return;
    }

    try {
        const response = await fetch('/api/manager/live-data', {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (response.status === 401) {
            localStorage.removeItem('token');
            window.location.href = '/login';
            return;
        }

        if (response.ok) {
            const data = await response.json();
            if (data.error) {
                showError(data.error);
            } else {
                currentDataQueue = data.companies;

                if (currentDataQueue.length === 0) {
                    const container = document.getElementById('live-feed-content');
                    if (!rotationInterval) {
                        container.innerHTML = `<div class="py-5 text-muted">Waiting for feed...</div>`;
                    }
                } else if (!rotationInterval) {
                    queueIndex = 0;
                    displayCompany(currentDataQueue[0]);
                    startRotation();
                }
            }
        } else {
            showError("Connection failed");
        }
    } catch (error) {
        console.error('Error:', error);
        showError("Network error");
    }
}

function startRotation() {
    if (rotationInterval) clearInterval(rotationInterval);

    rotationInterval = setInterval(() => {
        if (currentDataQueue.length > 0) {
            queueIndex = (queueIndex + 1) % currentDataQueue.length;
            displayCompany(currentDataQueue[queueIndex]);
        }
    }, 10000);
}

function displayCompany(company) {
    const container = document.getElementById('live-feed-content');
    if (!container) return;

    // Determine profit class
    const isProfit = company.is_profit;
    const statusColor = isProfit ? 'text-success' : 'text-danger';

    // Format period display
    let periodStr = company.period || '';

    // Render HTML
    const html = `
        <div>
            <div style="min-height: 120px; display: flex; align-items: center; justify-content: center; flex-direction: column;">
                <h1 class="display-4 fw-bold mb-1 text-truncate" style="max-width: 90%;" title="${company.name}">${company.name}</h1>
                <p class="text-secondary fs-5 mb-0">PERIOD: <span class="fw-bold">${periodStr}</span></p>
            </div>

            <div class="my-4 d-flex justify-content-center">
                <div class="traffic-light-container d-flex flex-row justify-content-center align-items-center gap-4 bg-dark p-4 rounded-pill shadow-lg" 
                     style="border: 1px solid #334155;">
                    <div class="light red ${!isProfit ? 'active' : ''}" style="width: 80px; height: 80px;"></div>
                    <div class="light yellow" style="width: 80px; height: 80px;"></div>
                    <div class="light green ${isProfit ? 'active' : ''}" style="width: 80px; height: 80px;"></div>
                </div>
            </div>

            <div class="row justify-content-center mt-5">
                <div class="col-md-3 border-end border-secondary">
                    <div class="text-info small text-uppercase fw-bold mb-2">Total Revenue</div>
                    <div class="h2 fw-bold">${company.revenue}</div>
                </div>
                <div class="col-md-3 border-end border-secondary">
                    <div class="text-info small text-uppercase fw-bold mb-2">Net Income</div>
                    <div class="h2 fw-bold ${statusColor}">${company.net_income}</div>
                </div>
                <div class="col-md-3">
                    <div class="text-info small text-uppercase fw-bold mb-2">Profit Margin</div>
                    <div class="h2 fw-bold ${parseFloat(company.margin) >= 0 ? 'text-success' : 'text-danger'}">
                        ${company.margin}
                    </div>
                </div>
            </div>
            
             <div class="mt-4 badge bg-secondary bg-opacity-25 px-3 py-2 text-body">
                STATUS: <span class="${statusColor}">${company.status}</span>
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
}

// Poll for new data every 30 seconds
fetchLiveData();
setInterval(fetchLiveData, 30000);
