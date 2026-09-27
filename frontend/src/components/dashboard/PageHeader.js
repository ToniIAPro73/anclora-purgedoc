import React from "react";
import { ShieldCheck, Lock } from "lucide-react";

/**
 * Compact page header for the authenticated dashboard workspace.
 * Title + a small privacy/security status strip + optional compact primary actions.
 * Intentionally NOT a hero: no oversized type, no full-width CTA.
 */
export const PageHeader = ({ title, subtitle, statusLabels = [], actions = null }) => {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0">
        <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
          {title}
        </h1>
        {subtitle && (
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">{subtitle}</p>
        )}

        {statusLabels.length > 0 && (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {statusLabels.map((label, idx) => (
              <span
                key={idx}
                className="inline-flex items-center gap-1.5 rounded-full border border-emerald-300 bg-emerald-50 px-2.5 py-1 text-[11px] font-medium text-emerald-700 dark:border-emerald-800/80 dark:bg-emerald-950/50 dark:text-emerald-300"
              >
                {idx === 0 ? (
                  <Lock className="h-3 w-3 shrink-0" />
                ) : (
                  <ShieldCheck className="h-3 w-3 shrink-0" />
                )}
                {label}
              </span>
            ))}
          </div>
        )}
      </div>

      {actions && (
        <div className="flex shrink-0 items-center gap-2">{actions}</div>
      )}
    </div>
  );
};

export default PageHeader;
