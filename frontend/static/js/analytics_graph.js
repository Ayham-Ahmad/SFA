/**
 * analytics_graph.js
 * Handles rendering, adding, and removing graphs using Plotly.
 */

const GraphManager = {
    track: document.getElementById('graphs-track'),

    init() {
        this.render();
        // Listen for theme changes from base.js to redraw charts with correct colors
        window.addEventListener('themeChanged', () => this.render());
    },

    add(plotlyData) {
        if (AppState.graphs.length >= AppState.maxGraphs) return false;

        AppState.graphs.push({
            id: crypto.randomUUID(),
            data: plotlyData
        });

        AppState.save();
        this.render();
        return true;
    },

    remove(index) {
        AppState.graphs.splice(index, 1);
        AppState.save();
        this.render();
    },

    render() {
        // Re-acquire track element if lost (e.g. after page updates)
        if (!this.track) this.track = document.getElementById('graphs-track');
        if (!this.track) return;

        this.track.innerHTML = '';

        if (AppState.graphs.length === 0) {
            this.renderEmpty();
            return;
        }

        const colors = Theme.getColors(); // From base.js

        AppState.graphs.forEach((graph, index) => {
            const card = document.createElement('div');
            card.className = 'graph-card';
            if (AppState.isEditMode) card.classList.add('edit-mode');

            // Delete Button (visible in edit mode)
            if (AppState.isEditMode) {
                const delBtn = document.createElement('button');
                delBtn.className = 'btn btn-danger btn-sm graph-delete-btn';
                delBtn.innerHTML = '<i class="fas fa-times"></i>';
                delBtn.onclick = (e) => {
                    e.stopPropagation();
                    this.remove(index);
                };
                card.appendChild(delBtn);
            }

            // Graph Container
            const plotDiv = document.createElement('div');
            plotDiv.className = 'graph-content';
            card.appendChild(plotDiv);
            this.track.appendChild(card);

            // Apply Theme to Layout Dynamically
            const layout = {
                ...graph.data.layout,
                paper_bgcolor: 'transparent',
                plot_bgcolor: 'transparent',
                font: { color: colors.text },
                xaxis: {
                    ...graph.data.layout.xaxis,
                    gridcolor: colors.grid,
                    zerolinecolor: colors.grid,
                    color: colors.text
                },
                yaxis: {
                    ...graph.data.layout.yaxis,
                    gridcolor: colors.grid,
                    zerolinecolor: colors.grid,
                    color: colors.text
                }
            };

            // Render Plotly
            Plotly.newPlot(plotDiv, graph.data.data, layout, {
                responsive: true,
                displayModeBar: false
            });

            // Replacement Logic Placeholder
            card.onclick = () => {
                if (typeof window._pendingReplacement !== 'undefined' && window._pendingReplacement) {
                    AppState.graphs[index].data = window._pendingReplacement;
                    AppState.save();
                    window._pendingReplacement = null;
                    this.render();
                    // Notify user via ChatInterface if available? 
                    // Ideally dispatch event, but for now we assume ChatInterface exists
                    if (typeof ChatInterface !== 'undefined') {
                        ChatInterface.addMessage("Graph replaced successfully.", 'bot-msg');
                    }
                }
            };
        });
    },

    renderEmpty() {
        this.track.innerHTML = `
            <div class="empty-graph-space">
                <div class="empty-graph-text">Graph Space</div>
            </div>
        `;
    },

    // Helper to build Plotly config from API response
    buildChartFromTemplate(config) {
        const colors = Theme.getColors();
        return {
            data: [{
                x: config.labels || [],
                y: config.values || [],
                type: config.chart_type || 'scatter',
                mode: config.chart_type === 'line' ? 'lines+markers' : undefined,
                marker: { color: colors.primary || '#0d6efd' }
            }],
            layout: {
                title: config.title,
                autosize: true,
                margin: { t: 40, r: 20, l: 40, b: 40 }
            }
        };
    }
};
