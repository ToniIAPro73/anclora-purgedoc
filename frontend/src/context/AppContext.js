import React, { createContext, useContext, useState, useEffect } from "react";
import translations from "../i18n";

const AppContext = createContext();

export const AppProvider = ({ children }) => {
  // Theme state: 'dark' (default as per spec) | 'light' | 'system'
  const [themeMode, setThemeMode] = useState(() => {
    return localStorage.getItem("anclora_theme") || "dark";
  });

  // Language state: 'es' (default) | 'en'
  const [lang, setLang] = useState(() => {
    return localStorage.getItem("anclora_lang") || "es";
  });

  // Apply dark/light class to <html> element
  useEffect(() => {
    const root = document.documentElement;
    localStorage.setItem("anclora_theme", themeMode);

    if (themeMode === "dark") {
      root.classList.add("dark");
    } else if (themeMode === "light") {
      root.classList.remove("dark");
    } else {
      // system mode
      const isSystemDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      if (isSystemDark) {
        root.classList.add("dark");
      } else {
        root.classList.remove("dark");
      }
    }
  }, [themeMode]);

  // Persist language
  useEffect(() => {
    localStorage.setItem("anclora_lang", lang);
  }, [lang]);

  const toggleLanguage = () => {
    setLang((prev) => (prev === "es" ? "en" : "es"));
  };

  const cycleTheme = () => {
    setThemeMode((prev) => {
      if (prev === "dark") return "light";
      if (prev === "light") return "system";
      return "dark";
    });
  };

  const t = (key) => {
    return translations[lang]?.[key] || key;
  };

  return (
    <AppContext.Provider
      value={{
        themeMode,
        setThemeMode,
        cycleTheme,
        lang,
        setLang,
        toggleLanguage,
        t
      }}
    >
      {children}
    </AppContext.Provider>
  );
};

export const useApp = () => useContext(AppContext);
