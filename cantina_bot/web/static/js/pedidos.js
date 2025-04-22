document.addEventListener('DOMContentLoaded', function() {
    // Filtros
    const searchInput = document.getElementById('search-orders');
    const statusFilter = document.getElementById('status-filter');
    const refreshBtn = document.getElementById('refresh-btn');

    // Modal
    const detailsModal = new bootstrap.Modal(document.getElementById('orderDetailsModal'));
    const viewDetailButtons = document.querySelectorAll('.view-details');

    // Atualizar filtros
    function applyFilters() {
        const searchValue = searchInput.value.toLowerCase();
        const statusValue = statusFilter.value.toLowerCase();

        document.querySelectorAll('tbody tr').forEach(row => {
            const user = row.cells[1].textContent.toLowerCase();
            const item = row.cells[2].textContent.toLowerCase();
            const status = row.dataset.status.toLowerCase();

            const matchesSearch = user.includes(searchValue) || item.includes(searchValue);
            const matchesStatus = statusValue === 'all' || status === statusValue;

            row.style.display = matchesSearch && matchesStatus ? '' : 'none';
        });
    }

    // Event listeners
    searchInput.addEventListener('input', applyFilters);
    statusFilter.addEventListener('change', applyFilters);
    refreshBtn.addEventListener('click', function() {
        window.location.reload();
    });

    // Mostrar detalhes do pedido
    viewDetailButtons.forEach(button => {
        button.addEventListener('click', function() {
            const row = this.closest('tr');
            const orderId = row.dataset.id;

            // Preencher modal
            document.getElementById('modal-order-id').textContent = orderId;
            document.getElementById('modal-order-user').textContent = row.cells[1].textContent;
            document.getElementById('modal-order-item').textContent = row.cells[2].textContent;
            document.getElementById('modal-order-quantity').textContent = row.cells[3].textContent;
            document.getElementById('modal-order-time').textContent = row.cells[5].textContent;

            // Status
            const statusBadge = document.getElementById('modal-order-status');
            statusBadge.textContent = row.cells[4].textContent;
            statusBadge.className = 'badge ' + row.cells[4].querySelector('.badge').className;

            // Buscar observações via API
            fetch(`/pedidos/${orderId}`)
                .then(response => response.json())
                .then(data => {
                    document.getElementById('modal-order-notes').textContent =
                        data.observacoes || 'Nenhuma observação';
                });

            detailsModal.show();
        });
    });

    // Atualizar status do pedido
    document.querySelectorAll('.mark-ready').forEach(button => {
        button.addEventListener('click', function() {
            const orderId = this.dataset.id;
            if (confirm(`Marcar pedido #${orderId} como pronto?`)) {
                updateOrderStatus(orderId, 'Pronto');
            }
        });
    });

    document.querySelectorAll('.cancel-order').forEach(button => {
        button.addEventListener('click', function() {
            const orderId = this.dataset.id;
            if (confirm(`Cancelar pedido #${orderId}?`)) {
                updateOrderStatus(orderId, 'Cancelado');
            }
        });
    });

    // Função para atualizar status (AJAX)
    function updateOrderStatus(orderId, newStatus) {
        fetch(`/pedidos/${orderId}`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ status: newStatus })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status) {
                // Atualizar UI
                const row = document.querySelector(`tr[data-id="${orderId}"]`);
                if (row) {
                    row.dataset.status = newStatus;
                    const statusCell = row.cells[4];
                    statusCell.innerHTML = `<span class="badge bg-${
                        newStatus === 'Recebido' ? 'primary' :
                        newStatus === 'Preparando' ? 'warning' :
                        newStatus === 'Pronto' ? 'success' :
                        newStatus === 'Entregue' ? 'secondary' : 'danger'
                    }">${newStatus}</span>`;
                }
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Erro ao atualizar pedido');
        });
    }

    // Notificar cliente
    document.getElementById('notify-customer').addEventListener('click', function() {
        const orderId = document.getElementById('modal-order-id').textContent;
        const message = prompt('Digite a mensagem para o cliente:');

        if (message) {
            // Enviar notificação (simulado)
            alert(`Notificação enviada para o pedido #${orderId}`);
            detailsModal.hide();
        }
    });
});