// PROMPT MESTRE - Settings API
const API_BASE = window.location.origin + '/api';

// Carrega configurações
async function loadSettings() {
    try {
        const res = await fetch(`${API_BASE}/settings`);
        const data = await res.json();
        
        // Preenche formulário
        setValue('evolution_api_url', data.evolution_api_url);
        setValue('evolution_api_key', data.evolution_api_key);
        setValue('evolution_instance', data.evolution_instance);
        setValue('meta_pixel_id', data.meta_pixel_id);
        setValue('meta_capi_token', data.meta_capi_token);
        setValue('system_prompt', data.system_prompt);
        
        // Regras de qualificação
        if (data.qualification_rules) {
            setValue('min_score_qualified', data.qualification_rules.min_score_qualified);
            renderCriteria(data.qualification_rules.criteria || []);
        }
        
    } catch (e) {
        console.error('Erro ao carregar configurações:', e);
    }
}

function setValue(id, value) {
    const el = document.getElementById(id);
    if (el && value) el.value = value;
}

function renderCriteria(criteria) {
    const container = document.getElementById('criteria-container');
    if (!container) return;
    
    container.innerHTML = criteria.map((c, i) => `
        <div class="d-flex align-items-center mb-3" data-index="${i}">
            <input type="text" class="form-control form-control-sm me-2" value="${c.key}" placeholder="Chave" style="width: 120px;">
            <input type="text" class="form-control form-control-sm me-2" value="${c.question}" placeholder="Palavra-chave" style="width: 120px;">
            <input type="number" class="form-control form-control-sm me-2" value="${c.weight}" placeholder="Peso" style="width: 80px;">
        </div>
    `).join('');
}

// Salva configurações
async function saveSettings() {
    const data = {
        evolution_api_url: document.getElementById('evolution_api_url')?.value || null,
        evolution_api_key: document.getElementById('evolution_api_key')?.value || null,
        evolution_instance: document.getElementById('evolution_instance')?.value || null,
        meta_pixel_id: document.getElementById('meta_pixel_id')?.value || null,
        meta_capi_token: document.getElementById('meta_capi_token')?.value || null,
        system_prompt: document.getElementById('system_prompt')?.value || null
    };
    
    // Remove valores vazios
    Object.keys(data).forEach(k => { if (!data[k]) delete data[k]; });
    
    try {
        const res = await fetch(`${API_BASE}/settings`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        
        if (res.ok) {
            alert('Configurações salvas!');
        } else {
            alert('Erro ao salvar');
        }
    } catch (e) {
        console.error('Erro:', e);
    }
}

// Salva regras de qualificação
async function saveQualificationRules() {
    const minScore = parseInt(document.getElementById('min_score_qualified')?.value) || 50;
    
    // Coleta critérios
    const criteriaEls = document.querySelectorAll('#criteria-container > div');
    const criteria = [];
    
    criteriaEls.forEach(el => {
        const inputs = el.querySelectorAll('input');
        if (inputs.length >= 3) {
            criteria.push({
                key: inputs[0].value,
                question: inputs[1].value,
                weight: parseInt(inputs[2].value) || 10
            });
        }
    });
    
    try {
        const res = await fetch(`${API_BASE}/settings/qualification-rules`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ min_score_qualified: minScore, criteria })
        });
        
        if (res.ok) {
            alert('Regras de qualificação salvas!');
        }
    } catch (e) {
        console.error('Erro:', e);
    }
}

// Init
document.addEventListener('DOMContentLoaded', loadSettings);
