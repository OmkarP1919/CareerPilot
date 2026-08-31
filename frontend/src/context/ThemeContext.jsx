import { createContext, useContext, useState, useEffect } from "react";

const ThemeContext = createContext(null);

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(() => {
    return localStorage.getItem("cp_theme") || "system";
  });

  const [textSize, setTextSizeState] = useState(() => {
    return localStorage.getItem("cp_text_size") || "md";
  });

  const [highContrast, setHighContrastState] = useState(() => {
    return localStorage.getItem("cp_high_contrast") === "true";
  });

  const [reducedMotion, setReducedMotionState] = useState(() => {
    return localStorage.getItem("cp_reduced_motion") === "true";
  });

  // Apply theme to document element
  useEffect(() => {
    const root = document.documentElement;

    const applyTheme = () => {
      let resolvedTheme = theme;
      if (theme === "system") {
        resolvedTheme = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
      }
      root.setAttribute("data-theme", resolvedTheme);
      localStorage.setItem("cp_theme", theme);
    };

    applyTheme();

    if (theme === "system") {
      const media = window.matchMedia("(prefers-color-scheme: dark)");
      const handler = () => applyTheme();
      media.addEventListener("change", handler);
      return () => media.removeEventListener("change", handler);
    }
  }, [theme]);

  // Apply text size
  useEffect(() => {
    const root = document.documentElement;
    root.setAttribute("data-text-size", textSize);
    localStorage.setItem("cp_text_size", textSize);
  }, [textSize]);

  // Apply high contrast
  useEffect(() => {
    const root = document.documentElement;
    root.setAttribute("data-contrast", highContrast ? "high" : "normal");
    localStorage.setItem("cp_high_contrast", String(highContrast));
  }, [highContrast]);

  // Apply reduced motion
  useEffect(() => {
    const root = document.documentElement;
    root.setAttribute("data-reduced-motion", String(reducedMotion));
    localStorage.setItem("cp_reduced_motion", String(reducedMotion));
  }, [reducedMotion]);

  const setTheme = (t) => setThemeState(t);
  const setTextSize = (s) => setTextSizeState(s);
  const setHighContrast = (c) => setHighContrastState(c);
  const setReducedMotion = (m) => setReducedMotionState(m);

  return (
    <ThemeContext.Provider
      value={{
        theme,
        setTheme,
        textSize,
        setTextSize,
        highContrast,
        setHighContrast,
        reducedMotion,
        setReducedMotion,
      }}
    >
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return ctx;
}
