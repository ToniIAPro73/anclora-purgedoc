import React from "react";
import { LogOut } from "lucide-react";
import { useApp } from "../context/AppContext";
import { useAuth } from "../context/AuthContext";
import { BrandMark } from "./BrandMark";
import LangToggle from "./LangToggle";
import ThemeToggle from "./ThemeToggle";

/** Canonical Anclora app header: identity and account controls only. */
export const Header = () => {
  const { t } = useApp();
  const { user, logout } = useAuth();

  return (
    <header data-testid="app-sticky-header" className="sticky top-0 z-50 w-full border-b border-slate-200/80 bg-white/90 backdrop-blur-xl dark:border-slate-800/80 dark:bg-[#0B0F19]/90">
      <div className="mx-auto flex h-[72px] w-full max-w-[1440px] items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        <div className="flex min-w-0 items-center gap-3">
          <div data-testid="header-logo-slot" className="flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-xl ring-1 ring-cyan-500/30 shadow-sm shadow-cyan-500/10"><BrandMark className="h-full w-full" /></div>
          <div className="min-w-0"><p className="truncate text-sm font-bold tracking-tight text-slate-950 dark:text-white">{t("app_name")}</p><p className="truncate text-[10px] font-medium uppercase tracking-[0.16em] text-cyan-600 dark:text-cyan-400">{t("privacy_badge")}</p></div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <LangToggle /><ThemeToggle />
          {user && <div className="ml-1 flex items-center gap-2 border-l border-slate-200 pl-3 dark:border-slate-700/70"><span data-testid="header-user-display" className="hidden max-w-[180px] truncate text-xs font-medium text-slate-500 dark:text-slate-400 lg:inline-block">{user.display_name || user.email}</span><button type="button" data-testid="auth-logout-button" onClick={logout} title="Cerrar sesión / Logout" aria-label="Cerrar sesión" className="rounded-lg p-2 text-slate-500 transition-colors hover:bg-red-500/10 hover:text-red-500 dark:text-slate-400"><LogOut className="h-4 w-4" /></button></div>}
        </div>
      </div>
    </header>
  );
};

export default Header;
