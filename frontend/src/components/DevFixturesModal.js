import React from "react";
import { useApp } from "../context/AppContext";
import { X, FileText, CheckCircle2, ShieldAlert } from "lucide-react";

export const DevFixturesModal = ({ isOpen, onClose, onLoadFixture }) => {
  const { t } = useApp();

  if (!isOpen) return null;

  const fixtures = [
    {
      id: "rrhh",
      name: t("fixture_hr"),
      profile: "rrhh",
      type: "PDF",
      desc: "Nómina de ejemplo con DNI (12345678Z), email corporativo, IBAN y salario líquido."
    },
    {
      id: "legal",
      name: t("fixture_legal"),
      profile: "legal",
      type: "DOCX",
      desc: "Contrato de servicios con CIF (A12345678, B98765432), DNI de apoderados y cláusulas litigiosas."
    },
    {
      id: "soporte",
      name: t("fixture_support"),
      profile: "soporte",
      type: "PDF",
      desc: "Ticket técnico de incidente con dirección IP (198.51.100.45) y token de API (sk_live_...)."
    }
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="relative w-full max-w-lg rounded-2xl bg-[#111827] border border-slate-700 shadow-2xl p-6 text-slate-100">
        
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-cyan-950 text-cyan-400 border border-cyan-800">
              DEV / QA MODE
            </span>
            <h3 className="text-base font-semibold text-white">
              {t("dev_fixtures_title")}
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

        <p className="text-xs text-slate-400 mt-3 leading-relaxed">
          {t("dev_fixtures_desc")}
        </p>

        <div className="mt-4 space-y-3">
          {fixtures.map((f) => (
            <div
              key={f.id}
              className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 hover:border-cyan-500/50 hover:bg-slate-800/60 transition-all flex items-center justify-between gap-3 group"
            >
              <div className="flex items-start gap-3">
                <div className="p-2 rounded-lg bg-blue-950/60 text-cyan-400 border border-cyan-800/40">
                  <FileText className="w-4 h-4" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-slate-200 group-hover:text-cyan-300 transition-colors">
                      {f.name}
                    </span>
                    <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-slate-800 text-slate-400 border border-slate-700">
                      {f.type}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-1">{f.desc}</p>
                </div>
              </div>

              <button
                type="button"
                data-testid={`load-fixture-${f.id}-btn`}
                onClick={() => {
                  onLoadFixture(f.id, f.profile);
                  onClose();
                }}
                className="px-3 py-1.5 text-xs font-medium rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white shrink-0 transition-colors shadow-sm"
              >
                Cargar
              </button>
            </div>
          ))}
        </div>

        <div className="mt-5 pt-3 border-t border-slate-800 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs font-medium rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
          >
            {t("btn_cancel")}
          </button>
        </div>

      </div>
    </div>
  );
};
