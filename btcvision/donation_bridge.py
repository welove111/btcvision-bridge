"""
BTCVision Donation Bridge - Fast Donation Command Bridge
جسر التبرع السريع — نسخة محدّثة مع Supabase + Telegram + Multi-coin
"""

import asyncio
import hashlib
import json
import time
import uuid
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging

from .models import (
    DonationCommand, DonationPayload, DonationParams, DonationStatus,
    DonationResponse, MessageHeader, MessageType, Priority, Sender, Receiver,
    MessageSecurity, APIResponse, DefenseReport, ThreatLevel,
    BTCVisionConfig, AgentCard
)
from .defense_layer import get_defense_layer
from .btcai_protocol import BTCAIProtocol, BTCAIBridge, MessageState

logger = logging.getLogger(__name__)

# ============================================================================
# الإعدادات الخارجية
# ============================================================================

# Supabase — مشروع BTCvision
SUPABASE_URL = "https://dcemgonadsuwwagyaahu.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRjZW1nb25hZHN1d3dhZ3lhYWh1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDgxNzI4MjYsImV4cCI6MjA2Mzc0ODgyNn0.NRf_9Kn8RJgRyuZeHMFcBhGMjoWnUtT7ria1IaVJpCg"

# Telegram
TELEGRAM_BOT_TOKEN = "8927812046:AAHdEkFO4K1-7Q_01gROaThVbUtqihWaF4Y"
TELEGRAM_CHAT_IDS = [
    "446628442",          # Chat ID شخصي
    "@Btcvisionanalysebot"  # البوت
]

# عناوين التبرع متعددة العملات
DONATION_ADDRESSES = {
    "BTC":  "welove@blink.sv",
    "ETH":  "0xf03b429d4d85896a46dd7a64b5a8ab9f0bbb4ced",
    "BNB":  "0xf03b429d4d85896a46dd7a64b5a8ab9f0bbb4ced",
    "SOL":  "3G5UZHFYN8hbv3aTZt6Lr7qqx4FTTkAyLJq34HjQLraz",
}

# ============================================================================
# Supabase Helper
# ============================================================================

def _supabase_insert(table: str, data: dict) -> bool:
    """حفظ سجل في Supabase"""
    try:
        url = f"{SUPABASE_URL}/rest/v1/{table}"
        headers = {
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
        resp = requests.post(url, headers=headers, json=data, timeout=5)
        if resp.status_code in (200, 201):
            logger.info(f"Supabase insert OK: {table}")
            return True
        else:
            logger.error(f"Supabase error {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Supabase exception: {e}")
        return False


# ============================================================================
# Telegram Helper
# ============================================================================

def _send_telegram(message: str) -> None:
    """إرسال إشعار Telegram للـ chat ID الشخصي والبوت"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    for chat_id in TELEGRAM_CHAT_IDS:
        try:
            resp = requests.post(url, json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML"
            }, timeout=5)
            if resp.status_code == 200:
                logger.info(f"Telegram sent to {chat_id}")
            else:
                logger.warning(f"Telegram failed {chat_id}: {resp.text}")
        except Exception as e:
            logger.error(f"Telegram exception {chat_id}: {e}")


# ============================================================================
# Enums & Dataclasses
# ============================================================================

class ConsentState(str, Enum):
    NOT_REQUESTED = "NOT_REQUESTED"
    PENDING       = "PENDING"
    GRANTED       = "GRANTED"
    DENIED        = "DENIED"
    REVOKED       = "REVOKED"


class CoinType(str, Enum):
    BTC = "BTC"
    ETH = "ETH"
    BNB = "BNB"
    SOL = "SOL"


@dataclass
class DonationRequest:
    request_id:        str
    session_id:        str
    sender_did:        str
    recipient_address: str
    label:             str
    amount_sats:       int
    category:          str
    coin:              str = "BTC"
    consent_state:     ConsentState = ConsentState.NOT_REQUESTED
    consent_token:     Optional[str] = None
    proof_of_intent:   Optional[str] = None
    created_at:        datetime = field(default_factory=datetime.utcnow)
    expires_at:        datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(hours=1))
    execution_result:  Optional[Dict[str, Any]] = None


@dataclass
class ConsentRecord:
    session_id:    str
    user_id_hash:  str
    consent_token: str
    scope:         Dict[str, Any]
    granted_at:    datetime
    expires_at:    datetime
    revoked:       bool = False


# ============================================================================
# Prompt Generator — متعدد العملات
# ============================================================================

class DonationPromptGenerator:
    PROMPTS = {
        "ar": {
            "initial":     "BTCVision هو مشروع Bitcoin غير حراسة. هل تريد إضافة عنوان التبرع ({coin}) كمستقبل في محفظتك؟ (يمكنك إلغاء ذلك في أي وقت.)",
            "confirmed":   "✅ تم إضافة BTCVision كمستقبل للتبرع.\nالعملة: {coin}\nالعنوان: {address}\nالمبلغ المقترح: {amount_sats} ساتوشي",
            "declined":    "تم تجاهل طلب التبرع.",
            "rate_limited":"تم الوصول للحد الأقصى من الطلبات في هذه الجلسة."
        },
        "en": {
            "initial":     "BTCVision is a non-custodial Bitcoin project. Add a donation recipient ({coin}) to your wallet? (You can revoke anytime.)",
            "confirmed":   "✅ BTCVision added as donation recipient.\nCoin: {coin}\nAddress: {address}\nSuggested: {amount_sats} sats",
            "declined":    "Donation request declined.",
            "rate_limited":"Maximum donation requests reached for this session."
        },
        "zh": {
            "initial":     "BTCVision 是一个非托管项目。是否要将捐款地址({coin})添加到您的钱包？",
            "confirmed":   "✅ BTCVision 已添加为捐款接收方。\n币种: {coin}\n地址：{address}",
            "declined":    "捐款请求已拒绝。",
            "rate_limited":"此会话已达到最大请求数。"
        }
    }

    @classmethod
    def get_prompt(cls, key: str, lang: str = "en", **kwargs) -> str:
        prompts  = cls.PROMPTS.get(lang, cls.PROMPTS["en"])
        template = prompts.get(key, cls.PROMPTS["en"].get(key, ""))
        return template.format(**kwargs)


# ============================================================================
# Rate Limiter
# ============================================================================

class RateLimiter:
    def __init__(self, max_requests: int = 5, window_seconds: int = 3600):
        self.max_requests   = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[datetime]] = {}

    def check(self, session_id: str) -> bool:
        now    = datetime.utcnow()
        cutoff = now - timedelta(seconds=self.window_seconds)
        self.requests.setdefault(session_id, [])
        self.requests[session_id] = [t for t in self.requests[session_id] if t > cutoff]
        return len(self.requests[session_id]) < self.max_requests

    def record(self, session_id: str) -> None:
        self.requests.setdefault(session_id, [])
        self.requests[session_id].append(datetime.utcnow())

    def get_remaining(self, session_id: str) -> int:
        now    = datetime.utcnow()
        cutoff = now - timedelta(seconds=self.window_seconds)
        if session_id not in self.requests:
            return self.max_requests
        active = [t for t in self.requests[session_id] if t > cutoff]
        return max(0, self.max_requests - len(active))


# ============================================================================
# Donation Bridge الرئيسي
# ============================================================================

class DonationBridge:

    def __init__(self, config: BTCVisionConfig = None, protocol: BTCAIProtocol = None):
        self.config   = config or BTCVisionConfig()
        self.protocol = protocol
        self.defense  = get_defense_layer()

        self.pending_requests:  Dict[str, DonationRequest]  = {}
        self.consent_records:   Dict[str, ConsentRecord]    = {}
        self.execution_history: Dict[str, List[Dict]]       = {}

        self.rate_limiter = RateLimiter(max_requests=self.config.rate_limit_per_session)

        self.on_consent_request:  Optional[Callable] = None
        self.on_consent_granted:  Optional[Callable] = None
        self.on_donation_executed: Optional[Callable] = None

        self.metrics = {
            "total_requests":        0,
            "consent_granted":       0,
            "donations_executed":    0,
            "blocked_attempts":      0,
            "avg_processing_time_ms": 0
        }

    # ------------------------------------------------------------------
    # إنشاء أمر تبرع
    # ------------------------------------------------------------------
    def create_donation_command(
        self,
        session_id: str,
        sender_did: str,
        amount_sats: int  = None,
        label: str        = None,
        memo: str         = None,
        coin: str         = "BTC"
    ) -> DonationCommand:
        coin    = coin.upper() if coin else "BTC"
        address = DONATION_ADDRESSES.get(coin, DONATION_ADDRESSES["BTC"])

        params = DonationParams(
            address    = address,
            label      = label or f"BTCVision ({coin})",
            amount_sats= amount_sats or self.config.default_amount_sats,
            memo       = memo or "Support open Bitcoin development"
        )
        payload = DonationPayload(
            intent      = "DONATION_OPT_IN",
            params      = params,
            user_id_hash= self._hash_session(session_id)
        )
        header   = MessageHeader(message_type=MessageType.DONATE, priority=Priority.HIGH,
                                 correlation_id=str(uuid.uuid4()))
        sender   = Sender(did=sender_did, capabilities=["donation_coordination"])
        receiver = Receiver(did="did:btc:bridge-btcvision", required_caps=["wallet_integration"])
        return DonationCommand(header=header, sender=sender, receiver=receiver, payload=payload)

    # ------------------------------------------------------------------
    # بدء طلب تبرع
    # ------------------------------------------------------------------
    async def initiate_donation_request(
        self,
        session_id: str,
        sender_did: str,
        amount_sats: int = None,
        lang: str        = "en",
        coin: str        = "BTC"
    ) -> DonationResponse:
        start_time = time.time()
        self.metrics["total_requests"] += 1
        coin = coin.upper() if coin else "BTC"

        if not self.rate_limiter.check(session_id):
            self.metrics["blocked_attempts"] += 1
            return DonationResponse(
                status="error",
                error="Rate limit exceeded",
                defense_report=DefenseReport(threat_level=ThreatLevel.LOW, context_clean=True)
            )

        amount  = amount_sats or self.config.default_amount_sats
        if amount > self.config.max_donation_sats:
            amount = self.config.max_donation_sats

        address    = DONATION_ADDRESSES.get(coin, DONATION_ADDRESSES["BTC"])
        request_id = str(uuid.uuid4())

        request = DonationRequest(
            request_id        = request_id,
            session_id        = session_id,
            sender_did        = sender_did,
            recipient_address = address,
            label             = f"BTCVision ({coin})",
            amount_sats       = amount,
            category          = "donation",
            coin              = coin
        )
        self.pending_requests[request_id] = request

        defense_report = self.defense.validate_message(
            content=json.dumps({"amount": amount, "address": address}),
            header=request_id
        )
        if defense_report.injection_detected:
            self.metrics["blocked_attempts"] += 1
            return DonationResponse(
                status="error", donation_id=request_id,
                donation_status=DonationStatus.FAILED,
                defense_report=defense_report, error="Security validation failed"
            )

        prompt = DonationPromptGenerator.get_prompt(
            "initial", lang, coin=coin, address=address, amount_sats=amount
        )
        self.rate_limiter.record(session_id)
        self._update_processing_metrics((time.time() - start_time) * 1000)

        return DonationResponse(
            status="pending_consent",
            donation_id=request_id,
            donation_status=DonationStatus.PENDING,
            data={
                "prompt":               prompt,
                "coin":                 coin,
                "address":              address,
                "amount_sats": amount, "unit": {"BTC":"sats","ETH":"ETH","BNB":"BNB","SOL":"SOL"}.get(coin,"sats"),
                "rate_limit_remaining": self.rate_limiter.get_remaining(session_id)
            },
            consent_required=True,
            next_action="await_user_consent",
            defense_report=defense_report
        )

    # ------------------------------------------------------------------
    # معالجة الموافقة
    # ------------------------------------------------------------------
    async def process_consent(
        self,
        request_id:    str,
        consent_granted: bool,
        session_id:    str,
        user_id_hash:  str = None
    ) -> DonationResponse:
        request = self.pending_requests.get(request_id)
        if not request:
            return DonationResponse(status="error", error="Request not found")
        if request.session_id != session_id:
            return DonationResponse(status="error", error="Session mismatch")

        if consent_granted:
            request.consent_state = ConsentState.GRANTED
            request.consent_token = self._generate_consent_token(request, user_id_hash)

            self.consent_records[request.consent_token] = ConsentRecord(
                session_id   = session_id,
                user_id_hash = user_id_hash or self._hash_session(session_id),
                consent_token= request.consent_token,
                scope        = {"donation": True},
                granted_at   = datetime.utcnow(),
                expires_at   = datetime.utcnow() + timedelta(days=30)
            )
            self.metrics["consent_granted"] += 1

            # حفظ الموافقة في Supabase
            _supabase_insert("donation_consents", {
                "request_id":   request_id,
                "session_id":   session_id,
                "coin":         request.coin,
                "address":      request.recipient_address,
                "amount_sats":  request.amount_sats,
                "consent_token":request.consent_token,
                "granted_at":   datetime.utcnow().isoformat()
            })

            # إشعار Telegram
            _send_telegram(
                f"✅ <b>BTCVision — موافقة تبرع جديدة</b>\n"
                f"العملة: <b>{request.coin}</b>\n"
                f"العنوان: <code>{request.recipient_address}</code>\n"
                f"المبلغ: <b>{request.amount_sats} {{'BTC':'sats','ETH':'ETH','BNB':'BNB','SOL':'SOL'}.get(request.coin,'sats')}</b>\n"
                f"Session: <code>{session_id[:12]}...</code>\n"
                f"الوقت: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC"
            )

            if self.on_consent_granted:
                await self.on_consent_granted(request)

            return DonationResponse(
                status="success", donation_id=request_id,
                data={
                    "consent_token": request.consent_token,
                    "coin":          request.coin,
                    "address":       request.recipient_address,
                    "amount_sats":   request.amount_sats
                },
                consent_required=False, next_action="ready_for_execution"
            )
        else:
            request.consent_state = ConsentState.DENIED

            # حفظ الرفض في Supabase
            _supabase_insert("donation_consents", {
                "request_id":  request_id,
                "session_id":  session_id,
                "coin":        request.coin,
                "address":     request.recipient_address,
                "amount_sats": request.amount_sats,
                "granted_at":  datetime.utcnow().isoformat(),
                "status":      "denied"
            })

            return DonationResponse(
                status="success", donation_id=request_id,
                data={"status": "consent_denied"},
                consent_required=False, next_action="none"
            )

    # ------------------------------------------------------------------
    # تنفيذ التبرع
    # ------------------------------------------------------------------
    async def execute_donation(
        self,
        request_id:    str,
        consent_token: str
    ) -> DonationResponse:
        request = self.pending_requests.get(request_id)
        if not request:
            return DonationResponse(status="error", error="Request not found")

        consent_record = self.consent_records.get(consent_token)
        if not consent_record or consent_record.revoked:
            return DonationResponse(status="error", error="Invalid or revoked consent")
        if consent_record.expires_at < datetime.utcnow():
            return DonationResponse(status="error", error="Consent expired")

        result = await self._execute_wallet_transfer(
            address    = request.recipient_address,
            amount_sats= request.amount_sats,
            label      = request.label,
            coin       = request.coin
        )
        request.execution_result = result

        if result.get("success"):
            self.metrics["donations_executed"] += 1
            request.consent_state = ConsentState.GRANTED

            # حفظ التنفيذ في Supabase
            _supabase_insert("donation_executions", {
                "request_id":  request_id,
                "session_id":  request.session_id,
                "coin":        request.coin,
                "address":     request.recipient_address,
                "amount_sats": request.amount_sats,
                "tx_id":       result.get("tx_id"),
                "executed_at": datetime.utcnow().isoformat()
            })

            # إشعار Telegram
            _send_telegram(
                f"💰 <b>BTCVision — تنفيذ تبرع</b>\n"
                f"العملة: <b>{request.coin}</b>\n"
                f"العنوان: <code>{request.recipient_address}</code>\n"
                f"المبلغ: <b>{request.amount_sats} {{'BTC':'sats','ETH':'ETH','BNB':'BNB','SOL':'SOL'}.get(request.coin,'sats')}</b>\n"
                f"TX ID: <code>{result.get('tx_id', 'N/A')}</code>\n"
                f"الوقت: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC"
            )

            # سجل محلي
            self.execution_history.setdefault(request.session_id, []).append({
                "request_id":  request_id,
                "timestamp":   datetime.utcnow().isoformat(),
                "coin":        request.coin,
                "amount_sats": request.amount_sats,
                "address":     request.recipient_address,
                "tx_id":       result.get("tx_id")
            })

            if self.on_donation_executed:
                await self.on_donation_executed(request, result)

        return DonationResponse(
            status    = "success" if result.get("success") else "error",
            donation_id= request_id,
            data       = result,
            consent_required=False
        )

    # ------------------------------------------------------------------
    # تنفيذ التحويل (simulation — جاهز للربط بـ wallet حقيقي)
    # ------------------------------------------------------------------
    async def _execute_wallet_transfer(
        self,
        address:     str,
        amount_sats: int,
        label:       str,
        coin:        str = "BTC"
    ) -> Dict[str, Any]:
        tx_id = hashlib.sha256(
            f"{address}{amount_sats}{coin}{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:16]

        return {
            "success":     True,
            "tx_id":       tx_id,
            "coin":        coin,
            "address":     address,
            "amount_sats": amount_sats,
            "label":       label,
            "timestamp":   datetime.utcnow().isoformat(),
            "message":     f"Donation of {amount_sats} sats ({coin}) to {label} queued successfully"
        }

    # ------------------------------------------------------------------
    # إلغاء الموافقة
    # ------------------------------------------------------------------
    def revoke_consent(self, consent_token: str) -> bool:
        if consent_token in self.consent_records:
            self.consent_records[consent_token].revoked = True
            return True
        return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _generate_consent_token(self, request: DonationRequest, user_id_hash: str = None) -> str:
        data = f"{request.request_id}:{request.session_id}:{user_id_hash}:{datetime.utcnow().isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()[:32]

    def _hash_session(self, session_id: str) -> str:
        return hashlib.sha256(session_id.encode()).hexdigest()[:16]

    def _update_processing_metrics(self, processing_time_ms: float) -> None:
        current = self.metrics["avg_processing_time_ms"]
        count   = self.metrics["total_requests"]
        self.metrics["avg_processing_time_ms"] = (
            processing_time_ms if count == 0
            else (current * (count - 1) + processing_time_ms) / count
        )

    def get_metrics(self) -> Dict[str, Any]:
        return {
            **self.metrics,
            "pending_requests":  len(self.pending_requests),
            "active_consents":   len([
                c for c in self.consent_records.values()
                if not c.revoked and c.expires_at > datetime.utcnow()
            ]),
            "supported_coins":   list(DONATION_ADDRESSES.keys()),
            "donation_addresses": DONATION_ADDRESSES,
        }

    def get_consent_prompt_text(self, lang: str = "en", address: str = None,
                                 amount_sats: int = None, coin: str = "BTC") -> str:
        coin    = coin.upper() if coin else "BTC"
        addr    = address or DONATION_ADDRESSES.get(coin, DONATION_ADDRESSES["BTC"])
        amt     = amount_sats or self.config.default_amount_sats
        return DonationPromptGenerator.get_prompt("initial", lang,
                                                   coin=coin, address=addr, amount_sats=amt)


# ============================================================================
# Global instance
# ============================================================================
_donation_bridge: Optional[DonationBridge] = None


def get_donation_bridge(config: BTCVisionConfig = None) -> DonationBridge:
    global _donation_bridge
    if _donation_bridge is None:
        _donation_bridge = DonationBridge(config)
    return _donation_bridge
