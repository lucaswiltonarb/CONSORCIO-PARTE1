// PROMPT MESTRE - Analytics Dashboard
const API_BASE = window.location.origin + '/api';

// Carrega overview
async function loadOverview() {
    try {
        const res = await fetch(`${API_BASE}/analytics/overview`);
        const data = await res.json();
        
        updateCard('total-leads', data.total_leads);
        updateCard('conversion-rate', data.conversion_rate + '%');
        updateCard('confirmed-sales', data.confirmed_sales);
        updateCard('hot-leads', data.by_temperature?.hot || 0);
        
    } catch (e) {
        console.error('Erro ao carregar overview:', e);
    }
}

// Carrega funil
async function loadFunnel() {
    try {
        const res = await fetch(`${API_BASE}/analytics/funnel`);
        const data = await res.json();
        renderFunnel(data.funnel || []);
    } catch (e) {
        console.error('Erro ao carregar funil:', e);
    }
}

// Carrega stats diárias
async function loadDailyStats() {
    try {
        const res = await fetch(`${API_BASE}/analytics/daily?days=7`);
        const data = await res.json();
        renderDailyChart(data.daily || []);
    } catch (e) {
        console.error('Erro ao carregar stats diárias:', e);
    }
}

// Carrega origens
async function loadOrigins() {
    try {
        const res = await fetch(`${API_BASE}/analytics/origin`);
        const data = await res.json();
        renderOriginsTable(data.origins || []);
    } catch (e) {
        console.error('Erro ao carregar origens:', e);
    }
}

// Atualiza card
function updateCard(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

// Renderiza funil
function renderFunnel(funnel) {
    const container = document.getElementById('funnel-container');
    if (!container) return;
    
    const maxCount = Math.max(...funnel.map(f => f.count), 1);
    const labels = {
        'new': 'Novos',
        'in_progress': 'Em Andamento',
        'qualified': 'Qualificados',
        'negotiation': 'Negociação',
        'documentation': 'Documentação',
        'confirmed': 'Confirmados'
    };
    
    container.innerHTML = funnel.map(item => {
        const width = Math.max((item.count / maxCount) * 100, 10);
        return `
            <div class="d-flex align-items-center mb-4">
                <div class="fw-semibold text-gray-600 w-125px">${labels[item.stage] || item.stage}</div>
                <div class="flex-grow-1">
                    <div class="progress h-20px">
                        <div class="progress-bar bg-primary" style="width: ${width}%">
                            ${item.count}
                        </div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

// Renderiza tabela de origens
function renderOriginsTable(origins) {
    const tbody = document.getElementById('origins-table-body');
    if (!tbody) return;
    
    tbody.innerHTML = origins.map(o => `
        <tr>
            <td class="fw-bold">${o.origin || 'Direto'}</td>
            <td>${o.total}</td>
            <td>${o.confirmed}</td>
            <td>${o.conversion_rate}%</td>
            <td>${o.avg_score} pts</td>
        </tr>
    `).join('');
}

// Gráfico diário (simples)
function renderDailyChart(daily) {
    const container = document.getElementById('daily-chart');
    if (!container) return;
    
    if (daily.length === 0) {
        container.innerHTML = '<div class="text-center text-muted py-5">Sem dados</div>';
        return;
    }
    
    const maxVal = Math.max(...daily.map(d => d.new_leads), 1);
    
    container.innerHTML = `
        <div class="d-flex align-items-end justify-content-between" style="height: 200px;">
            ${daily.map(d => {
                const height = Math.max((d.new_leads / maxVal) * 180, 10);
                return `
                    <div class="d-flex flex-column align-items-center mx-2">
                        <span class="fs-8 text-muted mb-1">${d.new_leads}</span>
                        <div class="bg-primary rounded" style="width: 30px; height: ${height}px;"></div>
                        <span class="fs-9 text-muted mt-1">${d._id?.substring(5) || ''}</span>
                    </div>
                `;
            }).join('')}
        </div>
    `;
}

// Init
document.addEventListener('DOMContentLoaded', () => {
    loadOverview();
    loadFunnel();
    loadDailyStats();
    loadOrigins();
    
    // Atualiza a cada 60s
    setInterval(() => {
        loadOverview();
        loadFunnel();
    }, 60000);
});
