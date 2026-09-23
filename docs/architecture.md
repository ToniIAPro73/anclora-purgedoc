# ANCLORA PURGEDOC — ARQUITECTURA TÉCNICA

## 1. Visión General
**Anclora Purgedoc** es una plataforma de ingeniería documental para la purga y redacción física real, privada y verificada de datos sensibles en archivos PDF y DOCX, tanto en procesamiento individual como en cola de procesamiento por lotes (*Batch Document Queue*) con monitorización en tiempo real mediante *Batch Progress Streaming (SSE)*, exportación forense tabular en *CSV*, gestión centralizada de ciclo de vida efímero (*Audit Retention Policies*) y portabilidad criptográfica de reglas (*Encrypted Profile Export & Import .aprules*).

```mermaid
graph TD
    A[Cliente / Navegador Web] -->|Subida individual / Lote multi-archivo| B[FastAPI Gateway /api]
    B --> C{Modo de Operación}
    C -->|Single Doc| D[Pipeline Soberano Unificado]
    C -->|Batch Queue| E[Batch Orchestrator + Semáforo Concurrencia]
    E -->|Workers limitados| D
    D --> F[Motor de Detección Híbrido]
    F -->|Reglas Base YAML| G[Perfiles: RRHH, Legal, DevOps]
    F -->|Custom Ruleset Overlay| H[Motor de Reglas RE2 / Safe Regex]
    H <-->|Export/Import Cifrado .aprules| CRYPTO[AES-256-GCM + Argon2id + AAD Binding]
    F -->|NLP Local| I[spaCy es_core_news_sm / en_core_web_sm]
    F -->|Mapeo coordenadas| J[PyMuPDF Word Bboxes / OCR Deskewed Bboxes]
    J -->|Revisión interactiva independiente| A
    A -->|Confirmación humana irreversible| K[Motor de Purga Real]
    K -->|PDF: PyMuPDF Stream Redaction + Garbage Coll| L[Artefacto Purgado]
    K -->|DOCX: OOXML Deep Scan & Sanitization| L
    L --> M[Verificador Automático Fail-Closed]
    M -->|Test de ausencia en stream y metadatos| N{¿Supera verificación?}
    N -->|SÍ| O[Estado: verified + Certificado Auditoría Individual]
    N -->|NO| P[Estado: verification_failed / Bloqueo Fail-Closed]
    O --> Q[Batch Audit Consolidado: JSON + PDF + CSV + ZIP Seguro]
    P --> Q

    E -.->|Eventos de Estado y Fases| EB[BatchEventBus In-Memory]
    EB -.->|GET /api/batches/{id}/events (SSE)| A

    LM[LifecycleManager Centralizado] -.->|Inactividad TTL / Active Ops Guards| D
    LM -.->|Limpieza en Cascada y Tombstones 410| EB
```

---

## 2. Límites y Fronteras de Privacidad
1. **Zero External AI / Cloud**: Ningún dato, fragmento, imagen o metadato se transmite a LLMs remotos ni APIs externas. 100% de la computación es local (spaCy, Tesseract, OpenCV, PyMuPDF, python-docx).
2. **Ciclo de vida efímero gobernado por TTL**: Los archivos se procesan en `/tmp/anclora-purgedoc/{session_id}/{batch_id}/{document_id}/` con TTL de inactividad configurable y borrado explícito. No existe base de datos permanente de documentos ni de contenido sensible.
3. **Auditoría Forense Criptográfica**: Las auditorías individuales y de lote nunca registran el texto sensible en texto plano, sino su hash SHA-256 (`sha256:...`).
4. **Zero-PII en Streaming y Exportaciones Cifradas (.aprules)**:
   - El archivo `.aprules` encripta todo el contenido funcional (nombres, patrones, ejemplos, descripciones). El envelope exterior únicamente expone parámetros técnicos necesarios para el descifrado.

---

## 3. Especificación Criptográfica de Exportación e Importación (.aprules)

### 3.1 Estructura del Envelope
```json
{
  "format": "anclora-purgedoc-ruleset",
  "format_version": 1,
  "crypto": {
    "cipher": "AES-256-GCM",
    "kdf": "Argon2id",
    "salt": "<base64_16_bytes>",
    "nonce": "<base64_12_bytes>",
    "memory_cost_kib": 65536,
    "time_cost": 3,
    "parallelism": 1
  },
  "ciphertext": "<base64_ciphertext_with_16_byte_auth_tag>"
}
```

### 3.2 Primitivas y Autenticación con AAD
- **Derivación de Clave (KDF)**: Argon2id derivando clave de 32 bytes (256 bits).
- **Cifrado Autenticado (AEAD)**: AES-256-GCM con Nonce/IV único de 12 bytes generado con CSPRNG por cada exportación.
- **AAD (Additional Authenticated Data)**: Serialización determinista y ordenada de los metadatos técnicos del envelope:
  ```json
  {"cipher":"AES-256-GCM","format":"anclora-purgedoc-ruleset","format_version":1,"kdf":"Argon2id","memory_cost_kib":65536,"nonce":"...","parallelism":1,"salt":"...","time_cost":3}
  ```
  Cualquier modificación maliciosa de los parámetros del envelope exterior invalida el tag de autenticación.

### 3.3 Validación de Parámetros Anti-DoS
- Antes de ejecutar Argon2id, el servidor valida estrictamente los límites:
  - `8192 <= memory_cost_kib <= 262144` (8 MiB a 256 MiB)
  - `1 <= time_cost <= 10`
  - `1 <= parallelism <= 4`
  - `len(salt) == 16` y `len(nonce) == 12`
  - `len(ciphertext) <= 5 MiB + 1024`
- Cualquier valor anómalo es rechazado de inmediato con `UNSUPPORTED_CRYPTO_PARAMETERS`.

---

## 4. Limitaciones Conocidas y Alcance de Borrado
1. **Alcance del Borrado**: La eliminación elimina los archivos y directorios gestionados por Anclora Purgedoc en `/tmp/`. No constituye un borrado físico seguro a nivel de hardware (SSD wear-leveling) ni tiene control sobre archivos que el usuario ya haya descargado a su dispositivo local.
2. **Modularidad del Backend**: `server.py` agrupa endpoints de procesamiento, reglas, lotes, streaming, ciclo de vida y criptografía. Se recomienda modularizar en routers dedicados (`routes/batch.py`, `routes/rules.py`, `routes/lifecycle.py`, etc.).
