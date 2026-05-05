import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from "react";

type ThemeMode = "day" | "night" | "auto";

interface ThemeContextValue {
  theme: ThemeMode;
  effectiveTheme: "day" | "night";
  setTheme: (t: ThemeMode) => void;
}

const ThemeContext = createContext<ThemeContextValue>({
  theme: "auto",
  effectiveTheme: "day",
  setTheme: () => {},
});

export function useTheme() {
  return useContext(ThemeContext);
}

function isNightPhase(phase: string): boolean {
  const nightPhases = [
    "night_begin", "guard_action", "wolf_discuss", "witch_action",
    "seer_action", "night_resolve",
  ];
  return nightPhases.includes(phase);
}

interface ThemeProviderProps {
  children: ReactNode;
  currentPhase?: string;
}

export function ThemeProvider({ children, currentPhase }: ThemeProviderProps) {
  const [theme, setThemeState] = useState<ThemeMode>("auto");

  const effectiveTheme: "day" | "night" =
    theme === "auto"
      ? currentPhase && isNightPhase(currentPhase)
        ? "night"
        : "day"
      : theme;

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", effectiveTheme);
  }, [effectiveTheme]);

  const setTheme = useCallback((t: ThemeMode) => {
    setThemeState(t);
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, effectiveTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}
