# ANCLORA PURGEDOC — ARQUITECTURA TÉCNICA

## 1. Visión General
**Anclora Purgedoc** es una plataforma de ingeniería documental para la purga y redacción física real, privada y verificada de datos sensibles en archivos PDF y DOCX.

```mermaid
graph TD
    A[Cliente / Navegador Web] -->|Subida efímera| B[FastAPI Gateway /api]
    B --> C[Motor de Detección Híbrido]
    C -->|Reglas YAML| D[Regex por Perfil: RRHH, Legal, DevOps]
    C -->|NLP Local| E[spaCy es_core_news_sm / en_core_web_sm]
    C -->|Mapeo coordenadas| F[PyMuPDF Word Bboxes]
    F -->|Revisión interactiva| A
    A -->|Confirmación humana irreversible| G[Motor de Purga Real]
    G -->|PDF: PyMuPDF Stream Redaction + Garbage Coll| H[Artefacto Purgado]
    G -->|DOCX: OOXML Deep Scan & Sanitization| H
    H --> I[Verificador Automático Fail-Closed]
    I -->|Test de ausencia en stream y metadatos| J{¿Supera verificación?}
    J -->|SÍ| K[Estado: Purga Verificada + Certificado Auditoría PDF/JSON]
    J -->|NO| L[Estado: Fallo Bloqueante Fail-Closed]
```

## 2. Límites y Fronteras de Privacidad
1. **Zero External AI**: Ningún dato, fragmento o metadato se transmite a LLMs remotos ni nubes externas.
2. **Ciclo de vida efímero**: Los archivos se almacenan en `/tmp/anclora-purgedoc/{session_id}` con TTL configurable y borrado explícito.
3. **Auditoría Forense Criptográfica**: Las auditorías nunca registran el texto sensible en claro, sino su hash SHA-256 (`sha256:...`).
