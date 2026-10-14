// PROJECT-FILES-003: every upload screen shows the one server policy and refuses a file before sending it.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeAll, beforeEach, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";

const api = vi.hoisted(() => ({ call: vi.fn() }));
vi.mock("@/lib/api-client", () => ({ apiClient: api.call }));
import { FilePicker } from "@/components/forms/FilePicker";

const POLICY = { logo: { types: ["image/png", "image/jpeg", "image/webp"], max_bytes: { "image/png": 1048576, "image/jpeg": 1048576, "image/webp": 1048576 } },
  attachment: { types: ["image/png", "image/jpeg", "image/webp", "application/pdf"],
    max_bytes: { "image/png": 5242880, "image/jpeg": 5242880, "image/webp": 5242880, "application/pdf": 2097152 } } };
const messages: Record<string, Record<string, unknown>> = {};
beforeAll(async () => { for (const l of ["ar", "en"] as const) messages[l] = await loadMessages(l) as Record<string, unknown>; });
beforeEach(() => { api.call.mockReset(); api.call.mockResolvedValue(POLICY); });
afterEach(cleanup);
const ui = (node: ReactNode, locale: "ar" | "en" = "en") => render(<NextIntlClientProvider locale={locale} messages={messages[locale]} timeZone="UTC">{node}</NextIntlClientProvider>);
const file = (name: string, type: string, size: number) => new File([new Uint8Array(size)], name, { type });

it("shows the limits from the server policy, in the screen's language", async () => {
  ui(<FilePicker kind="attachment" label="Upload" onFile={vi.fn()} />);
  expect(await screen.findByText(/PNG, JPEG, WebP up to 5 MB · PDF up to 2 MB/)).toBeTruthy();
  expect(api.call).toHaveBeenCalledWith("/system/file-policy", expect.objectContaining({ token: null }));
  cleanup();
  ui(<FilePicker kind="logo" label="رفع" onFile={vi.fn()} />, "ar");
  expect(await screen.findByText(/PNG, JPEG, WebP حتى 1 ميجابايت/)).toBeTruthy();
});

it("refuses a file over the limit or of another type before sending it", async () => {
  const onFile = vi.fn();
  ui(<FilePicker kind="attachment" label="Upload" onFile={onFile} />);
  await screen.findByText(/up to 5 MB/);
  fireEvent.change(screen.getByLabelText("Upload"), { target: { files: [file("scan.pdf", "application/pdf", 3 * 1024 * 1024)] } });
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", "The largest allowed file is 2 MB.");
  fireEvent.change(screen.getByLabelText("Upload"), { target: { files: [file("report.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", 100)] } });
  await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("This file type is not accepted"));
  expect(onFile).not.toHaveBeenCalled();
});

it("hands over a file within the policy", async () => {
  const onFile = vi.fn();
  ui(<FilePicker kind="attachment" label="Upload" onFile={onFile} />);
  await screen.findByText(/up to 5 MB/);
  const photo = file("defect.jpg", "image/jpeg", 4 * 1024 * 1024);
  fireEvent.change(screen.getByLabelText("Upload"), { target: { files: [photo] } });
  expect(onFile).toHaveBeenCalledWith(photo);
  expect(screen.queryByRole("alert")).toBeNull();
});
