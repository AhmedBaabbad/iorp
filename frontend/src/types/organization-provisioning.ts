export type OrganizationInput = {
  name: string;
  code: string;
  industry_type?: string;
  timezone: string;
  default_locale: "ar" | "en";
  logo_base64?: string;
};

export type OrganizationAdminInput = {
  full_name: string;
  email: string;
  phone?: string;
  password: string;
  password_confirmation: string;
};
