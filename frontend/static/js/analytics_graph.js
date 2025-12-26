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

    add(plotlyData, animate = true) {
        if (AppState.graphs.length >= AppState.maxGraphs) return false;

        AppState.graphs.push({
            id: crypto.randomUUID(),
            data: plotlyData,
            isNew: animate // Mark as new for animation
        });

        AppState.save();
        this.render();

        // Hide add button after adding
        const addBtn = document.getElementById('add-graph-btn');
        if (addBtn) addBtn.style.display = 'none';
        window._pendingGraph = null;

        return true;
    },

    // Set a pending graph (shows the + button)
    setPending(plotlyData) {
        window._pendingGraph = plotlyData;
        const addBtn = document.getElementById('add-graph-btn');
        if (addBtn && AppState.graphs.length < AppState.maxGraphs) {
            addBtn.style.display = 'flex';
            addBtn.classList.add('has-pending');
        }
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

            // Add juggle animation for new graphs
            if (graph.isNew) {
                card.classList.add('new-graph');
                // Remove the flag after animation
                setTimeout(() => {
                    graph.isNew = false;
                    AppState.save();
                }, 500);
            }

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

            // Apply Theme to Layout Dynamically with improved hover
            const layout = {
                ...graph.data.layout,
                paper_bgcolor: 'transparent',
                plot_bgcolor: 'transparent',
                font: { color: colors.text, size: 12 },
                hoverlabel: {
                    bgcolor: '#1a1a2e',
                    bordercolor: '#00d884',
                    font: {
                        color: '#ffffff',
                        size: 14,
                        family: 'Inter, Arial, sans-serif'
                    },
                    padding: { t: 10, b: 10, l: 15, r: 15 }
                },
                xaxis: {
                    ...graph.data.layout?.xaxis,
                    gridcolor: colors.grid,
                    zerolinecolor: colors.grid,
                    color: colors.text
                },
                yaxis: {
                    ...graph.data.layout?.yaxis,
                    gridcolor: colors.grid,
                    zerolinecolor: colors.grid,
                    color: colors.text
                }
            };

            // Render Plotly with enhanced config
            Plotly.newPlot(plotDiv, graph.data.data, layout, {
                responsive: true,
                displayModeBar: false,
                hovermode: 'closest'
            });

            // Replacement Logic Placeholder
            card.onclick = () => {
                if (typeof window._pendingReplacement !== 'undefined' && window._pendingReplacement) {
                    AppState.graphs[index].data = window._pendingReplacement;
                    AppState.save();
                    window._pendingReplacement = null;
                    this.render();
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

    // Helper to build Plotly config from API response - matches graph_builder.py format
    buildChartFromTemplate(config) {
        const colors = Theme.getColors();
        const chartType = config.chart_type || 'bar';

        // Determine trace type and mode based on chart type
        let trace = {
            x: config.labels || [],
            y: config.values || [],
            name: config.title || 'Value'
        };

        // Apply styling based on chart type (matching graph_builder.py)
        switch (chartType) {
            case 'line':
                trace.type = 'scatter';
                trace.mode = 'lines+markers';
                trace.line = { color: '#2196F3', width: 2 };
                trace.marker = { size: 8 };
                break;
            case 'bar':
                trace.type = 'bar';
                trace.marker = { color: '#4CAF50' };
                break;
            case 'scatter':
                trace.type = 'scatter';
                trace.mode = 'markers';
                trace.marker = { size: 12, color: '#FF5722' };
                break;
            case 'pie':
                trace = {
                    labels: config.labels || [],
                    values: config.values || [],
                    type: 'pie',
                    hole: 0.3,
                    textinfo: 'label+percent'
                };
                break;
            default:
                trace.type = 'bar';
                trace.marker = { color: '#4CAF50' };
        }

        return {
            data: [trace],
            layout: {
                title: config.title || '',
                autosize: true,
                margin: { t: 40, r: 20, l: 50, b: 40 },
                xaxis: { title: '' },
                yaxis: { title: config.y_axis_title || 'USD' }
            }
        };
    }
};
