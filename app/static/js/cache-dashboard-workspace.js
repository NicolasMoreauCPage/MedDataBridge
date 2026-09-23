        let hitMissChart = null;

        async function fetchMetrics() {
            try {
                const { data } = await window.medbridgeHttp.get('/api/metrics/cache');
                return data;
            } catch (error) {
                showError(`Error fetching metrics: ${error.message}`);
                return null;
            }
        }

        function showError(message) {
            // Show error in cache status badge
            document.getElementById('cache-status').innerHTML = `
                <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-red-100 text-red-700">
                    Error: ${message}
                </span>
            `;
        }

        function updateMetrics(data) {
            if (!data || !data.enabled) {
                document.getElementById('cache-status').innerHTML = `
                    <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-700">
                        Unavailable
                    </span>
                `;
                showError('Cache service is not available');
                return;
            }

            // Status badge
            document.getElementById('cache-status').innerHTML = `
                <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700">
                    Operational
                </span>
            `;

            // Hit rate
            const hitRate = data.hit_rate || 0;
            document.getElementById('hit-rate').textContent = hitRate + '%';

            // Hits and misses
            const hits = data.keyspace_hits || 0;
            const misses = data.keyspace_misses || 0;
            document.getElementById('total-hits').textContent = hits.toLocaleString();
            document.getElementById('total-misses').textContent = misses.toLocaleString();

            // Memory
            document.getElementById('memory-used').textContent = data.used_memory || '--';

            // Total operations
            const totalOps = hits + misses;
            document.getElementById('total-ops').textContent = totalOps.toLocaleString();

            // Additional info
            document.getElementById('total-connections').textContent = 
                (data.total_connections || 0).toLocaleString();
            document.getElementById('total-commands').textContent = 
                (data.total_commands || 0).toLocaleString();

            // Update chart
            updateChart(hits, misses);
        }

        function updateChart(hits, misses) {
            const ctx = document.getElementById('hitMissChart').getContext('2d');

            if (hitMissChart) {
                hitMissChart.destroy();
            }

            hitMissChart = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: ['Cache Hits', 'Cache Misses'],
                    datasets: [{
                        data: [hits, misses],
                        backgroundColor: [
                            'rgba(16, 185, 129, 0.8)',
                            'rgba(239, 68, 68, 0.8)'
                        ],
                        borderColor: [
                            'rgba(16, 185, 129, 1)',
                            'rgba(239, 68, 68, 1)'
                        ],
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: {
                                font: {
                                    size: 14,
                                    family: "'Inter', sans-serif"
                                },
                                padding: 20
                            }
                        },
                        tooltip: {
                            backgroundColor: 'rgba(0, 0, 0, 0.8)',
                            padding: 12,
                            borderColor: 'rgba(255, 255, 255, 0.2)',
                            borderWidth: 1,
                            titleFont: {
                                size: 14,
                                family: "'Inter', sans-serif"
                            },
                            bodyFont: {
                                size: 13,
                                family: "'Inter', sans-serif"
                            },
                            callbacks: {
                                label: function(context) {
                                    const label = context.label || '';
                                    const value = context.parsed || 0;
                                    const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                    const percentage = total > 0 ? ((value / total) * 100).toFixed(2) : 0;
                                    return `${label}: ${value.toLocaleString()} (${percentage}%)`;
                                }
                            }
                        }
                    }
                }
            });
        }

        async function refreshMetrics() {
            const btn = document.getElementById('refreshBtn');
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '<span class="animate-spin inline-block mr-2">⏳</span> Loading...';
            }

            const data = await fetchMetrics();
            if (data) {
                updateMetrics(data);
            }

            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '🔄 Refresh Metrics';
            }
        }

        // Auto-refresh every 30 seconds
        setInterval(refreshMetrics, 30000);

        // Initial load
        refreshMetrics();


document.getElementById('refreshBtn')?.addEventListener('click', refreshMetrics);
