import React, { useState } from "react";
import { useApp } from "../context/AppContext";
import {
  Check,
  X,
  Search,
  Filter,
  CheckCheck,
  Ban,
  ShieldCheck,
  ArrowRight,
  Sparkles
} from "lucide-react";

export const ReviewPanel = ({
  matches = [],
  activeMatchId,
  onSelectMatch,
  onUpdateStatus,
  onBulkUpdate,
  onTriggerPurgeModal
}) => {
  const { t } = useApp();
  const [statusFilter, setStatusFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");

  const filteredMatches = matches.filter((m) => {
    if (statusFilter !== "all" && m.status !== statusFilter) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const ent = (m.entity_type || "").toLowerCase();
      const prev = (m.text_preview || "").toLowerCase();
      return ent.includes(q) || prev.includes(q);
    }
    return true;
  });

  const totalCount = matches.length;
  const acceptedCount = matches.filter((m) => m.status === "accepted").length;
  const rejectedCount = matches.filter((m) => m.status === "rejected").length;
  const pendingCount = matches.filter((m) => m.status === "pending").length;

  return (
    <div className="flex flex-col h-full bg-[#111827] rounded-2xl border border-slate-800 overflow-hidden shadow-xl">
      
      {/* Header & Metrics */}
      <div className="p-4 border-b border-slate-800 bg-[#0E1525]">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-bold tracking-tight text-white flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-cyan-400" />
            {t("review_title")}
          </h2>
          <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-blue-950 text-cyan-300 border border-cyan-800">
            {totalCount} {t("stat_detected")}
          </span>
        </div>

        {/* Counters Badges */}
        <div className="grid grid-cols-3 gap-2 text-center text-xs">
          <div className="p-2 rounded-lg bg-emerald-950/40 border border-emerald-800/60">
            <span className="block text-[10px] text-emerald-400 font-mono uppercase">
              {t("stat_accepted")}
            </span>
            <strong className="text-sm font-bold text-emerald-200">{acceptedCount}</strong>
          </div>
          <div className="p-2 rounded-lg bg-amber-950/40 border border-amber-800/60">
            <span className="block text-[10px] text-amber-400 font-mono uppercase">
              {t("stat_pending")}
            </span>
            <strong className="text-sm font-bold text-amber-200">{pendingCount}</strong>
          </div>
          <div className="p-2 rounded-lg bg-slate-900 border border-slate-700">
            <span className="block text-[10px] text-slate-400 font-mono uppercase">
              {t("stat_rejected")}
            </span>
            <strong className="text-sm font-bold text-slate-300">{rejectedCount}</strong>
          </div>
        </div>

        {/* Search & Status Filters */}
        <div className="mt-3 flex items-center gap-2">
          <div className="relative flex-1">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
            <input
              type="text"
              data-testid="matches-search-input"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={t("search_placeholder")}
              className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg bg-slate-900 border border-slate-700 text-slate-200 focus:outline-none focus:border-cyan-500"
            />
          </div>

          <select
            data-testid="matches-filter-status"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-2 py-1.5 text-xs rounded-lg bg-slate-900 border border-slate-700 text-slate-300 focus:outline-none focus:border-cyan-500"
          >
            <option value="all">{t("filter_all")}</option>
            <option value="pending">{t("filter_pending")}</option>
            <option value="accepted">{t("filter_accepted")}</option>
            <option value="rejected">{t("filter_rejected")}</option>
          </select>
        </div>

        {/* Bulk Action Buttons */}
        <div className="mt-3 flex items-center gap-2">
          <button
            type="button"
            data-testid="accept-all-matches-btn"
            onClick={() => onBulkUpdate("accepted")}
            className="flex-1 py-1.5 px-2 text-[11px] font-medium rounded-lg bg-rose-950/60 hover:bg-rose-900/80 text-rose-300 border border-rose-800/60 transition-colors flex items-center justify-center gap-1.5"
          >
            <CheckCheck className="w-3.5 h-3.5" />
            {t("btn_accept_all")}
          </button>
          <button
            type="button"
            data-testid="reject-all-matches-btn"
            onClick={() => onBulkUpdate("rejected")}
            className="flex-1 py-1.5 px-2 text-[11px] font-medium rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-colors flex items-center justify-center gap-1.5"
          >
            <Ban className="w-3.5 h-3.5" />
            {t("btn_reject_all")}
          </button>
        </div>

      </div>

      {/* Matches List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2.5">
        {filteredMatches.length === 0 ? (
          <div className="text-center py-12 text-slate-500 text-xs">
            No se encontraron coincidencias para los filtros seleccionados.
          </div>
        ) : (
          filteredMatches.map((m) => {
            const isSelected = activeMatchId === m.id;
            const isAccepted = m.status === "accepted";
            const isRejected = m.status === "rejected";

            return (
              <div
                key={m.id}
                data-testid={`match-card-${m.id}`}
                onClick={() => onSelectMatch(m.id)}
                className={`p-3 rounded-xl border text-left cursor-pointer transition-all ${
                  isSelected
                    ? "bg-slate-800/90 border-cyan-400 shadow-[0_0_12px_rgba(56,189,248,0.2)] ring-1 ring-cyan-400"
                    : isAccepted
                    ? "bg-rose-950/20 border-rose-900/60 hover:bg-rose-950/30"
                    : isRejected
                    ? "bg-slate-900/40 border-slate-800/80 opacity-60 hover:opacity-100"
                    : "bg-slate-900/80 border-slate-800 hover:border-slate-700"
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-blue-950 text-cyan-300 border border-cyan-800/80 font-semibold">
                      {m.entity_type}
                    </span>
                    <span className="text-[10px] text-slate-400 font-mono">
                      Pág. {m.page}
                    </span>
                  </div>

                  <span className="text-[10px] font-mono text-slate-400">
                    {Math.round(m.confidence * 100)}% conf.
                  </span>
                </div>

                {/* Sanitized Context Preview */}
                <div className="my-1.5 text-xs font-mono text-slate-200 bg-black/40 px-2 py-1 rounded border border-slate-800 truncate">
                  {m.text_preview}
                </div>

                {/* Status Actions */}
                <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-800/80 text-[11px]">
                  <span className="font-mono text-[10px] text-slate-400">
                    Fuente: {m.source.join(" + ")}
                  </span>

                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      data-testid={`match-card-reject-btn-${m.id}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        onUpdateStatus(m.id, "rejected");
                      }}
                      className={`px-2 py-1 rounded transition-colors ${
                        isRejected
                          ? "bg-slate-700 text-slate-200 font-semibold"
                          : "hover:bg-slate-800 text-slate-400"
                      }`}
                      title="Rechazar / Conservar texto"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                    <button
                      type="button"
                      data-testid={`match-card-accept-btn-${m.id}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        onUpdateStatus(m.id, "accepted");
                      }}
                      className={`px-2.5 py-1 rounded transition-colors flex items-center gap-1 ${
                        isAccepted
                          ? "bg-rose-600 text-white font-semibold"
                          : "hover:bg-rose-950 text-rose-400 border border-rose-900/60"
                      }`}
                      title="Aceptar para purga física"
                    >
                      <Check className="w-3.5 h-3.5" />
                      <span>{t("btn_accept")}</span>
                    </button>
                  </div>
                </div>

              </div>
            );
          })
        )}
      </div>

      {/* Footer CTA */}
      <div className="p-4 border-t border-slate-800 bg-[#0E1525]">
        <button
          type="button"
          data-testid="trigger-purge-modal-btn"
          onClick={onTriggerPurgeModal}
          className="w-full py-3 px-4 rounded-xl font-bold text-xs uppercase tracking-wider text-white bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 shadow-[0_0_15px_rgba(56,189,248,0.25)] transition-all flex items-center justify-center gap-2"
        >
          <span>{t("btn_trigger_purge")}</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>

    </div>
  );
};
