import React from "react";

/**
 * Compact secondary-section panel: perfiles disponibles, seguridad/procesamiento
 * local, retencion/auto-eliminacion. Purely presentational.
 */
export const SecondaryPanel = ({ icon: Icon, title, children, testId }) => {
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
