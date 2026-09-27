import React from "react";
import { FileText, CheckCircle2, AlertTriangle, Clock, Ban } from "lucide-react";

const STATUS_STYLE = {
  verified: { icon: CheckCircle2, tone: "text-emerald-600 dark:text-emerald-400" },
  ready_to_purge: { icon: Clock, tone: "text-cyan-600 dark:text-cyan-400" },
  awaiting_review: { icon: Clock, tone: "text-amber-600 dark:text-amber-400" },
  error: { icon: AlertTriangle, tone: "text-red-600 dark:text-red-400" },
  cancelled: { icon: Ban, tone: "text-slate-400 dark:text-slate-500" }
};

/**
 * Reads real documents from the currently loaded batch (batchDetails.documents).
 * There is no cross-session history endpoint in this backend, so this list is
 * intentionally scoped to the active working batch rather than a fabricated
 * "recent sessions" feed.
 */
export const RecentActivityList = ({ documents = [], emptyLabel, title, onSelectDocument }) => {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-[#111827]/70">
      <h3 className="text-xs font-mono uppercase tracking-wider text-slate-500 dark:text-slate-400">
        {title}
      </h3>

      {documents.length === 0 ? (
        <p className="mt-3 text-sm text-slate-500 dark:text-slate-500">{emptyLabel}</p>
      ) : (
        <ul className="mt-3 divide-y divide-slate-100 dark:divide-slate-800/80">
          {documents.slice(0, 6).map((doc) => {
            const style = STATUS_STYLE[doc.status] || { icon: FileText, tone: "text-slate-400" };
            const StatusIcon = style.icon;
            return (
              <li key={doc.id}>
                <button
                  type="button"
                  onClick={() => onSelectDocument && onSelectDocument(doc.id)}
                  disabled={!onSelectDocument}
                  className="flex w-full items-center gap-3 py-2.5 text-left disabled:cursor-default"
                >
                  <StatusIcon className={`h-4 w-4 shrink-0 ${style.tone}`} />
                  <span className="min-w-0 flex-1 truncate text-sm text-slate-700 dark:text-slate-300">
                    {doc.filename}
                  </span>
                  <span className="shrink-0 rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                    {doc.status}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
};

export default RecentActivityList;
