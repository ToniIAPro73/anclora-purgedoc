import React, { useState } from "react";
import axios from "axios";
import { useApp } from "../context/AppContext";
import { Play, CheckCircle2, AlertTriangle, Loader2, Sparkles } from "lucide-react";

export const RegexTestBench = ({ rule, backendUrl }) => {
  const { t } = useApp();
  const [testText, setTestText] = useState(rule.example || "");
  const [testResult, setTestResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);

  const handleRunTest = async () => {
    if (!rule.pattern || !rule.pattern.trim()) {
      setErrorMsg("Introduce una expresión regular antes de probar.");
      return;
    }
    setErrorMsg(null);
    setLoading(true);

    try {
      const res = await axios.post(`${backendUrl}/api/rules/test`, {
        rule: rule,
        test_text: testText
      });
      setTestResult(res.data);
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || "Error al ejecutar test bench.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mt-4 p-4 rounded-xl bg-slate-900/90 border border-slate-800 text-xs text-slate-200 animate-in fade-in">
      <div className="flex items-center justify-between mb-2">
        <h4 className="font-bold text-slate-200 flex items-center gap-1.5">
          <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
          {t("test_bench_title")}
        </h4>
        <span className="text-[10px] font-mono text-cyan-400 px-2 py-0.5 rounded bg-blue-950 border border-cyan-800">
          RE2 Sandbox
        </span>
      </div>

      <p className="text-[11px] text-slate-400 mb-3">
        {t("test_bench_subtitle")}
      </p>

      {/* Input */}
      <div>
        <label className="block text-[10px] uppercase font-mono text-slate-400 mb-1">
          {t("test_bench_input_label")}
        </label>
        <textarea
          data-testid="test-bench-input"
          value={testText}
          onChange={(e) => setTestText(e.target.value)}
          placeholder={t("test_bench_input_placeholder")}
          rows={3}
          className="w-full p-2.5 rounded-lg bg-slate-950 border border-slate-700 text-slate-100 font-mono text-xs focus:outline-none focus:border-cyan-500"
        />
      </div>

      {errorMsg && (
        <div className="mt-2 p-2 rounded bg-red-950/60 border border-red-800 text-red-200 text-[11px] flex items-center gap-2">
          <AlertTriangle className="w-3.5 h-3.5 text-red-400 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Action CTA */}
      <div className="mt-3 flex items-center justify-between">
        <button
          type="button"
          data-testid="run-test-bench-btn"
          disabled={loading}
          onClick={handleRunTest}
          className="px-3.5 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-semibold flex items-center gap-1.5 transition-colors shadow-sm disabled:opacity-50"
        >
          {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
          <span>{t("btn_run_test")}</span>
        </button>

        {testResult && (
          <span className="text-[11px] font-mono text-slate-400">
            {testResult.count} {t("test_bench_matches_count")} {testResult.execution_time_ms} ms
          </span>
        )}
      </div>

      {/* Results view */}
      {testResult && (
        <div className="mt-3 pt-3 border-t border-slate-800" data-testid="test-bench-results">
          {testResult.error ? (
            <div className="text-red-400 flex items-center gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
              <span>{testResult.error}</span>
            </div>
          ) : testResult.count === 0 ? (
            <p className="text-slate-400 italic">{t("test_bench_no_matches")}</p>
          ) : (
            <div className="space-y-1.5">
              {testResult.matches.map((m, idx) => (
                <div
                  key={idx}
                  className="p-2 rounded bg-black/40 border border-slate-800 flex items-center justify-between text-[11px] font-mono"
                >
                  <span className="text-cyan-300 font-bold bg-cyan-950/60 px-1.5 py-0.5 rounded">
                    "{m.match_text}"
                  </span>
                  <div className="flex items-center gap-2 text-slate-400 text-[10px]">
                    <span>Pos: {m.start}–{m.end}</span>
                    <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
                      {m.entity_type}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
