# Rotas Evolution API - Gestão de Instâncias
from fastapi import APIRouter, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
import httpx
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/evolution", tags=["evolution"])

db: AsyncIOMotorDatabase = None

def set_db(database: AsyncIOMotorDatabase):
    global db
    db = database

async def get_evolution_config():
    settings = await db.settings.find_one({"id": "main_settings"}, {"_id": 0})
    if not settings or not settings.get('evolution_api_url'):
        raise HTTPException(status_code=400, detail="Evolution API não configurada")
    return settings

@router.get("/instances")
async def list_instances():
    """Lista todas as instâncias"""
    cfg = await get_evolution_config()
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.get(
            f"{cfg['evolution_api_url']}/instance/fetchInstances",
            headers={"apikey": cfg['evolution_api_key']}
        )
        return res.json()

@router.post("/instances")
async def create_instance(instance_name: str):
    """Cria nova instância"""
    cfg = await get_evolution_config()
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(
            f"{cfg['evolution_api_url']}/instance/create",
            headers={"apikey": cfg['evolution_api_key'], "Content-Type": "application/json"},
            json={"instanceName": instance_name, "qrcode": True}
        )
        return res.json()

@router.get("/instances/{instance_name}/qrcode")
async def get_qrcode(instance_name: str):
    """Gera QR Code para conexão"""
    cfg = await get_evolution_config()
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.get(
            f"{cfg['evolution_api_url']}/instance/connect/{instance_name}",
            headers={"apikey": cfg['evolution_api_key']}
        )
        return res.json()

@router.get("/instances/{instance_name}/status")
async def get_status(instance_name: str):
    """Status da conexão"""
    cfg = await get_evolution_config()
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.get(
            f"{cfg['evolution_api_url']}/instance/connectionState/{instance_name}",
            headers={"apikey": cfg['evolution_api_key']}
        )
        return res.json()

@router.delete("/instances/{instance_name}")
async def delete_instance(instance_name: str):
    """Remove instância"""
    cfg = await get_evolution_config()
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.delete(
            f"{cfg['evolution_api_url']}/instance/delete/{instance_name}",
            headers={"apikey": cfg['evolution_api_key']}
        )
        return res.json()

@router.post("/instances/{instance_name}/webhook")
async def set_webhook(instance_name: str, webhook_url: str):
    """Configura webhook da instância"""
    cfg = await get_evolution_config()
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(
            f"{cfg['evolution_api_url']}/webhook/set/{instance_name}",
            headers={"apikey": cfg['evolution_api_key'], "Content-Type": "application/json"},
            json={"url": webhook_url, "events": ["messages.upsert"]}
        )
        return res.json()

@router.post("/instances/{instance_name}/logout")
async def logout_instance(instance_name: str):
    """Desconecta instância"""
    cfg = await get_evolution_config()
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.delete(
            f"{cfg['evolution_api_url']}/instance/logout/{instance_name}",
            headers={"apikey": cfg['evolution_api_key']}
        )
        return res.json()
