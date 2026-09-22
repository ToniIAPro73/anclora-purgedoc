import React, { useRef } from "react";
import { useApp } from "../context/AppContext";
import { UploadCloud, FileText, CheckCircle, ShieldAlert, Sparkles, AlertCircle } from "lucide-react";

export const UploadScreen = ({
  selectedFile,
  setSelectedFile,
  selectedProfile,
  setSelectedProfile,
  onStartAnalysis,
  errorMessage
}) => {
  const { t } = useApp();
  const fileInputRef = useRef(null);

  const profiles = [
    {
      id: "rrhh",
      titleKey: "profile_hr_title",
      descKey: "profile_hr_desc",
      testId: "profile-select-rrhh",
      badge: "RRHH"
    },
    {
      id: "legal",
      titleKey: "profile_legal_title",
      descKey: "profile_legal_desc",
      testId: "profile-select-legal",
      badge: "LEGAL"
    },
    {
      id: "soporte",
      titleKey: "profile_support_title",
      descKey: "profile_support_desc",
      testId: "profile-select-soporte",
      badge: "DEVOPS"
    }
  ];

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      handleFileSelected(file);
    }
  };

  const handleFileSelected = (file) => {
    const ext = file.name.split(".").pop().toLowerCase();
    if (ext === "pdf" || ext === "docx") {
      setSelectedFile(file);
    } else {
      alert("Formato no soportado. Por favor sube un archivo .pdf o .docx.");
    }
  };

  return (
    <div className="max-w-4xl mx-auto py-8 px-4 sm:px-6">
      
      {/* Title & Value Proposition */}
      <div className="text-center mb-8">
        <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white dark:text-white light:text-slate-900">
          {t("upload_title")}
        </h1>
        <p className="mt-2 text-sm sm:text-base text-slate-400 max-w-2xl mx-auto">
          {t("upload_subtitle")}
        </p>
      </div>

      {/* Error Banner if any */}
      {errorMessage && (
        <div className="mb-6 p-4 rounded-xl bg-red-950/60 border border-red-800 text-red-200 text-sm flex items-start gap-3 animate-in fade-in">
          <AlertCircle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
          <div>
            <strong className="font-semibold">Error de validación:</strong> {errorMessage}
          </div>
        </div>
      )}

      {/* Upload Dropzone */}
      <div
        data-testid="upload-dropzone"
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`relative border-2 border-dashed rounded-2xl p-8 sm:p-12 text-center cursor-pointer transition-all ${
          selectedFile
            ? "border-cyan-500 bg-cyan-950/20"
            : "border-slate-700 hover:border-cyan-500/60 bg-[#111827]/70 hover:bg-[#111827]"
        }`}
      >
        <input
          type="file"
          ref={fileInputRef}
          onChange={(e) => {
            if (e.target.files && e.target.files[0]) {
              handleFileSelected(e.target.files[0]);
            }
          }}
          accept=".pdf,.docx"
          className="hidden"
          data-testid="file-input"
        />

        <div className="mx-auto w-14 h-14 rounded-full bg-blue-950/60 border border-cyan-500/30 flex items-center justify-center text-cyan-400 mb-4 shadow-[0_0_15px_rgba(56,189,248,0.15)]">
          {selectedFile ? <FileText className="w-7 h-7 text-cyan-300" /> : <UploadCloud className="w-7 h-7 text-cyan-400" />}
        </div>

        {selectedFile ? (
          <div>
            <span className="text-xs font-mono uppercase tracking-wider text-cyan-400">
              {t("selected_file")}
            </span>
            <p className="text-base sm:text-lg font-bold text-white mt-1 break-all">
              {selectedFile.name}
            </p>
            <p className="text-xs text-slate-400 mt-1">
              {(selectedFile.size / 1024).toFixed(1)} KB • {selectedFile.name.endsWith(".pdf") ? "PDF Nativo" : "DOCX OOXML"}
            </p>
          </div>
        ) : (
          <div>
            <p className="text-base font-semibold text-slate-200">
              {t("dropzone_prompt")}{" "}
              <span className="text-cyan-400 underline decoration-cyan-400/50 underline-offset-4">
                {t("dropzone_browse")}
              </span>
            </p>
            <p className="text-xs text-slate-400 mt-2">{t("dropzone_formats")}</p>
            <p className="text-xs text-slate-500 mt-1">{t("dropzone_max")}</p>
          </div>
        )}

        {/* Privacy Microcopy */}
        <div className="mt-6 pt-4 border-t border-slate-800/80 flex items-center justify-center gap-2 text-[11px] text-slate-400">
          <ShieldAlert className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>{t("dropzone_guarantee")}</span>
        </div>
      </div>

      {/* Vertical Profiles Selection */}
      <div className="mt-8">
        <label className="block text-xs font-mono uppercase tracking-wider text-cyan-400 mb-3">
          {t("select_profile_label")}
        </label>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {profiles.map((p) => {
            const isSelected = selectedProfile === p.id;
            return (
              <div
                key={p.id}
                data-testid={p.testId}
                onClick={() => setSelectedProfile(p.id)}
                className={`p-4 rounded-xl border text-left cursor-pointer transition-all ${
                  isSelected
                    ? "bg-slate-900 border-cyan-400 shadow-[0_0_15px_rgba(56,189,248,0.15)] ring-1 ring-cyan-400"
                    : "bg-[#111827]/70 border-slate-800 hover:border-slate-700 hover:bg-[#111827]"
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-800 text-cyan-300 border border-slate-700">
                    {p.badge}
                  </span>
                  {isSelected && <CheckCircle className="w-4 h-4 text-cyan-400" />}
                </div>
                <h3 className="text-sm font-semibold text-white">{t(p.titleKey)}</h3>
                <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">{t(p.descKey)}</p>
              </div>
            );
          })}
        </div>
      </div>

      {/* CTA Button */}
      <div className="mt-8 flex justify-center">
        <button
          type="button"
          data-testid="process-document-btn"
          disabled={!selectedFile}
          onClick={onStartAnalysis}
          className={`px-8 py-3.5 rounded-full font-semibold text-sm transition-all shadow-md flex items-center gap-2 ${
            selectedFile
              ? "bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 text-white shadow-[0_0_20px_rgba(56,189,248,0.3)] hover:scale-[1.01]"
              : "bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700"
          }`}
        >
          <Sparkles className="w-4 h-4" />
          <span>{t("btn_start_analysis")}</span>
        </button>
      </div>

    </div>
  );
};
