# PROMPT MESTRE - Backend Principal
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path

# Carrega variáveis de ambiente
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# App FastAPI
app = FastAPI(title="PROMPT MESTRE", description="Plataforma de Inteligência Comercial WhatsApp")

# Templates e Assets
TEMPLATE_DIR = Path("/app/template_extract")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# Monta assets estáticos
app.mount("/assets", StaticFiles(directory=str(TEMPLATE_DIR / "assets")), name="assets")

# Importa e configura rotas
from routes import webhook, leads, chat, settings, analytics

webhook.set_db(db)
leads.set_db(db)
chat.set_db(db)
settings.set_db(db)
analytics.set_db(db)

# Registra routers com prefixo /api
app.include_router(webhook.router, prefix="/api")
app.include_router(leads.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============ ROTAS HTML ============

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})

@app.get("/leads", response_class=HTMLResponse)
async def leads_page(request: Request):
    return templates.TemplateResponse("leads.html", {"request": request})

@app.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    return templates.TemplateResponse("config.html", {"request": request})

# Health check
@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "prompt_mestre"}

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
