import React from "react";
import { Link, Navigate } from "react-router-dom";
import {
  Sparkles,
  ShieldCheck,
  Check,
  FileText,
  ScanText,
  FileCheck,
  Lock,
  Layers,
  FileCode2,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useApp } from "../context/AppContext";
import { BrandMark } from "./BrandMark";
import LangToggle from "./LangToggle";
import ThemeToggle from "./ThemeToggle";

export default function Landing() {
  const { user, loading } = useAuth();
  const { lang } = useApp();
  const en = lang === "en";

  // Redirect authenticated user to protected workspace
  if (!loading && user) {
    return <Navigate to="/app" replace />;
  }

  const copy = en
    ? {
        eyebrow: "ANCLORA / DETERMINISTIC DOCUMENT REDACTION",
        title: "Physical redaction and fail-closed verification for sensitive documents.",
        lead: "PurgeDoc permanently sanitizes PDF and DOCX files using local OCR, spaCy NER, and regex rules. Private processing without sending document content to external AI APIs.",
        signIn: "Sign in",
        howItWorks: "How it works",
        activate: "Have an invitation? Activate access",
        proof: "Exclusive invitation access · Zero external AI leakage · Local OCR",
        valueEyebrow: "ZERO-LEAKAGE DOCUMENT PRIVACY",
        problem: "Black rectangles are not enough: True redaction requires byte sanitization.",
        problemLead: "Visual overlays leave underlying text, metadata, and OCR layers completely intact. PurgeDoc physically removes matching coordinates and replaces text with cryptographic audit proofs.",
        benefits: [
          "Physical redaction across PDF streams and DOCX XML packages",
          "Local OCR (spa + eng) for scanned contracts and image-based PDFs",
          "spaCy NER plus customizable regular expression rulesets",
          "Fail-closed verification: blocks release if any sensitive entity remains",
          "Cryptographic audit trail with SHA-256 integrity hash (JSON, PDF, CSV)",
          "High-throughput batch processing for compliance and GDPR pipelines",
        ],
        flowEyebrow: "A DETERMINISTIC REDACTION PIPELINE",
        flowTitle: "From sensitive document to audited sanitized release.",
        flow: [
          {
            title: "Upload & OCR Inspection",
            desc: "Ingest native PDFs, scanned images, or DOCX documents with automated local deskew and OCR.",
            icon: ScanText,
          },
          {
            title: "NER Detection & Interactive Review",
            desc: "Combine spaCy models with deterministic regex rules to identify PII, DNI, IBAN, and emails.",
            icon: FileText,
          },
          {
            title: "Physical Purge & Verification",
            desc: "Perform byte-level removal followed by an automated verification pass ensuring zero leakage.",
            icon: Lock,
          },
          {
            title: "Audit Manifest & Export",
            desc: "Download verified sanitized documents accompanied by SHA-256 cryptographic audit logs.",
            icon: FileCheck,
          },
        ],
        closingEyebrow: "PROVABLE COMPLIANCE",
        closing: "Protect sensitive data with deterministic guarantees.",
        footer: "Deterministic and verified document redaction",
        terms: "Terms",
        privacy: "Privacy",
      }
    : {
        eyebrow: "ANCLORA / REDACCIÓN DOCUMENTAL DETERMINISTA",
        title: "Redacción física real y verificación fail-closed para documentos sensibles.",
        lead: "PurgeDoc higieniza permanentemente archivos PDF y DOCX mediante OCR local, spaCy y reglas regex. Procesamiento privado sin enviar el contenido documental a APIs de IA externas.",
        signIn: "Iniciar sesión",
        howItWorks: "Ver cómo funciona",
        activate: "¿Tienes invitación? Activar acceso",
        proof: "Acceso exclusivo por invitación · Sin fugas a APIs de IA · OCR local",
        valueEyebrow: "PRIVACIDAD DOCUMENTAL SIN FUGAS",
        problem: "Un recuadro negro no basta: La verdadera redacción exige sanitización a nivel de bytes.",
        problemLead: "Las superposiciones visuales dejan intactos el texto subyacente, los metadatos y las capas de OCR. PurgeDoc elimina físicamente las coordenadas coincidentes y genera certificados de auditoría con SHA-256.",
        benefits: [
          "Redacción física real en streams de PDF y paquetes XML de DOCX",
          "OCR local (spa + eng) para contratos escaneados y documentos manuscritos",
          "Detección combinada con modelos spaCy y reglas regex personalizables",
          "Verificación fail-closed: bloquea la entrega si detecta cualquier residuo sensible",
          "Trazabilidad auditable con hash SHA-256 de integridad (JSON, PDF, CSV)",
          "Procesamiento por lotes de alto rendimiento para cumplimiento RGPD",
        ],
        flowEyebrow: "UN PIPELINE DE REDACCIÓN DETERMINISTA",
        flowTitle: "Del documento sensible al archivo verificado y auditable.",
        flow: [
          {
            title: "Carga e Inspección OCR",
            desc: "Ingesta de PDFs nativos, escaneos o DOCX con corrección de inclinación y OCR local.",
            icon: ScanText,
          },
          {
            title: "Detección NER y Revisión",
            desc: "Modelos spaCy y reglas deterministas para localizar PII, DNI/NIE, cuentas bancarias y correos.",
            icon: FileText,
          },
          {
            title: "Purga Física y Verificación",
            desc: "Destrucción física de bytes y escaneo posterior exhaustivo que garantiza cero fugas residuales.",
            icon: Lock,
          },
          {
            title: "Manifiesto de Auditoría y Descarga",
            desc: "Descarga de documentos higienizados certificados con hash de integridad criptográfico SHA-256.",
            icon: FileCheck,
          },
        ],
        closingEyebrow: "CUMPLIMIENTO DEMOSTRABLE",
        closing: "Protege los datos sensibles de tu organización con garantías reales.",
        footer: "Redacción y verificación documental determinista",
        terms: "Términos",
        privacy: "Privacidad",
      };

  return (
    <main className="landing-shell">
      {/* Top Navigation */}
      <nav className="landing-nav">
        <Link to="/" className="landing-brand">
          <BrandMark className="h-9 w-9 rounded-full shadow-sm shadow-[#38BDF8]/20" />
          <span>
            Anclora <b>PurgeDoc</b>
          </span>
        </Link>
        <div className="flex items-center gap-3">
          <a href="#how" className="landing-nav-link hidden sm:inline">
            {copy.howItWorks}
          </a>
          <LangToggle />
          <ThemeToggle />
          <Link to="/login" className="landing-nav-cta">
            {copy.signIn}
          </Link>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="landing-hero">
        <div className="landing-hero-copy fade-up">
          <p className="landing-eyebrow">
            <Sparkles size={14} /> {copy.eyebrow}
          </p>
          <h1>{copy.title}</h1>
          <p className="landing-lead">{copy.lead}</p>
          <div className="landing-actions flex-wrap">
            <Link to="/login" className="landing-primary">
              {copy.signIn}
            </Link>
            <a href="#how" className="landing-text-link">
              {copy.howItWorks}
            </a>
          </div>
          <div className="mt-4">
            <Link
              to="/activate"
              className="inline-flex items-center text-xs font-semibold text-[#38BDF8] hover:underline"
            >
              <span>{copy.activate}</span>
            </Link>
          </div>
          <div className="landing-proof">
            <ShieldCheck size={17} />
            <span>{copy.proof}</span>
          </div>
        </div>

        {/* Hero Visual Card: PurgeDoc Document Redaction & Verification Preview */}
        <div className="landing-hero-visual fade-up" style={{ animationDelay: "100ms" }}>
          <div className="landing-orbit landing-orbit-one" />
          <div className="landing-orbit landing-orbit-two" />
          <div className="landing-product-card">
            <div className="landing-card-top">
              <span className="landing-live-dot" />
              <span>{en ? "FAIL-CLOSED REDACTION ENGINE" : "MOTOR DE PURGA FAIL-CLOSED"}</span>
              <span className="ml-auto text-xs text-slate-400 font-mono">SHA-256 VERIFIED</span>
            </div>

            {/* Document Redaction Mini Visual Preview */}
            <div className="landing-doc-preview mt-3">
              <div className="flex justify-between items-center text-[10px] uppercase font-bold text-slate-500 mb-2 border-b border-slate-200 dark:border-slate-700/60 pb-1.5">
                <span className="text-red-500 dark:text-red-400">{en ? "ORIGINAL ENTITY" : "DATO DETECTADO"}</span>
                <span className="text-emerald-600 dark:text-emerald-400 font-semibold">{en ? "SANITIZED BYTES" : "ESTADO PURGADO"}</span>
              </div>
              <div className="space-y-1.5 font-mono text-[11px]">
                <div className="flex justify-between items-center bg-slate-100 dark:bg-slate-800/80 p-2 rounded">
                  <span className="line-through text-slate-400 dark:text-slate-500 text-[10px]">DNI: 48123987Z (Maria Lopez)</span>
                  <span className="px-1.5 py-0.5 rounded bg-black text-white text-[10px] font-bold tracking-widest">█████████</span>
                </div>
                <div className="flex justify-between items-center bg-slate-100 dark:bg-slate-800/80 p-2 rounded">
                  <span className="line-through text-slate-400 dark:text-slate-500 text-[10px]">IBAN: ES91 2100 0418 4502</span>
                  <span className="px-1.5 py-0.5 rounded bg-black text-white text-[10px] font-bold tracking-widest">████████████</span>
                </div>
                <div className="flex justify-between items-center bg-slate-100 dark:bg-slate-800/80 p-2 rounded">
                  <span className="line-through text-slate-400 dark:text-slate-500 text-[10px]">Email: m.lopez@hospital.es</span>
                  <span className="px-1.5 py-0.5 rounded bg-black text-white text-[10px] font-bold tracking-widest">███████████████</span>
                </div>
              </div>
            </div>

            <div className="landing-confidence mt-3">
              <span>
                <i className="confidence-green" /> {en ? "Physical Byte Sanitization" : "Purga Física de Bytes"}
              </span>
              <span>
                <i className="confidence-green" /> {en ? "Fail-Closed Scan Pass" : "Pase Verificador Fail-Closed"}
              </span>
              <span>
                <i className="confidence-green" /> {en ? "SHA-256 Audit Trail" : "Auditoría SHA-256"}
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Value / Problem Section */}
      <section className="landing-section landing-value">
        <p className="landing-eyebrow">{copy.valueEyebrow}</p>
        <h2>{copy.problem}</h2>
        <p className="landing-section-lead">{copy.problemLead}</p>
        <div className="landing-benefits">
          {copy.benefits.map((item) => (
            <div key={item} className="landing-benefit">
              <span>
                <Check size={15} />
              </span>
              <p>{item}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Workflow Section */}
      <section id="how" className="landing-section landing-flow">
        <div>
          <p className="landing-eyebrow">{copy.flowEyebrow}</p>
          <h2>{copy.flowTitle}</h2>
        </div>
        <div className="landing-flow-grid">
          {copy.flow.map((item, i) => {
            const Icon = item.icon;
            return (
              <div className="landing-flow-step" key={item.title}>
                <span>0{i + 1}</span>
                <div>
                  <Icon />
                  <h3>{item.title}</h3>
                  <p>{item.desc}</p>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Closing CTA */}
      <section className="landing-closing">
        <p className="landing-eyebrow">{copy.closingEyebrow}</p>
        <h2>{copy.closing}</h2>
        <div className="flex flex-col items-center gap-3">
          <Link to="/login" className="landing-primary">
            {copy.signIn}
          </Link>
          <Link to="/activate" className="text-xs text-[#38BDF8] hover:underline font-semibold mt-2">
            {copy.activate}
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="landing-footer">
        <span>© 2026 Anclora PurgeDoc</span>
        <span>{copy.footer}</span>
        <span>
          <span className="text-slate-400">v1.0 · Private Whitelist</span>
        </span>
      </footer>
    </main>
  );
}
