import React, { useState } from "react";
import axios from "axios";
import { useApp } from "../context/AppContext";
import { Moon, Sun, Monitor, Globe, FileCode2, Check, Sliders } from "lucide-react";
import { BrandMark } from "./BrandMark";

import { Layers } from "lucide-react";
export const Header = ({
  onOpenDevFixtures,
  onOpenRulesEditor,
  customRulesCount = 0,
  activeMode = "single",
  onToggleMode,
  sessionId,
  BACKEND_URL
}) => {
  const { themeMode, setThemeMode, cycleTheme, lang, toggleLanguage, t } = useApp();
  const [themeMenuOpen, setThemeMenuOpen] = useState(false);

  const isDevMode = true; // Enabled in dev/preview environment

  return (
    <header className="sticky top-0 z-50 w-full border-b border-slate-800 bg-[#0B0F19]/90 backdrop-blur-md transition-colors dark:bg-[#0B0F19]/95 dark:border-slate-800 light:bg-white/95 light:border-slate-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        
        {/* Left: Reserved Logo Slot & Product Name */}
        <div className="flex items-center gap-3">
          <div
            data-testid="header-logo-slot"
            className="w-9 h-9 rounded-full border border-cyan-500/30 flex items-center justify-center overflow-hidden shadow-sm"
          >
            <BrandMark className="w-full h-full" />
          </div>
          <div className="flex flex-col">
            <span className="font-bold text-lg tracking-tight text-white dark:text-white light:text-slate-900">
              {t("app_name")}
            </span>
            <span className="text-[10px] uppercase font-mono tracking-wider text-cyan-400 dark:text-cyan-400 light:text-blue-600">
              {t("privacy_badge")}
            </span>
          </div>
        </div>

        {/* Right Controls: Custom Rules + Dev Fixtures + ES/EN Pill + Circular Theme Switcher */}
        <div className="flex items-center gap-3">
          {/* Ephemeral Session TTL & Delete Session Now Button */}
          {sessionId && (
            <div className="flex items-center gap-2 mr-1">
              <span
                data-testid="session-ttl-indicator"
                className="hidden md:inline text-[10px] font-mono px-2 py-1 rounded bg-slate-900 border border-slate-700 text-slate-400"
                title={t("session_ttl_badge")}
              >
                ⏱️ {t("session_ttl_badge")}
              </span>
              <button
                type="button"
                data-testid="delete-session-now-btn"
                onClick={async () => {
                  if (window.confirm("¿Eliminar todos los documentos, auditorías y sesiones de forma inmediata e irreversible?")) {
                    try {
                      await axios.delete(`${BACKEND_URL}/api/sessions/${sessionId}`);
                      window.location.reload();
                    } catch (e) {
                      console.error("Failed to delete session:", e);
                    }
                  }
                }}
                className="px-2.5 py-1 text-xs rounded bg-red-950/60 hover:bg-red-900 text-red-300 border border-red-800/80 transition-colors"
                title={t("session_delete_now_btn")}
              >
                {t("session_delete_now_btn")}
              </button>
            </div>
          )}
          
          {/* Mode Switcher: Single vs Batch */}
          {onToggleMode && (
            <button
              type="button"
              data-testid="toggle-batch-mode-btn"
              onClick={onToggleMode}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-full transition-all shadow-sm ${
                activeMode === "batch"
                  ? "bg-cyan-500 text-slate-950 font-bold border border-cyan-400"
                  : "bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-700 hover:border-cyan-500/40"
              }`}
              title="Cambiar entre modo Individual y Procesamiento por Lotes"
            >
              <Layers className="w-3.5 h-3.5" />
              <span>{t("batch_mode_btn")}</span>
            </button>
          )}
          {/* Custom Rules Button */}
          {onOpenRulesEditor && (
            <button
              type="button"
              data-testid="open-rules-editor-btn"
              onClick={onOpenRulesEditor}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-full bg-slate-900 hover:bg-slate-800 text-cyan-300 border border-cyan-500/40 hover:border-cyan-400 transition-all shadow-sm"
              title="Editor de reglas personalizadas (Regex)"
            >
              <Sliders className="w-3.5 h-3.5 text-cyan-400" />
              <span>{t("rules_nav_btn")}</span>
              {customRulesCount > 0 && (
                <span
                  data-testid="rules-count-badge"
                  className="px-1.5 py-0.2 rounded-full text-[10px] font-mono bg-cyan-500 text-slate-950 font-bold"
                >
                  {customRulesCount}
                </span>
              )}
            </button>
          )}

          {/* Dev/QA Fixture Loader Button (Development/QA only) */}
          {isDevMode && onOpenDevFixtures && (
            <button
              type="button"
              data-testid="qa-fixtures-btn"
              onClick={onOpenDevFixtures}
              className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-full bg-slate-800/80 hover:bg-slate-700 text-cyan-300 border border-cyan-500/30 hover:border-cyan-400 transition-all shadow-sm"
              title="Cargar documento de prueba (Dev/QA)"
            >
              <FileCode2 className="w-3.5 h-3.5" />
              <span>{t("dev_fixtures_btn")}</span>
            </button>
          )}

          {/* Language Toggle: Custom Pill Button */}
          <button
            type="button"
            data-testid="language-toggle-btn"
            onClick={toggleLanguage}
            className="flex items-center gap-1.5 px-3 py-1.5 h-9 rounded-full bg-[#0E1525] border border-cyan-500/40 hover:border-cyan-400 text-[#F5F7FA] text-xs font-semibold shadow-[0_0_12px_rgba(59,130,246,0.15)] hover:shadow-[0_0_15px_rgba(56,189,248,0.25)] transition-all"
            aria-label={`Switch language to ${lang === "es" ? "English" : "Spanish"}`}
          >
            <Globe className="w-3.5 h-3.5 text-cyan-400" />
            <span className="tracking-wide font-mono uppercase">{lang}</span>
          </button>

          {/* Theme Switcher: Circular Pill Button with Subtle Cyan Glow */}
          <div className="relative">
            <button
              type="button"
              data-testid="theme-toggle-btn"
              onClick={() => setThemeMenuOpen(!themeMenuOpen)}
              className="w-9 h-9 rounded-full bg-[#0E1525] border border-cyan-500/40 hover:border-cyan-400 text-[#F5F7FA] flex items-center justify-center shadow-[0_0_12px_rgba(59,130,246,0.15)] hover:shadow-[0_0_15px_rgba(56,189,248,0.25)] transition-all"
              aria-label="Theme selector"
              aria-expanded={themeMenuOpen}
            >
              {themeMode === "dark" && <Moon className="w-4 h-4 text-cyan-400" />}
              {themeMode === "light" && <Sun className="w-4 h-4 text-amber-400" />}
              {themeMode === "system" && <Monitor className="w-4 h-4 text-blue-400" />}
            </button>

            {/* Dropdown Menu for Theme Selection */}
            {themeMenuOpen && (
              <div className="absolute right-0 mt-2 w-36 rounded-xl bg-[#111827] border border-slate-700 shadow-xl py-1 z-50 animate-in fade-in zoom-in-95 duration-100">
                <button
                  type="button"
                  data-testid="theme-option-dark"
                  onClick={() => {
                    setThemeMode("dark");
                    setThemeMenuOpen(false);
                  }}
                  className={`w-full px-3 py-2 text-xs flex items-center justify-between text-left hover:bg-slate-800 ${
                    themeMode === "dark" ? "text-cyan-400 font-semibold" : "text-slate-300"
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <Moon className="w-3.5 h-3.5" /> Oscuro / Dark
                  </span>
                  {themeMode === "dark" && <Check className="w-3 h-3" />}
                </button>
                <button
                  type="button"
                  data-testid="theme-option-light"
                  onClick={() => {
                    setThemeMode("light");
                    setThemeMenuOpen(false);
                  }}
                  className={`w-full px-3 py-2 text-xs flex items-center justify-between text-left hover:bg-slate-800 ${
                    themeMode === "light" ? "text-cyan-400 font-semibold" : "text-slate-300"
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <Sun className="w-3.5 h-3.5" /> Claro / Light
                  </span>
                  {themeMode === "light" && <Check className="w-3 h-3" />}
                </button>
                <button
                  type="button"
                  data-testid="theme-option-system"
                  onClick={() => {
                    setThemeMode("system");
                    setThemeMenuOpen(false);
                  }}
                  className={`w-full px-3 py-2 text-xs flex items-center justify-between text-left hover:bg-slate-800 ${
                    themeMode === "system" ? "text-cyan-400 font-semibold" : "text-slate-300"
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <Monitor className="w-3.5 h-3.5" /> Sistema / System
                  </span>
                  {themeMode === "system" && <Check className="w-3 h-3" />}
                </button>
              </div>
            )}
          </div>

        </div>

      </div>
    </header>
  );
};
