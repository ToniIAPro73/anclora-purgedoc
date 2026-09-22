# ANCLORA PURGEDOC — ARQUITECTURA TÉCNICA

## 1. Visión General
**Anclora Purgedoc** es una plataforma de ingeniería documental para la purga y redacción física real, privada y verificada de datos sensibles en archivos PDF y DOCX, tanto en procesamiento individual como en cola de procesamiento por lotes (*Batch Document Queue*) con monitorización en tiempo real mediante *Batch Progress Streaming (SSE)*.

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
    O --> Q[Batch Audit Consolidado + ZIP Seguro]
    P --> Q

    E -.->|Eventos de Estado y Fases| EB[BatchEventBus In-Memory]
    EB -.->|GET /api/batches/{id}/events (SSE)| A
```

---

## 2. Límites y Fronteras de Privacidad
1. **Zero External AI / Cloud**: Ningún dato, fragmento, imagen o metadato se transmite a LLMs remotos ni APIs externas. 100% de la computación es local (spaCy, Tesseract, OpenCV, PyMuPDF, python-docx).
2. **Ciclo de vida efímero**: Los archivos se procesan en `/tmp/anclora-purgedoc/{session_id}/{batch_id}/{document_id}/` con TTL configurable y borrado explícito. No existe base de datos permanente de documentos ni de contenido sensible.
3. **Auditoría Forense Criptográfica**: Las auditorías individuales y de lote nunca registran el texto sensible en texto plano, sino su hash SHA-256 (`sha256:...`).
4. **Zero-PII en Streaming SSE**: Los eventos transmitidos por SSE contienen únicamente identificadores opacos, estados, fases operativas reales y contadores. Cero texto plano, cero fragmentos de OCR y cero valores detectados.

---

## 3. Arquitectura del Event Bus y Streaming SSE

### 3.1 Abstracción de Event Bus (`services/event_bus.py`)
- **Diseño Desacoplado**: Clase abstracta `BaseEventBus` con implementación `InMemoryBatchEventBus` para permitir reemplazo transparente por Redis u otro broker en el futuro.
- **Secuencia Monotónica**: Cada evento asigna un entero incremental estricto (`sequence: int`) por lote.
- **Búfer de Historial Ring-Buffer**: Mantiene hasta 500 eventos en memoria por lote para soportar reconexiones robustas con `Last-Event-ID`.
- **Protección de Consumidores Lentos**: Colas `asyncio.Queue` acotadas (`maxsize=100`) con política de descarte del elemento más antiguo para prevenir consumo desmedido de memoria.
- **Aislamiento Estricto**: Validación de pertenencia del lote a la sesión solicitada; los suscriptores solo reciben eventos de su lote específico.

### 3.2 Endpoint SSE (`GET /api/batches/{batchId}/events`)
- Formato estándar Server-Sent Events (`text/event-stream`):
  ```text
  id: 4
  event: document_status_changed
  data: {"eventId":"evt_b1_4","sequence":4,"batchId":"b1","documentId":"d1","type":"document_status_changed","status":"analyzing","phase":"ocr_extraction","timestamp":"2026-09-22T20:15:00Z","schemaVersion":1,"payload":{"filename":"sample.pdf","isScanned":true}}
  ```
- Replay automático de eventos pendientes si el cliente envía `Last-Event-ID` o `?last_event_id=...`.
- Heartbeat periódico cada 15 segundos (`: heartbeat ...`) para evitar cierres de conexión por parte de balanceadores o proxies.
- Snapshot REST de respaldo disponible mediante `GET /api/batches/{batchId}` para reconciliación en caso de fallo de red prolongado.

---

## 4. Limitaciones Conocidas y Deuda Técnica
1. **Modularidad del Backend**: `server.py` agrupa endpoints individuales, de lote y de streaming. Se recomienda separar en sub-módulos (`backend/routes/batch.py`, `backend/routes/documents.py`, `backend/routes/rules.py`).
2. **Modularidad del Frontend**: `App.js` gestiona tanto el flujo individual como el selector de lote. Se recomienda extraer el contexto del lote en un hook dedicado si se amplían las funcionalidades.
