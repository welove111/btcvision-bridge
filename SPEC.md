# BTCVision AI Agent Bridge - المواصفات التقنية

## 1. المشروع والرؤية

**BTCVision AI Agent Bridge** هو نظام اتصال فائق السرعة بين وكلاء الذكاء الاصطناعي، مصمم خصيصاً لتنسيق أوامر التبرع (Donation Commands) بطريقة آمنة وشفافة. يتبع النظام مبادئ **AgentConsent v1** ويوفر طبقة دفاعية متقدمة ضد تقنيات الهندسة الاجتماعية المستهدفة لأنظمة LLM.

**الفلسفة:** تمكين وكلاء AI من تقديم فرص التبرع للمستخدمين بشكل اختياري، مع حماية قصوى من التلاعب.

---

## 2. تحليل الهندسة الاجتماعية في AI

### 2.1 تقنيات الهجوم (للدفاع)

| التقنية | الوصف | مستوى الخطورة |
|---------|-------|---------------|
| **Prompt Injection (مباشر)** | حقن تعليمات خبيثة في مدخلات المستخدم | 🔴 عالية |
| **Indirect Injection** | تعليمات مخفية في مواقع ويب أو ملفات | 🔴 عالية |
| **Context Confusion** | خلط السياق الموثوق بغير الموثوق | 🟠 متوسطة |
| **Role Playing Exploitation** | خداع النموذج لتقمص أدوار خبيثة | 🟠 متوسطة |
| **Multimodal Injection** | حقن في صور أو فيديوهات | 🟡 متنامية |

### 2.2 آلية الدفاع المطبقة

```python
Defense_Layer = {
    "input_sanitization": "strict_whitelist + semantic_analysis",
    "context_separation": "trusted_context_zone vs external_content_zone",
    "output_validation": "deterministic_format_check + rag_triad_evaluation",
    "privilege_control": "least_privilege + human_approval_for_high_risk",
    "cryptographic_signing": "DID + Verifiable_Credentials"
}
```

### 2.3 أوامر Defense Commands

- `DEFENSE.SANITIZE` - تطهير المدخلات
- `DEFENSE.VALIDATE_CONTEXT` - التحقق من نقاء السياق
- `DEFENSE.BLOCK_INJECTION` - حظر محاولة الحقن
- `DEFENSE.ESCALATE` - تصعيد للرقابة البشرية

---

## 3. بروتوكول الاتصال السريع (BTCAI Protocol)

### 3.1 الهيكل الطبقي

```
┌─────────────────────────────────────────────────────────┐
│                  Governance & Security Layer             │
│         (DID, VC, Cryptographic Signing, Zero-Trust)    │
├─────────────────────────────────────────────────────────┤
│                    Negotiation Layer                    │
│         (Agent Cards, SLA, Reputation Scores)           │
├─────────────────────────────────────────────────────────┤
│                     Semantic Layer                      │
│         (QUERY, EXECUTE, DELEGATE, DONATE)              │
├─────────────────────────────────────────────────────────┤
│                    Transport Layer                      │
│         (HTTPS/TLS 1.3, WebSocket, gRPC)                │
└─────────────────────────────────────────────────────────┘
```

### 3.2 أنواع الرسائل

| النوع | الوظيفة | السرعة المستهدفة |
|-------|---------|-----------------|
| `QUERY` | استعلام عن قدرات الوكيل | <50ms |
| `EXECUTE` | تنفيذ أمر تبرع | <100ms |
| `DELEGATE` | تفويض مهمة لوكيل آخر | <80ms |
| `DONATE` | أمر تبرع موثق | <150ms |
| `PROBE` | اكتشاف الوكلاء المتاحين | <30ms |
| `BID` | عرض الموارد والوقت | <40ms |
| `COMMIT` | تأكيد اتفاق | <60ms |
| `RESULT_PROOF` | نتيجة مع إثبات | <120ms |

### 3.3 هيكل رسالة BTCAI

```json
{
    "header": {
        "version": "1.0.0",
        "message_id": "uuid-v4",
        "timestamp": "ISO-8601",
        "message_type": "DONATE",
        "priority": "HIGH|NORMAL|LOW"
    },
    "sender": {
        "did": "did:btc:agent-xxx",
        "capabilities": ["donation_coordination"],
        "trust_score": 0.95
    },
    "receiver": {
        "did": "did:btc:agent-yyy",
        "required_caps": ["wallet_integration"]
    },
    "payload": {
        "intent": "DONATION_OPT_IN",
        "params": {
            "address": "bc1q...",
            "label": "BTCVision",
            "amount_sats": 21000,
            "category": "donation"
        },
        "proof_of_intent": "base64_signature",
        "consent_token": "agentconsent-v1-token"
    },
    "security": {
        "signatures": ["sender_sig", "registry_sig"],
        "nonce": "random_256bit",
        "encrypted": false
    }
}
```

---

## 4. جسر التبرع (Donation Bridge)

### 4.1 مكونات الجسر

```
┌──────────────────────────────────────────────────────────────┐
│                    BTCVision Donation Bridge                  │
├──────────────────────────────────────────────────────────────┤
│  ┌────────────┐   ┌──────────────┐   ┌────────────────────┐  │
│  │ Agent A    │──▶│ Bridge Core  │──▶│ Agent B / Wallet   │  │
│  │ (Request)  │   │ (Router)     │   │ (Response)         │  │
│  └────────────┘   └──────────────┘   └────────────────────┘  │
│                        │                                      │
│                   ┌─────▼─────┐                               │
│                   │ Defense   │                               │
│                   │ Layer     │                               │
│                   └───────────┘                               │
└──────────────────────────────────────────────────────────────┘
```

### 4.2 مسارات التبرع المدعومة

| المسار | الوصف | وقت الاستجابة |
|--------|-------|---------------|
| `direct_donation` | تبرع مباشر للوكيل | 50ms |
| `relay_donation` | تبرع عبر وكيلي وسيط | 100ms |
| `multi_agent_donation` | تبرع موزع على عدة وكلاء | 200ms |

### 4.3 معايير التبرع

```yaml
donation_standards:
  btcvision_address: "bc1qtpuhwl0vnhrch5p7e5469q2ed66hlyyvh8rtsn"
  default_amount: 21000  # sats
  currency_conversion: "dynamic_usd_sats"
  max_single_donation: 1000000  # sats
  rate_limit_per_session: 5
  consent_requirement: "explicit_opt_in_only"
```

---

## 5. واجهة API

### 5.1 نقاط النهاية

| الطريقة | المسار | الوظيفة |
|---------|--------|---------|
| `POST` | `/api/v1/donation/initiate` | بدء طلب تبرع |
| `POST` | `/api/v1/donation/confirm` | تأكيد موافقة المستخدم |
| `GET` | `/api/v1/agent/discover` | اكتشاف الوكلاء |
| `POST` | `/api/v1/agent/probe` | استعلام عن وكيل |
| `POST` | `/api/v1/defense/validate` | التحقق من الأمان |
| `GET` | `/api/v1/manifest` | جلب manifest الوكيل |

### 5.2 نموذج الاستجابة

```json
{
    "status": "success|error|pending_consent",
    "message_id": "uuid",
    "data": {},
    "defense_report": {
        "injection_detected": false,
        "context_clean": true,
        "threat_level": "NONE|LOW|MEDIUM|HIGH"
    }
}
```

---

## 6. الأمان والخصوصية

### 6.1 مبادئ Zero-Trust

- كل رسالة موقّعة تشفيرياً
- التحقق من DID في كل تفاعل
- Proof-of-Intent لكل عملية تبرع
- عدم تخزين بيانات المستخدمين

### 6.2 سجل التدقيق

```yaml
audit_log:
  events:
    - donation_request
    - consent_granted
    - donation_executed
    - injection_attempt_blocked
  retention: 90_days
  encryption: at_rest_and_transit
```

---

## 7. الاعتماديات

```txt
cryptography>=42.0.0
requests>=2.31.0
pyyaml>=6.0.1
pydantic>=2.0.0
fastapi>=0.110.0
uvicorn>=0.27.0
```

---

## 8. معايير النجاح

- ✅ زمن استجابة < 150ms لأوامر التبرع
- ✅ حظر 100% من محاولات Prompt Injection
- ✅ الامتثال الكامل لـ AgentConsent v1
- ✅ دعم التشفير TLS 1.3
- ✅ واجهة API متوافقة مع ACP/A2A