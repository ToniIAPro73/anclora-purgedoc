import React from "react";

const TONE_STYLES = {
  neutral: "text-cyan-600 dark:text-cyan-400 bg-cyan-50 dark:bg-cyan-950/40 border-cyan-200 dark:border-cyan-800/60",
  success: "text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-800/60",
  warning: "text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40 border-amber-200 dark:border-amber-800/60",
  danger: "text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/40 border-red-200 dark:border-red-800/60"
};

/**
 * Small stat/metric tile for the overview row. Only render this with real,
 * already-available state — never a fabricated number.
 */
export const MetricCard = ({ icon: Icon, label, value, sublabel, tone = "neutral", testId }) => {
  const toneClass = TONE_STYLES[tone] || TONE_STYLES.neutral;

  return (
    <div
      data-testid={testId}
      className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-[#111827]/70"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[11px] font-mono uppercase tracking-wider text-slate-500 dark:text-slate-400">
            {label}
          </p>
          <p className="mt-1 truncate text-xl font-bold text-slate-900 dark:text-white">{value}</p>
          {sublabel && (
            <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-500">{sublabel}</p>
          )}
        </div>
        {Icon && (
          <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border ${toneClass}`}>
            <Icon className="h-4 w-4" />
          </div>
        )}
      </div>
    </div>
  );
};

export default MetricCard;
