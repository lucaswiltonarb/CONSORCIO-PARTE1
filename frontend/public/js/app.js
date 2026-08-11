// PROMPT MESTRE - utilitários compartilhados
const API = '/api';
const TOKEN_KEY = 'pm_token';
const USER_KEY = 'pm_user';

function getToken() { return localStorage.getItem(TOKEN_KEY); }
function getUser() { try { return JSON.parse(localStorage.getItem(USER_KEY) || 'null'); } catch (e) { return null; } }

function logout() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  window.location.href = '/login.html';
}

async function api(path, options = {}) {
  const opts = { ...options, headers: { 'Content-Type': 'application/json', ...(options.headers || {}) } };
  const token = getToken();
  if (token) opts.headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${API}${path}`, opts);
  if (res.status === 401) { logout(); throw new Error('Sessão expirada'); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Erro na requisição');
  return data;
}

async function apiUpload(path, formData) {
  const token = getToken();
  const res = await fetch(`${API}${path}`, {
    method: 'POST',
    headers: token ? { 'Authorization': `Bearer ${token}` } : {},
    body: formData
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Falha no upload');
  return data;
}

function guard() {
  if (!getToken()) { window.location.href = '/login.html'; return false; }
  return true;
}

const NAV_ITENS = [
  { href: '/dashboard.html', label: 'Dashboard' },
  { href: '/chat.html', label: 'Atendimento' },
  { href: '/leads.html', label: 'Leads / CRM' },
  { href: '/treinamento.html', label: 'Treinamento IA' },
  { href: '/usuarios.html', label: 'Usuários', adminOnly: true },
  { href: '/config.html', label: 'Configurações' },
];

function renderNav(ativo) {
  const user = getUser() || {};
  const links = NAV_ITENS
    .filter(i => !i.adminOnly || user.role === 'admin')
    .map(i => `<a href="${i.href}" data-testid="nav-${i.label.toLowerCase().replace(/[^a-z]/g,'-')}"
        class="btn btn-sm mb-1" style="${i.href === ativo
          ? 'background:#ffffff;color:#101132;font-weight:600'
          : 'background:rgba(255,255,255,.08);color:#e6e6ef;border:1px solid rgba(255,255,255,.18)'}">${i.label}</a>`)
    .join('');

  const el = document.getElementById('pm-nav');
  if (!el) return;
  el.innerHTML = `
    <div class="py-4" style="background:#101132">
      <div class="container-fluid d-flex flex-column flex-md-row align-items-start align-items-md-center justify-content-between gap-3">
        <a href="/dashboard.html" class="text-decoration-none">
          <span class="text-white fs-3 fw-bolder">PROMPT<span class="text-primary">MESTRE</span></span>
        </a>
        <div class="d-flex flex-wrap align-items-center gap-2">
          ${links}
          <span class="fs-8 ms-2 me-1 d-none d-lg-inline" style="color:#8e8fa8">${user.email || ''}</span>
          <button onclick="logout()" data-testid="logout-btn" class="btn btn-sm btn-light-danger mb-1">Sair</button>
        </div>
      </div>
    </div>`;
}

function badgeTemp(t) {
  const map = { hot: 'danger', warm: 'warning', cold: 'secondary' };
  const nome = { hot: 'Quente', warm: 'Morno', cold: 'Frio' };
  return `<span class="badge badge-light-${map[t] || 'secondary'}">${nome[t] || t}</span>`;
}

const STAGE_LABEL = {
  new: 'Novo', in_progress: 'Em conversa', qualified: 'Qualificado',
  negotiation: 'Negociação', documentation: 'Documentação',
  confirmed: 'Venda confirmada', lost: 'Perdido'
};

function toast(msg, tipo = 'success') {
  const div = document.createElement('div');
  div.className = `alert alert-${tipo === 'success' ? 'success' : 'danger'} position-fixed`;
  div.style.cssText = 'top:20px;right:20px;z-index:9999;min-width:280px';
  div.setAttribute('data-testid', 'toast-msg');
  div.textContent = msg;
  document.body.appendChild(div);
  setTimeout(() => div.remove(), 3500);
}
