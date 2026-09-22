import React from "react";
import { useApp } from "../context/AppContext";
import {
  ShieldCheck,
  AlertOctagon,
  Download,
  FileCheck2,
  FileJson,
  RotateCcw,
  Fingerprint
} from "lucide-react";

export const ResultsScreen = ({
  purgeResult,
  documentMeta,
  backendUrl,
  onRestart
}) => {
  const { t } = useApp();

  const isVerified = purgeResult?.verification_passed === true;
  const docId = documentMeta?.id;

  const downloadPurgedUrl = `${backendUrl}/api/documents/${docId}/download`;
  const downloadAuditJsonUrl = `${backendUrl}/api/documents/${docId}/audit.json`;
  const downloadAuditPdfUrl = `${backendUrl}/api/documents/${docId}/audit.pdf`;

  return (
    <div className="max-w-3xl mx-auto py-10 px-4 sm:px-6">
      
      {/* Verification Status Banner */}
      {isVerified ? (
        <div
          data-testid="purge-result-verified-badge"
          className="p-6 rounded-2xl bg-emerald-950/40 border border-emerald-600 text-center shadow-[0_0_25px_rgba(16,185,129,0.15)] animate-in fade-in"
        >
          <div className="w-14 h-14 mx-auto rounded-full bg-emerald-900/60 border border-emerald-500 flex items-center justify-center text-emerald-400 mb-3 shadow-[0_0_15px_rgba(16,185,129,0.3)]">
            <ShieldCheck className="w-8 h-8 text-emerald-400" />
          </div>
          <h2 className="text-xl font-bold text-white tracking-tight">
            {t("result_verified_title")}
          </h2>
          <p className="text-xs sm:text-sm text-emerald-200/90 mt-2 max-w-xl mx-auto leading-relaxed">
            {t("result_verified_desc")}
          </p>
        </div>
      ) : (
        <div
          data-testid="purge-result-fail-closed-alert"
          className="p-6 rounded-2xl bg-red-950/60 border border-red-600 text-center shadow-[0_0_25px_rgba(239,68,68,0.2)] animate-in fade-in"
        >
          <div className="w-14 h-14 mx-auto rounded-full bg-red-900/60 border border-red-500 flex items-center justify-center text-red-400 mb-3">
            <AlertOctagon className="w-8 h-8 text-red-400" />
          </div>
          <h2 className="text-xl font-bold text-white tracking-tight">
            {t("result_failed_title")}
          </h2>
          <p className="text-xs sm:text-sm text-red-200/90 mt-2 max-w-xl mx-auto leading-relaxed">
            {t("result_failed_desc")}
          </p>
          {purgeResult?.failures && (
            <div className="mt-4 p-3 bg-black/40 rounded-xl text-left font-mono text-xs text-red-300">
              {purgeResult.failures.map((f, i) => (
                <div key={i}>• {f}</div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Forensic Audit Fingerprints */}
      <div className="mt-6 p-5 rounded-2xl bg-[#111827] border border-slate-800 text-xs">
        <h3 className="font-bold text-slate-200 flex items-center gap-2 mb-3">
          <Fingerprint className="w-4 h-4 text-cyan-400" />
          {t("summary_metrics")}
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-slate-300 font-mono">
          <div className="p-3 rounded-xl bg-slate-900 border border-slate-800">
            <span className="text-[10px] text-slate-500 uppercase block mb-1">
              {t("source_hash")}
            </span>
            <span className="text-[11px] text-cyan-300 break-all">
              {documentMeta?.source_sha256}
            </span>
          </div>

          <div className="p-3 rounded-xl bg-slate-900 border border-slate-800">
            <span className="text-[10px] text-slate-500 uppercase block mb-1">
              {t("output_hash")}
            </span>
            <span className="text-[11px] text-emerald-400 break-all">
              {purgeResult?.output_sha256 || "N/A (Bloqueado)"}
            </span>
          </div>
        </div>

        <div className="mt-3 flex items-center justify-between p-3 rounded-xl bg-slate-900/60 border border-slate-800 text-slate-400 text-[11px]">
          <span>{t("audit_id_label")}</span>
          <strong className="text-slate-200 font-mono">{purgeResult?.audit_id}</strong>
        </div>
      </div>

      {/* Download Actions */}
      <div className="mt-8 space-y-3">
        {isVerified && (
          <a
            href={downloadPurgedUrl}
            data-testid="download-purged-doc-btn"
            download
            className="w-full py-3.5 px-6 rounded-xl font-bold text-sm text-white bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 shadow-[0_0_20px_rgba(56,189,248,0.25)] transition-all flex items-center justify-center gap-2"
          >
            <Download className="w-4 h-4" />
            <span>{t("btn_download_doc")}</span>
          </a>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <a
            href={downloadAuditPdfUrl}
            data-testid="download-audit-pdf-btn"
            download
            className="py-3 px-4 rounded-xl font-semibold text-xs text-cyan-300 bg-slate-900 hover:bg-slate-800 border border-cyan-800/60 transition-colors flex items-center justify-center gap-2"
          >
            <FileCheck2 className="w-4 h-4 text-cyan-400" />
            <span>{t("btn_download_audit_pdf")}</span>
          </a>

          <a
            href={downloadAuditJsonUrl}
            data-testid="download-audit-json-btn"
            download
            className="py-3 px-4 rounded-xl font-semibold text-xs text-slate-300 bg-slate-900 hover:bg-slate-800 border border-slate-700 transition-colors flex items-center justify-center gap-2"
          >
            <FileJson className="w-4 h-4 text-slate-400" />
            <span>{t("btn_download_audit_json")}</span>
          </a>
        </div>
      </div>

      {/* Restart CTA */}
      <div className="mt-8 text-center">
        <button
          type="button"
          onClick={onRestart}
          className="inline-flex items-center gap-2 text-xs font-semibold text-slate-400 hover:text-white transition-colors"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          <span>{t("btn_restart")}</span>
        </button>
      </div>

    </div>
  );
};
