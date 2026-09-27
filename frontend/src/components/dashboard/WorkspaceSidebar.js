import React, { useState } from "react";
import axios from "axios";
import {
  Clock,
  FileText,
  Layers,
  LayoutDashboard,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  Sliders,
  Wrench
} from "lucide-react";

function navClass(active) {
  return `group flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm font-medium transition focus:outline-none focus:ring-2 focus:ring-cyan-400 ${
    active
      ? "bg-cyan-500/10 text-cyan-700 ring-1 ring-cyan-500/20 dark:text-cyan-300"
      : "text-slate-500 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800/80 dark:hover:text-white"
  }`;
}

/**
 * Primary workspace navigation. Only the core, always-relevant destinations
 * live here as equal-weight nav items (Dashboard, New document, Batch,
 * Custom rules, History). Session/settings and QA-only tooling are
 * deliberately tucked into lower-weight disclosures below the nav so they
 * never compete visually with the core actions, and no destructive action
 * (session delete) sits at the top level.
 */
export function WorkspaceSidebar({
  t,
  activeMode,
  currentStep,
  sessionId,
  backendUrl,
  customRulesCount,
  onGoDashboard,
  onNewDocument,
  onToggleMode,
  onOpenRulesEditor,
  onOpenHistory,
  onOpenDevFixtures
}) {
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem("purgedoc_sidebar_collapsed") === "true");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [devToolsOpen, setDevToolsOpen] = useState(false);

  const isHome = currentStep === "upload";
  const items = [
    { id: "dashboard", icon: LayoutDashboard, label: t("dash_nav_dashboard"), active: isHome, onClick: onGoDashboard },
    { id: "new-doc", icon: FileText, label: t("dash_action_new_doc_title"), active: false, onClick: onNewDocument },
    { id: "batch", icon: Layers, label: t("dash_action_batch_title"), active: isHome && activeMode === "batch", onClick: onToggleMode },
    { id: "rules", icon: Sliders, label: t("dash_action_rules_title"), active: false, onClick: onOpenRulesEditor, badge: customRulesCount },
    { id: "history", icon: Clock, label: t("dash_nav_history"), active: false, onClick: onOpenHistory }
  ];

  const toggleCollapsed = () =>
    setCollapsed((value) => {
      const next = !value;
      localStorage.setItem("purgedoc_sidebar_collapsed", String(next));
      return next;
    });

  const handleDeleteSession = async () => {
    if (!window.confirm("¿Eliminar todos los documentos, auditorías y sesiones de forma inmediata e irreversible?")) return;
    try {
      await axios.delete(`${backendUrl}/api/sessions/${sessionId}`);
      window.location.reload();
    } catch (error) {
      console.error("Failed to delete session:", error);
    }
  };

  return (
    <aside
      data-testid="workspace-sidebar"
      className={`hidden shrink-0 border-r border-slate-200/80 bg-white/70 px-3 py-4 transition-[width] duration-200 dark:border-slate-800/80 dark:bg-[#0B0F19]/70 md:flex md:flex-col ${
        collapsed ? "w-[76px]" : "w-[248px]"
      }`}
    >
      <div className="mb-5 flex items-center justify-between px-2">
        {!collapsed && <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">Workspace</span>}
        <button
          type="button"
          aria-label={collapsed ? "Expandir navegación" : "Contraer navegación"}
          aria-expanded={!collapsed}
          onClick={toggleCollapsed}
          className="rounded-lg p-2 text-slate-400 transition hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-400 dark:hover:bg-slate-800 dark:hover:text-cyan-400"
        >
          {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
        </button>
      </div>

      <nav aria-label="Navegación principal" className="space-y-1">
        {items.map(({ id, icon: Icon, label, active, onClick, badge }) => (
          <button
            key={id}
            type="button"
            data-testid={`sidebar-${id}`}
            aria-label={label}
            aria-current={active ? "page" : undefined}
            onClick={onClick}
            className={navClass(active)}
            title={collapsed ? label : undefined}
          >
            <Icon className="h-4 w-4 shrink-0" />
            {!collapsed && (
              <span className="flex min-w-0 flex-1 items-center justify-between gap-2">
                <span className="truncate">{label}</span>
                {badge > 0 && <span className="rounded-full bg-cyan-500 px-1.5 py-0.5 text-[10px] font-bold text-slate-950">{badge}</span>}
              </span>
            )}
          </button>
        ))}
      </nav>

      {/* Spacer pushes low-priority disclosures (settings, dev tools) to the bottom */}
      <div className="flex-1" />

      {/* Settings / session — tucked below the core nav, off by default */}
      <div className="mt-4 border-t border-slate-200/80 pt-3 dark:border-slate-800/80">
        <button
          type="button"
          data-testid="sidebar-settings"
          aria-expanded={settingsOpen}
          onClick={() => setSettingsOpen((v) => !v)}
          className={navClass(settingsOpen)}
          title={collapsed ? t("dash_nav_settings") : undefined}
        >
          <Settings className="h-4 w-4 shrink-0" />
          {!collapsed && <span className="truncate">{t("dash_nav_settings")}</span>}
        </button>

        {!collapsed && settingsOpen && (
          <div className="mt-2 space-y-3 rounded-xl border border-cyan-500/15 bg-cyan-500/5 p-3 text-xs leading-5 text-slate-500 dark:text-slate-400">
            <div>
              <p className="font-semibold text-slate-700 dark:text-slate-200">{t("dash_status_local")}</p>
              <p className="mt-1">{t("dash_status_failclosed")}</p>
            </div>
            {sessionId && (
              <>
                <div className="flex items-center justify-between border-t border-cyan-500/10 pt-3">
                  <span>{t("session_ttl_badge")}</span>
                  <span className="rounded bg-slate-900 px-1.5 py-0.5 font-mono text-[10px] text-slate-300 dark:bg-slate-800">TTL</span>
                </div>
                <button
                  type="button"
                  data-testid="delete-session-now-btn"
                  onClick={handleDeleteSession}
                  className="w-full rounded-lg border border-red-500/20 px-2 py-2 text-left text-[11px] font-semibold text-red-600 transition hover:bg-red-500/10 dark:text-red-300"
                >
                  {t("session_delete_now_btn")}
                </button>
              </>
            )}
          </div>
        )}
      </div>

      {/* Developer tools — QA/dev fixtures, admin-tier, never a first-level action */}
      {!collapsed ? (
        <div className="mt-2">
          <button
            type="button"
            data-testid="sidebar-dev-tools-toggle"
            aria-expanded={devToolsOpen}
            onClick={() => setDevToolsOpen((v) => !v)}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-[11px] font-medium text-slate-400 transition hover:text-slate-600 focus:outline-none focus:ring-2 focus:ring-cyan-400 dark:hover:text-slate-300"
          >
            <Wrench className="h-3.5 w-3.5 shrink-0" />
            <span className="truncate">{t("dash_nav_dev_tools")}</span>
          </button>
          {devToolsOpen && (
            <button
              type="button"
              data-testid="sidebar-open-dev-fixtures"
              onClick={onOpenDevFixtures}
              className="ml-3 mt-1 block rounded-lg px-2 py-1.5 text-left text-[11px] text-cyan-700 underline decoration-cyan-400/40 underline-offset-2 hover:text-cyan-600 dark:text-cyan-300"
            >
              {t("dash_dev_tools_link")}
            </button>
          )}
        </div>
      ) : (
        <button
          type="button"
          data-testid="sidebar-open-dev-fixtures-collapsed"
          title={t("dash_nav_dev_tools")}
          onClick={onOpenDevFixtures}
          className="mt-2 flex w-full items-center justify-center rounded-lg px-3 py-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800"
        >
          <Wrench className="h-3.5 w-3.5" />
        </button>
      )}
    </aside>
  );
}

export function MobileWorkspaceNav({ t, activeMode, currentStep, sessionId, onGoDashboard, onNewDocument, onToggleMode, onOpenRulesEditor, onOpenHistory, onOpenDevFixtures }) {
  const [open, setOpen] = useState(false);
  const close = (callback) => {
    callback?.();
    setOpen(false);
  };
  return (
    <div className="border-b border-slate-200/80 bg-white/80 px-4 py-2 dark:border-slate-800/80 dark:bg-[#0B0F19]/80 md:hidden">
      <button
        type="button"
        aria-expanded={open}
        aria-controls="purgedoc-mobile-nav"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between rounded-lg px-2 py-2 text-xs font-semibold text-slate-600 focus:outline-none focus:ring-2 focus:ring-cyan-400 dark:text-slate-300"
      >
        <span>Workspace navigation</span>
        {open ? <PanelLeftClose className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
      </button>
      {open && (
        <nav id="purgedoc-mobile-nav" aria-label="Navegación móvil" className="grid grid-cols-2 gap-2 pb-2 pt-2">
          <button type="button" onClick={() => close(onGoDashboard)} className="rounded-lg bg-slate-100 px-3 py-2 text-left text-xs font-semibold text-slate-700 focus:outline-none focus:ring-2 focus:ring-cyan-400 dark:bg-slate-800 dark:text-slate-200">
            {t("dash_nav_dashboard")}
          </button>
          <button type="button" onClick={() => close(onNewDocument)} className="rounded-lg bg-cyan-500/10 px-3 py-2 text-left text-xs font-semibold text-cyan-700 focus:outline-none focus:ring-2 focus:ring-cyan-400 dark:text-cyan-300">
            {t("dash_action_new_doc_title")}
          </button>
          <button type="button" onClick={() => close(onToggleMode)} className="rounded-lg bg-slate-100 px-3 py-2 text-left text-xs font-semibold text-slate-700 focus:outline-none focus:ring-2 focus:ring-cyan-400 dark:bg-slate-800 dark:text-slate-200">
            {t("dash_action_batch_title")}
          </button>
          <button type="button" onClick={() => close(onOpenRulesEditor)} className="rounded-lg bg-slate-100 px-3 py-2 text-left text-xs font-semibold text-slate-700 focus:outline-none focus:ring-2 focus:ring-cyan-400 dark:bg-slate-800 dark:text-slate-200">
            {t("dash_action_rules_title")}
          </button>
          <button type="button" onClick={() => close(onOpenHistory)} className="col-span-2 rounded-lg bg-slate-100 px-3 py-2 text-left text-xs font-semibold text-slate-700 focus:outline-none focus:ring-2 focus:ring-cyan-400 dark:bg-slate-800 dark:text-slate-200">
            {t("dash_nav_history")}
          </button>
          <div className="col-span-2 flex items-center justify-between pt-1">
            {sessionId && <span className="text-[11px] text-red-600 dark:text-red-300">{t("session_ttl_badge")}</span>}
            <button type="button" onClick={() => close(onOpenDevFixtures)} className="text-[11px] text-slate-400 underline decoration-slate-400/40 underline-offset-2 hover:text-slate-600 dark:hover:text-slate-300">
              {t("dash_nav_dev_tools")}
            </button>
          </div>
        </nav>
      )}
    </div>
  );
}
