import React, { useState, useEffect, useRef } from "react";
import { Sun, Moon, Laptop } from "lucide-react";
import { useApp } from "../context/AppContext";

export function ThemeToggle({ className = "" }) {
  const { themeMode, setThemeMode } = useApp();
  const [open, setOpen] = useState(false);
  const containerRef = useRef(null);

  const theme = themeMode || "dark";

  useEffect(() => {
    function handleClickOutside(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [open]);

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      <button
        type="button"
        data-testid="theme-toggle-button"
        onClick={() => setOpen(!open)}
        title="Cambiar tema / Switch theme"
        aria-label="Theme toggle"
        aria-expanded={open}
        className="anclora-toggle flex h-9 w-9 items-center justify-center rounded-full transition-all duration-200 border border-[#3B82F6]/40 hover:border-[#38BDF8] bg-[#0E1525] text-[#F5F7FA] hover:shadow-[#38BDF8]/20 focus:outline-none focus:ring-2 focus:ring-[#38BDF8]"
      >
        {theme === "dark" && <Moon className="h-[18px] w-[18px] text-[#38BDF8]" strokeWidth={1.6} />}
        {theme === "light" && <Sun className="h-[18px] w-[18px] text-amber-400" strokeWidth={1.6} />}
        {theme === "system" && <Laptop className="h-[18px] w-[18px] text-slate-300" strokeWidth={1.6} />}
      </button>

      {open && (
        <div
          data-testid="theme-dropdown-menu"
          className="absolute right-0 mt-2 w-36 rounded-lg shadow-xl py-1 z-50 border border-slate-700 dark:bg-[#0B1220] bg-white text-xs font-medium"
        >
          <button
            type="button"
            data-testid="theme-option-dark"
            onClick={() => {
              setThemeMode("dark");
              setOpen(false);
            }}
            className={`w-full px-3 py-2 flex items-center space-x-2 text-left hover:bg-[#3B82F6]/10 ${
              theme === "dark" ? "text-[#38BDF8] font-bold" : "text-slate-700 dark:text-slate-300"
            }`}
          >
            <Moon className="w-3.5 h-3.5 text-[#38BDF8]" />
            <span>Oscuro</span>
          </button>
          <button
            type="button"
            data-testid="theme-option-light"
            onClick={() => {
              setThemeMode("light");
              setOpen(false);
            }}
            className={`w-full px-3 py-2 flex items-center space-x-2 text-left hover:bg-[#3B82F6]/10 ${
              theme === "light" ? "text-[#38BDF8] font-bold" : "text-slate-700 dark:text-slate-300"
            }`}
          >
            <Sun className="w-3.5 h-3.5 text-amber-500" />
            <span>Claro</span>
          </button>
          <button
            type="button"
            data-testid="theme-option-system"
            onClick={() => {
              setThemeMode("system");
              setOpen(false);
            }}
            className={`w-full px-3 py-2 flex items-center space-x-2 text-left hover:bg-[#3B82F6]/10 ${
              theme === "system" ? "text-[#38BDF8] font-bold" : "text-slate-700 dark:text-slate-300"
            }`}
          >
            <Laptop className="w-3.5 h-3.5 text-slate-400" />
            <span>Sistema</span>
          </button>
        </div>
      )}
    </div>
  );
}

export default ThemeToggle;
