/**
 * analytics_state.js
 * Manages the application state (graphs, session, history) for Analytics.
 */

const AppState = {
    graphs: [],
    maxGraphs: 2,
    isEditMode: false,
    sessionId: null,
    username: Auth.getUsername(),

    // Persist state to local storage
    save() {
        const data = {
            graphs: this.graphs.map(g => g.data), // Save Plotly data
            sessionId: this.sessionId,
            timestamp: Date.now()
        };
        localStorage.setItem(this.getStorageKey(), JSON.stringify(data));
    },

    // Load state from local storage
    load() {
        try {
            const raw = localStorage.getItem(this.getStorageKey());
            if (!raw) return false;

            const data = JSON.parse(raw);
            if (data.sessionId) this.sessionId = data.sessionId;

            if (data.graphs && Array.isArray(data.graphs)) {
                this.graphs = data.graphs.map(d => ({
                    id: d.uid || crypto.randomUUID(),
                    data: d
                }));
            }
            return true;
        } catch (e) {
            console.error("State load failed", e);
            return false;
        }
    },

    getStorageKey() {
        return `sfa_analytics_${this.username}`;
    },

    clear() {
        localStorage.removeItem(this.getStorageKey());
        this.graphs = [];
        this.sessionId = crypto.randomUUID();
    }
};
