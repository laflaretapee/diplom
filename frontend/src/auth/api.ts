import { apiClient } from '../api/client';

import type {
  AuthSession,
  LoginRequest,
  LoginResponse,
  SessionUser,
  TokenResponse,
} from './types';

export async function login(request: LoginRequest): Promise<LoginResponse> {
  const { data } = await apiClient.post<LoginResponse>('/v1/auth/login', request);
  return data;
}

export async function refreshSession(): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>('/v1/auth/refresh');
  return data;
}

export async function fetchCurrentUser(accessToken?: string): Promise<SessionUser> {
  const { data } = await apiClient.get<SessionUser>(
    '/v1/auth/me',
    accessToken
      ? {
          headers: {
            Authorization: `Bearer ${accessToken}`,
          },
        }
      : undefined,
  );
  return data;
}

export async function logoutSession(): Promise<void> {
  await apiClient.post('/v1/auth/logout');
}

export async function loginWithSession(request: LoginRequest): Promise<AuthSession> {
  const { access_token } = await login(request);
  const user = await fetchCurrentUser(access_token);

  return {
    accessToken: access_token,
    user,
  };
}
