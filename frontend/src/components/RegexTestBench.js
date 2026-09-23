import React, { useState, useEffect } from "react";
import axios from "axios";
import { useApp } from "../context/AppContext";
import { Play, CheckCircle2, AlertTriangle, Loader2, Sparkles } from "lucide-react";

export const RegexTestBench = ({
  pattern = "",
  caseSensitive = false,
  exampleValue = "",
  onSetExample,
  backendUrl,
  rule
}) => {
  const { t } = useApp();
  // Support both controlled props and direct rule object
  const initialText = exampleValue || rule?.example || "";
  const effectivePattern = pattern || rule?.pattern || "";
  const effectiveCaseSensitive = caseSensitive !== undefined ? caseSensitive : (rule?.case_sensitive || false);
  const effectiveEntityType = rule?.entity_type || "CUSTOM_SENSITIVE";

  const [testText, setTestText] = useState(initialText);
  const [testResult, setTestResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);

  useEffect(() => {
    if (exampleValue !== undefined && exampleValue !== testText) {
      setTestText(exampleValue);
    }
  }, [exampleValue, testText]);

  const handleTextChange = (e) => {
    const val = e.target.value;
    setTestText(val);
    if (onSetExample) {
      onSetExample(val);
    }
  };

  const handleRunTest = async () => {
    if (!effectivePattern || !effectivePattern.trim()) {
      setErrorMsg("Introduce una expresión regular antes de probar.");
      return;
    }
    setErrorMsg(null);
    setLoading(true);

    try {
      const payloadRule = rule || {
        id: "test_bench_rule",
        name: "Test Bench Rule",
        pattern: effectivePattern,
        case_sensitive: effectiveCaseSensitive,
        entity_type: effectiveEntityType,
        confidence: 0.95,
        priority: 50,
        profiles: ["rrhh", "legal", "soporte"],
        enabled: true
      };

      const res = await axios.post(`${backendUrl}/api/rules/test`, {
        rule: payloadRule,
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
          onChange={handleTextChange}
          placeholder={t("test_bench_input_placeholder")}
          rows={3}
          className="w-full p-2.5 rounded-lg bg-slate-950 border border-slate-700 text-slate-100 font-mono text-xs focus:outline-none focus:border-cyan-500"
        />
      </div>

      {errorMsg && (
        <div className="mt-2.5 p-2.5 rounded-lg bg-red-950/80 border border-red-800 text-red-200 text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0 text-red-400" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Run Button */}
      <div className="mt-3 flex items-center justify-between">
        <span className="text-[10px] font-mono text-slate-500">
          Timeout de seguridad: 1.0s (Protección ReDoS)
        </span>

        <button
          type="button"
          data-testid="run-test-bench-btn"
          disabled={loading || !effectivePattern}
          onClick={handleRunTest}
          className="px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-semibold text-xs flex items-center gap-1.5 shadow-sm transition-all disabled:opacity-40"
        >
          {loading ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Play className="w-3.5 h-3.5" />
          )}
          <span>{t("test_bench_btn_run")}</span>
        </button>
      </div>

      {/* Results Box */}
      {testResult && (
        <div className="mt-3 pt-3 border-t border-slate-800" data-testid="test-bench-results">
          <div className="flex items-center justify-between text-[11px] mb-2 font-mono">
            <span className="text-slate-300">
              Coincidencias: <strong className="text-white">{testResult.count}</strong>
            </span>
            <span className="text-cyan-400">
              Tiempo: <strong>{testResult.execution_time_ms} ms</strong>
            </span>
          </div>

          {testResult.matches.length > 0 ? (
            <div className="space-y-1.5 max-h-36 overflow-y-auto pr-1">
              {testResult.matches.map((m, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between p-2 rounded bg-slate-950 border border-slate-800 font-mono text-[11px]"
                >
                  <span className="text-emerald-400 bg-emerald-950/60 px-1.5 py-0.5 rounded">
                    "{m.match_text}"
                  </span>
                  <span className="text-slate-500 text-[10px]">
                    pos [{m.start}:{m.end}]
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-2.5 rounded bg-slate-950 text-slate-400 text-center italic text-[11px]">
              No se detectaron coincidencias en el texto de prueba con este patrón.
            </div>
          )}
        </div>
      )}
    </div>
  );
};
