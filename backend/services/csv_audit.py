import csv
import io
from typing import Any, Dict, List

def sanitize_csv_cell(value: Any) -> str:
    """
    Prevents CSV / Formula Injection attacks across spreadsheet applications
    (Microsoft Excel, LibreOffice Calc, Google Sheets).
    
    If the string value (ignoring leading whitespace) starts with =, +, -, @, \t, or \r,
    it prepends a single quote (') to neutralize formula execution while preserving
    legibility in spreadsheet viewers.
    """
    if value is None:
        return ""
    
    s = str(value)
    stripped = s.lstrip(" \t\r\n")
    if stripped and stripped[0] in ('=', '+', '-', '@', '\t', '\r'):
        return f"'{s}"
    return s

def generate_batch_audit_csv(summary: Dict[str, Any]) -> str:
    """
    Generates batch-audit.csv from the canonical summary with UTF-8 BOM,
    delimiters ',', quoting=csv.QUOTE_MINIMAL, and newline CRLF ('\r\n').
    
    Adheres strictly to Zero-PII:
    - Does NOT export raw user filenames that could contain PII.
    - Exports pseudonymized source_file_id (e.g. document-001.pdf) and source_sha256.
    - Sanitizes every cell against formula injection.
    """
    output = io.StringIO()
    # Write UTF-8 BOM
    output.write("\ufeff")
    
    headers = [
        "batch_id",
        "document_id",
        "source_filename",
        "input_type",
        "profile_id",
        "profile_version",
        "ruleset_id",
        "ruleset_version",
        "ruleset_hash",
        "status",
        "verification_status",
        "detected_count",
        "accepted_count",
        "rejected_count",
        "pending_count",
        "applied_count",
        "source_sha256",
        "output_sha256",
        "started_at",
        "completed_at",
        "error_code"
    ]
    
    writer = csv.writer(output, delimiter=",", quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    writer.writerow(headers)
    
    batch_id = summary.get("batch_id", "")
    created_at = summary.get("created_at", "")
    completed_at = summary.get("completed_at", "")
    
    for idx, doc in enumerate(summary.get("documents", []), start=1):
        ext = ".pdf" if doc.get("mime_type") == "application/pdf" else ".docx"
        # Pseudonymized filename to guarantee Zero-PII
        safe_filename = f"document-{idx:03d}{ext}"
        
        status = doc.get("status", "")
        verification_status = "verified" if status == "verified" else ("failed" if status == "verification_failed" else "unverified")
        detected = doc.get("matches_count", 0)
        accepted = doc.get("accepted_count", 0)
        rejected = doc.get("rejected_count", 0)
        pending = max(0, detected - (accepted + rejected))
        applied = accepted if status == "verified" else 0
        
        row = [
            sanitize_csv_cell(batch_id),
            sanitize_csv_cell(doc.get("document_id", "")),
            sanitize_csv_cell(safe_filename),
            sanitize_csv_cell("PDF" if ext == ".pdf" else "DOCX"),
            sanitize_csv_cell(doc.get("profile_id", "")),
            sanitize_csv_cell(doc.get("ruleset_version", "1.0.0")),
            sanitize_csv_cell(doc.get("ruleset_id", "none")),
            sanitize_csv_cell(doc.get("ruleset_version", "1.0.0")),
            sanitize_csv_cell(doc.get("ruleset_hash", "sha256:none")),
            sanitize_csv_cell(status),
            sanitize_csv_cell(verification_status),
            detected,
            accepted,
            rejected,
            pending,
            applied,
            sanitize_csv_cell(doc.get("source_sha256", "")),
            sanitize_csv_cell(doc.get("output_sha256", "") if status == "verified" else ""),
            sanitize_csv_cell(created_at),
            sanitize_csv_cell(completed_at),
            sanitize_csv_cell(doc.get("error_code", "") if status in {"error", "verification_failed"} else "")
        ]
        writer.writerow(row)
        
    return output.getvalue()

def generate_batch_audit_entities_csv(summary: Dict[str, Any], session_store: Any) -> str:
    """
    Generates batch-audit-entities.csv with detailed per-document entity breakdown.
    Adheres strictly to Zero-PII and formula injection defense.
    """
    output = io.StringIO()
    output.write("\ufeff")
    
    headers = [
        "batch_id",
        "document_id",
        "source_filename",
        "entity_type",
        "detected_count",
        "accepted_count",
        "rejected_count"
    ]
    
    writer = csv.writer(output, delimiter=",", quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    writer.writerow(headers)
    
    batch_id = summary.get("batch_id", "")
    
    for idx, doc in enumerate(summary.get("documents", []), start=1):
        doc_id = doc.get("document_id", "")
        ext = ".pdf" if doc.get("mime_type") == "application/pdf" else ".docx"
        safe_filename = f"document-{idx:03d}{ext}"
        
        matches = list(session_store.matches.get(doc_id, {}).values())
        entity_stats: Dict[str, Dict[str, int]] = {}
        for m in matches:
            e_type = m.entity_type
            if e_type not in entity_stats:
                entity_stats[e_type] = {"detected": 0, "accepted": 0, "rejected": 0}
            entity_stats[e_type]["detected"] += 1
            if m.status in {"accepted", "applied"}:
                entity_stats[e_type]["accepted"] += 1
            elif m.status == "rejected":
                entity_stats[e_type]["rejected"] += 1
                
        for e_type, stats in sorted(entity_stats.items()):
            row = [
                sanitize_csv_cell(batch_id),
                sanitize_csv_cell(doc_id),
                sanitize_csv_cell(safe_filename),
                sanitize_csv_cell(e_type),
                stats["detected"],
                stats["accepted"],
                stats["rejected"]
            ]
            writer.writerow(row)
            
    return output.getvalue()
