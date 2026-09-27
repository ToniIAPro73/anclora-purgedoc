import React from "react";

/**
 * Compact quick-action card. Wires directly to an existing handler/state
 * transition passed in by the caller (PurgedocMainApp) — never reimplements
 * business logic itself.
 */
export const QuickActionCard = ({ icon: Icon, title, description, onClick, testId, badge, active = false }) => {
  return (
    <button
      type="button"
      data-testid={testId}
      onClick={onClick}
      className={`group flex items-start gap-3 rounded-xl border p-3.5 text-left transition-all ${
        active
          ? "border-cyan-400 bg-cyan-50 dark:border-cyan-500/60 dark:bg-cyan-950/30"
          : "border-slate-200 bg-white hover:border-cyan-300 hover:bg-slate-50 dark:border-slate-800 dark:bg-[#111827]/70 dark:hover:border-cyan-500/40 dark:hover:bg-[#111827]"
      }`}
    >
      {Icon && (
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-cyan-200 bg-cyan-50 text-cyan-600 dark:border-cyan-500/30 dark:bg-blue-950/60 dark:text-cyan-400">
          <Icon className="h-4 w-4" />
        </div>
      )}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-slate-900 dark:text-white">{title}</h3>
          {badge != null && badge > 0 && (
            <span className="rounded-full bg-cyan-500 px-1.5 py-0.2 text-[10px] font-mono font-bold text-slate-950">
              {badge}
            </span>
          )}
        </div>
        <p className="mt-0.5 text-xs leading-relaxed text-slate-500 dark:text-slate-400">{description}</p>
      </div>
    </button>
  );
};

export default QuickActionCard;
