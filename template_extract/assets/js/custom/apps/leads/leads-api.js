// PROMPT MESTRE - Leads Management API
const API_BASE = window.location.origin + '/api';

const STAGE_LABELS = {
    'new': 'Novo',
    'in_progress': 'Em Andamento',
    'qualified': 'Qualificado',
    'negotiation': 'Negociação',
    'documentation': 'Documentação',
    'confirmed': 'Confirmado',
    'lost': 'Perdido'
};

const STAGE_BADGES = {
    'new': 'secondary',
    'in_progress': 'info',
    'qualified': 'primary',
    'negotiation': 'warning',
    'documentation': 'dark',
    'confirmed': 'success',
    'lost': 'danger'
};

let currentFilters = {};

// Carrega leads
async function loadLeads(filters = {}) {
    try {
        const params = new URLSearchParams(filters);
        const res = await fetch(`${API_BASE}/leads?${params}`);
        const data = await res.json();
        renderLeadsTable(data.leads || []);
        updateStats(data);
    } catch (e) {
        console.error('Erro ao carregar leads:', e);
    }
}

// Renderiza tabela de leads
function renderLeadsTable(leads) {
    const tbody = document.getElementById('leads-table-body');
    if (!tbody) return;
    
    if (leads.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-5">Nenhum lead encontrado</td></tr>';
        return;
    }
    
    tbody.innerHTML = leads.map(lead => `
        <tr>
            <td>
                <div class="d-flex align-items-center">
                    <div class="symbol symbol-circle symbol-50px overflow-hidden me-3">
                        <div class="symbol-label bg-light-${STAGE_BADGES[lead.stage] || 'secondary'}">
                            <span class="text-${STAGE_BADGES[lead.stage] || 'secondary'} fs-5 fw-bold">
                                ${(lead.name || lead.phone || '?')[0].toUpperCase()}
                            </span>
                        </div>
                    </div>
                    <div class="d-flex flex-column">
                        <span class="text-gray-800 fw-bold">${lead.name || 'Sem nome'}</span>
                        <span class="text-muted fs-7">${lead.phone}</span>
                    </div>
                </div>
            </td>
            <td>
                <span class="badge badge-light-${STAGE_BADGES[lead.stage]}">${STAGE_LABELS[lead.stage]}</span>
            </td>
            <td>
                <div class="d-flex align-items-center">
                    <span class="badge badge-${lead.temperature === 'hot' ? 'danger' : lead.temperature === 'warm' ? 'warning' : 'secondary'}">
                        ${lead.temperature}
                    </span>
                </div>
            </td>
            <td>
                <div class="progress h-6px w-100">
                    <div class="progress-bar bg-primary" style="width: ${Math.min(lead.score, 100)}%"></div>
                </div>
                <span class="text-muted fs-7">${lead.score} pts</span>
            </td>
            <td>
                ${lead.human_takeover ? '<span class="badge badge-warning">Humano</span>' : '<span class="badge badge-info">IA</span>'}
            </td>
            <td class="text-muted">${new Date(lead.updated_at).toLocaleDateString('pt-BR')}</td>
            <td class="text-end">
                <div class="dropdown">
                    <button class="btn btn-sm btn-light btn-active-light-primary" data-bs-toggle="dropdown">Ações</button>
                    <div class="dropdown-menu dropdown-menu-end">
                        <a class="dropdown-item" href="/chat?lead=${lead.id}">Ver Chat</a>
                        <a class="dropdown-item" href="#" onclick="changeStage('${lead.id}')">Mudar Estágio</a>
                        <div class="dropdown-divider"></div>
                        <a class="dropdown-item text-success" href="#" onclick="confirmSale('${lead.id}')">✓ Confirmar Venda</a>
                        <a class="dropdown-item text-danger" href="#" onclick="markLost('${lead.id}')">✗ Marcar Perdido</a>
                    </div>
                </div>
            </td>
        </tr>
    `).join('');
}

// Atualiza estatísticas
function updateStats(data) {
    const totalEl = document.getElementById('total-leads');
    if (totalEl) totalEl.textContent = data.total || 0;
}

// Confirma venda (MANUAL)
async function confirmSale(leadId) {
    if (!confirm('CONFIRMAR VENDA para este lead?')) return;
    
    try {
        const res = await fetch(`${API_BASE}/leads/${leadId}/confirm-sale`, { method: 'POST' });
        if (res.ok) {
            alert('Venda confirmada com sucesso!');
            loadLeads(currentFilters);
        } else {
            alert('Erro ao confirmar venda');
        }
    } catch (e) {
        console.error('Erro:', e);
    }
}

// Marca como perdido
async function markLost(leadId) {
    const reason = prompt('Motivo da perda (opcional):');
    
    try {
        const res = await fetch(`${API_BASE}/leads/${leadId}/mark-lost?reason=${encodeURIComponent(reason || '')}`, { method: 'POST' });
        if (res.ok) {
            loadLeads(currentFilters);
        }
    } catch (e) {
        console.error('Erro:', e);
    }
}

// Muda estágio
async function changeStage(leadId) {
    const stage = prompt('Novo estágio (new, in_progress, qualified, negotiation, documentation):');
    if (!stage) return;
    
    try {
        const res = await fetch(`${API_BASE}/leads/${leadId}/stage?stage=${stage}`, { method: 'PATCH' });
        if (res.ok) {
            loadLeads(currentFilters);
        }
    } catch (e) {
        console.error('Erro:', e);
    }
}

// Filtros
function filterByStage(stage) {
    currentFilters.stage = stage || undefined;
    loadLeads(currentFilters);
}

function filterByTemperature(temp) {
    currentFilters.temperature = temp || undefined;
    loadLeads(currentFilters);
}

// Init
document.addEventListener('DOMContentLoaded', () => {
    loadLeads();
    setInterval(() => loadLeads(currentFilters), 30000);
});
