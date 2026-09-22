import os
from pathlib import Path
import fitz # PyMuPDF
import docx

FIXTURES_DIR = Path(__file__).parent / "fixtures"

def generate_all_fixtures():
    os.makedirs(FIXTURES_DIR, exist_ok=True)
    generate_hr_pdf()
    generate_legal_docx()
    generate_support_pdf()
    print("All synthetic fixtures generated successfully.")

def generate_hr_pdf():
    pdf_path = FIXTURES_DIR / "sample_rrhh_payroll.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842) # A4
    
    # Title
    page.insert_text((50, 60), "RECIBO DE NÓMINA CONFIDENCIAL — DICIEMBRE 2025", fontsize=14, fontname="helv", color=(0.1, 0.2, 0.5))
    page.insert_text((50, 85), "EMPRESA: Soluciones Tecnológicas Ibéricas S.L.", fontsize=10, fontname="helv")
    
    # Employee sensitive PII
    y = 120
    lines = [
        ("Nombre del Empleado:", "Laura Martínez Gómez"),
        ("DNI / Identificación Fiscal:", "12345678Z"),
        ("Número Afiliación Seguridad Social:", "NSS 28 12345678 40"),
        ("Dirección Postal:", "Calle Mayor 42, 28013 Madrid"),
        ("Correo Electrónico Corporativo:", "laura.martinez@example.test"),
        ("Teléfono de Contacto:", "+34 600 123 456"),
        ("Cuenta Bancaria (IBAN):", "ES00 0000 0000 0000 0000 0000"),
        ("Categoría Profesional:", "Ingeniera de Software Senior"),
        ("Salario Base Mensual:", "3.850,00 EUR"),
        ("Complemento de Destino:", "450,00 EUR"),
        ("Total Líquido a Percibir:", "4.300,00 EUR")
    ]
    
    for label, val in lines:
        page.insert_text((50, y), label, fontsize=10, fontname="helv", color=(0.2, 0.2, 0.2))
        page.insert_text((240, y), val, fontsize=10, fontname="helv", color=(0, 0, 0))
        y += 24
        
    page.insert_text((50, 480), "Documento de carácter estrictamente confidencial bajo normativa RGPD.", fontsize=9, fontname="helv", color=(0.4, 0.4, 0.4))
    
    # Set metadata
    doc.set_metadata({
        "author": "Laura Martínez Gómez",
        "creator": "Payroll System v2",
        "subject": "Nomina 12345678Z"
    })
    
    doc.save(str(pdf_path))
    doc.close()
    return str(pdf_path)

def generate_legal_docx():
    docx_path = FIXTURES_DIR / "sample_legal_contract.docx"
    doc = docx.Document()
    
    # Header
    section = doc.sections[0]
    header = section.header
    header.paragraphs[0].text = "ACUERDO DE CONFIDENCIALIDAD Y PRESTACIÓN DE SERVICIOS (REF: EXP-9982/2025)"
    
    # Title
    h1 = doc.add_heading("CONTRATO DE ARRENDAMIENTO DE SERVICIOS", level=1)
    
    p1 = doc.add_paragraph("En Madrid, a 15 de enero de 2026. COMPARECEN:")
    p2 = doc.add_paragraph(
        "De una parte, Don Carlos Fernández Soto, mayor de edad, con DNI 87654321B, con domicilio profesional en "
        "Paseo de la Castellana 100, 28046 Madrid, y correo carlos.fernandez@example.test, en nombre y representación de "
        "IBÉRICA CONSULTING S.A., con CIF A12345678."
    )
    p3 = doc.add_paragraph(
        "De otra parte, Doña Elena Ramos Blanco, con DNI 44556677C, en nombre de TECH SOLUTIONS SL, con CIF B98765432, "
        "con teléfono +34 654 987 321 y correo elena.ramos@example.test."
    )
    
    doc.add_heading("CLÁUSULAS", level=2)
    p4 = doc.add_paragraph(
        "PRIMERA. - Objeto del contrato: Prestación de asesoría legal en el Procedimiento Judicial nº 452/2025 "
        "ante el Juzgado de Primera Instancia nº 4 de Madrid."
    )
    p5 = doc.add_paragraph(
        "SEGUNDA. - Honorarios: Se fija un importe total de 12.500,00 EUR que será abonado mediante transferencia "
        "a la cuenta bancaria ES99 1234 5678 9012 3456 7890."
    )
    
    # Table with signatories
    table = doc.add_table(rows=1, cols=3)
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = "Representante"
    hdr_cells[1].text = "DNI"
    hdr_cells[2].text = "Email"
    
    row_cells = table.add_row().cells
    row_cells[0].text = "Carlos Fernández Soto"
    row_cells[1].text = "87654321B"
    row_cells[2].text = "carlos.fernandez@example.test"
    
    row_cells2 = table.add_row().cells
    row_cells2[0].text = "Elena Ramos Blanco"
    row_cells2[1].text = "44556677C"
    row_cells2[2].text = "elena.ramos@example.test"
    
    # Core props
    doc.core_properties.author = "Carlos Fernández Soto"
    doc.core_properties.comments = "Borrador de contrato confidencial"
    
    doc.save(str(docx_path))
    return str(docx_path)

def generate_support_pdf():
    pdf_path = FIXTURES_DIR / "sample_soporte_incident.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    
    page.insert_text((50, 60), "INFORME DE INCIDENCIA TÉCNICA Y DIAGNÓSTICO DE RED", fontsize=14, fontname="helv", color=(0.8, 0.1, 0.1))
    page.insert_text((50, 85), "DEVOPS & CYBERSECURITY OPERATIONS TICKET #8841", fontsize=10, fontname="helv")
    
    y = 120
    lines = [
        ("Ingeniero de Guardia:", "David Navarro Ruiz"),
        ("Email de Contacto:", "david.navarro@example.test"),
        ("Teléfono Urgencias:", "+34 611 223 344"),
        ("Identificador Cliente:", "CID-9942"),
        ("Dirección IP Afectada (Host 1):", "192.168.1.105"),
        ("Dirección IP Bastión Público:", "198.51.100.45"),
        ("API Token de Integración:", "purgedoc_test_token_REDACTED"),
        ("Token de Despliegue CI/CD:", "ghp_1234567890abcdefghijklmnopqrstuvwxyz"),
        ("Acceso a Base de Datos:", "Host: 10.0.4.12:5432 con usuario admin"),
        ("Diagnóstico del Incidente:", "Fuga potencial de credenciales mitigada temporalmente.")
    ]
    
    for label, val in lines:
        page.insert_text((50, y), label, fontsize=10, fontname="helv", color=(0.2, 0.2, 0.2))
        page.insert_text((230, y), val, fontsize=10, fontname="helv", color=(0, 0, 0))
        y += 24
        
    doc.set_metadata({
        "author": "David Navarro Ruiz",
        "creator": "Incident Reporter",
        "keywords": "198.51.100.45, token leak"
    })
    
    doc.save(str(pdf_path))
    doc.close()
    return str(pdf_path)

if __name__ == "__main__":
    generate_all_fixtures()
