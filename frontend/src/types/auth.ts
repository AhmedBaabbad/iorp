export type LoginRequest = {
  email: string;
  password: string;
};

export type LoginResponse = {
  access_token: string;
  token_type: string;
  expires_in?: number;
};

export type CurrentUser = {
  id: string;
  organization_id: string;
  organization_code: string;
  organization_name: string;
  organization_logo_url?: string | null;
  organization_timezone: string;
  full_name: string;
  email: string;
  phone: string | null;
  preferred_locale: "ar" | "en" | null;
  effective_locale: "ar" | "en";
  status: string;
  is_organization_root: boolean;
  roles: string[];
  permissions: string[];
  last_login_at: string | null;
  created_at: string;
  organization: {
    id: string;
    name: string;
    code: string;
    has_logo: boolean;
    logo_url: string | null;
    default_locale: "ar" | "en";
  };
};

export type UserProfileUpdate = {
  full_name?: string;
  phone?: string | null;
  preferred_locale?: "ar" | "en" | null;
};

export type AuthState = {
  user: CurrentUser | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
};
