import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

function normalizeHost(value: string): string | null {
  const trimmed = value.trim();

  if (!trimmed) {
    return null;
  }

  try {
    return new URL(trimmed.includes('://') ? trimmed : `https://${trimmed}`).hostname;
  } catch {
    return trimmed
      .replace(/^[a-z]+:\/\//i, '')
      .split('/')[0]
      ?.split(':')[0]
      ?.trim() || null;
  }
}

function collectAllowedHosts(...values: Array<string | undefined>): string[] {
  const hosts = new Set(['localhost', '127.0.0.1']);

  for (const value of values) {
    if (!value) {
      continue;
    }

    for (const item of value.split(',')) {
      const host = normalizeHost(item);

      if (host) {
        hosts.add(host);
      }
    }
  }

  return Array.from(hosts);
}

export default defineConfig(({ mode }) => {
  const env = { ...process.env, ...loadEnv(mode, process.cwd(), '') };
  const apiProxyTarget = env.VITE_API_PROXY_TARGET || 'http://api:8000';
  const allowedHosts = collectAllowedHosts(env.VITE_ALLOWED_HOSTS, env.FRONTEND_ORIGIN, env.NGINX_SERVER_NAME);

  return {
    plugins: [react()],
    server: {
      host: '0.0.0.0',
      allowedHosts,
      proxy: {
        '/api': {
          target: apiProxyTarget,
          changeOrigin: true,
        },
      },
    },
    preview: {
      host: '0.0.0.0',
      allowedHosts,
    },
  };
});
