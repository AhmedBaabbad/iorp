/**
 * The notification messages (PROJECT-UX-NOTIFY), kept outside React so the API client can announce a finished action:
 * every save, change, sending or decision tells the user what happened, in the screen's language.
 *
 * A message is either a text (a screen's own words) or an action key of common.notify, translated when shown. The API
 * client's automatic message after a change is "soft": a screen that says something more precise right after replaces
 * it, so the user never reads two messages for one click.
 */
export type NoteKind = "success" | "error" | "info";
export type Note = { id: number; kind: NoteKind; text?: string; action?: string; soft?: boolean; at: number };

let notes: Note[] = [];
let nextId = 1;
const listeners = new Set<(notes: Note[]) => void>();
const DURATION: Record<NoteKind, number> = { success: 4500, info: 5000, error: 8000 };
const REPLACES_WITHIN_MS = 3000;

function emit() {
  listeners.forEach((l) => l(notes));
}

export function subscribe(listener: (notes: Note[]) => void): () => void {
  listeners.add(listener);
  listener(notes);
  return () => { listeners.delete(listener); };
}

export function dismiss(id: number) {
  notes = notes.filter((n) => n.id !== id);
  emit();
}

function add(note: Omit<Note, "id" | "at">): number {
  const id = nextId++, at = Date.now();
  // A screen's own message replaces the automatic one sent for the same click; an automatic one never doubles another.
  if (!note.soft) notes = notes.filter((n) => !(n.soft && at - n.at < REPLACES_WITHIN_MS));
  else if (notes.some((n) => at - n.at < REPLACES_WITHIN_MS && n.kind === "success")) return 0;
  notes = [...notes.slice(-3), { ...note, id, at }];  // at most four at once
  emit();
  if (typeof window !== "undefined") window.setTimeout(() => dismiss(id), DURATION[note.kind]);
  return id;
}

/** Shows a message of the screen's own. Returns its id. */
export function pushNote(kind: NoteKind, text: string): number {
  return add({ kind, text });
}

/** Shows the standard message of a done action (common.notify.<action>); `soft` when sent automatically. */
export function pushAction(action: string, soft = false): number {
  return add({ kind: "success", action, soft });
}

const SKIP = /\/(auth|login|logout|refresh|forgot-password|preview[\w-]*|lookup)(\/|$)/;
const ACTIONS: Record<string, string> = {
  approve: "approve", reject: "reject", confirm: "confirm", issue: "issue", release: "release", close: "close", cancel: "cancel",
  reopen: "reopen", decide: "decide", "lot-decision": "decide", "return-decision": "decide", complete: "complete", revoke: "revoke",
  revise: "revise", accept: "accept", expire: "expire", start: "start", hold: "hold", resume: "resume", execute: "execute",
  archive: "archive", activate: "activate", deactivate: "deactivate", lock: "lock", unlock: "unlock", verify: "verify",
  "verify-effectiveness": "verify", "effectiveness-review": "verify", contain: "contain", containment: "contain",
  investigate: "investigate", investigation: "investigate", dispatch: "dispatch", deliver: "deliver", receive: "receive",
  "fail-delivery": "fail", reschedule: "reschedule", ready: "ready", plan: "plan", allocations: "allocate", allocate: "allocate",
  reorder: "reorder", settings: "settings", "quote-settings": "settings", "quality-settings": "settings", logo: "logo",
  permissions: "permissions", roles: "roles", "reset-password": "resetPassword", "change-password": "passwordChanged",
  attachments: "upload", submit: "submit", send: "send", "send-to-production": "transfer", transfer: "transfer", "link-user": "link",
  link: "link", map: "link", measurements: "measure", evaluate: "evaluate", evaluations: "evaluate", communications: "communicate",
  responses: "response", "follow-ups": "note", followups: "note", refer: "refer", "refer-to-quality": "refer", corrections: "record",
  entries: "record", record: "record", assign: "assign", "assign-owner": "assign", standard: "create",
};
const LOOKS_LIKE_ID = /^([0-9a-f]{8}-[0-9a-f-]{27,}|\d+)$/i;

/** The action a successful change stands for, from its method and address; null when there is nothing to announce. */
export function actionOf(method: string, path: string): string | null {
  const clean = path.split("?")[0].replace(/\/+$/, "");
  if (SKIP.test(clean)) return null;
  const segment = clean.split("/").pop() ?? "";
  if (method === "DELETE") return "delete";
  if (ACTIONS[segment]) return ACTIONS[segment];
  if (method === "PUT" || method === "PATCH") return "update";
  return LOOKS_LIKE_ID.test(segment) ? "save" : "create";
}
