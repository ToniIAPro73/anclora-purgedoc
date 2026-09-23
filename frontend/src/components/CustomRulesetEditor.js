import React, { useState, useEffect } from "react";
import axios from "axios";
import { useApp } from "../context/AppContext";
import { RegexTestBench } from "./RegexTestBench";
import {
  Sliders,
  Plus,
  Trash2,
  Copy,
  Edit2,
  Download,
  Upload,
  CheckCircle,
  XCircle,
  AlertTriangle,
  X,
  FileCode2,
  Check,
  RotateCcw,
  Lock,
  Unlock,
  KeyRound,
  ShieldCheck,
  Eye,
  EyeOff,
  FileSpreadsheet
} from "lucide-react";

export const CustomRulesetEditor = ({
  isOpen,
  onClose,
  backendUrl,
  customRules,
  setCustomRules
}) => {
  const { t } = useApp();

  const [activeTab, setActiveTab] = useState("list"); // 'list' | 'edit' | 'clone_base'
  const [editingRule, setEditingRule] = useState(null);
  const [filterProfile, setFilterProfile] = useState("all");
  const [filterStatus, setFilterStatus] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [baseProfiles, setBaseProfiles] = useState([]);
  const [deleteConfirmId, setDeleteConfirmId] = useState(null);
  const [saveValidationMsg, setSaveValidationMsg] = useState(null);

  // Encrypted Modal States
  const [isExportEncryptedOpen, setIsExportEncryptedOpen] = useState(false);
  const [isImportEncryptedOpen, setIsImportEncryptedOpen] = useState(false);

  // Export Encrypted Form
  const [exportPassword, setExportPassword] = useState("");
  const [exportConfirmPassword, setExportConfirmPassword] = useState("");
  const [showExportPassword, setShowExportPassword] = useState(false);
  const [exportRulesetName, setExportRulesetName] = useState("Anclora Custom Ruleset");
  const [exportError, setExportError] = useState(null);
  const [isExporting, setIsExporting] = useState(false);

  // Import Encrypted Form
  const [importEnvelope, setImportEnvelope] = useState(null);
  const [importPassword, setImportPassword] = useState("");
  const [showImportPassword, setShowImportPassword] = useState(false);
  const [importPreviewData, setImportPreviewData] = useState(null);
  const [importConflictStrategy, setImportConflictStrategy] = useState("copy"); // 'copy' | 'replace' | 'skip'
  const [importError, setImportError] = useState(null);
  const [isDecrypting, setIsDecrypting] = useState(false);

  // Fetch base profiles for cloning
  useEffect(() => {
    if (isOpen) {
      axios.get(`${backendUrl}/api/profiles`).then((res) => {
        setBaseProfiles(res.data);
      }).catch(console.error);
    }
  }, [isOpen, backendUrl]);

  // Clean state when closing modal to guarantee zero password persistence
  const handleCloseEditor = () => {
    setExportPassword("");
    setExportConfirmPassword("");
    setImportPassword("");
    setImportEnvelope(null);
    setImportPreviewData(null);
    setIsExportEncryptedOpen(false);
    setIsImportEncryptedOpen(false);
    onClose();
  };

  if (!isOpen) return null;

  // New blank rule template
  const handleNewRule = () => {
    setEditingRule({
      id: `rule_${Math.random().toString(36).substr(2, 8)}`,
      name: "",
      description: "",
      entity_type: "CUSTOM_SENSITIVE",
      pattern: "",
      case_sensitive: false,
      confidence: 0.95,
      priority: 50,
      profiles: ["rrhh", "legal", "soporte"],
      enabled: true,
      example: ""
    });
    setSaveValidationMsg(null);
    setActiveTab("edit");
  };

  // Duplicate rule
  const handleDuplicateRule = (rule) => {
    const duplicated = {
      ...rule,
      id: `rule_${Math.random().toString(36).substr(2, 8)}`,
      name: `${rule.name} (Copia)`,
      created_at: Date.now(),
      updated_at: Date.now()
    };
    const updated = [...customRules, duplicated];
    setCustomRules(updated);
    localStorage.setItem("anclora_custom_rules", JSON.stringify(updated));
  };

  // Toggle active/inactive
  const handleToggleEnabled = (ruleId) => {
    const updated = customRules.map((r) =>
      r.id === ruleId ? { ...r, enabled: !r.enabled, updated_at: Date.now() } : r
    );
    setCustomRules(updated);
    localStorage.setItem("anclora_custom_rules", JSON.stringify(updated));
  };

  // Delete rule
  const handleDeleteRule = (ruleId) => {
    const updated = customRules.filter((r) => r.id !== ruleId);
    setCustomRules(updated);
    localStorage.setItem("anclora_custom_rules", JSON.stringify(updated));
    setDeleteConfirmId(null);
  };

  // Save edited rule
  const handleSaveRule = async () => {
    setSaveValidationMsg(null);

    if (!editingRule.name.trim()) {
      setSaveValidationMsg({ type: "error", message: "El nombre de la regla es obligatorio." });
      return;
    }
    if (!editingRule.pattern.trim()) {
      setSaveValidationMsg({ type: "error", message: "El patrón Regex es obligatorio." });
      return;
    }

    try {
      const res = await axios.post(`${backendUrl}/api/rules/validate`, {
        pattern: editingRule.pattern,
        case_sensitive: editingRule.case_sensitive
      });

      if (!res.data.valid) {
        setSaveValidationMsg({ type: "error", message: res.data.error || "Patrón regex inválido o inseguro." });
        return;
      }

      const existingIndex = customRules.findIndex((r) => r.id === editingRule.id);
      let updated;
      if (existingIndex >= 0) {
        updated = [...customRules];
        updated[existingIndex] = { ...editingRule, updated_at: Date.now() };
      } else {
        updated = [...customRules, { ...editingRule, created_at: Date.now(), updated_at: Date.now() }];
      }

      setCustomRules(updated);
      localStorage.setItem("anclora_custom_rules", JSON.stringify(updated));
      setSaveValidationMsg({ type: "success", message: "Regla guardada correctamente." });

      setTimeout(() => {
        setActiveTab("list");
        setEditingRule(null);
        setSaveValidationMsg(null);
      }, 700);
    } catch (err) {
      setSaveValidationMsg({
        type: "error",
        message: err.response?.data?.detail?.error || "Error al validar la regla en el servidor."
      });
    }
  };

  // Export JSON (Plaintext warning)
  const handleExportJSON = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(customRules, null, 2));
    const dlAnchor = document.createElement("a");
    dlAnchor.setAttribute("href", dataStr);
    dlAnchor.setAttribute("download", `anclora-custom-rules-${Date.now()}.json`);
    dlAnchor.click();
  };

  // Import JSON
  const handleImportJSON = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (event) => {
        try {
          const imported = JSON.parse(event.target.result);
          if (Array.isArray(imported)) {
            const merged = [...customRules];
            imported.forEach((newRule) => {
              if (newRule.id && newRule.name && newRule.pattern) {
                const idx = merged.findIndex((r) => r.id === newRule.id);
                if (idx >= 0) {
                  merged[idx] = newRule;
                } else {
                  merged.push(newRule);
                }
              }
            });
            setCustomRules(merged);
            localStorage.setItem("anclora_custom_rules", JSON.stringify(merged));
            alert("Reglas importadas correctamente.");
          } else {
            alert("El archivo importado no contiene una lista de reglas válida.");
          }
        } catch (err) {
          alert("Error al leer el archivo JSON.");
        }
      };
      reader.readAsText(file);
    }
  };

  // -------------------------------------------------------------
  // Encrypted Profile Export (.aprules)
  // -------------------------------------------------------------
  const calculatePasswordStrength = (pass) => {
    if (!pass) return { score: 0, label: "Vacía", color: "bg-slate-700" };
    let score = 0;
    if (pass.length >= 8) score += 1;
    if (pass.length >= 12) score += 1;
    if (/[A-Z]/.test(pass) && /[a-z]/.test(pass)) score += 1;
    if (/[0-9]/.test(pass)) score += 1;
    if (/[^A-Za-z0-9]/.test(pass)) score += 1;

    if (score <= 1) return { score: 1, label: "Débil", color: "bg-rose-600" };
    if (score <= 3) return { score: 2, label: "Media", color: "bg-amber-500" };
    return { score: 3, label: "Fuerte", color: "bg-emerald-500" };
  };

  const handleExecuteEncryptedExport = async () => {
    setExportError(null);
    if (!exportPassword) {
      setExportError(t("password_too_short_error"));
      return;
    }
    if (exportPassword.length < 8) {
      setExportError(t("password_too_short_error"));
      return;
    }
    if (exportPassword !== exportConfirmPassword) {
      setExportError(t("password_mismatch_error"));
      return;
    }

    setIsExporting(true);
    try {
      const payload = {
        ruleset: {
          ruleset_id: "custom_export",
          version: "1.0.0",
          rules: customRules
        },
        password: exportPassword,
        ruleset_name: exportRulesetName,
        description: "Anclora Purgedoc Encrypted Profile"
      };

      const res = await axios.post(`${backendUrl}/api/rules/export-encrypted`, payload);
      const envelope = res.data;

      // Trigger safe download with pseudonymized name
      const shortId = Math.random().toString(36).substring(2, 8);
      const dataStr = "data:application/json;charset=utf-8," + encodeURIComponent(JSON.stringify(envelope, null, 2));
      const dlAnchor = document.createElement("a");
      dlAnchor.setAttribute("href", dataStr);
      dlAnchor.setAttribute("download", `anclora-purgedoc-ruleset-${shortId}.aprules`);
      dlAnchor.click();

      // Clean password from state immediately
      setExportPassword("");
      setExportConfirmPassword("");
      setIsExportEncryptedOpen(false);
    } catch (err) {
      console.error("Encrypted export error:", err);
      setExportError(err.response?.data?.detail?.detail || "Error al exportar archivo cifrado.");
    } finally {
      setIsExporting(false);
    }
  };

  // -------------------------------------------------------------
  // Encrypted Profile Import (.aprules)
  // -------------------------------------------------------------
  const handleSelectAprulesFile = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImportError(null);
    setImportPreviewData(null);

    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const parsed = JSON.parse(event.target.result);
        if (parsed.format !== "anclora-purgedoc-ruleset") {
          setImportError("El archivo seleccionado no tiene el formato válido de Anclora Purgedoc (.aprules).");
          return;
        }
        setImportEnvelope(parsed);
      } catch (err) {
        setImportError("Error al analizar el archivo .aprules (JSON corrupto o inválido).");
      }
    };
    reader.readAsText(file);
  };

  const handleDecryptAndPreview = async () => {
    if (!importEnvelope || !importPassword) {
      setImportError("Introduce la contraseña para descifrar el ruleset.");
      return;
    }
    setImportError(null);
    setIsDecrypting(true);

    try {
      const payload = {
        envelope: importEnvelope,
        password: importPassword,
        current_rules: customRules
      };

      const res = await axios.post(`${backendUrl}/api/rules/preview-encrypted`, payload);
      setImportPreviewData(res.data);
    } catch (err) {
      console.error("Decrypt error:", err);
      const detail = err.response?.data?.detail?.detail || "Contraseña incorrecta o archivo .aprules manipulado.";
      setImportError(detail);
    } finally {
      setIsDecrypting(false);
    }
  };

  const handleCommitImport = () => {
    if (!importPreviewData || !importPreviewData.rules) return;

    let merged = [...customRules];
    const incomingRules = importPreviewData.rules;

    incomingRules.forEach((newRule) => {
      const existingIdx = merged.findIndex((r) => r.id === newRule.id || r.name === newRule.name);
      if (existingIdx >= 0) {
        if (importConflictStrategy === "replace") {
          merged[existingIdx] = { ...newRule, updated_at: Date.now() };
        } else if (importConflictStrategy === "copy") {
          merged.push({
            ...newRule,
            id: `rule_${Math.random().toString(36).substring(2, 8)}`,
            name: `${newRule.name} (Importada)`,
            created_at: Date.now(),
            updated_at: Date.now()
          });
        }
        // 'skip': do nothing
      } else {
        merged.push(newRule);
      }
    });

    setCustomRules(merged);
    localStorage.setItem("anclora_custom_rules", JSON.stringify(merged));

    // Clear password state
    setImportPassword("");
    setImportEnvelope(null);
    setImportPreviewData(null);
    setIsImportEncryptedOpen(false);
  };

  // Filtered list
  const filteredRules = customRules.filter((r) => {
    if (filterStatus === "active" && !r.enabled) return false;
    if (filterStatus === "disabled" && r.enabled) return false;
    if (filterProfile !== "all" && !r.profiles.includes(filterProfile)) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return r.name.toLowerCase().includes(q) || r.entity_type.toLowerCase().includes(q) || r.pattern.includes(q);
    }
    return true;
  });

  const pwdStrength = calculatePasswordStrength(exportPassword);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md animate-in fade-in duration-150">
      <div className="relative w-full max-w-4xl rounded-2xl bg-[#0F172A] border border-slate-700 shadow-2xl p-6 text-slate-100 flex flex-col max-h-[90vh]">
        
        {/* Top Header */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-800 shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-blue-950 border border-cyan-500/40 flex items-center justify-center text-cyan-400">
              <Sliders className="w-4 h-4 text-cyan-400" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white">{t("rules_title")}</h2>
              <p className="text-xs text-slate-400">{t("rules_subtitle")}</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              data-testid="close-rules-editor-btn"
              onClick={handleCloseEditor}
              className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Action Bar (List View) */}
        {activeTab === "list" && (
          <div className="py-3 flex flex-wrap items-center justify-between gap-3 border-b border-slate-800/80 shrink-0">
            <div className="flex items-center gap-2">
              <button
                type="button"
                data-testid="create-rule-btn"
                onClick={handleNewRule}
                className="px-3 py-1.5 rounded-lg bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 text-white font-semibold text-xs flex items-center gap-1.5 shadow-sm transition-all"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>{t("btn_new_rule")}</span>
              </button>

              <button
                type="button"
                data-testid="clone-base-rule-tab-btn"
                onClick={() => setActiveTab("clone_base")}
                className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 flex items-center gap-1.5 transition-colors"
              >
                <FileCode2 className="w-3.5 h-3.5 text-cyan-400" />
                <span>{t("btn_clone_base")}</span>
              </button>
            </div>

            <div className="flex items-center gap-2 flex-wrap">
              {/* Encrypted Export (.aprules) */}
              <button
                type="button"
                data-testid="export-encrypted-rules-btn"
                disabled={customRules.length === 0}
                onClick={() => {
                  setExportPassword("");
                  setExportConfirmPassword("");
                  setExportError(null);
                  setIsExportEncryptedOpen(true);
                }}
                className="px-2.5 py-1.5 rounded-lg bg-cyan-950 hover:bg-cyan-900 text-cyan-300 border border-cyan-800/80 text-xs font-semibold flex items-center gap-1.5 transition-colors disabled:opacity-40"
              >
                <Lock className="w-3.5 h-3.5" />
                <span>{t("btn_export_encrypted")}</span>
              </button>

              {/* Encrypted Import (.aprules) */}
              <button
                type="button"
                data-testid="import-encrypted-rules-btn"
                onClick={() => {
                  setImportPassword("");
                  setImportEnvelope(null);
                  setImportPreviewData(null);
                  setImportError(null);
                  setIsImportEncryptedOpen(true);
                }}
                className="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-medium flex items-center gap-1.5 transition-colors"
              >
                <Unlock className="w-3.5 h-3.5 text-cyan-400" />
                <span>{t("btn_import_encrypted")}</span>
              </button>

              {/* Plaintext JSON Fallbacks */}
              <label
                data-testid="import-rules-label"
                className="px-2.5 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-400 text-xs font-medium border border-slate-800 flex items-center gap-1 cursor-pointer transition-colors"
                title="Importar JSON plano (sin cifrar)"
              >
                <Upload className="w-3 h-3" />
                <span>JSON</span>
                <input
                  type="file"
                  accept=".json"
                  onChange={handleImportJSON}
                  className="hidden"
                />
              </label>

              <button
                type="button"
                data-testid="export-rules-btn"
                disabled={customRules.length === 0}
                onClick={handleExportJSON}
                className="px-2.5 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-400 text-xs font-medium border border-slate-800 flex items-center gap-1 transition-colors disabled:opacity-40"
                title="Exportar JSON plano (sin cifrar)"
              >
                <Download className="w-3 h-3" />
                <span>JSON</span>
              </button>
            </div>
          </div>
        )}

        {/* MAIN BODY CONTENT */}
        <div className="flex-1 overflow-y-auto py-3">
          
          {/* TAB 1: RULES LIST */}
          {activeTab === "list" && (
            <div>
              {/* Filter Row */}
              <div className="flex flex-wrap items-center gap-2 mb-4">
                <input
                  type="text"
                  placeholder="Buscar regla por nombre, patrón o categoría..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="flex-1 min-w-[200px] px-3 py-1.5 text-xs rounded-lg bg-slate-900 border border-slate-700 text-slate-200 focus:outline-none focus:border-cyan-500"
                />

                <select
                  value={filterProfile}
                  onChange={(e) => setFilterProfile(e.target.value)}
                  className="px-2.5 py-1.5 text-xs rounded-lg bg-slate-900 border border-slate-700 text-slate-300"
                >
                  <option value="all">Todos los perfiles</option>
                  <option value="rrhh">RRHH</option>
                  <option value="legal">Legal</option>
                  <option value="soporte">Soporte Técnico</option>
                </select>

                <select
                  value={filterStatus}
                  onChange={(e) => setFilterStatus(e.target.value)}
                  className="px-2.5 py-1.5 text-xs rounded-lg bg-slate-900 border border-slate-700 text-slate-300"
                >
                  <option value="all">Todos los estados</option>
                  <option value="active">Activas</option>
                  <option value="disabled">Inactivas</option>
                </select>
              </div>

              {/* Rules List */}
              {filteredRules.length === 0 ? (
                <div className="text-center py-12 px-4 rounded-xl border border-dashed border-slate-800 bg-slate-900/40">
                  <Sliders className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                  <p className="text-xs text-slate-400">{t("rules_empty")}</p>
                </div>
              ) : (
                <div className="space-y-2.5">
                  {filteredRules.map((rule) => (
                    <div
                      key={rule.id}
                      data-testid={`custom-rule-card-${rule.id}`}
                      className={`p-3.5 rounded-xl border transition-all ${
                        rule.enabled
                          ? "bg-slate-900/80 border-slate-800 hover:border-slate-700"
                          : "bg-slate-950/40 border-slate-900 opacity-60"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-bold text-xs text-white truncate">{rule.name}</span>
                            <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-blue-950 text-cyan-300 border border-cyan-800/60">
                              {rule.entity_type}
                            </span>
                            <span className="text-[10px] text-slate-400 font-mono">
                              P: {rule.priority}
                            </span>
                          </div>

                          <div className="mt-1.5 font-mono text-[11px] text-emerald-400 bg-slate-950 px-2.5 py-1 rounded border border-slate-800/80 inline-block max-w-full truncate">
                            {rule.pattern}
                          </div>

                          {rule.description && (
                            <p className="text-[11px] text-slate-400 mt-1">{rule.description}</p>
                          )}

                          <div className="flex items-center gap-1.5 mt-2 flex-wrap">
                            {rule.profiles.map((p) => (
                              <span key={p} className="text-[9px] uppercase px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 font-mono">
                                {p}
                              </span>
                            ))}
                          </div>
                        </div>

                        {/* Actions */}
                        <div className="flex items-center gap-1 shrink-0">
                          <button
                            type="button"
                            data-testid={`toggle-rule-status-${rule.id}`}
                            onClick={() => handleToggleEnabled(rule.id)}
                            className={`px-2 py-1 text-[11px] rounded font-semibold transition-colors ${
                              rule.enabled
                                ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                                : "bg-slate-800 text-slate-400 border border-slate-700"
                            }`}
                          >
                            {rule.enabled ? t("rule_status_active") : t("rule_status_disabled")}
                          </button>

                          <button
                            type="button"
                            data-testid={`edit-rule-btn-${rule.id}`}
                            onClick={() => {
                              setEditingRule({ ...rule });
                              setSaveValidationMsg(null);
                              setActiveTab("edit");
                            }}
                            className="p-1.5 rounded hover:bg-slate-800 text-slate-300 hover:text-white"
                            title={t("btn_edit")}
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>

                          <button
                            type="button"
                            data-testid={`duplicate-rule-btn-${rule.id}`}
                            onClick={() => handleDuplicateRule(rule)}
                            className="p-1.5 rounded hover:bg-slate-800 text-slate-300 hover:text-white"
                            title={t("btn_duplicate")}
                          >
                            <Copy className="w-3.5 h-3.5" />
                          </button>

                          <button
                            type="button"
                            data-testid={`delete-rule-btn-${rule.id}`}
                            onClick={() => setDeleteConfirmId(rule.id)}
                            className="p-1.5 rounded hover:bg-red-950/60 text-red-400"
                            title={t("btn_delete")}
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>

                      {/* Delete confirmation inline */}
                      {deleteConfirmId === rule.id && (
                        <div className="mt-3 p-3 rounded-lg bg-red-950/80 border border-red-800 text-xs flex items-center justify-between gap-3 animate-in fade-in">
                          <span className="text-red-200">{t("delete_confirm_desc")}</span>
                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              onClick={() => setDeleteConfirmId(null)}
                              className="px-2.5 py-1 text-xs rounded bg-slate-800 text-slate-300"
                            >
                              Cancelar
                            </button>
                            <button
                              type="button"
                              data-testid={`confirm-delete-rule-btn-${rule.id}`}
                              onClick={() => handleDeleteRule(rule.id)}
                              className="px-2.5 py-1 text-xs rounded bg-red-600 hover:bg-red-500 text-white font-bold"
                            >
                              Confirmar Eliminación
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* TAB 2: EDIT / CREATE RULE */}
          {activeTab === "edit" && editingRule && (
            <div className="space-y-4">
              <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                <span className="text-xs font-bold uppercase font-mono text-cyan-400">
                  {editingRule.id.startsWith("rule_") ? "Configurar Regla" : "Nueva Regla"}
                </span>
                <button
                  type="button"
                  onClick={() => {
                    setActiveTab("list");
                    setEditingRule(null);
                  }}
                  className="text-xs text-slate-400 hover:text-white"
                >
                  Volver al listado
                </button>
              </div>

              {saveValidationMsg && (
                <div
                  className={`p-3 rounded-lg text-xs flex items-center gap-2 ${
                    saveValidationMsg.type === "error"
                      ? "bg-red-950/80 border border-red-800 text-red-200"
                      : "bg-emerald-950/80 border border-emerald-800 text-emerald-200"
                  }`}
                >
                  {saveValidationMsg.type === "error" ? (
                    <AlertTriangle className="w-4 h-4 shrink-0 text-red-400" />
                  ) : (
                    <CheckCircle className="w-4 h-4 shrink-0 text-emerald-400" />
                  )}
                  <span>{saveValidationMsg.message}</span>
                </div>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    {t("rule_name")} *
                  </label>
                  <input
                    type="text"
                    data-testid="rule-name-input"
                    value={editingRule.name}
                    onChange={(e) => setEditingRule({ ...editingRule, name: e.target.value })}
                    placeholder="Ej. Código Proyecto Confidencial"
                    className="w-full px-3 py-2 text-xs rounded-lg bg-slate-900 border border-slate-700 text-slate-200 focus:outline-none focus:border-cyan-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    {t("rule_entity_type")} *
                  </label>
                  <input
                    type="text"
                    data-testid="rule-entity-input"
                    value={editingRule.entity_type}
                    onChange={(e) =>
                      setEditingRule({ ...editingRule, entity_type: e.target.value.toUpperCase().replace(/\s+/g, "_") })
                    }
                    placeholder="Ej. PROJECT_ID"
                    className="w-full px-3 py-2 text-xs rounded-lg bg-slate-900 border border-slate-700 text-slate-200 font-mono focus:outline-none focus:border-cyan-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  {t("rule_pattern")} (Safe RE2/PCRE) *
                </label>
                <input
                  type="text"
                  data-testid="rule-pattern-input"
                  value={editingRule.pattern}
                  onChange={(e) => setEditingRule({ ...editingRule, pattern: e.target.value })}
                  placeholder="Ej. PRJ-[A-Z0-9]{4,8}"
                  className="w-full px-3 py-2 text-xs rounded-lg bg-slate-900 border border-slate-700 text-emerald-400 font-mono focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="flex items-center gap-2 pt-4">
                  <input
                    type="checkbox"
                    id="case_sensitive_check"
                    checked={editingRule.case_sensitive}
                    onChange={(e) => setEditingRule({ ...editingRule, case_sensitive: e.target.checked })}
                    className="rounded bg-slate-900 border-slate-700 text-cyan-500"
                  />
                  <label htmlFor="case_sensitive_check" className="text-xs text-slate-300 cursor-pointer">
                    {t("rule_case_sensitive")}
                  </label>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    {t("rule_priority")} (1-100)
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="100"
                    value={editingRule.priority}
                    onChange={(e) => setEditingRule({ ...editingRule, priority: parseInt(e.target.value) || 10 })}
                    className="w-full px-3 py-1.5 text-xs rounded-lg bg-slate-900 border border-slate-700 text-slate-200"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    Perfiles Activos
                  </label>
                  <div className="flex items-center gap-2 pt-1 text-xs">
                    {["rrhh", "legal", "soporte"].map((p) => {
                      const isChecked = editingRule.profiles.includes(p);
                      return (
                        <label key={p} className="flex items-center gap-1 cursor-pointer text-[11px] text-slate-300">
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => {
                              const newProfiles = isChecked
                                ? editingRule.profiles.filter((x) => x !== p)
                                : [...editingRule.profiles, p];
                              setEditingRule({ ...editingRule, profiles: newProfiles });
                            }}
                          />
                          <span className="uppercase font-mono">{p}</span>
                        </label>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* Interactive Regex Test Bench Component */}
              <div className="mt-4 pt-3 border-t border-slate-800">
                <RegexTestBench
                  backendUrl={backendUrl}
                  pattern={editingRule.pattern}
                  caseSensitive={editingRule.case_sensitive}
                  exampleValue={editingRule.example}
                  onSetExample={(val) => setEditingRule({ ...editingRule, example: val })}
                />
              </div>

              {/* Save Bar */}
              <div className="flex items-center justify-end gap-2 pt-4 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => {
                    setActiveTab("list");
                    setEditingRule(null);
                  }}
                  className="px-3 py-1.5 text-xs rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700"
                >
                  Cancelar
                </button>

                <button
                  type="button"
                  data-testid="save-custom-rule-btn"
                  onClick={handleSaveRule}
                  className="px-4 py-2 text-xs rounded-lg bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 text-white font-bold shadow-md transition-all flex items-center gap-1.5"
                >
                  <Check className="w-3.5 h-3.5" />
                  <span>{t("btn_save_rule")}</span>
                </button>
              </div>
            </div>
          )}

          {/* TAB 3: CLONE FROM BASE PROFILE */}
          {activeTab === "clone_base" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                <span className="text-xs font-bold uppercase font-mono text-cyan-400">
                  Clonar Reglas desde Perfiles de Fábrica
                </span>
                <button
                  type="button"
                  onClick={() => setActiveTab("list")}
                  className="text-xs text-slate-400 hover:text-white"
                >
                  Volver al listado
                </button>
              </div>

              <div className="space-y-3">
                {baseProfiles.map((p) => (
                  <div key={p.id} className="p-3 rounded-xl bg-slate-900 border border-slate-800">
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-bold text-xs text-white uppercase font-mono">{p.name} ({p.id})</span>
                      <span className="text-[10px] text-slate-400">{p.rules_count} reglas de fábrica</span>
                    </div>

                    <div className="space-y-1.5">
                      {p.rules?.slice(0, 5).map((r, i) => (
                        <div key={i} className="flex items-center justify-between p-2 rounded bg-slate-950 text-xs">
                          <div>
                            <span className="font-semibold text-slate-200">{r.name}</span>
                            <span className="ml-2 font-mono text-[10px] text-cyan-400">{r.pattern}</span>
                          </div>
                          <button
                            type="button"
                            onClick={() => {
                              setEditingRule({
                                id: `rule_${Math.random().toString(36).substr(2, 8)}`,
                                name: `${r.name} (Clonada)`,
                                description: `Clonada de perfil ${p.name}`,
                                entity_type: r.name.toUpperCase().replace(/\s+/g, "_"),
                                pattern: r.pattern,
                                case_sensitive: false,
                                confidence: 0.95,
                                priority: 40,
                                profiles: [p.id],
                                enabled: true,
                                example: ""
                              });
                              setActiveTab("edit");
                            }}
                            className="px-2 py-1 text-[10px] font-semibold rounded bg-cyan-950 text-cyan-300 border border-cyan-800 hover:bg-cyan-900"
                          >
                            Clonar como Regla Custom
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

        </div>

      </div>

      {/* ------------------------------------------------------------- */}
      {/* EXPORT ENCRYPTED MODAL (.aprules) */}
      {/* ------------------------------------------------------------- */}
      {isExportEncryptedOpen && (
        <div className="fixed inset-0 z-60 flex items-center justify-center p-4 bg-black/90 backdrop-blur-md">
          <div className="relative w-full max-w-lg rounded-2xl bg-[#0E1526] border border-cyan-500/40 shadow-2xl p-6 text-slate-100 space-y-4 animate-in fade-in">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Lock className="w-5 h-5 text-cyan-400" />
                <h3 className="text-sm font-bold text-white">{t("encrypted_export_title")}</h3>
              </div>
              <button
                type="button"
                onClick={() => {
                  setExportPassword("");
                  setExportConfirmPassword("");
                  setIsExportEncryptedOpen(false);
                }}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {exportError && (
              <div className="p-3 rounded-lg bg-red-950/80 border border-red-800 text-red-200 text-xs flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0 text-red-400" />
                <span>{exportError}</span>
              </div>
            )}

            {/* Warning notice */}
            <div className="p-3 rounded-xl bg-amber-950/40 border border-amber-900/60 text-[11px] text-amber-200 flex items-start gap-2">
              <ShieldCheck className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
              <p>{t("password_warning")}</p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Nombre del Ruleset
              </label>
              <input
                type="text"
                data-testid="export-ruleset-name-input"
                value={exportRulesetName}
                onChange={(e) => setExportRulesetName(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-lg bg-slate-900 border border-slate-700 text-slate-200 focus:outline-none focus:border-cyan-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                {t("password_label")} *
              </label>
              <div className="relative">
                <input
                  type={showExportPassword ? "text" : "password"}
                  data-testid="export-password-input"
                  autoComplete="new-password"
                  value={exportPassword}
                  onChange={(e) => setExportPassword(e.target.value)}
                  placeholder="Mínimo 8 caracteres..."
                  className="w-full px-3 py-2 pr-9 text-xs rounded-lg bg-slate-900 border border-slate-700 text-slate-200 focus:outline-none focus:border-cyan-500"
                />
                <button
                  type="button"
                  onClick={() => setShowExportPassword(!showExportPassword)}
                  className="absolute right-2.5 top-2.5 text-slate-400 hover:text-white"
                >
                  {showExportPassword ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                </button>
              </div>

              {/* Strength meter */}
              {exportPassword && (
                <div className="mt-1.5 flex items-center gap-2">
                  <div className="flex-1 h-1 bg-slate-800 rounded-full overflow-hidden">
                    <div className={`h-full ${pwdStrength.color}`} style={{ width: `${(pwdStrength.score / 3) * 100}%` }} />
                  </div>
                  <span className="text-[10px] font-mono text-slate-400">{pwdStrength.label}</span>
                </div>
              )}
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                {t("password_confirm_label")} *
              </label>
              <input
                type={showExportPassword ? "text" : "password"}
                data-testid="export-confirm-password-input"
                autoComplete="new-password"
                value={exportConfirmPassword}
                onChange={(e) => setExportConfirmPassword(e.target.value)}
                placeholder="Repite la contraseña..."
                className="w-full px-3 py-2 text-xs rounded-lg bg-slate-900 border border-slate-700 text-slate-200 focus:outline-none focus:border-cyan-500"
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-800">
              <button
                type="button"
                onClick={() => {
                  setExportPassword("");
                  setExportConfirmPassword("");
                  setIsExportEncryptedOpen(false);
                }}
                className="px-3 py-1.5 text-xs rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700"
              >
                Cancelar
              </button>
              <button
                type="button"
                data-testid="confirm-export-encrypted-btn"
                disabled={isExporting}
                onClick={handleExecuteEncryptedExport}
                className="px-4 py-2 text-xs rounded-lg bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 text-white font-bold shadow-md transition-all flex items-center gap-1.5 disabled:opacity-50"
              >
                <Lock className="w-3.5 h-3.5" />
                <span>{isExporting ? "Cifrando..." : t("btn_confirm_export_encrypted")}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* IMPORT ENCRYPTED MODAL (.aprules) */}
      {/* ------------------------------------------------------------- */}
      {isImportEncryptedOpen && (
        <div className="fixed inset-0 z-60 flex items-center justify-center p-4 bg-black/90 backdrop-blur-md">
          <div className="relative w-full max-w-lg rounded-2xl bg-[#0E1526] border border-cyan-500/40 shadow-2xl p-6 text-slate-100 space-y-4 animate-in fade-in">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Unlock className="w-5 h-5 text-cyan-400" />
                <h3 className="text-sm font-bold text-white">{t("encrypted_import_title")}</h3>
              </div>
              <button
                type="button"
                onClick={() => {
                  setImportPassword("");
                  setImportEnvelope(null);
                  setImportPreviewData(null);
                  setIsImportEncryptedOpen(false);
                }}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {importError && (
              <div className="p-3 rounded-lg bg-red-950/80 border border-red-800 text-red-200 text-xs flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0 text-red-400" />
                <span>{importError}</span>
              </div>
            )}

            {/* Step 1: File selection and password input */}
            {!importPreviewData && (
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    Archivo Cifrado (.aprules)
                  </label>
                  <input
                    type="file"
                    data-testid="import-aprules-file-input"
                    accept=".aprules,.json"
                    onChange={handleSelectAprulesFile}
                    className="w-full text-xs text-slate-400 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-slate-800 file:text-cyan-400 hover:file:bg-slate-700"
                  />
                  {importEnvelope && (
                    <span className="text-[10px] text-emerald-400 font-mono mt-1 block">
                      ✓ Archivo cargado ({importEnvelope.format_version ? `v${importEnvelope.format_version}` : ""})
                    </span>
                  )}
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    Contraseña de Descifrado
                  </label>
                  <div className="relative">
                    <input
                      type={showImportPassword ? "text" : "password"}
                      data-testid="import-password-input"
                      autoComplete="current-password"
                      value={importPassword}
                      onChange={(e) => setImportPassword(e.target.value)}
                      placeholder="Introduce la contraseña..."
                      className="w-full px-3 py-2 pr-9 text-xs rounded-lg bg-slate-900 border border-slate-700 text-slate-200 focus:outline-none focus:border-cyan-500"
                    />
                    <button
                      type="button"
                      onClick={() => setShowImportPassword(!showImportPassword)}
                      className="absolute right-2.5 top-2.5 text-slate-400 hover:text-white"
                    >
                      {showImportPassword ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                </div>

                <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-800">
                  <button
                    type="button"
                    onClick={() => {
                      setImportPassword("");
                      setImportEnvelope(null);
                      setIsImportEncryptedOpen(false);
                    }}
                    className="px-3 py-1.5 text-xs rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700"
                  >
                    Cancelar
                  </button>
                  <button
                    type="button"
                    data-testid="decrypt-preview-btn"
                    disabled={!importEnvelope || !importPassword || isDecrypting}
                    onClick={handleDecryptAndPreview}
                    className="px-4 py-2 text-xs rounded-lg bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 text-white font-bold shadow-md transition-all flex items-center gap-1.5 disabled:opacity-40"
                  >
                    <KeyRound className="w-3.5 h-3.5" />
                    <span>{isDecrypting ? "Descifrando..." : t("btn_decrypt_preview")}</span>
                  </button>
                </div>
              </div>
            )}

            {/* Step 2: Decrypted Preview and Conflict Resolution */}
            {importPreviewData && (
              <div className="space-y-4 animate-in fade-in">
                <div className="p-3 rounded-xl bg-emerald-950/40 border border-emerald-900/60 text-xs">
                  <div className="flex items-center gap-1.5 font-bold text-emerald-300 mb-1">
                    <CheckCircle className="w-4 h-4 text-emerald-400" />
                    <span>{t("preview_encrypted_header")}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-300 mt-2">
                    <div>Ruleset: <strong className="text-white">{importPreviewData.name}</strong></div>
                    <div>Reglas contenidas: <strong className="text-white">{importPreviewData.rules_count}</strong></div>
                    <div>Versión: <span className="font-mono text-cyan-300">{importPreviewData.version}</span></div>
                    <div>Hash canónico: <span className="font-mono text-[10px] text-slate-400">{importPreviewData.canonical_hash.substring(0, 16)}...</span></div>
                  </div>
                </div>

                {/* Conflict Options */}
                {importPreviewData.conflicts && importPreviewData.conflicts.length > 0 ? (
                  <div className="p-3 rounded-xl bg-amber-950/30 border border-amber-900/60 text-xs space-y-2">
                    <span className="font-semibold text-amber-300 block">
                      {t("conflicts_detected_label")} ({importPreviewData.conflicts.length})
                    </span>
                    <div className="space-y-1">
                      {importPreviewData.conflicts.map((c, i) => (
                        <div key={i} className="text-[11px] text-slate-300 font-mono">
                          • {c.name} ({c.rule_id})
                        </div>
                      ))}
                    </div>

                    <div className="pt-2 flex items-center gap-3 text-[11px]">
                      <label className="flex items-center gap-1 cursor-pointer">
                        <input
                          type="radio"
                          name="conflict_action"
                          checked={importConflictStrategy === "copy"}
                          onChange={() => setImportConflictStrategy("copy")}
                        />
                        <span>{t("conflict_action_copy")}</span>
                      </label>
                      <label className="flex items-center gap-1 cursor-pointer">
                        <input
                          type="radio"
                          name="conflict_action"
                          checked={importConflictStrategy === "replace"}
                          onChange={() => setImportConflictStrategy("replace")}
                        />
                        <span>{t("conflict_action_replace")}</span>
                      </label>
                      <label className="flex items-center gap-1 cursor-pointer">
                        <input
                          type="radio"
                          name="conflict_action"
                          checked={importConflictStrategy === "skip"}
                          onChange={() => setImportConflictStrategy("skip")}
                        />
                        <span>{t("conflict_action_skip")}</span>
                      </label>
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-slate-400">
                    No se detectaron conflictos con las reglas actuales del sistema.
                  </p>
                )}

                <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-800">
                  <button
                    type="button"
                    onClick={() => {
                      setImportPreviewData(null);
                    }}
                    className="px-3 py-1.5 text-xs rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700"
                  >
                    Atrás
                  </button>
                  <button
                    type="button"
                    data-testid="commit-import-rules-btn"
                    onClick={handleCommitImport}
                    className="px-4 py-2 text-xs rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold shadow-md transition-all flex items-center gap-1.5"
                  >
                    <Check className="w-3.5 h-3.5" />
                    <span>{t("btn_commit_import")}</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

    </div>
  );
};
