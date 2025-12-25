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
        try {
            const loaded = AppState.load();
            if (!loaded || !AppState.graphs || AppState.graphs.length === 0) {
                console.log("State empty, attempting to load defaults...");
                if (!loaded) AppState.sessionId = crypto.randomUUID();
                await MainController.loadDefaultGraphs();
            }
        } catch (e) {
            console.error("State load error:", e);
        }

        // 3. Init UI Components (Always run this!)
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

            if (data.trend?.values?.length) {
                const chart = GraphManager.buildChartFromTemplate({
                    ...data.trend, title: data.trend.title || 'Graph 1'
                });
                GraphManager.add(chart);
            }
            if (data.income_trend?.values?.length) {
                const chart = GraphManager.buildChartFromTemplate({
                    ...data.income_trend, title: data.income_trend.title || 'Graph 2'
                });
                GraphManager.add(chart);
            }
        } catch (e) {
            console.error("Defaults failed to load", e);
            // Don't throw, just let it be empty so renderEmpty() shows "Graph Space"
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
// Since explicit onclicks are used in HTML, we must expose these functions to global scope
window.sendMessage = () => ChatInterface.sendMessage();
window.requestGraph = () => ChatInterface.requestGraph();
window.toggleEditMode = () => MainController.toggleEditMode();
window.resetDashboard = () => MainController.resetDashboard();

// Start
document.addEventListener('DOMContentLoaded', MainController.init);
