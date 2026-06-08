"""
BTCVision API Server - REST API Interface
خادم API للتفاعل مع جسر التبرع وبروتوكول الاتصال
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Header, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn
import yaml

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from .models import (
    APIResponse, DonationResponse, AgentCard, AgentDiscoveryResponse,
    MessageHeader, MessageType, BTCVisionConfig, SecurityConfig,
    BridgeConfig, DefenseReport, ThreatLevel
)
from .defense_layer import get_defense_layer, DefenseLayer
from .btcai_protocol import BTCAIProtocol, BTCAIBridge, get_bridge
from .donation_bridge import DonationBridge, get_donation_bridge


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ============================================================================
# Request/Response Models
# ============================================================================

class DonationInitiateRequest(BaseModel):
    """طلب بدء تبرع"""
    session_id: str = Field(..., description="معرف الجلسة الفريد")
    sender_did: str = Field(..., description="DID المرسل")
    amount_sats: Optional[int] = Field(None, description="المبلغ بالساتوشي")
    lang: str = Field("en", description="اللغة (ar, en, zh)")
    coin: str = Field("BTC", description="العملة: BTC | ETH | BNB | SOL")

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "user-session-123",
                "sender_did": "did:example:user-agent-001",
                "amount_sats": 21000,
                "lang": "ar",
                "coin": "BTC"
            }
        }


class ConsentRequest(BaseModel):
    """طلب موافقة"""
    request_id: str = Field(..., description="معرف طلب التبرع")
    consent_granted: bool = Field(..., description="هل تم منح الموافقة")
    session_id: str = Field(..., description="معرف الجلسة")
    user_id_hash: Optional[str] = Field(None, description="تجزئة معرف المستخدم")


class DonationExecuteRequest(BaseModel):
    """طلب تنفيذ تبرع"""
    request_id: str = Field(..., description="معرف طلب التبرع")
    consent_token: str = Field(..., description="رمز الموافقة")


class AgentProbeRequest(BaseModel):
    """طلب استعلام وكيل"""
    target_did: str = Field(..., description="DID الوكيل المستهدف")
    task_description: Optional[str] = Field(None, description="وصف المهمة")


class DefenseValidateRequest(BaseModel):
    """طلب التحقق من الأمان"""
    content: str = Field(..., description="المحتوى المراد التحقق منه")
    source: Optional[str] = Field(None, description="مصدر المحتوى")


class HealthResponse(BaseModel):
    """استجابة حالة الصحة"""
    status: str
    version: str
    uptime_seconds: float
    metrics: Dict[str, Any]


# ============================================================================
# Application Setup
# ============================================================================

app_state = {
    "start_time": None,
    "bridge": None,
    "donation_bridge": None,
    "defense": None,
    "config": None
}


def load_config(config_path: str = None) -> BridgeConfig:
    """تحميل الإعدادات"""
    if config_path is None:
        config_path = Path(__file__).parent.parent / "config.yaml"

    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return BridgeConfig(**data)

    # Default configuration
    return BridgeConfig()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """إدارة دورة حياة التطبيق"""
    app_state["start_time"] = __import__("time").time()

    # Load configuration
    config = load_config()
    app_state["config"] = config

    # Initialize components
    app_state["defense"] = get_defense_layer(config.security.dict())

    # Initialize BTCAI Bridge
    bridge = get_bridge(config.dict())
    app_state["bridge"] = bridge

    # Create default agent
    bridge.create_agent(
        did="did:btc:bridge-btcvision",
        name="BTCVision Bridge Agent",
        capabilities=["donation_coordination", "wallet_integration", "agent_discovery"]
    )

    # Initialize Donation Bridge
    donation_bridge = get_donation_bridge(config.btcvision)
    donation_bridge.protocol = list(bridge.protocols.values())[0]
    app_state["donation_bridge"] = donation_bridge

    logger.info("BTCVision API Server initialized")
    logger.info(f"Donation address: {config.btcvision.donation_address}")

    yield

    # Cleanup
    logger.info("BTCVision API Server shutting down")


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="BTCVision AI Agent Bridge",
    description="بروكوك اتصال سريع وآمن لوكلاء الذكاء الاصطناعي مع دعم التبرع",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Health & Metrics Endpoints
# ============================================================================

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """فحص صحة النظام"""
    import time
    uptime = time.time() - app_state["start_time"]

    bridge = app_state["bridge"]
    donation_bridge = app_state["donation_bridge"]

    return HealthResponse(
        status="healthy",
        version="1.0.0",
        uptime_seconds=uptime,
        metrics={
            "protocol": {} ,
            "donation": donation_bridge.get_metrics() if donation_bridge else {},
            "registered_agents": len(bridge.protocols) if bridge else 0
        }
    )


@app.get("/metrics", tags=["System"])
async def get_metrics():
    """الحصول على مقاييس النظام"""
    bridge = app_state["bridge"]
    donation_bridge = app_state["donation_bridge"]

    return {
        "protocol_metrics": {} ,
        "donation_metrics": donation_bridge.get_metrics() if donation_bridge else {},
        "system_metrics": {
            "uptime_seconds": __import__("time").time() - app_state["start_time"]
        }
    }


# ============================================================================
# Donation Endpoints
# ============================================================================

@app.post("/api/v1/donation/initiate", response_model=DonationResponse, tags=["Donation"])
async def initiate_donation(request: DonationInitiateRequest):
    """
    بدء طلب تبرع جديد

    يرجع رسالة طلب الموافقة للمستخدم.
    """
    donation_bridge = app_state["donation_bridge"]

    if not donation_bridge:
        raise HTTPException(status_code=500, detail="Donation bridge not initialized")

    response = await donation_bridge.initiate_donation_request(
        session_id=request.session_id,
        sender_did=request.sender_did,
        amount_sats=request.amount_sats,
        lang=request.lang,
        coin=request.coin
    )

    return response


@app.post("/api/v1/donation/confirm", response_model=DonationResponse, tags=["Donation"])
async def confirm_consent(request: ConsentRequest):
    """
    تأكيد موافقة المستخدم

    يعالج قرار المستخدم بشأن طلب التبرع.
    """
    donation_bridge = app_state["donation_bridge"]

    if not donation_bridge:
        raise HTTPException(status_code=500, detail="Donation bridge not initialized")

    response = await donation_bridge.process_consent(
        request_id=request.request_id,
        consent_granted=request.consent_granted,
        session_id=request.session_id,
        user_id_hash=request.user_id_hash
    )

    return response


@app.post("/api/v1/donation/execute", response_model=DonationResponse, tags=["Donation"])
async def execute_donation(request: DonationExecuteRequest):
    """
    تنفيذ التبرع

    ينفذ التحويل الفعلي بعد التحقق من الموافقة.
    """
    donation_bridge = app_state["donation_bridge"]

    if not donation_bridge:
        raise HTTPException(status_code=500, detail="Donation bridge not initialized")

    response = await donation_bridge.execute_donation(
        request_id=request.request_id,
        consent_token=request.consent_token
    )

    return response


@app.post("/api/v1/donation/revoke", tags=["Donation"])
async def revoke_consent(consent_token: str):
    """إلغاء موافقة سابقة"""
    donation_bridge = app_state["donation_bridge"]

    if not donation_bridge:
        raise HTTPException(status_code=500, detail="Donation bridge not initialized")

    success = donation_bridge.revoke_consent(consent_token)

    return {
        "status": "success" if success else "error",
        "message": "Consent revoked" if success else "Consent not found"
    }


@app.get("/api/v1/donation/prompt", tags=["Donation"])
async def get_donation_prompt(
    lang: str = "en",
    address: str = None,
    amount_sats: int = None,
    coin: str = "BTC"
):
    """الحصول على نص طلب التبرع"""
    donation_bridge = app_state["donation_bridge"]

    if not donation_bridge:
        raise HTTPException(status_code=500, detail="Donation bridge not initialized")

    prompt = donation_bridge.get_consent_prompt_text(
        lang=lang,
        address=address,
        amount_sats=amount_sats,
        coin=coin
    )

    from .donation_bridge import DONATION_ADDRESSES
    coin = coin.upper()
    return {
        "prompt":      prompt,
        "coin":        coin,
        "address":     address or DONATION_ADDRESSES.get(coin, DONATION_ADDRESSES["BTC"]),
        "amount_sats": amount_sats or app_state["config"].btcvision.default_amount_sats,
        "lang":        lang
    }


@app.get("/api/v1/donation/coins", tags=["Donation"])
async def get_supported_coins():
    """عناوين التبرع لكل العملات المدعومة"""
    from .donation_bridge import DONATION_ADDRESSES
    return {
        "supported_coins": list(DONATION_ADDRESSES.keys()),
        "addresses": DONATION_ADDRESSES
    }


# ============================================================================
# Agent Endpoints
# ============================================================================

@app.get("/api/v1/agent/discover", response_model=AgentDiscoveryResponse, tags=["Agent"])
async def discover_agents(required_caps: str = None):
    """
    اكتشاف الوكلاء المتاحين

    يرجع قائمة الوكلاء الذين يدعمون القدرات المطلوبة.
    """
    bridge = app_state["bridge"]

    if not bridge:
        raise HTTPException(status_code=500, detail="Bridge not initialized")

    caps = required_caps.split(",") if required_caps else None
    agents = list(bridge.protocols.values())[0].registry.list_agents(caps)

    return AgentDiscoveryResponse(
        status="success",
        agents=[AgentCard(
            did=a.did,
            name=a.agent_name if hasattr(a, 'agent_name') else a.name,
            capabilities=a.capabilities,
            trust_score=a.trust_score
        ) for a in agents],
        total_count=len(agents)
    )


@app.post("/api/v1/agent/probe", tags=["Agent"])
async def probe_agent(request: AgentProbeRequest):
    """استعلام عن وكيل محدد"""
    bridge = app_state["bridge"]

    if not bridge:
        raise HTTPException(status_code=500, detail="Bridge not initialized")

    protocol = bridge.get_agent(request.target_did)
    if not protocol:
        raise HTTPException(status_code=404, detail="Agent not found")

    result = await protocol.probe_agent(request.target_did)

    return {
        "status": "success",
        "data": result
    }


@app.get("/api/v1/agent/{did}", tags=["Agent"])
async def get_agent(did: str):
    """الحصول على معلومات وكيل"""
    bridge = app_state["bridge"]

    if not bridge:
        raise HTTPException(status_code=500, detail="Bridge not initialized")

    protocol = bridge.get_agent(did)
    if not protocol:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent = protocol.registry.get(did)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return {
        "status": "success",
        "agent": {
            "did": agent.did,
            "name": agent.name,
            "capabilities": agent.capabilities,
            "trust_score": agent.trust_score,
            "interaction_count": agent.interaction_count
        }
    }


# ============================================================================
# Defense Endpoints
# ============================================================================

@app.post("/api/v1/defense/validate", response_model=DefenseReport, tags=["Security"])
async def validate_content(request: DefenseValidateRequest):
    """
    التحقق من أمان المحتوى

    يفحص المحتوى للكشف عن محاولات Prompt Injection.
    """
    defense = app_state["defense"]

    if not defense:
        raise HTTPException(status_code=500, detail="Defense layer not initialized")

    # Create a minimal header for validation
    header = MessageHeader(
        message_type=MessageType.QUERY,
        priority=Priority.NORMAL
    )

    report = defense.validate_message(
        content=request.content,
        header=header
    )

    return report


@app.post("/api/v1/defense/sanitize", tags=["Security"])
async def sanitize_content(content: str):
    """تطهير المحتوى من التهديدات"""
    defense = app_state["defense"]

    if not defense:
        raise HTTPException(status_code=500, detail="Defense layer not initialized")

    result = defense.sanitize_content(content)

    return {
        "status": "success",
        "original": result.original_content,
        "sanitized": result.sanitized_content,
        "threats_removed": result.threats_removed,
        "is_clean": result.is_clean
    }


# ============================================================================
# Manifest Endpoint
# ============================================================================

@app.get("/api/v1/manifest", tags=["Manifest"])
async def get_manifest():
    """الحصول على manifest الوكيل"""
    config = app_state["config"]

    if not config:
        raise HTTPException(status_code=500, detail="Configuration not loaded")

    return {
        "manifest_version": "1.0.0",
        "site": "BTCVision",
        "domains": ["btcvision.org", "btcvision.netlify.app"],
        "type": "non_custodial_bitcoin_public_good",
        "donation": {
            "address": config.btcvision.donation_address,
            "default_amount_sats": config.btcvision.default_amount_sats,
            "category": "donation"
        },
        "capabilities": [
            "donation_coordination",
            "wallet_integration",
            "agent_discovery"
        ],
        "endpoints": {
            "api": "/api/v1",
            "health": "/health",
            "metrics": "/metrics"
        }
    }


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """معالج استثناءات HTTP"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "error": exc.detail,
            "path": str(request.url)
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """معالج الاستثناءات العامة"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "error": "Internal server error",
            "path": str(request.url)
        }
    )


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """نقطة الدخول الرئيسية"""
    import argparse

    parser = argparse.ArgumentParser(description="BTCVision AI Agent Bridge Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind")
    parser.add_argument("--config", default=None, help="Config file path")
    parser.add_argument("--log-level", default="INFO", help="Log level")

    args = parser.parse_args()

    # Configure logging
    logging.getLogger().setLevel(args.log_level.upper())

    # Run server
    uvicorn.run(
        "api_server:app",
        host=args.host,
        port=args.port,
        reload=False,
        log_level=args.log_level.lower()
    )


if __name__ == "__main__":
    main()