import { create } from 'zustand';

interface ThemeState {
  isDark: boolean;
  toggle: () => void;
}

const stored = typeof window !== 'undefined' ? localStorage.getItem('japonica-theme') : null;

export const useThemeStore = create<ThemeState>((set) => ({
  isDark: stored !== 'light',
  toggle: () =>
    set((s) => {
      const next = !s.isDark;
      localStorage.setItem('japonica-theme', next ? 'dark' : 'light');
      return { isDark: next };
    }),
}));
