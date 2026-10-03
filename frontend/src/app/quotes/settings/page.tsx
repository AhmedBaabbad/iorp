import { PermissionGate } from "@/features/auth/permission-gate";
import { QuoteSettingsPage } from "@/features/quotes/components/QuoteSettingsPage";

export default function Page() {
  return <PermissionGate code="commercial:quote_settings:read"><QuoteSettingsPage /></PermissionGate>;
}
