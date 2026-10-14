// PROJECT-GOV-004: a document shows who signed each step, and on whose behalf under a delegation.
import { cleanup, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, beforeAll, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";

const api = vi.hoisted(() => ({ call: vi.fn() }));
vi.mock("@/lib/api-client", () => ({ apiClient: api.call }));
vi.mock("@/hooks/useFormatter", () => ({ useFormatter: () => ({ dateTime: (v: string) => v }) }));
import { Signatures } from "@/components/Signatures";

let ar: Record<string, unknown>;
beforeAll(async () => { ar = await loadMessages("ar") as Record<string, unknown>; });
afterEach(cleanup);

it("names the signer and on whose behalf, in the screen's language", async () => {
  api.call.mockResolvedValue([{ step: "approve", signer_name: "محمد", authority_name: "أحمد", delegated: true, signed_at: "2026-10-12T10:00:00Z", notes: null },
                              { step: "issue", signer_name: "سارة", authority_name: "سارة", delegated: false, signed_at: "2026-10-13T10:00:00Z", notes: null }]);
  render(<NextIntlClientProvider locale="ar" messages={ar} timeZone="UTC"><Signatures resourceType="purchase_order" id="p1" /></NextIntlClientProvider>);
  expect(await screen.findByText("محمد — بالتفويض عن أحمد")).toBeTruthy();
  expect(screen.getByText("سارة")).toBeTruthy();
  expect(api.call).toHaveBeenCalledWith("/approvals/purchase_order/p1");
});

it("shows nothing when nothing is signed (or the reader may not see it)", async () => {
  api.call.mockRejectedValue(new Error("404"));
  const { container } = render(<NextIntlClientProvider locale="ar" messages={ar} timeZone="UTC"><Signatures resourceType="quote" id="q1" /></NextIntlClientProvider>);
  await new Promise((r) => setTimeout(r, 10));
  expect(container.textContent).toBe("");
});
