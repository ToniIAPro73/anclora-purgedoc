import React from "react";
import { useApp } from "../context/AppContext";
import { AlertTriangle, ShieldCheck, X } from "lucide-react";

export const ConfirmationModal = ({
  isOpen,
  onClose,
  onConfirmPurge,
  acceptedCount,
  pendingCount
}) => {
  const { t } = useApp();

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="relative w-full max-w-lg rounded-2xl bg-[#111827] border border-slate-700 shadow-2xl p-6 text-slate-100">
        
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div className="flex items-center gap-2 text-amber-400">
            <AlertTriangle className="w-5 h-5 text-amber-400" />
            <h3 className="text-base font-bold text-white">
              {t("modal_title")}
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Warning Callout */}
        <div className="mt-4 p-4 rounded-xl bg-amber-950/40 border border-amber-800/80 text-amber-200 text-xs leading-relaxed">
          <p className="font-bold text-amber-300 mb-1">{t("modal_warning_title")}</p>
          <p>{t("modal_warning_desc")}</p>
        </div>

        {/* Counts summary */}
        <div className="mt-4 space-y-2 text-xs">
          <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-between">
            <span className="text-slate-300">{t("modal_items_to_purge")}</span>
            <strong className="text-sm font-bold text-rose-400 font-mono">
              {acceptedCount}
            </strong>
          </div>
          <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-between">
            <span className="text-slate-400">{t("modal_items_pending")}</span>
            <strong className="text-sm font-semibold text-slate-400 font-mono">
              {pendingCount}
            </strong>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="mt-6 pt-4 border-t border-slate-800 flex items-center justify-end gap-3">
          <button
            type="button"
            data-testid="cancel-purge-btn"
            onClick={onClose}
            className="px-4 py-2.5 text-xs font-semibold rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
          >
            {t("btn_cancel")}
          </button>

          <button
            type="button"
            data-testid="confirm-purge-btn"
            onClick={onConfirmPurge}
            className="px-5 py-2.5 text-xs font-bold rounded-xl text-white bg-gradient-to-r from-rose-600 to-red-600 hover:from-rose-500 hover:to-red-500 shadow-[0_0_15px_rgba(239,68,68,0.3)] transition-all"
          >
            {t("btn_confirm_purge")}
          </button>
        </div>

      </div>
    </div>
  );
};
