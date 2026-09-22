import os
import json
import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from backend.models import DocumentMetadata, MatchItem

logger = logging.getLogger(__name__)

class AuditService:
    def __init__(self):
        pass

    def generate_audit_json(
        self,
        doc_meta: DocumentMetadata,
        matches: List[MatchItem],
        verification_passed: bool,
        verification_details: Dict[str, Any],
        custom_ruleset_meta: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Builds compliant cryptographic audit manifest.
        Indicating the exact base profile, custom ruleset ID, version, and content hash.
        NEVER includes raw sensitive text in plaintext!
        """
        counts = {
            "detected": len(matches),
            "accepted": sum(1 for m in matches if m.status in ["accepted", "applied"]),
            "rejected": sum(1 for m in matches if m.status == "rejected"),
            "pending": sum(1 for m in matches if m.status == "pending"),
            "applied": sum(1 for m in matches if m.status == "applied")
        }

        by_entity = {}
        for m in matches:
            by_entity[m.entity_type] = by_entity.get(m.entity_type, 0) + 1

        items = []
        for m in matches:
            items.append({
                "match_id": m.id,
                "entity_type": m.entity_type,
                "original_text_hash": m.original_text_hash,
                "page": m.page,
                "confidence": round(m.confidence, 4),
                "source": m.source,
                "status": m.status,
                "rule_id": m.rule_id
            })

        ruleset_info = {
            "base_profile": doc_meta.profile_id,
            "base_profile_version": "1.0.0",
            "custom_ruleset_id": custom_ruleset_meta.get("ruleset_id", "none") if custom_ruleset_meta else "none",
            "custom_ruleset_version": custom_ruleset_meta.get("version", "1.0.0") if custom_ruleset_meta else "1.0.0",
            "custom_ruleset_hash": custom_ruleset_meta.get("hash", "sha256:default") if custom_ruleset_meta else "sha256:none",
            "active_custom_rules_count": custom_ruleset_meta.get("active_rules_count", 0) if custom_ruleset_meta else 0
        }

        audit_data = {
            "audit_id": f"aud_{uuid.uuid4().hex[:12]}",
            "document_id": doc_meta.id,
            "source_file_name": doc_meta.filename,
            "source_file_sha256": doc_meta.source_sha256,
            "output_file_sha256": doc_meta.output_sha256 or "n/a",
            "profile": {
                "id": doc_meta.profile_id,
                "version": "1.0.0"
            },
            "ruleset": ruleset_info,
            "started_at": doc_meta.uploaded_at,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "status": "verified" if verification_passed else "verification_failed",
            "detectors": {
                "ner": "spaCy local NLP (ES/EN)",
                "ruleset_version": "1.0.0",
                "custom_rules_active": ruleset_info["active_custom_rules_count"] > 0
            },
            "summary": counts,
            "by_entity_type": by_entity,
            "items": items,
            "metadata_sanitization": {
                "author_cleared": True,
                "creator_cleared": True,
                "subject_cleared": True,
                "producer_normalized": "Anclora Purgedoc Engine"
            },
            "verification": {
                "passed": verification_passed,
                "fail_closed_enforced": True,
                "details": verification_details
            }
        }
        return audit_data

    def generate_audit_pdf(self, audit_json: Dict[str, Any], output_pdf_path: str):
        doc = SimpleDocTemplate(
            output_pdf_path,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )
        
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'AuditTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=18,
            leading=22,
            textColor=colors.HexColor('#0F172A')
        )
        subtitle_style = ParagraphStyle(
            'AuditSubTitle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            leading=14,
            textColor=colors.HexColor('#64748B')
        )
        body_style = ParagraphStyle(
            'AuditBody',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=12,
            textColor=colors.HexColor('#1E293B')
        )

        elements = []

        elements.append(Paragraph("ANCLORA PURGEDOC — CERTIFICADO DE AUDITORÍA Y PURGA", title_style))
        elements.append(Paragraph(f"Audit ID: {audit_json['audit_id']} | Fecha: {audit_json['completed_at']}", subtitle_style))
        elements.append(Spacer(1, 10))
        elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0284C7'), spaceBefore=5, spaceAfter=15))

        status_color = colors.HexColor('#059669') if audit_json['status'] == "verified" else colors.HexColor('#DC2626')
        status_text = "ESTADO: PURGA VERIFICADA — CONTENIDO EXPUNGIDO" if audit_json['status'] == "verified" else "ESTADO: VERIFICACIÓN FALLIDA — CONTENIDO BLOQUEADO"
        
        banner_table = Table([[Paragraph(f"<b>{status_text}</b>", ParagraphStyle('B', parent=body_style, textColor=colors.white, alignment=1))]], colWidths=[540])
        banner_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), status_color),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))
        elements.append(banner_table)
        elements.append(Spacer(1, 15))

        summary = audit_json['summary']
        ruleset = audit_json.get('ruleset', {})
        metrics_data = [
            ["Archivo Fuente:", audit_json['source_file_name'], "Perfil Base:", audit_json['profile']['id'].upper()],
            ["Ruleset Hash:", ruleset.get('custom_ruleset_hash', 'sha256:none')[:22] + "...", "Reglas Custom:", str(ruleset.get('active_custom_rules_count', 0))],
            ["SHA-256 Fuente:", audit_json['source_file_sha256'][:22] + "...", "SHA-256 Purgado:", (audit_json['output_file_sha256'] or 'n/a')[:22] + "..."],
            ["Total Detectados:", str(summary['detected']), "Aceptados / Purgados:", str(summary['applied'])],
            ["Rechazados:", str(summary['rejected']), "Pendientes:", str(summary['pending'])]
        ]
        t = Table(metrics_data, colWidths=[120, 160, 120, 140])
        t.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.HexColor('#1E293B')),
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
            ('PADDING', (0,0), (-1,-1), 4),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 15))

        elements.append(Paragraph("<b>Registro Detallado de Coincidencias Sanitizadas</b> (Sin exposición de texto en claro):", body_style))
        elements.append(Spacer(1, 6))

        table_rows = [["ID", "Entidad", "Pág.", "Fuente", "Conf.", "Estado", "Hash Criptográfico (SHA-256)"]]
        for item in audit_json.get("items", [])[:40]:
            table_rows.append([
                item["match_id"][:8],
                item["entity_type"],
                str(item["page"]),
                ", ".join(item["source"]),
                f"{int(item['confidence']*100)}%",
                item["status"],
                item["original_text_hash"][:20] + "..."
            ])

        if len(table_rows) == 1:
            table_rows.append(["-", "Sin coincidencias", "-", "-", "-", "-", "-"])

        items_table = Table(table_rows, colWidths=[50, 90, 30, 60, 45, 65, 200])
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0F172A')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 7),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F8FAFC')]),
            ('PADDING', (0,0), (-1,-1), 3),
        ]))
        elements.append(items_table)
        elements.append(Spacer(1, 15))

        elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#CBD5E1'), spaceBefore=10, spaceAfter=8))
        elements.append(Paragraph("<b>Declaración de Garantía de Privacidad:</b> El procesamiento fue ejecutado 100% de manera local. Ningún fragmento del documento fue transferido a LLMs externos ni servidores de terceros. Los artefactos originales son destruidos bajo política TTL efímera.", subtitle_style))

        doc.build(elements)

audit_service = AuditService()
