# PROMPT MESTRE - Backend Principal
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging

# MongoDB
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="PROMPT MESTRE", description="Plataforma de Inteligência Comercial WhatsApp")

# UI estática (também servida pelo servidor do frontend na porta 3000)
TEMPLATE_DIR = Path("/app/frontend/public")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
app.mount("/assets", StaticFiles(directory=str(TEMPLATE_DIR / "assets")), name="assets")
app.mount("/js", StaticFiles(directory=str(TEMPLATE_DIR / "js")), name="js")

from routes import webhook, leads, chat, settings, analytics, evolution, auth, training, documents

for modulo in (webhook, leads, chat, settings, analytics, evolution, auth, training, documents):
    modulo.set_db(db)
    app.include_router(modulo.router, prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PAGINAS = ["login", "dashboard", "chat", "leads", "config", "treinamento", "usuarios"]


@app.get("/")
async def index():
    return RedirectResponse(url="/dashboard.html")


def _registrar_pagina(nome: str):
    @app.get(f"/{nome}", response_class=HTMLResponse, name=f"page_{nome}")
    async def pagina(request: Request, _nome=nome):
        return templates.TemplateResponse(f"{_nome}.html", {"request": request})

    @app.get(f"/{nome}.html", response_class=HTMLResponse, name=f"page_{nome}_html")
    async def pagina_html(request: Request, _nome=nome):
        return templates.TemplateResponse(f"{_nome}.html", {"request": request})


for _p in PAGINAS:
    _registrar_pagina(_p)


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "prompt_mestre"}


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.leads.create_index("phone")
    await db.messages.create_index("lead_id")
    await auth.seed_admin(db)
    logger.info("PROMPT MESTRE iniciado")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
