import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClientProvider } from '@tanstack/react-query';
import { ConfigProvider } from 'antd';
import 'antd/dist/reset.css';

import { App } from './App';
import { queryClient } from './app/queryClient';
import { appTheme } from './app/theme';
import './styles/global.css';

const container = document.getElementById('root');

if (!container) {
  throw new Error('Root container not found');
}

ReactDOM.createRoot(container).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ConfigProvider theme={appTheme}>
        <App />
      </ConfigProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
