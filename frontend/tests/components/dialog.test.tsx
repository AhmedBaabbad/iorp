import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { useState, type ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Dialog } from "@/components/ui/Dialog";

function ui(children: ReactNode, locale = "en") {
  return render(<NextIntlClientProvider locale={locale} messages={{ common: { actions: { close: locale === "ar" ? "إغلاق" : "Close" } } }}>{children}</NextIntlClientProvider>);
}
afterEach(() => { cleanup(); document.body.style.overflow = ""; });

describe("Dialog", () => {
  it("preserves autoFocus on a footer button when the dialog opens", () => {
    ui(<Dialog title="Edit" onClose={() => {}} footer={<button autoFocus>Save</button>}><input aria-label="Quantity" /></Dialog>);
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Save" }));
  });
  it("renders a labelled dialog, its footer, and a named close button", () => {
    const close = vi.fn();
    ui(<Dialog title="Edit result" onClose={close} footer={<button>Save</button>}><input aria-label="Quantity" /></Dialog>);
    expect(screen.getByRole("dialog", { name: "Edit result" }).getAttribute("aria-modal")).toBe("true");
    expect(screen.getByRole("button", { name: "Save" }).closest("footer")).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(close).toHaveBeenCalledTimes(1);
  });
  it("closes on Escape", () => {
    const close = vi.fn();
    ui(<Dialog title="Edit" onClose={close}>Body</Dialog>);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(close).toHaveBeenCalledTimes(1);
  });
  it("blocks Escape and the close button while busy, including updates", () => {
    const close = vi.fn();
    const { rerender } = ui(<Dialog title="Edit" onClose={close}>Body</Dialog>);
    rerender(<NextIntlClientProvider locale="en" messages={{ common: { actions: { close: "Close" } } }}><Dialog title="Edit" onClose={close} busy>Body</Dialog></NextIntlClientProvider>);
    fireEvent.keyDown(document, { key: "Escape" });
    const button = screen.getByRole("button", { name: "Close" }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    fireEvent.click(button);
    expect(close).not.toHaveBeenCalled();
  });
  it("does not close on a backdrop click", () => {
    const close = vi.fn();
    ui(<Dialog title="Edit" onClose={close}>Body</Dialog>);
    fireEvent.click(screen.getByRole("dialog").parentElement!);
    expect(close).not.toHaveBeenCalled();
  });
  it("locks body overflow and restores the previous value on unmount", () => {
    document.body.style.overflow = "scroll";
    const { unmount } = ui(<Dialog title="Edit" onClose={() => {}}>Body</Dialog>);
    expect(document.body.style.overflow).toBe("hidden");
    unmount();
    expect(document.body.style.overflow).toBe("scroll");
  });
  it("keeps the scroll lock when dialogs are removed out of order", () => {
    document.body.style.overflow = "auto";
    const first = ui(<Dialog title="First" onClose={() => {}}>Body</Dialog>);
    const second = ui(<Dialog title="Second" onClose={() => {}}>Body</Dialog>);
    first.unmount();
    expect(document.body.style.overflow).toBe("hidden");
    second.unmount();
    expect(document.body.style.overflow).toBe("auto");
  });
  it("submits from a footer button inside the form", () => {
    const submit = vi.fn(event => event.preventDefault());
    ui(<Dialog title="Edit" onClose={() => {}} onSubmit={submit} footer={<button type="submit">Save</button>}><input name="quantity" /></Dialog>);
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(submit).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("dialog").tagName).toBe("FORM");
  });
  it("uses a div without onSubmit and can be an alertdialog", () => {
    ui(<Dialog title="Delete" role="alertdialog" onClose={() => {}}>Body</Dialog>);
    expect(screen.getByRole("alertdialog", { name: "Delete" }).tagName).toBe("DIV");
  });
  it("focuses the first enabled body control and traps Tab in both directions", () => {
    ui(<Dialog title="Edit" onClose={() => {}} footer={<button>Save</button>}><input aria-label="Disabled" disabled /><input aria-label="Quantity" /></Dialog>);
    const input = screen.getByRole("textbox", { name: "Quantity" });
    expect(document.activeElement).toBe(input);
    screen.getByRole("button", { name: "Save" }).focus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Close" }));
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Save" }));
  });
  it("keeps focus inside a busy dialog with no enabled controls", () => {
    ui(<Dialog title="Saving" busy onClose={() => {}}>Body</Dialog>);
    const panel = screen.getByRole("dialog");
    expect(document.activeElement).toBe(panel);
    fireEvent.keyDown(document, { key: "Tab" });
    expect(document.activeElement).toBe(panel);
  });
  it("restores focus to the opener", () => {
    function Example() {
      const [open, setOpen] = useState(false);
      return <><button onClick={() => setOpen(true)}>Open</button>{open && <Dialog title="Edit" onClose={() => setOpen(false)}><input autoFocus aria-label="Quantity" /></Dialog>}</>;
    }
    ui(<Example />);
    const opener = screen.getByRole("button", { name: "Open" });
    opener.focus(); fireEvent.click(opener);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(document.activeElement).toBe(opener);
  });
  it("only closes the top nested dialog and restores focus within the parent", () => {
    function Example() {
      const [nested, setNested] = useState(false);
      return <Dialog title="Parent" onClose={parentClose}><button onClick={() => setNested(true)}>Open child</button>{nested && <Dialog title="Child" onClose={() => setNested(false)}><input aria-label="Child input" /></Dialog>}</Dialog>;
    }
    const parentClose = vi.fn();
    ui(<Example />);
    const opener = screen.getByRole("button", { name: "Open child" });
    fireEvent.click(opener);
    expect(within(screen.getByRole("dialog", { name: "Child" })).getByRole("textbox")).toBe(document.activeElement);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "Child" })).toBeNull();
    expect(parentClose).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(opener);
    expect(document.body.style.overflow).toBe("hidden");
  });
  it("uses the Arabic close label", () => {
    ui(<Dialog title="نتيجة الإنتاج" onClose={() => {}}>المحتوى</Dialog>, "ar");
    expect(screen.getByRole("button", { name: "إغلاق" })).toBeDefined();
  });
});

it("does not submit the parent form from a nested dialog portal", () => {
  const parent = vi.fn(event => event.preventDefault());
  const child = vi.fn(event => event.preventDefault());
  ui(<Dialog title="Parent" onClose={() => {}} onSubmit={parent}>
    <Dialog title="Child" onClose={() => {}} onSubmit={child} footer={<button type="submit">Save child</button>}>Child body</Dialog>
  </Dialog>);
  fireEvent.click(screen.getByRole("button", { name: "Save child" }));
  expect(child).toHaveBeenCalledTimes(1);
  expect(parent).not.toHaveBeenCalled();
});
