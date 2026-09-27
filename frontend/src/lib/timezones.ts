export function listTimezones(): string[] {
  try {
    return Intl.supportedValuesOf("timeZone");
  } catch {
    return ["UTC", "Asia/Riyadh", "Africa/Cairo", "Europe/London", "America/New_York"];
  }
}

export const TIMEZONES = listTimezones();

export function timezoneLabel(timezone: string): string {
  try {
    const offset = new Intl.DateTimeFormat("en-US", { timeZone: timezone, timeZoneName: "shortOffset" })
      .formatToParts(new Date())
      .find((part) => part.type === "timeZoneName")?.value;
    return offset ? `${timezone} (${offset})` : timezone;
  } catch {
    return timezone;
  }
}
