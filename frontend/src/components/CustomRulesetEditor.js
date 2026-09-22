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
  RotateCcw
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

  // Fetch base profiles for cloning
  useEffect(() => {
    if (isOpen) {
      axios.get(`${backendUrl}/api/profiles`).then((res) => {
        setBaseProfiles(res.data);
      }).catch(console.error);
    }
  }, [isOpen, backendUrl]);

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

  // Clone from factory base rule
  const handleCloneFromBase = (baseRule, profileId) => {
    setEditingRule({
      id: `rule_clone_${Math.random().toString(36).substr(2, 8)}`,
      name: `Copia de ${baseRule.description || baseRule.id}`,
      description: `Clonada de regla base ${baseRule.id} del perfil ${profileId}`,
      entity_type: baseRule.entity_type,
      pattern: baseRule.pattern,
      case_sensitive: baseRule.case_sensitive || false,
      confidence: baseRule.confidence || 0.95,
      priority: 60,
      profiles: [profileId],
      enabled: true,
      example: ""
    });
    setSaveValidationMsg(null);
    setActiveTab("edit");
  };

  // Duplicate an existing custom rule
  const handleDuplicateRule = (rule) => {
    const duplicated = {
      ...rule,
      id: `rule_${Math.random().toString(36).substr(2, 8)}`,
      name: `${rule.name} (Copia)`
    };
    const updated = [...customRules, duplicated];
    setCustomRules(updated);
    localStorage.setItem("anclora_custom_rules", JSON.stringify(updated));
  };

  // Toggle active/inactive
  const handleToggleEnabled = (ruleId) => {
    const updated = customRules.map((r) =>
      r.id === ruleId ? { ...r, enabled: !r.enabled } : r
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

  // Save edited/created rule
  const handleSaveRule = async () => {
    if (!editingRule.name.trim()) {
      setSaveValidationMsg("El nombre de la regla es obligatorio.");
      return;
    }
    if (!editingRule.pattern.trim()) {
      setSaveValidationMsg("La expresión regular no puede estar vacía.");
      return;
    }

    // Validate with backend RE2 / safe regex validator
    try {
      const valRes = await axios.post(`${backendUrl}/api/rules/validate`, {
        pattern: editingRule.pattern,
        case_sensitive: editingRule.case_sensitive
      });
      if (!valRes.data.valid) {
        setSaveValidationMsg(valRes.data.error || "Expresión regular inválida.");
        return;
      }
    } catch (err) {
      setSaveValidationMsg("Error de comunicación con el motor de validación.");
      return;
    }

    const existingIndex = customRules.findIndex((r) => r.id === editingRule.id);
    let updated = [];
    if (existingIndex >= 0) {
      updated = [...customRules];
      updated[existingIndex] = editingRule;
    } else {
      updated = [...customRules, editingRule];
    }

    setCustomRules(updated);
    localStorage.setItem("anclora_custom_rules", JSON.stringify(updated));
    setActiveTab("list");
  };

  // Export Ruleset JSON
  const handleExportJSON = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(customRules, null, 2));
    const downloadAnchor = document.createElement("a");
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `anclora_ruleset_${Date.now()}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  // Import Ruleset JSON
  const handleImportJSON = (e) => {
    const fileReader = new FileReader();
    if (e.target.files && e.target.files[0]) {
      fileReader.readAsText(e.target.files[0], "UTF-8");
      fileReader.onload = (event) => {
        try {
          const parsed = JSON.parse(event.target.result);
          if (Array.isArray(parsed)) {
            setCustomRules(parsed);
            localStorage.setItem("anclora_custom_rules", JSON.stringify(parsed));
          } else {
            alert("El archivo importado no contiene una lista de reglas válida.");
          }
        } catch (err) {
          alert("Error al leer el archivo JSON.");
        }
      };
    }
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
              onClick={onClose}
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

            <div className="flex items-center gap-2">
              {/* Import / Export JSON */}
              <label
                data-testid="import-rules-label"
                className="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 flex items-center gap-1.5 cursor-pointer transition-colors"
              >
                <Upload className="w-3.5 h-3.5" />
                <span>{t("btn_import_rules")}</span>
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
                className="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 flex items-center gap-1.5 transition-colors disabled:opacity-40"
              >
                <Download className="w-3.5 h-3.5" />
                <span>{t("btn_export_rules")}</span>
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

              {/* Rules Cards List */}
              {filteredRules.length === 0 ? (
                <div className="p-12 text-center text-slate-500 text-xs">
                  {t("rules_empty")}
                </div>
              ) : (
                <div className="space-y-3">
                  {filteredRules.map((rule) => (
                    <div
                      key={rule.id}
                      data-testid={`custom-rule-card-${rule.id}`}
                      className={`p-4 rounded-xl border transition-all ${
                        rule.enabled
                          ? "bg-slate-900/90 border-slate-800 hover:border-slate-700"
                          : "bg-slate-950/60 border-slate-900 opacity-60"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-bold text-sm text-slate-100">{rule.name}</span>
                            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-950 text-cyan-300 border border-cyan-800">
                              {rule.entity_type}
                            </span>
                            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
                              Prio: {rule.priority}
                            </span>
                            <span className="text-[10px] font-mono text-slate-400">
                              {rule.profiles.join(", ")}
                            </span>
                          </div>

                          <div className="mt-2 font-mono text-xs text-cyan-200 bg-black/40 px-2.5 py-1.5 rounded border border-slate-800 truncate">
                            {rule.pattern}
                          </div>

                          {rule.description && (
                            <p className="mt-1.5 text-xs text-slate-400">{rule.description}</p>
                          )}
                        </div>

                        {/* Actions */}
                        <div className="flex items-center gap-1.5 shrink-0">
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

          {/* TAB 2: EDIT / CREATE RULE WITH TEST BENCH */}
          {activeTab === "edit" && editingRule && (
            <div className="space-y-4 max-w-2xl mx-auto">
              <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                <h3 className="text-sm font-bold text-white">
                  {editingRule.name ? `Editar: ${editingRule.name}` : t("btn_new_rule")}
                </h3>
                <button
                  type="button"
                  onClick={() => setActiveTab("list")}
                  className="text-xs text-slate-400 hover:text-white"
                >
                  Volver al listado
                </button>
              </div>

              {saveValidationMsg && (
                <div className="p-3 rounded-lg bg-red-950/70 border border-red-800 text-red-200 text-xs flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
                  <span>{saveValidationMsg}</span>
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                <div>
                  <label className="block text-[11px] font-mono text-slate-400 mb-1">
                    {t("rule_name")} *
                  </label>
                  <input
                    type="text"
                    data-testid="rule-name-input"
                    value={editingRule.name}
                    onChange={(e) => setEditingRule({ ...editingRule, name: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-100"
                    placeholder="Ej. ID de Proyecto Confidencial"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-mono text-slate-400 mb-1">
                    {t("rule_entity_type")} *
                  </label>
                  <input
                    type="text"
                    data-testid="rule-entity-input"
                    value={editingRule.entity_type}
                    onChange={(e) => setEditingRule({ ...editingRule, entity_type: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-100"
                    placeholder="CUSTOM_IDENTIFIER"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-mono text-slate-400 mb-1">
                  {t("rule_pattern")} (Safe RE2/PCRE) *
                </label>
                <input
                  type="text"
                  data-testid="rule-pattern-input"
                  value={editingRule.pattern}
                  onChange={(e) => setEditingRule({ ...editingRule, pattern: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-cyan-200 font-mono text-xs"
                  placeholder="PROJ-[A-Z0-9]{6}"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                <div>
                  <label className="block text-[11px] font-mono text-slate-400 mb-1">
                    {t("rule_priority")} (1 - 100)
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="100"
                    value={editingRule.priority}
                    onChange={(e) => setEditingRule({ ...editingRule, priority: parseInt(e.target.value) || 10 })}
                    className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-100"
                  />
                </div>

                <div className="flex items-center gap-2 pt-6">
                  <input
                    type="checkbox"
                    id="rule_case"
                    checked={editingRule.case_sensitive}
                    onChange={(e) => setEditingRule({ ...editingRule, case_sensitive: e.target.checked })}
                    className="rounded bg-slate-900 border-slate-700 text-cyan-500"
                  />
                  <label htmlFor="rule_case" className="text-xs text-slate-300">
                    {t("rule_case_sensitive")}
                  </label>
                </div>

                <div className="flex items-center gap-2 pt-6">
                  <input
                    type="checkbox"
                    id="rule_enabled"
                    checked={editingRule.enabled}
                    onChange={(e) => setEditingRule({ ...editingRule, enabled: e.target.checked })}
                    className="rounded bg-slate-900 border-slate-700 text-cyan-500"
                  />
                  <label htmlFor="rule_enabled" className="text-xs text-slate-300 font-bold text-emerald-400">
                    {t("rule_status_active")}
                  </label>
                </div>
              </div>

              {/* Profiles checkboxes */}
              <div>
                <label className="block text-[11px] font-mono text-slate-400 mb-1">
                  {t("rule_profiles")}
                </label>
                <div className="flex items-center gap-4 text-xs">
                  {["rrhh", "legal", "soporte"].map((p) => {
                    const isChecked = editingRule.profiles.includes(p);
                    return (
                      <label key={p} className="flex items-center gap-1.5 cursor-pointer text-slate-300">
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={(e) => {
                            const newProfiles = e.target.checked
                              ? [...editingRule.profiles, p]
                              : editingRule.profiles.filter((x) => x !== p);
                            setEditingRule({ ...editingRule, profiles: newProfiles });
                          }}
                          className="rounded bg-slate-900 border-slate-700 text-cyan-500"
                        />
                        <span className="uppercase font-mono">{p}</span>
                      </label>
                    );
                  })}
                </div>
              </div>

              {/* Description */}
              <div>
                <label className="block text-[11px] font-mono text-slate-400 mb-1">
                  {t("rule_desc")}
                </label>
                <textarea
                  rows={2}
                  value={editingRule.description}
                  onChange={(e) => setEditingRule({ ...editingRule, description: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-200 text-xs"
                />
              </div>

              {/* Integrated Regex Test Bench */}
              <RegexTestBench rule={editingRule} backendUrl={backendUrl} />

              {/* Action buttons */}
              <div className="pt-4 border-t border-slate-800 flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setActiveTab("list")}
                  className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition-colors"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  data-testid="save-custom-rule-btn"
                  onClick={handleSaveRule}
                  className="px-5 py-2 rounded-lg bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 text-white font-bold text-xs shadow-md transition-all"
                >
                  {t("btn_save_rule")}
                </button>
              </div>
            </div>
          )}

          {/* TAB 3: CLONE FACTORY BASE RULE */}
          {activeTab === "clone_base" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                <h3 className="text-sm font-bold text-white">
                  Clonar Regla de Perfiles Integrados (Presets de Fábrica)
                </h3>
                <button
                  type="button"
                  onClick={() => setActiveTab("list")}
                  className="text-xs text-slate-400 hover:text-white"
                >
                  Volver al listado
                </button>
              </div>

              <div className="space-y-4">
                {baseProfiles.map((p) => (
                  <div key={p.id} className="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-bold text-xs uppercase font-mono text-cyan-400">
                        Perfil: {p.name_es || p.id}
                      </span>
                      <span className="text-[10px] text-slate-500 font-mono">
                        {p.regex_rules?.length || 0} reglas integradas
                      </span>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2">
                      {(p.regex_rules || []).map((br) => (
                        <div
                          key={br.id}
                          className="p-2.5 rounded-lg bg-black/40 border border-slate-800/80 flex items-center justify-between gap-2"
                        >
                          <div className="min-w-0">
                            <span className="font-bold text-xs text-slate-200 block truncate">
                              {br.description || br.id}
                            </span>
                            <span className="text-[10px] font-mono text-slate-400 block truncate">
                              {br.pattern}
                            </span>
                          </div>

                          <button
                            type="button"
                            onClick={() => handleCloneFromBase(br, p.id)}
                            className="px-2.5 py-1 text-[11px] font-medium rounded bg-cyan-950 hover:bg-cyan-900 text-cyan-300 border border-cyan-800/80 shrink-0 transition-colors"
                          >
                            Clonar
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
    </div>
  );
};
