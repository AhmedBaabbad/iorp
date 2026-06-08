export type LoginRequest = {
  email: string;
  password: string;
};

export type LoginResponse = {
  access_token: string;
  token_type: string;
};

export type CurrentUser = {
  id: string;
  organization_id: string;
  organization_code: string;
  full_name: string;
  email: string;
  status: string;
  roles: string[];
};

export type AuthState = {
  user: CurrentUser | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
};
