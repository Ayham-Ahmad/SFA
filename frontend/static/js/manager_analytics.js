/**
 * manager_analytics.js
 * Comprehensive management for the Analytics & Chat page.
 * Handles: Graph workspace, Persistent User Sessions, AI Chat, and Theme reactivity.
 */

// --- Global State ---
const AppState = {
    graphs: [],
    maxGraphs: 3,
    sessionId: null,
    isEditMode: false,
    pendingGraphData: null,
    username: localStorage.getItem('username') || 'Guest',

    // --- Key Identification ---
    getStorageKey() {
        return `sfa_workspace_${this.username}`;
    },

    // --- Persistence ---
    save() {
        const payload = {
            graphs: this.graphs,
            chatHtml: document.getElementById('chat-messages').innerHTML,
            sessionId: this.sessionId,
            timestamp: Date.now()
        };
        localStorage.setItem(this.getStorageKey(), JSON.stringify(payload));
    },

    load() {
        const saved = localStorage.getItem(this.getStorageKey());
        if (!saved) return false;
        try {
            const data = JSON.parse(saved);
            this.graphs = data.graphs || [];
            this.sessionId = data.sessionId;

            if (data.chatHtml) {
                document.getElementById('chat-messages').innerHTML = data.chatHtml;
                this.scrollToBottom();
            }
            return true;
        } catch (e) {
            console.error("Load failed", e);
            return false;
        }
    },

    clear() {
        localStorage.removeItem(this.getStorageKey());
        // Set a flag to prevent fetching history on next load
        localStorage.setItem('sfa_skip_history', 'true');
    },

    scrollToBottom() {
        const box = document.getElementById('chat-messages');
        if (box) box.scrollTop = box.scrollHeight;
    }
};

// --- Graph Management ---
const GraphManager = {
    draggedIndex: null,
    isPlacementMode: false,  // When a new graph is waiting to be placed

    init() {
        this.track = document.getElementById('graphs-track');
        this.container = document.getElementById('graphs-space');
        this.render();
    },

    // Toggle EDIT mode (delete/reorder functionality)
    toggleEdit(force = null) {
        AppState.isEditMode = force !== null ? force : !AppState.isEditMode;
        // Exit placement mode when entering edit mode
        if (AppState.isEditMode) this.isPlacementMode = false;
        this.container.classList.toggle('edit-mode', AppState.isEditMode);
        this.container.classList.remove('placement-mode');
        this.render();
    },

    // Enter PLACEMENT mode (when new graph is generated)
    enterPlacementMode(graphData) {
        AppState.pendingGraphData = graphData;
        this.isPlacementMode = true;
        AppState.isEditMode = false;
        this.container.classList.remove('edit-mode');
        this.container.classList.add('placement-mode');
        this.render();
    },

    exitPlacementMode() {
        AppState.pendingGraphData = null;
        this.isPlacementMode = false;
        this.container.classList.remove('placement-mode');
        this.render();
    },

    add(graphData) {
        if (AppState.graphs.length >= AppState.maxGraphs) AppState.graphs.shift();
        AppState.graphs.push(graphData);
        this.render();
        AppState.save();
    },

    replace(index, graphData) {
        if (AppState.graphs[index]) {
            AppState.graphs[index] = graphData;
            this.render();
            AppState.save();
        }
    },

    delete(index) {
        if (confirm("Delete this graph?")) {
            AppState.graphs.splice(index, 1);
            this.render();
            AppState.save();
        }
    },

    deleteAll() {
        if (confirm("Delete all graphs?")) {
            AppState.graphs = [];
            this.toggleEdit(false);
            this.render();
            AppState.save();
        }
    },

    reorder(fromIndex, toIndex) {
        if (fromIndex === toIndex) return;
        const [moved] = AppState.graphs.splice(fromIndex, 1);
        AppState.graphs.splice(toIndex, 0, moved);
        this.render();
        AppState.save();
    },

    render() {
        this.track.innerHTML = '';

        // Remove any existing Delete All button
        const existingDelAllBtn = this.container.querySelector('.delete-all-btn');
        if (existingDelAllBtn) existingDelAllBtn.remove();

        // --- EMPTY STATE: Show "Graph Space" placeholder ---
        if (AppState.graphs.length === 0 && !this.isPlacementMode) {
            this.track.innerHTML = `
                <div class="empty-graph-space">
                    <div class="empty-graph-text">Graph Space</div>
                </div>
            `;
            return;
        }

        // --- EDIT MODE: Delete All button ---
        if (AppState.isEditMode && AppState.graphs.length > 0) {
            const delAllBtn = document.createElement('button');
            delAllBtn.className = 'btn btn-sm btn-danger delete-all-btn';
            delAllBtn.innerHTML = '<i class="fas fa-trash"></i> Delete All';
            delAllBtn.onclick = (e) => { e.stopPropagation(); this.deleteAll(); };
            delAllBtn.style.cssText = 'position:absolute; top:10px; left:20px; z-index:30;';
            this.container.appendChild(delAllBtn);
        }

        AppState.graphs.forEach((g, i) => {
            const card = document.createElement('div');
            card.className = 'graph-card';
            card.dataset.index = i;

            // --- EDIT MODE: Drag-and-drop + delete buttons ---
            if (AppState.isEditMode) {
                card.classList.add('editing');
                card.draggable = true;
                card.ondragstart = () => { this.draggedIndex = i; card.classList.add('dragging'); };
                card.ondragend = () => { card.classList.remove('dragging'); this.draggedIndex = null; };
                card.ondragover = (e) => { e.preventDefault(); card.classList.add('drag-over'); };
                card.ondragleave = () => { card.classList.remove('drag-over'); };
                card.ondrop = (e) => {
                    e.preventDefault();
                    card.classList.remove('drag-over');
                    if (this.draggedIndex !== null && this.draggedIndex !== i) {
                        this.reorder(this.draggedIndex, i);
                    }
                };

                // Delete button
                const delBtn = document.createElement('button');
                delBtn.className = 'btn btn-sm btn-danger graph-delete-btn';
                delBtn.innerHTML = '<i class="fas fa-trash"></i>';
                delBtn.title = 'Delete this graph';
                delBtn.onclick = (e) => { e.stopPropagation(); this.delete(i); };
                card.appendChild(delBtn);

                // Drag handle
                const dragHandle = document.createElement('div');
                dragHandle.className = 'graph-drag-handle';
                dragHandle.innerHTML = '<i class="fas fa-grip-vertical"></i>';
                dragHandle.title = 'Drag to reorder';
                card.appendChild(dragHandle);
            }
            // --- PLACEMENT MODE: Click to replace ---
            else if (this.isPlacementMode) {
                card.classList.add('replaceable');
                card.onclick = () => {
                    this.replace(i, AppState.pendingGraphData);
                    this.exitPlacementMode();
                    addMessageUI("Graph replaced.", "bot-msg");
                };

                // Add "Replace" badge overlay
                const replaceBadge = document.createElement('div');
                replaceBadge.className = 'replace-badge';
                replaceBadge.innerHTML = '<i class="fas fa-exchange-alt"></i> Replace';
                card.appendChild(replaceBadge);
            }

            const div = document.createElement('div');
            div.className = 'graph-content';
            div.id = `slot-${i}`;
            card.appendChild(div);
            this.track.appendChild(card);

            const theme = getThemeColors();
            const layout = { ...g.layout, ...getCommonLayout(theme) };
            Plotly.newPlot(div.id, g.data, layout, { responsive: true, displayModeBar: false });
        });

        // --- PLACEMENT MODE: Show + button to add as new ---
        if (this.isPlacementMode && AppState.graphs.length < AppState.maxGraphs) {
            const addBtn = document.createElement('div');
            addBtn.className = 'add-graph-btn placement-add';
            addBtn.innerHTML = '<i class="fas fa-plus fa-2x"></i>';
            addBtn.title = 'Add as new graph';
            addBtn.onclick = () => {
                this.add(AppState.pendingGraphData);
                this.exitPlacementMode();
                addMessageUI("Graph added.", "bot-msg");
            };
            this.track.appendChild(addBtn);
        }

        setTimeout(() => window.dispatchEvent(new Event('resize')), 100);
    },

    handleCardClick(i) {
        // This is now handled inline in render()
    },

    handleAddClick() {
        // This is now handled inline in render()
    }
};

// --- Chat Interface ---

// Live status polling helper
let statusPollInterval = null;

function startStatusPolling(queryId, statusElement) {
    // Poll every 500ms for live status updates
    statusPollInterval = setInterval(async () => {
        try {
            const res = await fetch(`/chat/status/${queryId}`, {
                headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
            });
            const data = await res.json();
            if (data.step) {
                // Update the status text with the current step
                const timerSpan = statusElement.querySelector('span');
                const timerText = timerSpan ? timerSpan.outerHTML : '';
                statusElement.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${data.step} ${timerText}`;
            }
        } catch (e) {
            // Ignore polling errors
        }
    }, 500);
}

function stopStatusPolling() {
    if (statusPollInterval) {
        clearInterval(statusPollInterval);
        statusPollInterval = null;
    }
}

async function sendMessage() {
    const input = document.getElementById('user-input');
    const msg = input.value.trim();
    if (!msg) return;

    addMessageUI(msg, 'user-msg');
    input.value = '';
    input.disabled = true;

    const status = document.getElementById('status-indicator');
    const stopBtn = document.getElementById('stop-btn');
    const sendBtn = document.getElementById('send-btn');

    let seconds = 0;
    status.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Starting... <span id="timer-text"></span>';
    const timerSpan = document.getElementById('timer-text');
    const timer = setInterval(() => {
        seconds++;
        timerSpan.textContent = `${seconds}s`;
    }, 1000);

    // Show stop button, hide send button
    if (stopBtn) stopBtn.style.display = 'inline-block';
    if (sendBtn) sendBtn.style.display = 'none';

    // Generate query ID for cancellation
    currentQueryId = crypto.randomUUID();

    // Start live status polling
    startStatusPolling(currentQueryId, status);

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            },
            body: JSON.stringify({
                message: msg,
                session_id: AppState.sessionId,
                query_id: currentQueryId
            })
        });
        const data = await response.json();
        clearInterval(timer);
        stopStatusPolling();
        status.textContent = '';
        addMessageUI(data.response, 'bot-msg', data.chat_id, data.chart_data);
    } catch (e) {
        clearInterval(timer);
        stopStatusPolling();
        status.textContent = 'Error sending message.';
    } finally {
        input.disabled = false;
        input.focus();
        currentQueryId = null;
        // Hide stop button, show send button
        if (stopBtn) stopBtn.style.display = 'none';
        if (sendBtn) sendBtn.style.display = 'inline-block';
    }
}

async function requestGraph() {
    const input = document.getElementById('user-input');
    const msg = input.value.trim();
    if (!msg) return alert("Describe the graph you want!");

    addMessageUI(msg, 'user-msg');
    input.value = '';
    input.disabled = true;

    const status = document.getElementById('status-indicator');
    const stopBtn = document.getElementById('stop-btn');
    const sendBtn = document.getElementById('send-btn');

    let seconds = 0;
    status.innerHTML = '<i class="fas fa-chart-line fa-spin"></i> Starting... <span id="graph-timer-text"></span>';
    const timerSpan = document.getElementById('graph-timer-text');
    const timer = setInterval(() => {
        seconds++;
        timerSpan.textContent = `${seconds}s`;
    }, 1000);

    // Show stop button, hide send button
    if (stopBtn) stopBtn.style.display = 'inline-block';
    if (sendBtn) sendBtn.style.display = 'none';

    // Generate query ID for cancellation
    currentQueryId = crypto.randomUUID();

    // Start live status polling
    startStatusPolling(currentQueryId, status);

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            },
            body: JSON.stringify({
                message: msg,
                session_id: AppState.sessionId,
                interaction_type: 'graph',
                query_id: currentQueryId
            })
        });
        const data = await response.json();
        clearInterval(timer);
        stopStatusPolling();
        status.textContent = '';

        if (data.chart_data) {
            const plotlyData = buildChartFromTemplate(data.chart_data);
            addMessageUI(data.response, 'bot-msg', data.chat_id);

            // Placement logic
            if (AppState.graphs.length === 0) {
                // Empty workspace: auto-insert
                GraphManager.add(plotlyData);
                addMessageUI("Graph added to workspace.", 'bot-msg');
            } else {
                // Has graphs: enter placement mode (click to replace OR click + to add)
                GraphManager.enterPlacementMode(plotlyData);
                if (AppState.graphs.length < AppState.maxGraphs) {
                    addMessageUI("Click a graph to replace, or click + to add.", 'bot-msg');
                } else {
                    addMessageUI("Workspace full. Click a graph to replace.", 'bot-msg');
                }
            }

            // Scroll to top to show the graphs area
            window.scrollTo({ top: 0, behavior: 'smooth' });
        } else {
            addMessageUI(data.response || "Couldn't generate graph.", 'bot-msg');
        }
    } catch (e) {
        clearInterval(timer);
        stopStatusPolling();
        status.textContent = 'Error.';
    } finally {
        input.disabled = false;
        currentQueryId = null;
        // Hide stop button, show send button
        if (stopBtn) stopBtn.style.display = 'none';
        if (sendBtn) sendBtn.style.display = 'inline-block';
    }
}

function addMessageUI(text, className, chatId = null, chartData = null) {
    if (!text) return;
    const box = document.getElementById('chat-messages');
    const div = document.createElement('div');
    div.className = `message ${className}`;

    // Markdown / Rendering
    if (typeof marked !== 'undefined') {
        div.innerHTML = marked.parse(text);
    } else {
        div.textContent = text;
    }

    // Feedback
    if (className === 'bot-msg' && chatId) {
        const fb = document.createElement('div');
        fb.className = 'mt-2 d-flex gap-2';
        fb.innerHTML = `
            <button class="btn btn-sm btn-outline-success" onclick="rate(${chatId}, 'like')"><i class="fas fa-thumbs-up"></i></button>
            <button class="btn btn-sm btn-outline-danger" onclick="rate(${chatId}, 'dislike')"><i class="fas fa-thumbs-down"></i></button>
        `;
        div.appendChild(fb);
    }

    box.appendChild(div);
    AppState.scrollToBottom();
    AppState.save();

    // If chart data came with a text message (implicit)
    if (chartData) {
        const plotly = buildChartFromTemplate(chartData);
        AppState.pendingGraphData = plotly;
        GraphManager.toggleEdit(true);
    }
}

// --- Lifecycle ---
document.addEventListener('DOMContentLoaded', async () => {
    // 1. Load Local State FIRST (so AppState.graphs is populated)
    const hasLocal = AppState.load();

    // 2. Initialize GraphManager (which will render the loaded graphs)
    GraphManager.init();

    // 3. Handle First Load / History Fetch
    // KEY FIX: Always try to sync history if we have a session ID, ensuring resilience against server restarts.
    if (AppState.sessionId) {
        await restoreFromBackend();
    } else {
        // New Session
        AppState.sessionId = crypto.randomUUID();
        if (localStorage.getItem('sfa_skip_history')) {
            localStorage.removeItem('sfa_skip_history');
        }
        loadDefaultGraphs();
    }

    // 4. Update Greeting
    const greet = document.getElementById('chat-greeting');
    if (greet && !hasLocal) greet.textContent = `Hello ${AppState.username}! How can I help?`;

    // 5. Listen for config updates from Settings page
    window.addEventListener('storage', (e) => {
        if (e.key === 'sfa_config_updated') {
            // Settings were saved, refresh default graphs
            console.log('Config updated, refreshing graphs...');
            refreshGraphs();
        }
    });

    // 6. Also check on window focus (if same tab navigation)
    let lastConfigCheck = localStorage.getItem('sfa_config_updated');
    window.addEventListener('focus', () => {
        const currentConfig = localStorage.getItem('sfa_config_updated');
        if (currentConfig && currentConfig !== lastConfigCheck) {
            lastConfigCheck = currentConfig;
            console.log('Detected config change on focus, refreshing...');
            refreshGraphs();
        }
    });
});

async function restoreFromBackend() {
    // Only fetch history for the CURRENT session. 
    // After a reset, this session is brand new and has no messages.
    if (!AppState.sessionId) {
        loadDefaultGraphs();
        return;
    }

    try {
        const res = await fetch(`/chat/history?session_id=${AppState.sessionId}`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        });
        const history = await res.json();
        if (history.length > 0) {
            document.getElementById('chat-messages').innerHTML = '';
            history.forEach(item => {
                addMessageUI(item.question, 'user-msg');
                addMessageUI(item.answer, 'bot-msg', item.id);
            });
        } else if (AppState.graphs.length === 0) {
            // Only load defaults if workspace is empty
            loadDefaultGraphs();
        }
    } catch (e) {
        if (AppState.graphs.length === 0) loadDefaultGraphs();
    }
}

async function loadDefaultGraphs() {
    try {
        const res = await fetch('/api/dashboard/metrics', {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        });
        const data = await res.json();

        // Only add graphs if data exists - use chart_type from settings
        if (data.graph1?.dates?.length && data.graph1?.values?.length) {
            const graph1Chart = buildChartFromTemplate({
                chart_type: data.graph1.chart_type,
                labels: data.graph1.dates,
                values: data.graph1.values,
                title: data.graph1.title,
                yLabel: data.graph1.y_label || 'Value'
            });
            // Tag as default for smart refreshing
            graph1Chart.sourceId = 'default_1';
            GraphManager.add(graph1Chart);
        }

        if (data.graph2?.dates?.length && data.graph2?.values?.length) {
            const graph2Chart = buildChartFromTemplate({
                chart_type: data.graph2.chart_type,
                labels: data.graph2.dates,
                values: data.graph2.values,
                title: data.graph2.title,
                yLabel: data.graph2.y_label || 'Value'
            });
            // Tag as default for smart refreshing
            graph2Chart.sourceId = 'default_2';
            GraphManager.add(graph2Chart);
        }
    } catch (e) { console.error("Default graphs failed", e); }
}

// --- Utils ---
function toggleEditMode() { GraphManager.toggleEdit(); }
function resetDashboard() {
    // Show Bootstrap modal instead of browser confirm
    const modal = new bootstrap.Modal(document.getElementById('resetModal'));
    modal.show();
}

function confirmReset() {
    // Close modal and reset
    bootstrap.Modal.getInstance(document.getElementById('resetModal')).hide();
    AppState.clear();
    location.reload();
}

// Current query ID for cancellation
let currentQueryId = null;

function stopQuery() {
    if (currentQueryId) {
        fetch(`/chat/cancel/${currentQueryId}`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        });

        const status = document.getElementById('status-indicator');
        if (status) status.textContent = 'Query cancelled.';

        const stopBtn = document.getElementById('stop-btn');
        if (stopBtn) stopBtn.style.display = 'none';

        const input = document.getElementById('user-input');
        if (input) input.disabled = false;

        currentQueryId = null;
    }
}

async function refreshGraphs() {
    GraphManager.exitPlacementMode();

    // Show loading indicator on graphs that are being updated
    // Instead of clearing all, we just fetch new data and update the ones that match

    try {
        const res = await fetch('/api/dashboard/metrics', {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        });
        const data = await res.json();

        let updatedAny = false;

        // Iterate through existing graphs and update only linked defaults
        AppState.graphs = AppState.graphs.map(g => {
            if (g.sourceId === 'default_1' && data.graph1?.dates?.length) {
                updatedAny = true;
                const newChart = buildChartFromTemplate({
                    chart_type: data.graph1.chart_type,
                    labels: data.graph1.dates,
                    values: data.graph1.values,
                    title: data.graph1.title,
                    yLabel: data.graph1.y_label || 'Value'
                });
                newChart.sourceId = 'default_1';
                return newChart;
            }
            if (g.sourceId === 'default_2' && data.graph2?.dates?.length) {
                updatedAny = true;
                const newChart = buildChartFromTemplate({
                    chart_type: data.graph2.chart_type,
                    labels: data.graph2.dates,
                    values: data.graph2.values,
                    title: data.graph2.title,
                    yLabel: data.graph2.y_label || 'Value'
                });
                newChart.sourceId = 'default_2';
                return newChart;
            }
            // Keep AI graphs or unlinked graphs exactly as they are
            return g;
        });

        GraphManager.render();
        AppState.save();

        // Feedback
        const status = document.getElementById('status-indicator');
        if (status) {
            status.innerHTML = updatedAny
                ? '<span class="text-success fade-out">Graphs updated</span>'
                : '<span class="text-secondary fade-out">No default graphs to update</span>';
            setTimeout(() => status.innerHTML = '', 3000);
        }

    } catch (e) {
        console.error("Refresh failed", e);
    }
}

function rate(id, type) {
    fetch(`/chat/feedback/${id}?feedback=${type}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
    }).then(() => {
        // Reset both buttons to default state
        const likeBtn = document.querySelector(`[onclick="rate(${id}, 'like')"]`);
        const dislikeBtn = document.querySelector(`[onclick="rate(${id}, 'dislike')"]`);

        if (likeBtn) {
            likeBtn.classList.remove('btn-success');
            likeBtn.classList.add('btn-outline-success');
            likeBtn.style.opacity = '0.7';
        }
        if (dislikeBtn) {
            dislikeBtn.classList.remove('btn-danger');
            dislikeBtn.classList.add('btn-outline-danger');
            dislikeBtn.style.opacity = '0.7';
        }

        // Highlight the clicked button
        const clickedBtn = document.querySelector(`[onclick="rate(${id}, '${type}')"]`);
        if (clickedBtn) {
            clickedBtn.style.opacity = '1';
            clickedBtn.classList.remove('btn-outline-success', 'btn-outline-danger');
            clickedBtn.classList.add(type === 'like' ? 'btn-success' : 'btn-danger');
        }
    });
}

// ============================================
// FINANCIAL CHART TEMPLATE ENGINE
// ============================================

function getThemeColors() {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    return {
        text: isDark ? '#e0e0e0' : '#333',
        grid: isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.08)'
    };
}

function getFinancialPalette(theme) {
    return {
        revenue: '#2ecc71',           // Green growth
        incomePositive: '#1abc9c',    // Teal profit
        incomeNegative: '#e74c3c',    // Red loss
        expense: '#f39c12',           // Orange expense
        stock: '#3498db',             // Blue stock
        grid: theme.grid,
        text: theme.text
    };
}

function buildChartFromTemplate(chartData) {
    const theme = getThemeColors();
    const palette = getFinancialPalette(theme);
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';

    const { template, chart_type, labels, values, title, yLabel, is_percentage, y_axis_title } = chartData;
    const templateKey = template || chart_type; // Support both old and new format

    // Determine axis formatting based on is_percentage flag
    const isPercentage = is_percentage === true;
    const tickPrefix = isPercentage ? '' : '$';
    const tickSuffix = isPercentage ? '%' : '';
    const hoverValueFormat = isPercentage ? '%{y:.1f}%' : '$%{y:,.0f}';

    const baseLayout = {
        title: { text: title, font: { size: 14, color: theme.text } },
        xaxis: {
            type: 'category',  // Force categorical to prevent "2024.5" interpolation
            showgrid: false,
            tickfont: { size: 9, color: theme.text },
            tickangle: -45,
            nticks: 8,  // Show max 8 labels to avoid clutter
            categoryorder: 'array',  // Preserve label order from data
            categoryarray: labels    // Use exact labels as categories
        },
        yaxis: {
            title: y_axis_title || yLabel || '',
            tickprefix: tickPrefix,
            ticksuffix: tickSuffix,
            separatethousands: true,
            gridcolor: theme.grid,
            tickfont: { size: 10, color: theme.text }
        },
        font: { color: theme.text, family: 'Inter, system-ui, sans-serif' },
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        hovermode: 'x unified',
        hoverlabel: {
            bgcolor: isDark ? '#2b3035' : '#ffffff',
            bordercolor: isDark ? '#444' : '#ddd',
            font: { color: isDark ? '#e0e0e0' : '#333', size: 12 }
        },
        margin: { l: 60, r: 20, t: 50, b: 60 }
    };

    // ======= PERCENTAGE DATA (Line chart for margin/rate trends) =======
    if (isPercentage || templateKey === 'line') {
        return {
            data: [{
                x: labels,
                y: values,
                type: 'scatter',
                mode: 'lines+markers',
                line: { width: 2, color: '#9b59b6', shape: 'spline' },
                marker: { size: 6 },
                hovertemplate: `<b>%{x}</b><br>Value: ${hoverValueFormat}<extra></extra>`
            }],
            layout: baseLayout
        };
    }

    // ======= REVENUE TREND (Line + Area Fill) =======
    if (templateKey === 'revenue_trend' || templateKey === 'scatter') {
        return {
            data: [{
                x: labels,
                y: values,
                type: 'scatter',
                mode: 'lines',
                line: { width: 3, color: palette.revenue, shape: 'spline' },
                fill: 'tozeroy',
                fillcolor: 'rgba(46,204,113,0.15)',
                hovertemplate: '<b>%{x}</b><br>Revenue: $%{y:,.0f}<extra></extra>'
            }],
            layout: baseLayout
        };
    }

    // ======= NET INCOME (Positive/Negative Bars) =======
    if (templateKey === 'net_income' || templateKey === 'bar') {
        const colors = values.map(v =>
            v >= 0 ? palette.incomePositive : palette.incomeNegative
        );
        return {
            data: [{
                x: labels,
                y: values,
                type: 'bar',
                marker: { color: colors, line: { width: 0 } },
                hovertemplate: `<b>%{x}</b><br>Value: ${hoverValueFormat}<extra></extra>`
            }],
            layout: baseLayout
        };
    }

    // ======= EXPENSES (Donut Pie Chart) =======
    if (templateKey === 'expenses' || templateKey === 'pie') {
        return {
            data: [{
                labels: labels,
                values: values,
                type: 'pie',
                hole: 0.45,
                marker: {
                    colors: ['#f39c12', '#e67e22', '#d35400', '#e74c3c', '#c0392b']
                },
                textinfo: 'label+percent',
                hovertemplate: '%{label}: $%{value:,.0f}<extra></extra>'
            }],
            layout: {
                ...baseLayout,
                xaxis: undefined,
                yaxis: undefined,
                showlegend: false
            }
        };
    }

    // ======= STOCK PRICE (Clean Line) =======
    if (templateKey === 'stock_price') {
        return {
            data: [{
                x: labels,
                y: values,
                type: 'scatter',
                mode: 'lines',
                line: { color: palette.stock, width: 2 },
                hovertemplate: '<b>%{x}</b><br>Price: $%{y:.2f}<extra></extra>'
            }],
            layout: {
                ...baseLayout,
                yaxis: { ...baseLayout.yaxis, title: 'Stock Price (USD)' }
            }
        };
    }

    // ======= FALLBACK (Bar Chart) =======
    console.warn('Unknown chart template:', templateKey, '- using bar fallback');
    return {
        data: [{
            x: labels,
            y: values,
            type: 'bar',
            marker: { color: palette.stock },
            hovertemplate: `<b>%{x}</b><br>Value: ${hoverValueFormat}<extra></extra>`
        }],
        layout: baseLayout
    };
}

function getCommonLayout(theme) {
    return {
        font: { color: theme.text },
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        margin: { l: 50, r: 15, t: 40, b: 50 }
    };
}

// React to theme changes
new MutationObserver(() => GraphManager.render()).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
