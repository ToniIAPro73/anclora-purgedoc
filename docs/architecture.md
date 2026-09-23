# ANCLORA PURGEDOC — ARQUITECTURA TÉCNICA

## 1. Visión General
**Anclora Purgedoc** es una plataforma de ingeniería documental para la purga y redacción física real, privada y verificada de datos sensibles en archivos PDF y DOCX, tanto en procesamiento individual como en cola de procesamiento por lotes (*Batch Document Queue*) con monitorización en tiempo real mediante *Batch Progress Streaming (SSE)*, exportación forense tabular en *CSV* y gestión centralizada de ciclo de vida efímero (*Audit Retention Policies*).

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
4. **Zero-PII en Streaming y Exportaciones Tabulares (CSV)**:
   - Los nombres de archivo se pseudonimizan como `document-001.pdf` en CSV para evitar filtraciones de PII a través de nombres personales.
   - Trazabilidad preservada estrictamente mediante `source_sha256` y `document_id`.

---

## 3. Arquitectura del Ciclo de Vida y Retención (`services/lifecycle.py`)

### 3.1 Política de Expiración Basada en Inactividad
- `SESSION_TTL_MINUTES=60`: Expiración calculada como `last_activity_at + ttl_seconds`. Las acciones humanas (subida, revisión, navegación, purga, descarga) renuevan el timestamp. Los heartbeats técnicos de SSE **NO** renuevan el TTL.
- Protección del estado `awaiting_review`: Los artefactos fuente e intermedios no se eliminan mientras la sesión esté activa y en espera de decisión humana.
- Expiración dependiente de ciclo de vida: Los documentos fuente pasan a ser elegibles para eliminación (`eligible_for_cleanup_at`) únicamente después de que el documento haya generado exitosamente un output `verified` y sus auditorías asociadas.

### 3.2 Protección de Operaciones Activas y Bloqueo de Concurrencia
- Gestor de contexto `protect_operation(session_id, op_name)`: Incrementa un contador atómico `active_operations` bajo bloques `try/finally` para evitar carreras entre cleanup y operaciones en curso (OCR, purga, verificación, generación de ZIP o descargas).
- Bloqueo de granularidad fina: `asyncio.Lock` independiente por sesión, lote y documento. Las operaciones batch no se bloquean entre lotes distintos.

### 3.3 Borrado Manual y Trazabilidad Tombstone
- Borrado manual de lote: `DELETE /api/batches/{id}` elimina los archivos de ese lote exacto y limpia sus suscriptores en el event bus, dejando intactos los demás lotes de la sesión.
- Borrado manual de sesión: `DELETE /api/sessions/{id}` ejecuta un borrado en cascada (lotes, documentos, temporales en disco, memoria y buses SSE).
- Registro tombstone: El acceso a recursos eliminados o expirados responde con `HTTP 410 Gone` y `{ "code": "RESOURCE_EXPIRED", "detail": "RESOURCE_EXPIRED" }`.

---

## 4. Limitaciones Conocidas y Alcance de Borrado
1. **Alcance del Borrado**: La eliminación elimina los archivos y directorios gestionados por Anclora Purgedoc en `/tmp/`. No constituye un borrado físico seguro a nivel de hardware (SSD wear-leveling) ni tiene control sobre archivos que el usuario ya haya descargado a su dispositivo local.
2. **Modularidad del Backend**: `server.py` agrupa endpoints de procesamiento, reglas, lotes, streaming y ciclo de vida. Se recomienda modularizar en routers dedicados (`routes/batch.py`, `routes/lifecycle.py`, etc.).
