# ANCLORA PURGEDOC — ARQUITECTURA TÉCNICA

## 1. Visión General
**Anclora Purgedoc** es una plataforma de ingeniería documental para la purga y redacción física real, privada y verificada de datos sensibles en archivos PDF y DOCX, tanto en procesamiento individual como en cola de procesamiento por lotes (*Batch Document Queue*) con monitorización en tiempo real mediante *Batch Progress Streaming (SSE)* y exportación forense tabular en *CSV*.

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
```

---

## 2. Límites y Fronteras de Privacidad
1. **Zero External AI / Cloud**: Ningún dato, fragmento, imagen o metadato se transmite a LLMs remotos ni APIs externas. 100% de la computación es local (spaCy, Tesseract, OpenCV, PyMuPDF, python-docx).
2. **Ciclo de vida efímero**: Los archivos se procesan en `/tmp/anclora-purgedoc/{session_id}/{batch_id}/{document_id}/` con TTL configurable y borrado explícito. No existe base de datos permanente de documentos ni de contenido sensible.
3. **Auditoría Forense Criptográfica**: Las auditorías individuales y de lote nunca registran el texto sensible en texto plano, sino su hash SHA-256 (`sha256:...`).
4. **Zero-PII en Streaming y Exportaciones Tabulares (CSV)**:
   - Los nombres de archivo se pseudonimizan como `document-001.pdf` en CSV para evitar filtraciones de PII a través de nombres personales.
   - Trazabilidad preservada estrictamente mediante `source_sha256` y `document_id`.

---

## 3. Especificación de Exportación Tabular CSV

### 3.1 Esquemas Técnicos Estables (en inglés)
1. **Resumen de Documentos (`batch-audit.csv`)**:
   - `batch_id`
   - `document_id`
   - `source_filename` (pseudonimizado: `document-XXX.ext`)
   - `input_type` (`PDF` / `DOCX`)
   - `profile_id` (`rrhh`, `legal`, `soporte`)
   - `profile_version`
   - `ruleset_id`
   - `ruleset_version`
   - `ruleset_hash`
   - `status` (`verified`, `verification_failed`, `error`, `cancelled`)
   - `verification_status` (`verified`, `failed`, `unverified`)
   - `detected_count`
   - `accepted_count`
   - `rejected_count`
   - `pending_count`
   - `applied_count`
   - `source_sha256`
   - `output_sha256`
   - `started_at`
   - `completed_at`
   - `error_code`

2. **Detalle por Entidad (`batch-audit-entities.csv`)**:
   - `batch_id`
   - `document_id`
   - `source_filename`
   - `entity_type`
   - `detected_count`
   - `accepted_count`
   - `rejected_count`

### 3.2 Estrategia Anti-Inyección de Fórmulas (CSV / Formula Injection)
- Cualquier valor de celda que comience por `=`, `+`, `-`, `@`, `\t` o `\r` (incluso tras espacios en blanco iniciales) se neutraliza anteponiendo un apóstrofe `'`.
- Formato estándar RFC 4180 con comillas mínimas (`csv.QUOTE_MINIMAL`), saltos de línea CRLF (`\r\n`) y codificación UTF-8 con BOM (`\ufeff`) para visualización instantánea y sin problemas de encoding en Microsoft Excel, LibreOffice y Google Sheets.

---

## 4. Limitaciones Conocidas y Deuda Técnica
1. **Modularidad del Backend**: `server.py` agrupa endpoints individuales, de lote, de streaming y exportación CSV. Se recomienda separar en sub-módulos (`backend/routes/batch.py`, `backend/routes/documents.py`, `backend/routes/rules.py`).
2. **Modularidad del Frontend**: `App.js` gestiona tanto el flujo individual como el selector de lote. Se recomienda extraer el contexto del lote en un hook dedicado si se amplían las funcionalidades.
