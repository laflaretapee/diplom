import type { CSSProperties } from 'react';

export function themeSurfaceVars(isDark: boolean): CSSProperties {
  return {
    '--j-surface-strong': isDark ? '#131313' : '#FFFFFF',
    '--j-surface-panel': isDark ? '#201F1F' : '#FFFFFF',
    '--j-surface-high': isDark ? '#2A2A2A' : '#F6F3F2',
    '--j-surface-muted': isDark ? '#1A1A1A' : '#FCF9F8',
    '--j-text': isDark ? '#E5E2E1' : '#1C1B1B',
    '--j-text-secondary': isDark ? '#BFB6A8' : '#4F4538',
    '--j-text-tertiary': isDark ? '#8F8578' : '#817567',
    '--j-border': isDark ? '#4F4538' : '#D3C4B3',
    '--j-border-strong': isDark ? '#353534' : '#E5E2E1',
    '--j-warning-bg': isDark ? '#2A2418' : '#FFDDAE',
    '--j-header-glass': isDark ? 'rgba(14, 14, 14, 0.82)' : 'rgba(255, 255, 255, 0.86)',
    '--j-shadow': isDark ? 'rgba(0, 0, 0, 0.22)' : 'rgba(49, 48, 48, 0.08)',
    '--j-shadow-strong': isDark ? 'rgba(0, 0, 0, 0.35)' : 'rgba(49, 48, 48, 0.12)',
  } as CSSProperties;
}
