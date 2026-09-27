export function isReadOnlyStatus(status: string) {
  return status === "cancelled" || status === "completed";
}

export function formatStatus(status: string) {
  return status.replace("_", " ");
}
