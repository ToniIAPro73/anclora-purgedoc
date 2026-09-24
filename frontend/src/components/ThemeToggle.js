import React from "react";
import { Sun, Moon, Laptop } from "lucide-react";
import { useApp } from "../context/AppContext";

export function ThemeToggle({ className = "" }) {
  const { themeMode, cycleTheme } = useApp();
  const theme = themeMode || "dark";

  return (
    <button
      type="button"
      data-testid="theme-toggle-button"
      onClick={cycleTheme}
      title="Cambiar tema / Switch theme"
      aria-label="Theme toggle"
      className={`anclora-toggle flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition-all duration-200 border border-[#3B82F6]/40 hover:border-[#38BDF8] bg-[#0E1525] text-[#F5F7FA] hover:shadow-[#38BDF8]/20 focus:outline-none focus:ring-2 focus:ring-[#38BDF8] ${className}`}
    >
      {theme === "dark" && <Moon className="h-[18px] w-[18px] text-[#38BDF8]" strokeWidth={1.6} />}
      {theme === "light" && <Sun className="h-[18px] w-[18px] text-amber-400" strokeWidth={1.6} />}
      {theme === "system" && <Laptop className="h-[18px] w-[18px] text-slate-300" strokeWidth={1.6} />}
    </button>
  );
}

export default ThemeToggle;
