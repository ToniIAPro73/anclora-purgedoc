# ANCLORA PURGEDOC — MVP 1.0

Plataforma de purga documental real, privada y verificada para archivos PDF y DOCX con informe de auditoría criptográfico.

## Características Principales
- **100% Procesamiento Local**: Cero llamadas a APIs de LLM externas o nubes de terceros. Motor NER con spaCy (`es_core_news_sm`, `en_core_web_sm`) y reglas regex configurables en YAML (`backend/config/profiles/*.yaml`).
- **Perfiles Verticales Especializados**:
  - **RRHH / Nóminas**: DNI, NIE, SSN, IBAN, salarios, nombres, teléfonos y direcciones.
  - **Legal / Contratos**: CIF, DNI de otorgantes, autos judiciales, cláusulas y honorarios.
  - **Soporte Técnico / DevOps**: Direcciones IP, API keys, tokens JWT, emails y tickets.
- **Purga Física Real**:
  - En **PDF**: Eliminación física de comandos y streams mediante PyMuPDF (`apply_redactions`) con recolección de basura.
  - En **DOCX**: Saneamiento profundo de paquetes OOXML (`word/document.xml`, tablas, headers, footers y `core.xml`).
- **Verificación Fail-Closed**: Reinspección automática post-proceso. Si queda cualquier residuo, se bloquea la certificación de seguridad.
- **Auditoría Forense Criptográfica**: Exportación en PDF imprimible y JSON estructurado sin exponer datos en claro (hashing SHA-256).
- **Diseño & Accesibilidad**: Interfaz en español e inglés (ES/EN), modos Claro / Oscuro / Sistema (Oscuro por defecto), visor interactivo con bounding boxes sincronizados y accesibilidad WCAG 2.1 AA.

## Puesta en Marcha Local

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m spacy download es_core_news_sm
python -m spacy download en_core_web_sm
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

### Frontend
```bash
cd frontend
yarn install
yarn start
```

### Ejecución de Pruebas
```bash
PYTHONPATH=. pytest backend/tests/test_redaction_pipeline.py -v
```
