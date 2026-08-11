# Rotas de Analytics - Dashboard Traffic Manager
from fastapi import APIRouter, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analytics", tags=["analytics"])

db: AsyncIOMotorDatabase = None

def set_db(database: AsyncIOMotorDatabase):
    global db
    db = database

@router.get("/overview")
async def get_overview():
    """Métricas gerais do funil"""
    # Contagem por estágio
    pipeline = [
        {"$group": {"_id": "$stage", "count": {"$sum": 1}}}
    ]
    stages = await db.leads.aggregate(pipeline).to_list(20)
    stages_dict = {s['_id']: s['count'] for s in stages}
    
    # Contagem por temperatura
    temp_pipeline = [
        {"$group": {"_id": "$temperature", "count": {"$sum": 1}}}
    ]
    temps = await db.leads.aggregate(temp_pipeline).to_list(10)
    temps_dict = {t['_id']: t['count'] for t in temps}
    
    total = await db.leads.count_documents({})
    confirmed = stages_dict.get('confirmed', 0)
    
    return {
        "total_leads": total,
        "by_stage": stages_dict,
        "by_temperature": temps_dict,
        "conversion_rate": round((confirmed / total * 100) if total > 0 else 0, 2),
        "confirmed_sales": confirmed
    }

@router.get("/funnel")
async def get_funnel_metrics():
    """Métricas do funil de conversão"""
    stages_order = ['new', 'in_progress', 'qualified', 'negotiation', 'documentation', 'confirmed']
    
    pipeline = [
        {"$match": {"stage": {"$ne": "lost"}}},
        {"$group": {"_id": "$stage", "count": {"$sum": 1}}}
    ]
    
    result = await db.leads.aggregate(pipeline).to_list(20)
    counts = {r['_id']: r['count'] for r in result}
    
    funnel = []
    for stage in stages_order:
        count = counts.get(stage, 0)
        funnel.append({"stage": stage, "count": count})
    
    return {"funnel": funnel}

@router.get("/daily")
async def get_daily_stats(days: int = Query(default=7, le=30)):
    """Estatísticas diárias"""
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    pipeline = [
        {"$match": {"created_at": {"$gte": start_date.isoformat()}}},
        {"$addFields": {
            "date": {"$substr": ["$created_at", 0, 10]}
        }},
        {"$group": {
            "_id": "$date",
            "new_leads": {"$sum": 1},
            "qualified": {
                "$sum": {"$cond": [{"$eq": ["$stage", "qualified"]}, 1, 0]}
            },
            "confirmed": {
                "$sum": {"$cond": [{"$eq": ["$stage", "confirmed"]}, 1, 0]}
            }
        }},
        {"$sort": {"_id": 1}}
    ]
    
    daily = await db.leads.aggregate(pipeline).to_list(days)
    
    return {"daily": daily}

@router.get("/origin")
async def get_origin_stats():
    """Estatísticas por origem"""
    pipeline = [
        {"$group": {
            "_id": "$origin",
            "total": {"$sum": 1},
            "confirmed": {
                "$sum": {"$cond": [{"$eq": ["$stage", "confirmed"]}, 1, 0]}
            },
            "avg_score": {"$avg": "$score"}
        }},
        {"$project": {
            "origin": {"$ifNull": ["$_id", "direto"]},
            "total": 1,
            "confirmed": 1,
            "avg_score": {"$round": ["$avg_score", 1]},
            "conversion_rate": {
                "$round": [{"$multiply": [{"$divide": ["$confirmed", {"$max": ["$total", 1]}]}, 100]}, 1]
            }
        }}
    ]
    
    origins = await db.leads.aggregate(pipeline).to_list(50)
    return {"origins": origins}
