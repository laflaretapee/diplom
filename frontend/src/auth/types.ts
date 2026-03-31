export const roles = ['super_admin', 'franchisee', 'point_manager', 'staff'] as const;

export type Role = (typeof roles)[number];

export type SessionStatus = 'anonymous' | 'bootstrapping' | 'authenticated';

export interface SessionUser {
  id: string;
  email: string;
  name: string;
  role: Role;
  is_active: boolean;
}

export interface AuthSession {
  accessToken: string;
  user: SessionUser;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: 'bearer';
  user: SessionUser;
}

export interface TokenResponse {
  access_token: string;
  token_type: 'bearer';
}
