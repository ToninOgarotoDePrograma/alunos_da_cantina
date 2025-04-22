function initDashboardCharts(stats) {
    // Gráfico de Pedidos
    const ctx = document.getElementById('pedidosChart').getContext('2d');
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Recebidos', 'Preparando', 'Prontos', 'Entregues'],
            datasets: [{
                label: 'Status dos Pedidos',
                data: [
                    stats.pedidos_recebidos,
                    stats.pedidos_preparando,
                    stats.pedidos_prontos,
                    stats.pedidos_entregues
                ],
                backgroundColor: [
                    '#3498db',
                    '#f39c12',
                    '#2ecc71',
                    '#95a5a6'
                ]
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'top',
                }
            }
        }
    });
}