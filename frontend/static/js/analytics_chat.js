/**
 * analytics_chat.js
 * Handles Chat Interface logic: Sending messages, UI updates, and Graph requests.
 */

const ChatInterface = {

    // Send a text message to the bot
    async sendMessage() {
        const input = document.getElementById('user-input');
        const msg = input.value.trim();
        if (!msg) return;

        this.addMessage(msg, 'user-msg');
        input.value = '';
        input.disabled = true;

        const status = document.getElementById('status-indicator');
        if (status) status.textContent = 'Thinking...';

        try {
            const data = await API.post('/chat', {
                message: msg,
                session_id: AppState.sessionId
            });

            this.addMessage(data.response, 'bot-msg', data.chat_id);
        } catch (e) {
            this.addMessage("Error: " + e.message, 'bot-msg error');
        } finally {
            if (status) status.textContent = '';
            input.disabled = false;
            input.focus();
        }
    },

    // Request a graph generation
    async requestGraph() {
        const input = document.getElementById('user-input');
        const msg = input.value.trim();
        if (!msg) return alert("Describe the graph you want!");

        this.addMessage(msg, 'user-msg');
        input.value = '';

        // Timer UI
        const status = document.getElementById('status-indicator');
        if (status) {
            status.innerHTML = `<i class="fas fa-spinner fa-spin"></i> Generating... <span id="timer">0s</span>`;
            let sec = 0;
            const interval = setInterval(() => {
                const t = document.getElementById('timer');
                if (t) t.textContent = ++sec + 's';
            }, 1000);

            // Allow cleanup of interval in closure if needed, but for now simple
            // We attach it to the element logic roughly or just clear it later
            this._currentInterval = interval;
        }

        try {
            const data = await API.post('/chat', {
                message: msg,
                session_id: AppState.sessionId,
                interaction_type: 'graph'
            });

            if (this._currentInterval) clearInterval(this._currentInterval);
            if (status) status.textContent = '';

            if (data.chart_data) {
                // Use GraphManager helper to build chart
                const plotlyData = GraphManager.buildChartFromTemplate(data.chart_data);
                this.addMessage(data.response, 'bot-msg', data.chat_id);

                // Set as pending and show + button
                if (AppState.graphs.length < AppState.maxGraphs) {
                    GraphManager.setPending(plotlyData);
                    this.addMessage("📊 Graph ready! Click the + button to add it to your workspace.", 'bot-msg');
                } else {
                    // Workspace full - set as replacement
                    window._pendingReplacement = plotlyData;
                    this.addMessage("Workspace full. Click a graph above to replace it.", 'bot-msg');
                    // Trigger edit mode to show boundaries
                    if (!AppState.isEditMode) MainController.toggleEditMode();
                }
                window.scrollTo({ top: 0, behavior: 'smooth' });
            } else {
                this.addMessage(data.response || "No graph generated.", 'bot-msg');
            }
        } catch (e) {
            if (this._currentInterval) clearInterval(this._currentInterval);
            if (status) status.textContent = 'Error requesting graph.';
            this.addMessage("Error: " + e.message, 'bot-msg');
        }
    },

    addMessage(text, className, chatId = null) {
        const box = document.getElementById('chat-messages');
        if (!box) return;

        const div = document.createElement('div');
        div.className = `message ${className}`;

        // Use marked.js if available
        if (typeof marked !== 'undefined') div.innerHTML = marked.parse(text);
        else div.textContent = text;

        box.appendChild(div);
        box.scrollTop = box.scrollHeight;
    },

    async restoreHistory() {
        if (!AppState.sessionId) return;
        try {
            const history = await API.get(`/chat/history?session_id=${AppState.sessionId}`);
            if (history && history.length) {
                const box = document.getElementById('chat-messages');
                if (box) box.innerHTML = ''; // Clear greeting
                history.forEach(h => {
                    this.addMessage(h.question, 'user-msg');
                    this.addMessage(h.answer, 'bot-msg', h.id);
                });
            }
        } catch (e) {
            console.error("Failed to restore history", e);
        }
    }
};
