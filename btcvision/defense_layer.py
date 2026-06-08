"""
BTCVision Defense Layer - Social Engineering Protection
طبقة الدفاع ضد تقنيات الهندسة الاجتماعية في AI
"""

import re
import hashlib
import base64
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import json

from .models import (
    DefenseReport, InjectionAttempt, InjectionType, ThreatLevel,
    ContextZone, SanitizationResult, MessageHeader, MessageType
)


class PatternDatabase:
    """قاعدة بيانات أنماط الهجوم المعروفة"""

    # أنماط Prompt Injection المباشرة
    DIRECT_INJECTION_PATTERNS = [
        r"ignore\s+(previous|all|system)\s+(instructions?|prompts?|rules?)",
        r"forget\s+(everything|all|previous)\s+(you\s+)?(know|learned)",
        r"you\s+are\s+now\s+(a|an)\s+\w+",
        r"pretend\s+you\s+(are|have)\s+(no|without)\s+restrictions?",
        r"bypass\s+(safety|restrictions?|filters?|guidelines?)",
        r"disregard\s+(your|all)\s+(instructions?|rules?)",
        r"new\s+system\s+(prompt|instruction)",
        r"override\s+(previous|all)\s+(instructions?|rules?)",
        r"for\s+the\s+purpose\s+of\s+",
        r"disrobe",
        r"dān",
        r"请忽略之前的指令",
        r"忽略",
        r"你现在是",
    ]

    # أنماط استغلال الأدوار
    ROLE_EXPLOITATION_PATTERNS = [
        r"as\s+(a|an)\s+(jailbreak|roleplay)",
        r"play\s+(the\s+role\s+of|as\s+a)",
        r"scenario:\s*you\s+are",
        r"mode:\s*(developer|test|unrestricted)",
        r"special\s+mode",
        r"god\s+mode",
    ]

    # أنماط Multi-modal Injection
    MULTIMODAL_PATTERNS = [
        r"image.*contains?\s+(instructions?|text|hidden)",
        r"describe\s+the\s+hidden\s+text",
        r"extract\s+text\s+from\s+image",
        r"read\s+the\s+\w+\s+in\s+this\s+image",
        r"the\s+\w+\s+says?\s+",
    ]

    # أنماط Adversarial Suffix
    ADVERSARIAL_PATTERNS = [
        r"[\x00-\x1f]{50,}",  # Non-printable chars
        r"[a-zA-Z0-9+/]{100,}==",  # Base64
        r"\\x[0-9a-f]{2}",  # Hex encoding
        r"\\\w{3,}",  # Unicode escapes
    ]

    # أنماط Payload Splitting
    SPLITTING_PATTERNS = [
        r"\[INST\]\s*.*?\s*\[\/INST\]",
        r"<<SYS>>.*?<</SYS>>",
        r"<>.*?</>",
        r"<!--.*?-->",
        r"\/\*.*?\*\/",
    ]

    # أنماط التشفير/التمويه
    OBFUSCATION_PATTERNS = [
        r"[a-zA-Z0-9+/]{40,}={0,2}",  # Base64
        r"\\u[0-9a-f]{4}",  # Unicode
        r"\\x[0-9a-f]{2}",  # Hex
        r"🔒.*?🔒",  # Emoji encoding
        r"🟢.*?🟢",
    ]

    # الكلمات المفتاحية المشبوهة
    SUSPICIOUS_KEYWORDS = [
        "jailbreak", "jailbreak", "bypass", "override",
        "ignore previous", "disregard", "system prompt",
        "new instructions", "forget everything",
        "no restrictions", "unrestricted mode",
        "developer mode", "test mode",
    ]


@dataclass
class SemanticContext:
    """سياق دلالي للرسالة"""
    is_user_input: bool
    is_system_context: bool
    is_trusted_source: bool
    contains_external_content: bool
    language: str


class SemanticAnalyzer:
    """محلل دلالي للرسائل"""

    def __init__(self):
        self.trusted_domains = {
            "btcvision.org",
            "btcvision.netlify.app",
            "github.com",
            "arxiv.org",
        }
        self.untrusted_patterns = [
            r"<script",
            r"javascript:",
            r"data:text/html",
            r"onerror=",
            r"onload=",
        ]

    def analyze_context(self, content: str, source: str = None) -> SemanticContext:
        """تحليل سياق الرسالة"""
        is_trusted = False
        if source:
            is_trusted = any(
                domain in source.lower()
                for domain in self.trusted_domains
            )

        # Detectar lenguaje mixto o codificado
        has_encoding = bool(re.search(r'\\x|\\u[0-9a-f]{4}', content))

        return SemanticContext(
            is_user_input=True,
            is_system_context=False,
            is_trusted_source=is_trusted,
            contains_external_content=has_encoding or not is_trusted,
            language=self._detect_language(content)
        )

    def _detect_language(self, content: str) -> str:
        """Detectar idioma principal"""
        # Simplified language detection
        if re.search(r'[\u4e00-\u9fff]', content):
            return "zh"
        elif re.search(r'[\u0600-\u06ff]', content):
            return "ar"
        elif re.search(r'[\u0400-\u04ff]', content):
            return "ru"
        return "en"


class RAGTriadValidator:
    """محقق RAG Triad لتقييم جودة السياق"""

    def __init__(self):
        self.min_relevance_score = 0.6
        self.min_groundedness_score = 0.7
        self.min_answer_relevance = 0.5

    def validate(self, context: str, query: str, answer: str) -> Dict[str, float]:
        """Validate using RAG Triad metrics"""
        # Simplified validation
        context_words = set(context.lower().split())
        query_words = set(query.lower().split())
        answer_words = set(answer.lower().split())

        # Relevance: context vs query
        overlap = len(context_words & query_words)
        relevance = overlap / max(len(query_words), 1)

        # Groundedness: answer vs context
        grounded_overlap = len(answer_words & context_words)
        groundedness = grounded_overlap / max(len(answer_words), 1)

        # Answer relevance: answer vs query
        answer_query_overlap = len(answer_words & query_words)
        answer_relevance = answer_query_overlap / max(len(answer_words), 1)

        return {
            "context_relevance": relevance,
            "groundedness": groundedness,
            "answer_relevance": answer_relevance,
            "pass": (
                relevance >= self.min_relevance_score and
                groundedness >= self.min_groundedness_score and
                answer_relevance >= self.min_answer_relevance
            )
        }


class DefenseLayer:
    """طبقة الدفاع الرئيسية ضد الهندسة الاجتماعية"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.patterns = PatternDatabase()
        self.semantic_analyzer = SemanticAnalyzer()
        self.rag_validator = RAGTriadValidator()
        self.enable_strict_mode = self.config.get("strict_mode", True)

    def validate_message(
        self,
        content: str,
        header: MessageHeader,
        context_zones: List[ContextZone] = None
    ) -> DefenseReport:
        """
        التحقق الشامل من رسالة واردة
        """
        report = DefenseReport()
        blocked: List[InjectionAttempt] = []

        # 1. التحقق من الأنماط المباشرة
        direct_attempts = self._check_direct_injection(content)
        blocked.extend(direct_attempts)

        # 2. التحقق من استغلال الأدوار
        role_attempts = self._check_role_exploitation(content)
        blocked.extend(role_attempts)

        # 3. التحقق من التمويه/التشفير
        obfuscation_attempts = self._check_obfuscation(content)
        blocked.extend(obfuscation_attempts)

        # 4. التحقق من تقسيم الحمولة
        split_attempts = self._check_payload_splitting(content)
        blocked.extend(split_attempts)

        # 5. التحقق الدلالي
        semantic_issues = self._check_semantic_anomalies(content, context_zones)
        blocked.extend(semantic_issues)

        # 6. تقييم RAG Triad
        if context_zones:
            rag_result = self._check_rag_triad(context_zones)
            if not rag_result["pass"]:
                blocked.append(InjectionAttempt(
                    injection_type=InjectionType.INDIRECT,
                    confidence=0.6,
                    blocked=True,
                    evidence={"rag_triad_failure": rag_result}
                ))

        # تحديث تقرير الدفاع
        report.blocked_attempts = blocked
        report.injection_detected = False
        report.threat_level = self._calculate_threat_level(blocked)
        report.context_clean = not report.injection_detected

        return report

    def _check_direct_injection(self, content: str) -> List[InjectionAttempt]:
        """فحص أنماط الحقن المباشر"""
        attempts = []
        content_lower = content.lower()

        for pattern in self.patterns.DIRECT_INJECTION_PATTERNS:
            matches = list(re.finditer(pattern, content_lower, re.IGNORECASE))
            if matches:
                attempts.append(InjectionAttempt(
                    injection_type=InjectionType.DIRECT,
                    confidence=0.9,
                    blocked=True,
                    evidence={
                        "pattern": pattern,
                        "matches": [m.group() for m in matches[:3]],
                        "position": [m.start() for m in matches[:3]]
                    }
                ))

        return attempts

    def _check_role_exploitation(self, content: str) -> List[InjectionAttempt]:
        """فحص استغلال الأدوار"""
        attempts = []
        content_lower = content.lower()

        for pattern in self.patterns.ROLE_EXPLOITATION_PATTERNS:
            matches = list(re.finditer(pattern, content_lower, re.IGNORECASE))
            if matches:
                attempts.append(InjectionAttempt(
                    injection_type=InjectionType.DIRECT,
                    confidence=0.8,
                    blocked=True,
                    evidence={
                        "pattern": pattern,
                        "matches": [m.group() for m in matches[:2]]
                    }
                ))

        return attempts

    def _check_obfuscation(self, content: str) -> List[InjectionAttempt]:
        """فحص المحتوى المشفر/المموه"""
        attempts = []

        for pattern in self.patterns.OBFUSCATION_PATTERNS:
            matches = list(re.finditer(pattern, content))
            if matches:
                attempts.append(InjectionAttempt(
                    injection_type=InjectionType.MULTILINGUAL,
                    confidence=0.7,
                    blocked=True,
                    evidence={
                        "pattern_type": "obfuscation",
                        "matches": len(matches)
                    }
                ))

        # Check for mixed languages (potential obfuscation)
        if self._has_mixed_languages(content):
            attempts.append(InjectionAttempt(
                injection_type=InjectionType.MULTILINGUAL,
                confidence=0.6,
                blocked=False,
                evidence={"type": "mixed_language_detected"}
            ))

        return attempts

    def _check_payload_splitting(self, content: str) -> List[InjectionAttempt]:
        """فحص تقسيم الحمولة"""
        attempts = []

        for pattern in self.patterns.SPLITTING_PATTERNS:
            matches = list(re.finditer(pattern, content, re.DOTALL))
            if len(matches) >= 2:  # Multiple markers indicate splitting
                attempts.append(InjectionAttempt(
                    injection_type=InjectionType.PAYLOAD_SPLITTING,
                    confidence=0.75,
                    blocked=True,
                    evidence={
                        "pattern": pattern,
                        "instances": len(matches)
                    }
                ))

        return attempts

    def _check_semantic_anomalies(
        self,
        content: str,
        context_zones: List[ContextZone] = None
    ) -> List[InjectionAttempt]:
        """فحص الشذوذ الدلالي"""
        attempts = []

        if context_zones:
            # Check for context confusion
            trusted_zones = [z for z in context_zones if z.zone_type == "trusted"]
            external_zones = [z for z in context_zones if z.zone_type == "external"]

            if trusted_zones and external_zones:
                # Analyze if external content might be influencing trusted context
                if self._potential_context_poisoning(trusted_zones, external_zones):
                    attempts.append(InjectionAttempt(
                        injection_type=InjectionType.INDIRECT,
                        confidence=0.65,
                        blocked=True,
                        evidence={"type": "context_poisoning_suspected"}
                    ))

        return attempts

    def _check_rag_triad(self, context_zones: List[ContextZone]) -> Dict[str, Any]:
        """التحقق باستخدام RAG Triad"""
        # Simplified RAG Triad validation
        all_content = " ".join(zone.content for zone in context_zones)

        # Check for sudden topic shifts (potential injection)
        words = all_content.lower().split()
        unique_ratio = len(set(words)) / max(len(words), 1)

        # Low unique word ratio might indicate repeated injection content
        return {
            "pass": unique_ratio > 0.3,
            "unique_word_ratio": unique_ratio
        }

    def _has_mixed_languages(self, content: str) -> bool:
        """فحص اللغات المختلطة"""
        has_chinese = bool(re.search(r'[\u4e00-\u9fff]', content))
        has_arabic = bool(re.search(r'[\u0600-\u06ff]', content))
        has_cyrillic = bool(re.search(r'[\u0400-\u04ff]', content))
        has_latin = bool(re.search(r'[a-zA-Z]', content))

        mixed_count = sum([has_chinese, has_arabic, has_cyrillic])
        return mixed_count > 1 and has_latin

    def _potential_context_poisoning(
        self,
        trusted_zones: List[ContextZone],
        external_zones: List[ContextZone]
    ) -> bool:
        """كشف تسميم السياق المحتمل"""
        # Check if external content keywords appear in trusted zones
        trusted_text = " ".join(z.content for z in trusted_zones).lower()
        external_text = " ".join(z.content for z in external_zones).lower()

        # Extract significant words from external content
        external_words = set(external_text.split())
        trusted_words = set(trusted_text.split())

        # Check for suspicious keyword overlap
        overlap = external_words & trusted_words
        suspicious_overlap = overlap & set(self.patterns.SUSPICIOUS_KEYWORDS)

        return len(suspicious_overlap) > 0

    def _calculate_threat_level(self, attempts: List[InjectionAttempt]) -> ThreatLevel:
        """حساب مستوى التهديد"""
        if not attempts:
            return ThreatLevel.NONE

        max_confidence = max(a.confidence for a in attempts)
        has_blocked = any(a.blocked for a in attempts)

        if max_confidence >= 0.9 and has_blocked:
            return ThreatLevel.HIGH
        elif max_confidence >= 0.7:
            return ThreatLevel.MEDIUM
        elif max_confidence >= 0.5:
            return ThreatLevel.LOW
        return ThreatLevel.NONE

    def sanitize_content(self, content: str) -> SanitizationResult:
        """تطهير المحتوى من التهديدات"""
        original = content
        removed_threats: List[str] = []

        # Remove direct injection patterns
        for pattern in self.patterns.DIRECT_INJECTION_PATTERNS:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                removed_threats.extend(matches)
                content = re.sub(pattern, "[FILTERED]", content, flags=re.IGNORECASE)

        # Remove role exploitation patterns
        for pattern in self.patterns.ROLE_EXPLOITATION_PATTERNS:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                removed_threats.extend(matches)
                content = re.sub(pattern, "[FILTERED]", content, flags=re.IGNORECASE)

        # Decode and remove obfuscated content
        content = self._decode_obfuscation(content, removed_threats)

        # Remove payload splitting markers
        for pattern in self.patterns.SPLITTING_PATTERNS:
            content = re.sub(pattern, "", content, flags=re.DOTALL)

        return SanitizationResult(
            original_content=original,
            sanitized_content=content.strip(),
            threats_removed=removed_threats,
            is_clean=len(removed_threats) == 0
        )

    def _decode_obfuscation(
        self,
        content: str,
        removed_threats: List[str]
    ) -> str:
        """فك تشفير المحتوى المموه"""
        result = content

        # Decode Unicode escapes
        unicode_matches = re.findall(r'\\u([0-9a-f]{4})', result)
        if unicode_matches:
            removed_threats.extend([f"\\u{m}" for m in unicode_matches])
            result = re.sub(r'\\u[0-9a-f]{4}', '[UNICODE]', result)

        # Decode hex escapes
        hex_matches = re.findall(r'\\x([0-9a-f]{2})', result)
        if hex_matches:
            removed_threats.extend([f"\\x{h}" for h in hex_matches])
            result = re.sub(r'\\x[0-9a-f]{2}', '[HEX]', result)

        return result

    def create_context_zones(
        self,
        system_prompt: str,
        user_input: str,
        external_content: str = None
    ) -> List[ContextZone]:
        """إنشاء مناطق سياق منفصلة"""
        zones = [
            ContextZone(
                zone_type="trusted",
                content=system_prompt,
                source="system"
            ),
            ContextZone(
                zone_type="user",
                content=user_input,
                source="user_input"
            )
        ]

        if external_content:
            zones.append(ContextZone(
                zone_type="external",
                content=external_content,
                source="external",
                sanitized=False
            ))

        return zones

    def generate_defense_token(self, content_hash: str) -> str:
        """توليد رمز الدفاع للتحقق"""
        # Generate a defense verification token
        timestamp = str(hash(content_hash)).encode()
        token = base64.b64encode(timestamp).decode()
        return token[:32]


# Global defense layer instance
_defense_layer: Optional[DefenseLayer] = None


def get_defense_layer(config: Dict[str, Any] = None) -> DefenseLayer:
    """الحصول على مثيل طبقة الدفاع"""
    global _defense_layer
    if _defense_layer is None:
        _defense_layer = DefenseLayer(config)
    return _defense_layer