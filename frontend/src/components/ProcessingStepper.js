import React from "react";
import { useApp } from "../context/AppContext";
import { Loader2, CheckCircle2 } from "lucide-react";

export const ProcessingStepper = ({ activeStage = 1, isPurging = false }) => {
  const { t } = useApp();

  const analysisStages = [
    t("stage_1"),
    t("stage_2"),
    t("stage_3"),
    t("stage_4")
  ];

  const purgeStages = [
    t("purge_stage_1"),
    t("purge_stage_2"),
    t("purge_stage_3"),
    t("purge_stage_4"),
    t("purge_stage_5")
  ];

  const stages = isPurging ? purgeStages : analysisStages;
  const title = isPurging ? t("purging_title") : t("stepper_title");

  return (
    <div className="max-w-2xl mx-auto py-16 px-4">
      <div className="rounded-2xl bg-[#111827] border border-slate-800 p-8 shadow-2xl text-center">
        
        <div className="inline-flex p-3 rounded-full bg-blue-950/80 border border-cyan-500/40 text-cyan-400 mb-6 shadow-[0_0_15px_rgba(56,189,248,0.2)]">
          <Loader2 className="w-8 h-8 animate-spin text-cyan-400" />
        </div>

        <h2 className="text-xl font-bold text-white mb-2">{title}</h2>
        <p className="text-xs text-slate-400 mb-8 font-mono">
          {t("privacy_badge")}
        </p>

        {/* Real Stages List */}
        <div className="space-y-4 text-left max-w-lg mx-auto" data-testid="stepper-stage-indicator">
          {stages.map((stg, idx) => {
            const stepNum = idx + 1;
            const isCompleted = stepNum < activeStage;
            const isCurrent = stepNum === activeStage;

            return (
              <div
                key={idx}
                className={`p-3 rounded-xl border flex items-center gap-3 transition-all ${
                  isCompleted
                    ? "bg-emerald-950/30 border-emerald-800/60 text-emerald-300"
                    : isCurrent
                    ? "bg-cyan-950/40 border-cyan-500 text-cyan-200 shadow-[0_0_10px_rgba(56,189,248,0.15)] ring-1 ring-cyan-500"
                    : "bg-slate-900/40 border-slate-800 text-slate-500"
                }`}
              >
                {isCompleted ? (
                  <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
                ) : isCurrent ? (
                  <Loader2 className="w-5 h-5 text-cyan-400 animate-spin shrink-0" />
                ) : (
                  <div className="w-5 h-5 rounded-full border border-slate-700 flex items-center justify-center text-[10px] text-slate-500 font-mono shrink-0">
                    {stepNum}
                  </div>
                )}
                <span className="text-xs sm:text-sm font-medium">{stg}</span>
              </div>
            );
          })}
        </div>

      </div>
    </div>
  );
};
