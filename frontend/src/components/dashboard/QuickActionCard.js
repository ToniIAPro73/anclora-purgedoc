import React from "react";
import { ArrowRight } from "lucide-react";

/**
 * Quick-action card. Wires directly to an existing handler/state transition
 * passed in by the caller (PurgedocMainApp) — never reimplements business
 * logic itself.
 *
 * variant="secondary" (default): today's compact, low-emphasis tile — for
 *   actions that must stay clearly subordinate to the primary action.
 * variant="primary": the single dominant call-to-action on the dashboard
 *   (e.g. "New document"). Larger, solid gradient, unmistakable at a glance.
 */
export const QuickActionCard = ({ icon: Icon, title, description, onClick, testId, badge, active = false, variant = "secondary" }) => {
  if (variant === "primary") {
    return (
      <button
        type="button"
        data-testid={testId}
        onClick={onClick}
        className="group flex w-full items-center gap-4 rounded-2xl border border-transparent bg-gradient-to-r from-blue-600 to-cyan-500 p-5 sm:p-6 text-left shadow-lg shadow-cyan-500/20 transition-all hover:shadow-xl hover:shadow-cyan-500/30 hover:brightness-105 focus:outline-none focus:ring-2 focus:ring-cyan-300 focus:ring-offset-2 dark:focus:ring-offset-[#0B0F19]"
      >
        {Icon && (
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-white/15 text-white ring-1 ring-white/25">
            <Icon className="h-6 w-6" />
          </div>
        )}
        <div className="min-w-0 flex-1">
          <h3 className="text-base sm:text-lg font-bold text-white">{title}</h3>
          <p className="mt-0.5 text-xs sm:text-sm leading-relaxed text-cyan-50/90">{description}</p>
        </div>
        <ArrowRight className="h-5 w-5 shrink-0 text-white/80 transition-transform group-hover:translate-x-0.5" />
      </button>
    );
  }

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
