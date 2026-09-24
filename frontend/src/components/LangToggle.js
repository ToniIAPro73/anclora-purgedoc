import React from "react";
import { Globe } from "lucide-react";
import { useApp } from "../context/AppContext";

export function LangToggle({ className = "" }) {
  const { lang, toggleLanguage } = useApp();

  return (
    <button
      type="button"
      data-testid="lang-toggle-button"
      onClick={toggleLanguage}
      title={lang === "es" ? "Switch to English" : "Cambiar a Español"}
      aria-label="Language"
      className={`anclora-toggle flex h-9 items-center gap-1.5 rounded-full px-3 transition-all duration-200 border border-[#3B82F6]/40 hover:border-[#38BDF8] shadow-sm bg-[#0E1525] text-[#F5F7FA] hover:shadow-[#38BDF8]/20 focus:outline-none focus:ring-2 focus:ring-[#38BDF8] ${className}`}
    >
      <Globe className="h-[16px] w-[16px] text-[#38BDF8]" strokeWidth={1.6} />
      <span className="text-[12.5px] font-bold tracking-wide">{(lang || "es").toUpperCase()}</span>
    </button>
  );
}

export default LangToggle;
