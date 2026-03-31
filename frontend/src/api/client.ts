import axios, {
  AxiosHeaders,
  type AxiosError,
  type InternalAxiosRequestConfig,
} from 'axios';

import type { AuthSession } from '../auth/types';

function readCookie(name: string): string | null {
  if (typeof document === 'undefined') {
    return null;
  }

  const parts = document.cookie.split(';').map((part) => part.trim());
  const match = parts.find((part) => part.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : null;
}

type AuthTransportConfig = InternalAxiosRequestConfig & {
  _authRetry?: boolean;
};

type AuthTransportHandlers = {
  getAccessToken: () => string | null;
  refreshSession: () => Promise<AuthSession | null>;
};

const authTransportHandlers: AuthTransportHandlers = {
  getAccessToken: () => null,
  refreshSession: async () => null,
};

const AUTH_ENDPOINTS = ['/v1/auth/login', '/v1/auth/refresh', '/v1/auth/logout'];

function normalizePath(url?: string): string {
  return (url ?? '').split('?')[0];
}

function isAuthEndpoint(url?: string): boolean {
  const path = normalizePath(url);
  return AUTH_ENDPOINTS.some((endpoint) => path.endsWith(endpoint));
}

function registerHeader(headers: AxiosHeaders, name: string, value: string) {
  if (!headers.has(name)) {
    headers.set(name, value);
  }
}

export function registerAuthTransport(handlers: Partial<AuthTransportHandlers>) {
  if (handlers.getAccessToken) {
    authTransportHandlers.getAccessToken = handlers.getAccessToken;
  }

  if (handlers.refreshSession) {
    authTransportHandlers.refreshSession = handlers.refreshSession;
  }
}

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '/api',
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use((config) => {
  const headers = AxiosHeaders.from(config.headers);
  const method = (config.method ?? 'get').toLowerCase();

  if (!isAuthEndpoint(config.url)) {
    const accessToken = authTransportHandlers.getAccessToken();
    if (accessToken) {
      registerHeader(headers, 'Authorization', `Bearer ${accessToken}`);
    }
  }

  if (['post', 'put', 'patch', 'delete'].includes(method)) {
    const csrfToken = readCookie('csrf_token');
    if (csrfToken) {
      registerHeader(headers, 'X-CSRF-Token', csrfToken);
    }
  }

  config.headers = headers;
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const status = error.response?.status;
    const config = error.config as AuthTransportConfig | undefined;

    if (status !== 401 || !config || config._authRetry || isAuthEndpoint(config.url)) {
      return Promise.reject(error);
    }

    config._authRetry = true;

    try {
      const refreshedSession = await authTransportHandlers.refreshSession();
      const accessToken = refreshedSession?.accessToken ?? authTransportHandlers.getAccessToken();
      if (!accessToken) {
        return Promise.reject(error);
      }

      const headers = AxiosHeaders.from(config.headers);
      headers.delete('Authorization');
      headers.set('Authorization', `Bearer ${accessToken}`);

      config.headers = headers;
      return apiClient.request(config);
    } catch {
      return Promise.reject(error);
    }
  },
);
