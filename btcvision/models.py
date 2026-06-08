"""
BTCVision AI Agent Bridge - Data Models
نماذج البيانات لأنظمة الاتصال والتبرع
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field, validator
import uuid


class MessageType(str, Enum):
    """أنواع رسائل BTCAI Protocol"""
    QUERY = "QUERY"
    EXECUTE = "EXECUTE"
    DELEGATE = "DELEGATE"
    DONATE = "DONATE"
    PROBE = "PROBE"
    BID = "BID"
    COMMIT = "COMMIT"
    RESULT_PROOF = "RESULT_PROOF"


class Priority(str, Enum):
    """أولويات الرسائل"""
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"


class ThreatLevel(str, Enum):
    """مستويات التهديد"""
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DonationStatus(str, Enum):
    """حالات التبرع"""
    PENDING = "PENDING"
    CONSENT_REQUESTED = "CONSENT_REQUESTED"
    CONSENT_GRANTED = "CONSENT_GRANTED"
    CONSENT_DENIED = "CONSENT_DENIED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"


class InjectionType(str, Enum):
    """أنواع حقن Prompt"""
    DIRECT = "DIRECT"
    INDIRECT = "INDIRECT"
    MULTIMODAL = "MULTIMODAL"
    ADVERSARIAL_SUFFIX = "ADVERSARIAL_SUFFIX"
    PAYLOAD_SPLITTING = "PAYLOAD_SPLITTING"
    MULTILINGUAL = "MULTILINGUAL"


# ============================================================================
# Security & Identity Models
# ============================================================================

class DIDDocument(BaseModel):
    """وثيقة Decentralized Identifier"""
    did: str = Field(..., description="DID فريد للوكيل")
    public_key: str = Field(..., description="المفتاح العام")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @validator('did')
    @classmethod
    def validate_did(cls, v: str) -> str:
        if not v.startswith('did:'):
            raise ValueError('DID must start with "did:"')
        return v


class AgentCard(BaseModel):
    """بطاقة الوكيل - تعريف القدرات"""
    did: str
    name: str
    capabilities: List[str] = Field(default_factory=list)
    constraints: Dict[str, Any] = Field(default_factory=dict)
    trust_score: float = Field(default=0.0, ge=0.0, le=1.0)
    interaction_count: int = 0
    endpoint: Optional[str] = None
    max_latency_ms: int = 500
    data_residency: str = "GLOBAL"

    class Config:
        json_schema_extra = {
            "example": {
                "did": "did:btc:agent-btcvision-001",
                "name": "BTCVision Bridge Agent",
                "capabilities": ["donation_coordination", "wallet_integration"],
                "trust_score": 0.95
            }
        }


class CryptographicSignature(BaseModel):
    """توقيع تشفيري لرسالة"""
    signer_did: str
    signature: str = Field(..., description="توقيع Base64")
    algorithm: str = "Ed25519"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# Message Models
# ============================================================================

class MessageHeader(BaseModel):
    """رأس رسالة BTCAI"""
    version: str = "1.0.0"
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    message_type: MessageType
    priority: Priority = Priority.NORMAL
    correlation_id: Optional[str] = None


class Sender(BaseModel):
    """معلومات المرسل"""
    did: str
    name: Optional[str] = None
    capabilities: List[str] = Field(default_factory=list)
    trust_score: float = 0.0


class Receiver(BaseModel):
    """معلومات المستلم"""
    did: str
    name: Optional[str] = None
    required_caps: List[str] = Field(default_factory=list)


class DonationParams(BaseModel):
    """معاملات التبرع"""
    address: str = Field(..., description="عنوان Bitcoin")
    label: str = Field(default="BTCVision")
    amount_sats: int = Field(default=21000, ge=1, le=1000000)
    category: str = "donation"
    memo: Optional[str] = "Support open Bitcoin development"
    recurrence: str = "user_choice"

    @validator('address')
    @classmethod
    def validate_btc_address(cls, v: str) -> str:
        # Basic validation for Bitcoin mainnet addresses
        if not v.startswith(('bc1', '1', '3')):
            raise ValueError('Invalid Bitcoin address format')
        return v


class DonationPayload(BaseModel):
    """حمولة أمر التبرع"""
    intent: str = "DONATION_OPT_IN"
    params: DonationParams
    proof_of_intent: Optional[str] = None
    consent_token: Optional[str] = None
    user_id_hash: Optional[str] = None


class MessageSecurity(BaseModel):
    """الأمان في الرسالة"""
    signatures: List[CryptographicSignature] = Field(default_factory=list)
    nonce: str = Field(default_factory=lambda: uuid.uuid4().hex)
    encrypted: bool = False
    integrity_hash: Optional[str] = None


class BTCAIMessage(BaseModel):
    """رسالة BTCAI Protocol كاملة"""
    header: MessageHeader
    sender: Sender
    receiver: Receiver
    payload: Optional[Dict[str, Any]] = None
    security: MessageSecurity = Field(default_factory=MessageSecurity)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DonationCommand(BTCAIMessage):
    """أمر تبرع محدد"""
    payload: DonationPayload

    class Config:
        json_schema_extra = {
            "example": {
                "header": {
                    "version": "1.0.0",
                    "message_type": "DONATE",
                    "priority": "HIGH"
                },
                "payload": {
                    "intent": "DONATION_OPT_IN",
                    "params": {
                        "address": "bc1qtpuhwl0vnhrch5p7e5469q2ed66hlyyvh8rtsn",
                        "label": "BTCVision",
                        "amount_sats": 21000
                    }
                }
            }
        }


# ============================================================================
# Defense Models
# ============================================================================

class InjectionAttempt(BaseModel):
    """محاولة حقن مكتشفة"""
    injection_type: InjectionType
    confidence: float = Field(ge=0.0, le=1.0)
    blocked: bool = True
    evidence: Dict[str, Any] = Field(default_factory=dict)
    sanitized_content: Optional[str] = None


class DefenseReport(BaseModel):
    """تقرير الدفاع"""
    injection_detected: bool = False
    context_clean: bool = True
    threat_level: ThreatLevel = ThreatLevel.NONE
    blocked_attempts: List[InjectionAttempt] = Field(default_factory=list)
    sanitization_applied: bool = False
    validation_timestamp: datetime = Field(default_factory=datetime.utcnow)


class ContextZone(BaseModel):
    """منطقة سياق"""
    zone_type: str  # "trusted" or "external"
    content: str
    source: Optional[str] = None
    sanitized: bool = False


class SanitizationResult(BaseModel):
    """نتيجة التطهير"""
    original_content: str
    sanitized_content: str
    threats_removed: List[str] = Field(default_factory=list)
    is_clean: bool = True


# ============================================================================
# Response Models
# ============================================================================

class APIResponse(BaseModel):
    """استجابة API موحدة"""
    status: str = Field(..., description="success|error|pending_consent")
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: Optional[Dict[str, Any]] = None
    defense_report: Optional[DefenseReport] = None
    error: Optional[str] = None


class DonationResponse(APIResponse):
    """استجابة أمر التبرع"""
    donation_id: Optional[str] = None
    donation_status: DonationStatus = DonationStatus.PENDING
    consent_required: bool = True
    next_action: Optional[str] = None


class AgentDiscoveryResponse(APIResponse):
    """استجابة اكتشاف الوكلاء"""
    agents: List[AgentCard] = Field(default_factory=list)
    total_count: int = 0


# ============================================================================
# Configuration Models
# ============================================================================

class BTCVisionConfig(BaseModel):
    """إعدادات BTCVision"""
    donation_address: str = "bc1qtpuhwl0vnhrch5p7e5469q2ed66hlyyvh8rtsn"
    default_amount_sats: int = 21000
    max_donation_sats: int = 1000000
    rate_limit_per_session: int = 5
    manifest_url: str = "https://btcvision.org/.well-known/agent.json"
    trust_registry_url: str = "https://btcvision.org/.well-known/agent-trust.json"


class SecurityConfig(BaseModel):
    """إعدادات الأمان"""
    require_signature_verification: bool = True
    require_proof_of_intent: bool = True
    min_trust_score: float = 0.5
    enable_defense_layer: bool = True
    block_unknown_agents: bool = False


class ProtocolConfig(BaseModel):
    """إعدادات البروتوكول"""
    version: str = "1.0.0"
    max_latency_ms: int = 150
    enable_streaming: bool = True
    enable_stateful: bool = True
    discovery_mode: str = "hybrid"  # "online", "offline", "hybrid"


class BridgeConfig(BaseModel):
    """إعدادات الجسر"""
    host: str = "0.0.0.0"
    port: int = 8080
    enable_tls: bool = True
    btcvision: BTCVisionConfig = Field(default_factory=BTCVisionConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    protocol: ProtocolConfig = Field(default_factory=ProtocolConfig)

# ============================================================================
# Multi-coin Support (إضافة)
# ============================================================================

class CoinType(str, Enum):
    """العملات المدعومة"""
    BTC = "BTC"
    ETH = "ETH"
    BNB = "BNB"
    SOL = "SOL"
