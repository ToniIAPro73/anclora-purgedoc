import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import { useApp } from "../context/AppContext";
import {
  Layers,
  UploadCloud,
  FileText,
  Play,
  ShieldCheck,
  AlertTriangle,
  X,
  Trash2,
  Ban,
  CheckCircle2,
  Download,
  FileCheck2,
  FileJson,
  Loader2,
  FileSpreadsheet,
  Filter,
  Eye,
  Activity,
  Radio
} from "lucide-react";

export const BatchQueueScreen = ({
  backendUrl,
  sessionId,
  batchId,
  batchDetails,
  onRefreshBatch,
  onSelectDocumentForReview,
  customRules,
  onOpenRulesEditor
}) => {
  const { t } = useApp();
  const fileInputRef = useRef(null);
  const eventSourceRef = useRef(null);
  const lastSequenceRef = useRef(0);
  const fallbackIntervalRef = useRef(null);

  const [filterStatus, setFilterStatus] = useState("all");
  const [isUploading, setIsUploading] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isPurging, setIsPurging] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);

  // SSE Stream State
  const [streamConnected, setStreamConnected] = useState(false);
  const [documentPhases, setDocumentPhases] = useState({}); // docId -> phase string
  const [activeWorkers, setActiveWorkers] = useState(0);

  const limits = batchDetails?.limits || {
    max_documents: 10,
    max_file_size_mb: 25,
    max_total_size_mb: 100,
    max_concurrent: 2,
    current_documents_count: 0
  };

  const documents = batchDetails?.documents || [];
  const batch = batchDetails?.batch || {};

  // Compute metrics
  const totalDocs = documents.length;
  const verifiedDocs = documents.filter((d) => d.status === "verified").length;
  const errorDocs = documents.filter((d) => d.status === "error" || d.status === "verification_failed").length;
  const inReviewDocs = documents.filter((d) => d.status === "awaiting_review" || d.status === "ready_to_purge").length;
  const readyToPurgeDocs = documents.filter((d) => {
    if (d.status !== "awaiting_review" && d.status !== "ready_to_purge") return false;
    return d.pending_count === 0;
  });

  // -------------------------------------------------------------
  // SSE Real-Time Progress Stream with Monotonic Sequence & Last-Event-ID
  // -------------------------------------------------------------
  useEffect(() => {
    if (!batchId) return;

    let isSubscribed = true;

    function connectSSE() {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }

      const sseUrl = `${backendUrl}/api/batches/${batchId}/events?last_event_id=${lastSequenceRef.current}`;
      const es = new EventSource(sseUrl);
      eventSourceRef.current = es;

      es.onopen = () => {
        if (!isSubscribed) return;
        setStreamConnected(true);
        // Clear polling fallback while SSE is healthy
        if (fallbackIntervalRef.current) {
          clearInterval(fallbackIntervalRef.current);
          fallbackIntervalRef.current = null;
        }
      };

      es.onerror = () => {
        if (!isSubscribed) return;
        setStreamConnected(false);
        // Setup moderate snapshot fallback polling if disconnected
        if (!fallbackIntervalRef.current) {
          fallbackIntervalRef.current = setInterval(() => {
            onRefreshBatch();
          }, 3500);
        }
      };

      // Handler for typed events
      const handleEvent = (event) => {
        if (!isSubscribed) return;
        try {
          const parsed = JSON.parse(event.data);
          const seq = parsed.sequence || 0;
          if (seq > 0 && seq <= lastSequenceRef.current) {
            // Ignore duplicate or older event
            return;
          }
          if (seq > 0) {
            lastSequenceRef.current = seq;
          }

          const docId = parsed.documentId;
          const phase = parsed.phase;
          const workers = parsed.payload?.activeWorkers;

          if (workers !== undefined) {
            setActiveWorkers(workers);
          }

          if (docId && phase) {
            setDocumentPhases((prev) => ({
              ...prev,
              [docId]: phase
            }));
          }

          // Trigger lightweight state snapshot refresh on major transitions
          const transitionTypes = [
            "document_status_changed",
            "document_awaiting_review",
            "document_verified",
            "document_verification_failed",
            "document_error",
            "document_cancelled",
            "batch_status_changed",
            "batch_completed"
          ];
          if (transitionTypes.includes(parsed.type)) {
            onRefreshBatch();
          }
        } catch (e) {
          console.error("Error processing SSE event:", e);
        }
      };

      es.addEventListener("document_status_changed", handleEvent);
      es.addEventListener("document_awaiting_review", handleEvent);
      es.addEventListener("document_verified", handleEvent);
      es.addEventListener("document_verification_failed", handleEvent);
      es.addEventListener("document_error", handleEvent);
      es.addEventListener("document_cancelled", handleEvent);
      es.addEventListener("batch_status_changed", handleEvent);
      es.addEventListener("batch_completed", handleEvent);
      es.addEventListener("stream_connected", handleEvent);
    }

    connectSSE();

    return () => {
      isSubscribed = false;
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      if (fallbackIntervalRef.current) {
        clearInterval(fallbackIntervalRef.current);
        fallbackIntervalRef.current = null;
      }
    };
  }, [batchId, backendUrl]);

  // Handle Drag & Drop / File Selection
  const handleFilesAdded = async (files) => {
    if (!files || files.length === 0 || !batchId) return;
    setErrorMessage(null);
    setIsUploading(true);

    try {
      const formData = new FormData();
      for (let i = 0; i < files.length; i++) {
        formData.append("files", files[i]);
      }

      await axios.post(`${backendUrl}/api/batches/${batchId}/documents`, formData, {
        headers: { "Content-Type": "multipart/form-data" }
      });
      await onRefreshBatch();
    } catch (err) {
      console.error("Error uploading to batch:", err);
      setErrorMessage(err.response?.data?.detail || "Error al subir archivos a la cola.");
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  // Remove single document before analysis
  const handleRemoveDoc = async (docId) => {
    try {
      await axios.delete(`${backendUrl}/api/batches/${batchId}/documents/${docId}`);
      await onRefreshBatch();
    } catch (err) {
      console.error("Error removing document:", err);
    }
  };

  // Cancel single document
  const handleCancelDoc = async (docId) => {
    try {
      await axios.post(`${backendUrl}/api/batches/${batchId}/documents/${docId}/cancel`);
      await onRefreshBatch();
    } catch (err) {
      console.error("Error cancelling document:", err);
    }
  };

  // Update single document profile
  const handleProfileChange = async (docId, profileId) => {
    try {
      await axios.patch(`${backendUrl}/api/batches/${batchId}/documents/${docId}/profile`, {
        profile_id: profileId
      });
      await onRefreshBatch();
    } catch (err) {
      console.error("Error updating profile:", err);
    }
  };

  // Start Batch Analysis with Controlled Concurrency
  const handleStartAnalysis = async () => {
    if (!batchId) return;
    setErrorMessage(null);
    setIsAnalyzing(true);

    try {
      await axios.post(`${backendUrl}/api/batches/${batchId}/analyze`, {
        custom_rules: customRules,
        ruleset_id: "batch_custom_ruleset",
        ruleset_version: "1.0.0"
      });
      await onRefreshBatch();
    } catch (err) {
      console.error("Error analyzing batch:", err);
      setErrorMessage(err.response?.data?.detail || "Error al analizar la cola de documentos.");
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Start Batch Purge for ready documents
  const handleStartBatchPurge = async () => {
    if (!batchId || readyToPurgeDocs.length === 0) return;
    setErrorMessage(null);
    setIsPurging(true);

    try {
      const readyDocIds = readyToPurgeDocs.map((d) => d.id);
      await axios.post(`${backendUrl}/api/batches/${batchId}/purge`, {
        document_ids: readyDocIds
      });
      await onRefreshBatch();
    } catch (err) {
      console.error("Error purging batch:", err);
      setErrorMessage(err.response?.data?.detail || "Error al ejecutar la purga del lote.");
    } finally {
      setIsPurging(false);
    }
  };

  // Cancel entire batch
  const handleCancelBatch = async () => {
    if (!batchId) return;
    try {
      await axios.post(`${backendUrl}/api/batches/${batchId}/cancel`);
      await onRefreshBatch();
    } catch (err) {
      console.error("Error cancelling batch:", err);
    }
  };

  // Filtered documents
  const filteredDocs = documents.filter((d) => {
    if (filterStatus === "review") return d.status === "awaiting_review" || d.status === "ready_to_purge";
    if (filterStatus === "ready") return (d.status === "awaiting_review" || d.status === "ready_to_purge") && d.pending_count === 0;
    if (filterStatus === "verified") return d.status === "verified";
    if (filterStatus === "errors") return d.status === "error" || d.status === "verification_failed";
    return true;
  });

  const getPhaseDisplay = (doc) => {
    const livePhase = documentPhases[doc.id];
    if (livePhase) {
      switch (livePhase) {
        case "validating":
          return "Validando formato";
        case "extracting":
        case "extracting_pdf_content":
          return "Extrayendo texto";
        case "ocr_extraction":
          return "OCR Tesseract";
        case "deskew_normalization":
          return "Deskew OpenCV";
        case "ner_detection":
          return "NER Local spaCy";
        case "purging":
          return "Redacción física real";
        case "verifying":
          return "Verificación fail-closed";
        case "generating_audit":
          return "Certificado criptográfico";
        default:
          return livePhase;
      }
    }
    return null;
  };

  const getStatusBadge = (doc) => {
    const status = doc.status;
    const phase = getPhaseDisplay(doc);

    switch (status) {
      case "queued":
        return <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-slate-300">En cola</span>;
      case "validating":
      case "analyzing":
        return (
          <div className="flex flex-col gap-0.5">
            <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-blue-950 text-cyan-300 border border-cyan-800 flex items-center gap-1">
              <Loader2 className="w-2.5 h-2.5 animate-spin" /> Analizando
            </span>
            {phase && <span className="text-[9px] font-mono text-cyan-400/80">{phase}</span>}
          </div>
        );
      case "awaiting_review":
        return <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-amber-950 text-amber-300 border border-amber-800">Revisión requerida</span>;
      case "purging":
      case "verifying":
        return (
          <div className="flex flex-col gap-0.5">
            <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-purple-950 text-purple-300 border border-purple-800 flex items-center gap-1">
              <Loader2 className="w-2.5 h-2.5 animate-spin" /> Purgando
            </span>
            {phase && <span className="text-[9px] font-mono text-purple-400/80">{phase}</span>}
          </div>
        );
      case "verified":
        return <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-950 text-emerald-300 border border-emerald-800 flex items-center gap-1"><CheckCircle2 className="w-2.5 h-2.5 text-emerald-400" /> Verificado</span>;
      case "verification_failed":
      case "error":
        return <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-rose-950 text-rose-300 border border-rose-800 flex items-center gap-1"><AlertTriangle className="w-2.5 h-2.5 text-rose-400" /> Fallido</span>;
      case "cancelled":
        return <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-900 text-slate-400 border border-slate-800">Cancelado</span>;
      default:
        return <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-slate-300">{status}</span>;
    }
  };

  return (
    <div className="max-w-6xl mx-auto py-6 px-4 sm:px-6 space-y-6">
      
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2.5 flex-wrap">
            <h1 className="text-2xl font-extrabold text-white tracking-tight flex items-center gap-2.5">
              <Layers className="w-6 h-6 text-cyan-400" />
              {t("batch_title")}
            </h1>
            
            {/* Live SSE Status Pill */}
            <span
              data-testid="sse-status-badge"
              className={`text-[11px] font-mono px-2 py-0.5 rounded-full flex items-center gap-1.5 border transition-all ${
                streamConnected
                  ? "bg-emerald-950 text-emerald-400 border-emerald-800"
                  : "bg-amber-950 text-amber-400 border-amber-800"
              }`}
            >
              <Radio className={`w-3 h-3 ${streamConnected ? "text-emerald-400 animate-pulse" : "text-amber-400"}`} />
              <span>{streamConnected ? t("batch_live_stream_connected") : t("batch_live_stream_reconnecting")}</span>
            </span>

            {/* Workers Count Badge */}
            <span
              data-testid="batch-workers-badge"
              className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-cyan-950 text-cyan-300 border border-cyan-800"
            >
              Workers: {activeWorkers} / {limits.max_concurrent} máx
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">{t("batch_subtitle")}</p>
        </div>

        {/* Global Batch Controls */}
        <div className="flex items-center gap-2 flex-wrap">
          {batch.status === "completed_verified" || batch.status === "completed_with_errors" ? (
            <>
              <a
                href={`${backendUrl}/api/batches/${batchId}/download-zip`}
                data-testid="batch-download-zip-btn"
                download
                className="px-3.5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold flex items-center gap-1.5 shadow-sm transition-all"
              >
                <Download className="w-3.5 h-3.5" />
                <span>{t("batch_btn_download_zip")}</span>
              </a>

              <a
                href={`${backendUrl}/api/batches/${batchId}/audit.pdf`}
                data-testid="batch-audit-pdf-btn"
                download
                className="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 flex items-center gap-1.5 transition-colors"
              >
                <FileCheck2 className="w-3.5 h-3.5 text-cyan-400" />
                <span>{t("batch_btn_audit_pdf")}</span>
              </a>

              <a
                href={`${backendUrl}/api/batches/${batchId}/audit.json`}
                data-testid="batch-audit-json-btn"
                download
                className="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 flex items-center gap-1.5 transition-colors"
              >
                <FileJson className="w-3.5 h-3.5 text-cyan-400" />
                <span>{t("batch_btn_audit_json")}</span>
              </a>
              <a
                href={`${backendUrl}/api/batches/${batchId}/audit.csv`}
                data-testid="batch-audit-csv-btn"
                download
                className="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 flex items-center gap-1.5 transition-colors"
              >
                <FileSpreadsheet className="w-3.5 h-3.5 text-cyan-400" />
                <span>{t("batch_btn_audit_csv")}</span>
              </a>
            </>
          ) : null}

          {documents.some((d) => d.status === "queued" || d.status === "error") && (
            <button
              type="button"
              data-testid="start-batch-analysis-btn"
              disabled={isAnalyzing}
              onClick={handleStartAnalysis}
              className="px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-bold flex items-center gap-1.5 shadow-sm transition-all disabled:opacity-50"
            >
              {isAnalyzing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
              <span>{t("batch_btn_analyze_all")}</span>
            </button>
          )}

          {readyToPurgeDocs.length > 0 && (
            <button
              type="button"
              data-testid="batch-purge-ready-btn"
              disabled={isPurging}
              onClick={handleStartBatchPurge}
              className="px-4 py-2 rounded-lg bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 text-white text-xs font-bold flex items-center gap-1.5 shadow-md transition-all disabled:opacity-50"
            >
              {isPurging ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ShieldCheck className="w-3.5 h-3.5" />}
              <span>{t("batch_btn_purge_ready")} ({readyToPurgeDocs.length})</span>
            </button>
          )}

          {batch.status !== "cancelled" && batch.status !== "completed_verified" && (
            <button
              type="button"
              data-testid="cancel-batch-btn"
              onClick={handleCancelBatch}
              className="px-3 py-2 rounded-lg bg-slate-800 hover:bg-rose-950 text-slate-400 hover:text-rose-300 text-xs font-medium border border-slate-700 hover:border-rose-800 transition-colors"
              title="Cancelar Lote"
            >
              <Ban className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Error message */}
      {errorMessage && (
        <div className="p-3.5 rounded-xl bg-red-950/70 border border-red-800 text-red-200 text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Metrics Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
        <div className="p-3 rounded-xl bg-[#111827] border border-slate-800">
          <span className="text-[10px] font-mono text-slate-500 uppercase block mb-1">
            {t("batch_stat_total")}
          </span>
          <span className="text-base font-bold text-white">
            {totalDocs} <span className="text-xs font-normal text-slate-500">/ {limits.max_documents} máx</span>
          </span>
        </div>

        <div className="p-3 rounded-xl bg-emerald-950/30 border border-emerald-900/60">
          <span className="text-[10px] font-mono text-emerald-400 uppercase block mb-1">
            {t("batch_stat_verified")}
          </span>
          <span className="text-base font-bold text-emerald-300">{verifiedDocs}</span>
        </div>

        <div className="p-3 rounded-xl bg-amber-950/30 border border-amber-900/60">
          <span className="text-[10px] font-mono text-amber-400 uppercase block mb-1">
            {t("batch_stat_review")}
          </span>
          <span className="text-base font-bold text-amber-300">{inReviewDocs}</span>
        </div>

        <div className="p-3 rounded-xl bg-slate-900 border border-slate-800">
          <span className="text-[10px] font-mono text-slate-400 uppercase block mb-1">
            {t("batch_stat_errors")}
          </span>
          <span className="text-base font-bold text-slate-300">{errorDocs}</span>
        </div>
      </div>

      {/* Drag & Drop Multi-Upload Zone */}
      {batch.status !== "completed_verified" && (
        <div
          data-testid="batch-dropzone"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            if (e.dataTransfer.files) handleFilesAdded(e.dataTransfer.files);
          }}
          onClick={() => fileInputRef.current?.click()}
          className="border-2 border-dashed border-slate-700 hover:border-cyan-500/60 rounded-2xl p-6 text-center cursor-pointer bg-[#111827]/70 hover:bg-[#111827] transition-all"
        >
          <input
            type="file"
            ref={fileInputRef}
            multiple
            accept=".pdf,.docx"
            onChange={(e) => {
              if (e.target.files) handleFilesAdded(e.target.files);
            }}
            className="hidden"
            data-testid="batch-file-input"
          />

          <div className="w-10 h-10 mx-auto rounded-full bg-blue-950/60 border border-cyan-500/30 flex items-center justify-center text-cyan-400 mb-2">
            {isUploading ? <Loader2 className="w-5 h-5 animate-spin" /> : <UploadCloud className="w-5 h-5" />}
          </div>
          <p className="text-sm font-semibold text-slate-200">
            {t("batch_dropzone_prompt")}
          </p>
          <p className="text-[11px] text-slate-500 mt-1">
            {t("batch_dropzone_limits")
              .replace("{maxDocs}", limits.max_documents)
              .replace("{maxFileMb}", limits.max_file_size_mb)
              .replace("{maxTotalMb}", limits.max_total_size_mb)}
          </p>
        </div>
      )}

      {/* Filters & Queue Table */}
      <div className="bg-[#111827] rounded-2xl border border-slate-800 overflow-hidden shadow-xl">
        <div className="p-3.5 border-b border-slate-800 bg-[#0E1525] flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-white uppercase font-mono">Cola de Documentos</span>
            <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400">
              {filteredDocs.length} visibles
            </span>
          </div>

          <div className="flex items-center gap-2 text-xs">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <select
              data-testid="batch-filter-status"
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="px-2.5 py-1 rounded-lg bg-slate-900 border border-slate-700 text-slate-300 focus:outline-none focus:border-cyan-500"
            >
              <option value="all">{t("batch_filter_all")}</option>
              <option value="review">{t("batch_filter_review")}</option>
              <option value="ready">{t("batch_filter_ready")}</option>
              <option value="verified">{t("batch_filter_verified")}</option>
              <option value="errors">{t("batch_filter_errors")}</option>
            </select>
          </div>
        </div>

        {/* Documents Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-[#0B0F19] text-[11px] uppercase font-mono text-slate-400 border-b border-slate-800">
              <tr>
                <th className="py-2.5 px-4">{t("batch_col_doc")}</th>
                <th className="py-2.5 px-3">{t("batch_col_type")}</th>
                <th className="py-2.5 px-3">{t("batch_col_profile")}</th>
                <th className="py-2.5 px-3">{t("batch_col_status")}</th>
                <th className="py-2.5 px-3">{t("batch_col_matches")}</th>
                <th className="py-2.5 px-4 text-right">{t("batch_col_actions")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/80 font-sans">
              {filteredDocs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-slate-500 italic text-xs">
                    No hay documentos en la cola con los criterios seleccionados.
                  </td>
                </tr>
              ) : (
                filteredDocs.map((doc) => {
                  const isPdf = doc.mime_type === "application/pdf";
                  return (
                    <tr
                      key={doc.id}
                      data-testid={`batch-doc-row-${doc.id}`}
                      className="hover:bg-slate-900/50 transition-colors"
                    >
                      {/* Filename & size */}
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <FileText className={`w-4 h-4 shrink-0 ${isPdf ? "text-cyan-400" : "text-blue-400"}`} />
                          <div className="min-w-0">
                            <span className="font-semibold text-white block truncate max-w-[220px]" title={doc.filename}>
                              {doc.filename}
                            </span>
                            <span className="text-[10px] text-slate-500 font-mono">
                              {(doc.size_bytes / 1024).toFixed(1)} KB
                            </span>
                          </div>
                        </div>
                      </td>

                      {/* Type */}
                      <td className="py-3 px-3">
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                          {isPdf ? "PDF" : "DOCX"}
                        </span>
                      </td>

                      {/* Profile Override */}
                      <td className="py-3 px-3">
                        {doc.status === "queued" || doc.status === "awaiting_review" ? (
                          <select
                            data-testid={`doc-profile-select-${doc.id}`}
                            value={doc.profile_id}
                            onChange={(e) => handleProfileChange(doc.id, e.target.value)}
                            className="text-[11px] py-1 px-1.5 rounded bg-slate-900 border border-slate-700 text-cyan-300 font-mono"
                          >
                            <option value="rrhh">RRHH</option>
                            <option value="legal">Legal</option>
                            <option value="soporte">DevOps</option>
                          </select>
                        ) : (
                          <span className="text-[11px] font-mono text-cyan-300 uppercase">
                            {doc.profile_id}
                          </span>
                        )}
                      </td>

                      {/* Status & Live Phase */}
                      <td className="py-3 px-3">
                        {getStatusBadge(doc)}
                      </td>

                      {/* Matches breakdown */}
                      <td className="py-3 px-3">
                        {doc.matches_count !== undefined && doc.matches_count > 0 ? (
                          <div className="text-[11px] font-mono space-x-1.5">
                            <span className="text-white font-bold">{doc.matches_count}</span>
                            <span className="text-emerald-400">({doc.accepted_count}✓</span>
                            <span className="text-slate-400">{doc.rejected_count}✗</span>
                            <span className="text-amber-400">{doc.pending_count}?)</span>
                          </div>
                        ) : (
                          <span className="text-[11px] text-slate-500 font-mono">-</span>
                        )}
                      </td>

                      {/* Actions */}
                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          {/* Review Button */}
                          {(doc.status === "awaiting_review" || doc.status === "ready_to_purge" || doc.status === "verified") && (
                            <button
                              type="button"
                              data-testid={`review-doc-btn-${doc.id}`}
                              onClick={() => onSelectDocumentForReview(doc.id)}
                              className="px-2.5 py-1 text-[11px] font-semibold rounded bg-cyan-950 hover:bg-cyan-900 text-cyan-300 border border-cyan-800/80 flex items-center gap-1 transition-colors"
                              title={t("batch_action_review")}
                            >
                              <Eye className="w-3 h-3" />
                              <span>{t("batch_action_review")}</span>
                            </button>
                          )}

                          {/* Cancel Button */}
                          {doc.status !== "verified" && doc.status !== "cancelled" && (
                            <button
                              type="button"
                              data-testid={`cancel-doc-btn-${doc.id}`}
                              onClick={() => handleCancelDoc(doc.id)}
                              className="p-1 rounded hover:bg-slate-800 text-slate-500 hover:text-amber-400"
                              title={t("batch_action_cancel")}
                            >
                              <Ban className="w-3.5 h-3.5" />
                            </button>
                          )}

                          {/* Remove from queue button */}
                          {doc.status === "queued" && (
                            <button
                              type="button"
                              data-testid={`remove-doc-btn-${doc.id}`}
                              onClick={() => handleRemoveDoc(doc.id)}
                              className="p-1 rounded hover:bg-red-950 text-slate-500 hover:text-rose-400"
                              title={t("batch_action_remove")}
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  );
};
