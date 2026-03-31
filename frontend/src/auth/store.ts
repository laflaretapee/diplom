import { create } from 'zustand';

import { registerAuthTransport } from '../api/client';

import {
  fetchCurrentUser,
  logoutSession,
  refreshSession as refreshAuthToken,
} from './api';
import type {
  AuthSession,
  LoginResponse,
  Role,
  SessionStatus,
  SessionUser,
} from './types';

interface AuthState {
  status: SessionStatus;
  accessToken: string | null;
  user: SessionUser | null;
  token: string | null;
  name: string | null;
  role: Role | null;
  login: (payload: LoginResponse | AuthSession) => void;
  setSession: (session: AuthSession) => void;
  clearSession: () => void;
  bootstrap: () => Promise<void>;
  refreshSession: () => Promise<AuthSession | null>;
  logout: () => Promise<void>;
}

const anonymousState = {
  status: 'anonymous' as const,
  accessToken: null,
  user: null,
  token: null,
  name: null,
  role: null,
};

function toLegacyFields(user: SessionUser | null, accessToken: string | null) {
  return {
    accessToken,
    user,
    token: accessToken,
    name: user?.name ?? null,
    role: user?.role ?? null,
  };
}

function commitSession(set: (partial: Partial<AuthState>) => void, session: AuthSession) {
  set({
    status: 'authenticated',
    ...toLegacyFields(session.user, session.accessToken),
  });
}

function setAnonymousSession(set: (partial: Partial<AuthState>) => void) {
  set({ ...anonymousState });
}

async function loadAuthenticatedSession(accessToken: string): Promise<AuthSession> {
  const user = await fetchCurrentUser(accessToken);
  return {
    accessToken,
    user,
  };
}

let refreshInFlight: Promise<AuthSession | null> | null = null;

export const useAuthStore = create<AuthState>((set, get) => ({
  ...anonymousState,
  login: (payload) => {
    if ('accessToken' in payload) {
      commitSession(set, payload);
      return;
    }

    if ('access_token' in payload) {
      commitSession(set, {
        accessToken: payload.access_token,
        user: payload.user,
      });
      return;
    }
  },
  setSession: (session) => {
    commitSession(set, session);
  },
  clearSession: () => {
    setAnonymousSession(set);
  },
  bootstrap: async () => {
    if (get().status === 'bootstrapping') {
      return;
    }

    set({ status: 'bootstrapping' });
    try {
      const currentAccessToken = get().accessToken;
      if (currentAccessToken) {
        const session = await loadAuthenticatedSession(currentAccessToken);
        commitSession(set, session);
        return;
      }

      await get().refreshSession();
    } catch {
      setAnonymousSession(set);
    }
  },
  refreshSession: async () => {
    if (refreshInFlight) {
      return refreshInFlight;
    }

    refreshInFlight = (async () => {
      try {
        const { access_token } = await refreshAuthToken();
        const session = await loadAuthenticatedSession(access_token);
        commitSession(set, session);
        return session;
      } catch {
        setAnonymousSession(set);
        return null;
      } finally {
        refreshInFlight = null;
      }
    })();

    return refreshInFlight;
  },
  logout: async () => {
    try {
      await logoutSession();
    } finally {
      setAnonymousSession(set);
    }
  },
}));

registerAuthTransport({
  getAccessToken: () => useAuthStore.getState().accessToken,
  refreshSession: () => useAuthStore.getState().refreshSession(),
});
