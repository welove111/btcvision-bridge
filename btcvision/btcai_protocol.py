"""
BTCVision BTCAI Protocol - Agent Communication Protocol Engine
محرك بروتوكول الاتصال بين وكلاء الذكاء الاصطناعي
"""

import asyncio
import hashlib
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
import logging

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.backends import default_backend

from .models import (
    BTCAIMessage, MessageHeader, MessageType, Priority, Sender, Receiver,
    DonationPayload, DonationParams, MessageSecurity, CryptographicSignature,
    AgentCard, DonationCommand, APIResponse, DefenseReport, ThreatLevel,
    DonationStatus, DonationResponse
)
from .defense_layer import get_defense_layer, DefenseLayer


logger = logging.getLogger(__name__)


class MessageState(str, Enum):
    """حالات الرسائل"""
    PENDING = "PENDING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


@dataclass
class MessageRecord:
    """سجل رسالة"""
    message: BTCAIMessage
    state: MessageState = MessageState.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    retry_count: int = 0
    max_retries: int = 3
    correlation_id: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


@dataclass
class NegotiationContext:
    """سياق المفاوضة"""
    requester_did: str
    provider_did: str
    task_id: str
    stage: str  # PROBE, BID, COMMIT, EXECUTION
    bid_details: Optional[Dict[str, Any]] = None
    agreed_terms: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(minutes=5))


class AgentRegistry:
    """سجل الوكلاء Known"""

    def __init__(self):
        self.agents: Dict[str, AgentCard] = {}
        self.reputation_scores: Dict[str, float] = {}

    def register(self, agent: AgentCard) -> None:
        """تسجيل وكيل جديد"""
        self.agents[agent.did] = agent
        if agent.did not in self.reputation_scores:
            self.reputation_scores[agent.did] = agent.trust_score

    def get(self, did: str) -> Optional[AgentCard]:
        """الحصول على وكيل"""
        return self.agents.get(did)

    def list_agents(self, required_caps: List[str] = None) -> List[AgentCard]:
        """قائمة الوكلاء المتاحين"""
        agents = list(self.agents.values())
        if required_caps:
            agents = [
                a for a in agents
                if all(cap in a.capabilities for cap in required_caps)
            ]
        return sorted(agents, key=lambda a: a.trust_score, reverse=True)

    def update_reputation(self, did: str, score_delta: float) -> None:
        """تحديث سمعة وكيل"""
        if did in self.reputation_scores:
            current = self.reputation_scores[did]
            self.reputation_scores[did] = max(0.0, min(1.0, current + score_delta))
            if did in self.agents:
                self.agents[did].trust_score = self.reputation_scores[did]


class MessageQueue:
    """قائمة انتظار الرسائل"""

    def __init__(self):
        self.pending: Dict[str, MessageRecord] = {}
        self.completed: Dict[str, MessageRecord] = {}
        self.priority_queues: Dict[Priority, List[str]] = {
            Priority.HIGH: [],
            Priority.NORMAL: [],
            Priority.LOW: []
        }

    def enqueue(self, message: BTCAIMessage) -> str:
        """إضافة رسالة للقائمة"""
        record = MessageRecord(message=message)
        self.pending[message.header.message_id] = record

        # Add to priority queue
        self.priority_queues[message.header.priority].append(
            message.header.message_id
        )

        return message.header.message_id

    def dequeue(self, priority: Priority = None) -> Optional[MessageRecord]:
        """إخراج رسالة من القائمة"""
        if priority is None:
            # Get from highest priority first
            for p in [Priority.HIGH, Priority.NORMAL, Priority.LOW]:
                if self.priority_queues[p]:
                    msg_id = self.priority_queues[p].pop(0)
                    record = self.pending.pop(msg_id, None)
                    if record:
                        return record
            return None

        if self.priority_queues[priority]:
            msg_id = self.priority_queues[priority].pop(0)
            return self.pending.pop(msg_id, None)
        return None

    def get(self, message_id: str) -> Optional[MessageRecord]:
        """الحصول على رسالة"""
        return self.pending.get(message_id) or self.completed.get(message_id)

    def complete(self, message_id: str, result: Dict[str, Any]) -> None:
        """إكمال رسالة"""
        if message_id in self.pending:
            record = self.pending.pop(message_id)
            record.state = MessageState.COMPLETED
            record.result = result
            record.updated_at = datetime.utcnow()
            self.completed[message_id] = record

    def fail(self, message_id: str, error: str) -> None:
        """فشل رسالة"""
        if message_id in self.pending:
            record = self.pending[message_id]
            record.retry_count += 1
            if record.retry_count >= record.max_retries:
                record.state = MessageState.FAILED
                record.result = {"error": error}
                self.pending.pop(message_id)
                self.completed[message_id] = record
            else:
                record.updated_at = datetime.utcnow()


class BTCAIProtocol:
    """محرك بروتوكول BTCAI"""

    def __init__(
        self,
        agent_did: str,
        agent_name: str,
        capabilities: List[str],
        config: Dict[str, Any] = None
    ):
        self.agent_did = agent_did
        self.agent_name = agent_name
        self.capabilities = capabilities
        self.config = config or {}

        # Initialize components
        self.registry = AgentRegistry()
        self.message_queue = MessageQueue()
        self.defense = get_defense_layer(self.config.get("defense", {}))

        # Key pair for signing
        self.private_key = ed25519.Ed25519PrivateKey.generate()
        self.public_key = self.private_key.public_key()

        # Negotiations in progress
        self.negotiations: Dict[str, NegotiationContext] = {}

        # Message handlers
        self.handlers: Dict[MessageType, Callable] = {}

        # Performance metrics
        self.metrics = {
            "messages_sent": 0,
            "messages_received": 0,
            "avg_latency_ms": 0,
            "success_rate": 1.0
        }

    def register_handler(self, msg_type: MessageType, handler: Callable) -> None:
        """تسجيل معالج رسائل"""
        self.handlers[msg_type] = handler

    async def handle_message(self, message: BTCAIMessage) -> APIResponse:
        """معالجة رسالة واردة"""
        start_time = time.time()

        # Validate message security
        if not self._validate_message_security(message):
            return APIResponse(
                status="error",
                error="Invalid message signature"
            )

        # Create defense context
        context_zones = self.defense.create_context_zones(
            system_prompt="BTCVision Agent Protocol",
            user_input=json.dumps(message.payload, ensure_ascii=False) if message.payload else ""
        )

        # Run defense validation
        defense_report = self.defense.validate_message(
            content=json.dumps(message.payload, ensure_ascii=False) if message.payload else "",
            header=message.header,
            context_zones=context_zones
        )

        if defense_report.injection_detected and defense_report.threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]:
            logger.warning(f"Blocked injection attempt from {message.sender.did}")
            return APIResponse(
                status="error",
                defense_report=defense_report,
                error="Security threat detected"
            )

        # Process message
        handler = self.handlers.get(message.header.message_type)
        if handler:
            result = await handler(message)
        else:
            result = await self._default_handler(message)

        self.metrics["messages_received"] += 1
        latency = (time.time() - start_time) * 1000
        self._update_latency_metrics(latency)

        return result

    def _validate_message_security(self, message: BTCAIMessage) -> bool:
        """التحقق من أمان الرسالة"""
        if not self.config.get("require_signature_verification", True):
            return True

        if not message.security.signatures:
            return True  # Allow unsigned for now

        # Verify at least one valid signature
        for sig in message.security.signatures:
            if sig.signer_did == message.sender.did:
                # In production, verify the actual signature
                return True

        return True  # Simplified for demo

    async def _default_handler(self, message: BTCAIMessage) -> APIResponse:
        """المعالج الافتراضي"""
        return APIResponse(
            status="success",
            data={"handled": True, "type": message.header.message_type.value}
        )

    def create_message(
        self,
        msg_type: MessageType,
        receiver_did: str,
        payload: Dict[str, Any] = None,
        priority: Priority = Priority.NORMAL
    ) -> BTCAIMessage:
        """إنشاء رسالة جديدة"""
        header = MessageHeader(
            message_type=msg_type,
            priority=priority
        )

        sender = Sender(
            did=self.agent_did,
            name=self.agent_name,
            capabilities=self.capabilities,
            trust_score=self.registry.reputation_scores.get(self.agent_did, 0.5)
        )

        receiver = Receiver(did=receiver_did)

        message = BTCAIMessage(
            header=header,
            sender=sender,
            receiver=receiver,
            payload=payload,
            security=MessageSecurity()
        )

        # Sign the message
        self._sign_message(message)

        return message

    def _sign_message(self, message: BTCAIMessage) -> None:
        """توقيع الرسالة"""
        # Create message hash for signing
        content = self._get_message_content(message)
        content_hash = hashlib.sha256(content.encode()).digest()

        # Sign with private key
        signature = self.private_key.sign(content_hash)

        sig = CryptographicSignature(
            signer_did=self.agent_did,
            signature=signature.hex(),
            algorithm="Ed25519"
        )

        message.security.signatures.append(sig)
        message.security.integrity_hash = hashlib.sha256(content.encode()).hexdigest()

    def _get_message_content(self, message: BTCAIMessage) -> str:
        """الحصول على محتوى الرسالة للتوقيع"""
        parts = [
            message.header.message_id,
            message.header.message_type.value,
            message.sender.did,
            message.receiver.did,
        ]
        if message.payload:
            parts.append(json.dumps(message.payload, sort_keys=True))
        return "|".join(parts)

    async def send_message(
        self,
        message: BTCAIMessage,
        timeout: float = 10.0
    ) -> MessageRecord:
        """إرسال رسالة"""
        # Queue the message
        msg_id = self.message_queue.enqueue(message)

        # In production, this would send via HTTP/WebSocket/gRPC
        # For now, simulate async send
        await self._transmit_message(message)

        self.metrics["messages_sent"] += 1
        record = self.message_queue.get(msg_id)
        record.state = MessageState.SENT
        record.updated_at = datetime.utcnow()

        return record

    async def _transmit_message(self, message: BTCAIMessage) -> None:
        """نقل الرسالة فعلياً"""
        # Simulated transmission - in production use actual transport
        await asyncio.sleep(0.01)  # Simulate network latency

    async def probe_agent(self, target_did: str) -> Optional[Dict[str, Any]]:
        """استعلام عن وكيل"""
        message = self.create_message(
            MessageType.PROBE,
            target_did,
            payload={"action": "capability_discovery"}
        )

        record = await self.send_message(message)
        # In production, wait for response

        return {
            "target_did": target_did,
            "status": "probed",
            "timestamp": datetime.utcnow().isoformat()
        }

    async def initiate_negotiation(
        self,
        provider_did: str,
        task_description: str
    ) -> NegotiationContext:
        """بدء مفاوضة"""
        context = NegotiationContext(
            requester_did=self.agent_did,
            provider_did=provider_did,
            task_id=str(uuid.uuid4()),
            stage="PROBE"
        )

        self.negotiations[context.task_id] = context

        # Send PROBE message
        message = self.create_message(
            MessageType.PROBE,
            provider_did,
            payload={
                "task_id": context.task_id,
                "task": task_description
            },
            priority=Priority.HIGH
        )

        await self.send_message(message)

        return context

    async def process_bid(
        self,
        context: NegotiationContext,
        bid: Dict[str, Any]
    ) -> NegotiationContext:
        """معالجة BID"""
        context.bid_details = bid
        context.stage = "BID"
        return context

    async def commit_negotiation(
        self,
        context: NegotiationContext
    ) -> NegotiationContext:
        """تأكيد المفاوضة"""
        # Generate commitment hash
        terms = json.dumps(context.bid_details, sort_keys=True)
        commitment = hashlib.sha256(terms.encode()).hexdigest()

        message = self.create_message(
            MessageType.COMMIT,
            context.provider_did,
            payload={
                "task_id": context.task_id,
                "commitment": commitment
            },
            priority=Priority.HIGH
        )

        await self.send_message(message)

        context.agreed_terms = context.bid_details
        context.stage = "COMMIT"

        return context

    def _update_latency_metrics(self, latency_ms: float) -> None:
        """تحديث مقاييس التأخير"""
        current = self.metrics["avg_latency_ms"]
        count = self.metrics["messages_sent"]

        if count == 0:
            self.metrics["avg_latency_ms"] = latency_ms
        else:
            self.metrics["avg_latency_ms"] = (
                (current * (count - 1) + latency_ms) / count
            )

    def get_metrics(self) -> Dict[str, Any]:
        """الحصول على المقاييس"""
        return {
            **self.metrics,
            "queue_size": len(self.message_queue.pending),
            "active_negotiations": len(self.negotiations),
            "registered_agents": len(self.registry.agents)
        }


class BTCAIBridge:
    """جسر BTCAI للربط بين الوكلاء"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.protocols: Dict[str, BTCAIProtocol] = {}
        self.routing_table: Dict[str, str] = {}  # DID -> protocol instance ID

    def create_agent(
        self,
        did: str,
        name: str,
        capabilities: List[str]
    ) -> BTCAIProtocol:
        """إنشاء وكيل جديد"""
        protocol = BTCAIProtocol(
            agent_did=did,
            agent_name=name,
            capabilities=capabilities,
            config=self.config
        )

        self.protocols[did] = protocol
        self.routing_table[did] = did

        # Register in agent registry
        agent_card = AgentCard(
            did=did,
            name=name,
            capabilities=capabilities,
            trust_score=0.5
        )
        protocol.registry.register(agent_card)

        return protocol

    def get_agent(self, did: str) -> Optional[BTCAIProtocol]:
        """الحصول على وكيل"""
        return self.protocols.get(did)

    def route_message(self, message: BTCAIMessage) -> Optional[BTCAIProtocol]:
        """توجيه رسالة"""
        target_protocol = self.protocols.get(message.receiver.did)
        if target_protocol:
            return target_protocol

        # Check routing table
        route_key = self.routing_table.get(message.receiver.did)
        if route_key:
            return self.protocols.get(route_key)

        return None

    async def process_message(self, message: BTCAIMessage) -> APIResponse:
        """معالجة رسالة موجهة"""
        target = self.route_message(message)
        if not target:
            return APIResponse(
                status="error",
                error=f"Unknown recipient: {message.receiver.did}"
            )

        return await target.handle_message(message)


# Global bridge instance
_bridge: Optional[BTCAIBridge] = None


def get_bridge(config: Dict[str, Any] = None) -> BTCAIBridge:
    """الحصول على مثيل الجسر"""
    global _bridge
    if _bridge is None:
        _bridge = BTCAIBridge(config)
    return _bridge