/**
 * manager_analytics.js
 * Main Controller: Orchestrates Initialization, State Loading, and Global Event Handlers.
 * Depends on: analytics_state.js, analytics_graph.js, analytics_chat.js
 */

const MainController = {
    init: async () => {
        // 1. Check Connection
        try {
            const status = await API.get('/api/database/status');
            if (!status.connected) {
                MainController.showDatabaseRequired();
                return;
            }
        } catch (e) {
            MainController.showDatabaseRequired();
            return;
        }

        // 2. Load State or Defaults
        if (!AppState.load()) {
            AppState.sessionId = crypto.randomUUID();
            await MainController.loadDefaultGraphs();
        }

        // 3. Init UI Components
        GraphManager.init();
        ChatInterface.restoreHistory();
    },

    showDatabaseRequired: () => {
        const box = document.getElementById('graphs-track');
        if (box) {
            box.innerHTML = `<div class="text-center py-5 text-muted">
                <i class="fas fa-database fa-3x mb-3"></i><h5>Database Required</h5>
                <a href="/settings" class="btn btn-primary">Connect</a>
             </div>`;
        }
        const input = document.getElementById('user-input');
        if (input) input.disabled = true;
    },

    loadDefaultGraphs: async () => {
        try {
            const data = await API.get('/api/dashboard/metrics');
            let graphsAdded = 0;

            // Only add graphs if they have actual data (dates AND values)
            // API returns 'dates' not 'labels'
            if (data.trend?.values?.length && data.trend?.dates?.length) {
                const chart = GraphManager.buildChartFromTemplate({
                    labels: data.trend.dates,  // Map dates to labels
                    values: data.trend.values,
                    title: data.trend.title || 'Graph 1',
                    chart_type: data.trend.chart_type || 'line',
                    y_axis_title: data.trend.y_label || 'Value'
                });
                GraphManager.add(chart);
                graphsAdded++;
            }

            if (data.income_trend?.values?.length && data.income_trend?.dates?.length) {
                const chart = GraphManager.buildChartFromTemplate({
                    labels: data.income_trend.dates,  // Map dates to labels
                    values: data.income_trend.values,
                    title: data.income_trend.title || 'Graph 2',
                    chart_type: data.income_trend.chart_type || 'bar',
                    y_axis_title: data.income_trend.y_label || 'Value'
                });
                GraphManager.add(chart);
                graphsAdded++;
            }

            // If no graphs were added, show empty placeholder
            if (graphsAdded === 0) {
                GraphManager.renderEmpty();
            }
        } catch (e) {
            console.error("Defaults failed", e);
            // Show empty placeholder on error
            GraphManager.renderEmpty();
        }
    },

    toggleEditMode: () => {
        AppState.isEditMode = !AppState.isEditMode;
        GraphManager.render(); // Re-render to show/hide delete buttons

        // Update button UI
        const btn = document.getElementById('edit-mode-btn');
        if (btn) {
            btn.innerHTML = AppState.isEditMode ? '<i class="fas fa-check"></i> Done' : '<i class="fas fa-edit"></i>';
            btn.className = AppState.isEditMode ? 'btn btn-sm btn-primary' : 'btn btn-sm btn-outline-primary';
        }
    },

    resetDashboard: () => {
        if (confirm("Reset everything?")) {
            AppState.clear();
            location.reload();
        }
    }
};

// Global Event Handlers (exposed for HTML onclicks)
window.sendMessage = () => ChatInterface.sendMessage();
window.requestGraph = () => ChatInterface.requestGraph();
window.toggleEditMode = () => MainController.toggleEditMode();
window.resetDashboard = () => MainController.resetDashboard();
window.stopQuery = () => ChatInterface.stopQuery && ChatInterface.stopQuery();

// Add pending graph when + button is clicked
window.addPendingGraph = () => {
    if (window._pendingGraph) {
        GraphManager.add(window._pendingGraph, true);
        window._pendingGraph = null;
        const addBtn = document.getElementById('add-graph-btn');
        if (addBtn) {
            addBtn.style.display = 'none';
            addBtn.classList.remove('has-pending');
        }
    }
};

// Start
document.addEventListener('DOMContentLoaded', MainController.init);
