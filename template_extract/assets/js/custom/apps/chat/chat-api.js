// PROMPT MESTRE - Chat API Integration
const API_BASE = window.location.origin + '/api';
let currentLeadId = null;
let pollingInterval = null;

// Elementos do DOM
const chatList = document.querySelector('[data-kt-element="messages"]');
const chatInput = document.querySelector('[data-kt-element="input"]');
const sendBtn = document.querySelector('[data-kt-element="send"]');
const contactsList = document.getElementById('kt_chat_contacts_body');

// Carrega conversas ativas
async function loadActiveChats() {
    try {
        const res = await fetch(`${API_BASE}/chat/active`);
        const data = await res.json();
        renderContactsList(data.chats || []);
    } catch (e) {
        console.error('Erro ao carregar chats:', e);
    }
}

// Renderiza lista de contatos
function renderContactsList(chats) {
    if (!contactsList) return;
    
    if (chats.length === 0) {
        contactsList.innerHTML = '<div class="text-center text-muted py-5">Nenhuma conversa ativa</div>';
        return;
    }
    
    contactsList.innerHTML = chats.map(chat => `
        <div class="d-flex flex-stack py-4 border-bottom cursor-pointer chat-contact" 
             data-lead-id="${chat.id}" onclick="selectChat('${chat.id}')">
            <div class="d-flex align-items-center">
                <div class="symbol symbol-45px symbol-circle">
                    <span class="symbol-label bg-light-${chat.human_takeover ? 'warning' : 'primary'} text-${chat.human_takeover ? 'warning' : 'primary'} fs-6 fw-bolder">
                        ${(chat.name || chat.phone || '?')[0].toUpperCase()}
                    </span>
                </div>
                <div class="ms-5">
                    <a href="#" class="fs-5 fw-bold text-gray-900 text-hover-primary mb-2">
                        ${chat.name || chat.phone}
                    </a>
                    <div class="fw-semibold text-muted">
                        ${chat.last_message?.content?.substring(0, 30) || 'Sem mensagens'}...
                    </div>
                </div>
            </div>
            <div class="d-flex flex-column align-items-end ms-2">
                <span class="badge badge-${getTemperatureBadge(chat.temperature)} mb-1">${chat.temperature}</span>
                <span class="text-muted fs-7">${chat.stage}</span>
            </div>
        </div>
    `).join('');
}

function getTemperatureBadge(temp) {
    return temp === 'hot' ? 'danger' : temp === 'warm' ? 'warning' : 'secondary';
}

// Seleciona chat
async function selectChat(leadId) {
    currentLeadId = leadId;
    document.querySelectorAll('.chat-contact').forEach(el => el.classList.remove('bg-light-primary'));
    document.querySelector(`[data-lead-id="${leadId}"]`)?.classList.add('bg-light-primary');
    await loadMessages(leadId);
    startPolling();
}

// Carrega mensagens do lead
async function loadMessages(leadId) {
    try {
        const res = await fetch(`${API_BASE}/leads/${leadId}/messages`);
        const data = await res.json();
        renderMessages(data.messages || []);
    } catch (e) {
        console.error('Erro ao carregar mensagens:', e);
    }
}

// Renderiza mensagens
function renderMessages(messages) {
    if (!chatList) return;
    
    chatList.innerHTML = messages.map(msg => {
        const isLead = msg.role === 'lead';
        const isHuman = msg.role === 'human';
        const align = isLead ? 'start' : 'end';
        const bgClass = isLead ? 'bg-light-info' : (isHuman ? 'bg-light-success' : 'bg-light-primary');
        const label = isLead ? 'Cliente' : (isHuman ? 'Você' : 'IA');
        
        return `
            <div class="d-flex justify-content-${align} mb-10">
                <div class="d-flex flex-column align-items-${align}">
                    <div class="d-flex align-items-center mb-2">
                        <span class="text-muted fs-7">${label} - ${new Date(msg.timestamp).toLocaleTimeString('pt-BR')}</span>
                    </div>
                    <div class="p-5 rounded ${bgClass} text-gray-900 fw-semibold mw-lg-400px text-${align}">
                        ${msg.content}
                    </div>
                </div>
            </div>
        `;
    }).join('');
    
    chatList.scrollTop = chatList.scrollHeight;
}

// Envia mensagem como humano
async function sendMessage() {
    if (!currentLeadId || !chatInput) return;
    
    const content = chatInput.value.trim();
    if (!content) return;
    
    try {
        const res = await fetch(`${API_BASE}/chat/send?lead_id=${currentLeadId}&content=${encodeURIComponent(content)}`, {
            method: 'POST'
        });
        
        if (res.ok) {
            chatInput.value = '';
            await loadMessages(currentLeadId);
        } else {
            alert('Erro ao enviar mensagem');
        }
    } catch (e) {
        console.error('Erro:', e);
    }
}

// Assume controle (takeover)
async function takeoverChat() {
    if (!currentLeadId) return;
    
    try {
        await fetch(`${API_BASE}/leads/${currentLeadId}/takeover`, { method: 'POST' });
        alert('Você assumiu o controle da conversa');
        loadActiveChats();
    } catch (e) {
        console.error('Erro:', e);
    }
}

// Devolve para IA
async function releaseChat() {
    if (!currentLeadId) return;
    
    try {
        await fetch(`${API_BASE}/leads/${currentLeadId}/release`, { method: 'POST' });
        alert('Conversa devolvida para o agente IA');
        loadActiveChats();
    } catch (e) {
        console.error('Erro:', e);
    }
}

// Polling para novas mensagens
function startPolling() {
    if (pollingInterval) clearInterval(pollingInterval);
    pollingInterval = setInterval(() => {
        if (currentLeadId) loadMessages(currentLeadId);
    }, 5000);
}

// Event listeners
document.addEventListener('DOMContentLoaded', () => {
    loadActiveChats();
    
    if (sendBtn) {
        sendBtn.addEventListener('click', sendMessage);
    }
    
    if (chatInput) {
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }
    
    // Atualiza lista a cada 10s
    setInterval(loadActiveChats, 10000);
});
