# PROMPT MESTRE - PRD

## Problema original
Plataforma completa de inteligência comercial e atendimento via WhatsApp para empresa de consórcio:
Evolution API (gestão de instâncias no painel), agente IA (Claude Sonnet 5) que aprende com conversas
históricas dos especialistas e qualifica leads de forma invisível, CRM/funil, confirmação de venda
APENAS manual, intervenção humana, Meta CAPI configurável e dashboard para gestor de tráfego.
Restrições do usuário: SUPER ECONÔMICO em tokens, sem React SPA (HTML servido diretamente), idioma PT-BR.

## Arquitetura (atualizada em 11/08/2026)
- Backend FastAPI `/app/backend/server.py` (rotas /api + serve as páginas HTML).
- **UI em `/app/frontend/public/`** (login, dashboard, chat, leads, treinamento, usuarios, config + `js/app.js` + `assets` Metronic).
  Motivo: o ingress do preview envia todo tráfego não-/api para a porta 3000 (servidor do frontend);
  por isso as páginas ficam em `frontend/public` e são servidas em `/dashboard.html`, `/chat.html`, etc.
  A pasta `/app/template_extract` ficou como origem do template (não é mais a UI ativa).
- Rotas: `auth.py`, `leads.py`, `chat.py`, `documents.py`, `training.py`, `settings.py`, `analytics.py`,
  `evolution.py`, `webhook.py`. Serviços: `claude_service.py`, `evolution_service.py`, `meta_capi_service.py`.
- Coleções Mongo: `users`, `leads`, `messages`, `events`, `settings`, `playbooks`, `login_attempts`.

## Implementado
### Sessões anteriores
- Backend + UI HTML (dashboard, chat, leads, config), gestão de instâncias Evolution (criar, QR, webhook, status).

### 11/08/2026 (esta sessão)
- **Correção crítica**: preview estava servindo o app React vazio. UI migrada para `frontend/public` → plataforma no ar.
- **Autenticação JWT multi-usuário**: login, bcrypt, bloqueio após 5 tentativas (15 min), perfis admin/atendente,
  página `/usuarios.html` (criar, trocar senha, desativar, excluir). Admin semeado do `.env`.
- **Agente IA Claude Sonnet 5** (emergentintegrations/EMERGENT_LLM_KEY): regras invioláveis (nunca confirma venda,
  qualificação invisível, transferência imediata quando o cliente pede humano), contexto do lead + playbook.
- **Qualificação por IA** com fallback por palavras-chave; score, temperatura e avanço automático de estágio.
- **Módulo de Treinamento** `/treinamento.html`: upload do export .txt do WhatsApp → parser → playbook gerado pela IA,
  ativar/desativar/excluir; playbooks ativos entram no contexto de todo atendimento.
- **Controle de documentação**: checklist padrão, solicitar/receber/remover, progresso por lead.
- **Confirmação manual de venda** + marcar perdido, com evento Purchase para Meta CAPI.
- **Handoff humano**: assumir/devolver; enviar mensagem manual ativa o modo humano e silencia a IA.
- Dashboard com funil, origem e últimos 7 dias.

## Testes realizados (curl e2e + screenshots)
Login/JWT, /auth/me, usuários (criar), documentos (solicitar/receber/progresso), estágio, takeover,
confirm-sale, analytics, import de treinamento com playbook real gerado, webhook simulado da Evolution
(lead criado, qualificado score 35, resposta da IA gerada). Layout desktop e mobile validados.

## Backlog
- P1: Ligar credenciais reais da Evolution e conectar instância (usuário fará no painel).
- P1: Notificação sonora/desktop para o atendente quando um lead pede humano.
- P2: Valor da venda (ticket) no confirm-sale para ROI real por origem.
- P2: Relatório de ROI com custo de mídia importado do gestor de tráfego.
- P2: Follow-up automático de leads inativos (24h/72h).
