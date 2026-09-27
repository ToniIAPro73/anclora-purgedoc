import React, { useState } from "react";
import { ChevronDown } from "lucide-react";

/**
 * Compact secondary-section panel. Purely presentational.
 *
 * Pass `collapsible` + `summary` to turn it into a single trust/disclosure
 * strip: it shows the icon, title and a one-line summary by default, and
 * only reveals `children` (the full detail) when expanded. This is how
 * security + retention information is condensed into ONE block instead of
 * several competing panels.
 */
export const SecondaryPanel = ({ icon: Icon, title, children, testId, collapsible = false, summary = null, defaultOpen = false }) => {
  const [open, setOpen] = useState(defaultOpen);

  if (collapsible) {
    return (
      <div
        data-testid={testId}
        className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-[#111827]/70"
      >
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          data-testid={testId ? `${testId}-toggle` : undefined}
          className="flex w-full items-center justify-between gap-2 text-left focus:outline-none"
        >
          <span className="flex min-w-0 items-center gap-2">
            {Icon && <Icon className="h-4 w-4 shrink-0 text-cyan-600 dark:text-cyan-400" />}
            <span className="text-xs font-mono uppercase tracking-wider text-slate-500 dark:text-slate-400">
              {title}
            </span>
          </span>
          <ChevronDown className={`h-4 w-4 shrink-0 text-slate-400 transition-transform ${open ? "rotate-180" : ""}`} />
        </button>

        {summary && (
          <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{summary}</p>
        )}

        {open && (
          <div className="mt-3 space-y-3 border-t border-slate-100 pt-3 text-xs leading-relaxed text-slate-500 dark:border-slate-800 dark:text-slate-400">
            {children}
          </div>
        )}
      </div>
    );
  }

  return (
    <div
      data-testid={testId}
      className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-[#111827]/70"
    >
      <div className="flex items-center gap-2">
        {Icon && <Icon className="h-4 w-4 text-cyan-600 dark:text-cyan-400" />}
        <h3 className="text-xs font-mono uppercase tracking-wider text-slate-500 dark:text-slate-400">
          {title}
        </h3>
      </div>
      <div className="mt-2.5 text-sm text-slate-600 dark:text-slate-300">{children}</div>
    </div>
  );
};

export default SecondaryPanel;
