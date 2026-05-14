import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClientProvider } from '@tanstack/react-query';
import { ConfigProvider } from 'antd';
import 'antd/dist/reset.css';

import { App } from './App';
import { queryClient } from './app/queryClient';
import { appTheme, lightTheme } from './app/theme';
import { themeSurfaceVars } from './app/themeVars';
import { useThemeStore } from './store/themeStore';
import './styles/global.css';

function ThemeProvider({ children }: { children: React.ReactNode }) {
  const isDark = useThemeStore((s) => s.isDark);
  return (
    <ConfigProvider theme={isDark ? appTheme : lightTheme}>
      <div style={themeSurfaceVars(isDark)}>{children}</div>
    </ConfigProvider>
  );
}

const container = document.getElementById('root');

if (!container) {
  throw new Error('Root container not found');
}

ReactDOM.createRoot(container).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <App />
      </ThemeProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
