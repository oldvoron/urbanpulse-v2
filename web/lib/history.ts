// Local (browser) history of jobs launched from this device.
// There is no real auth yet (see brief §0), so history is deliberately
// localStorage-scoped rather than global — a job's shareable link still
// works for anyone via /analysis/[id].

export interface HistoryEntry {
  jobId: string;
  cityName: string;
  kind: "analyze" | "compare";
  createdAt: string; // ISO
}

const KEY = "urbanpulse.history.v1";

export function listHistory(): HistoryEntry[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(localStorage.getItem(KEY) || "[]");
  } catch {
    return [];
  }
}

export function addHistory(entry: HistoryEntry) {
  if (typeof window === "undefined") return;
  const items = listHistory().filter((e) => e.jobId !== entry.jobId);
  items.unshift(entry);
  localStorage.setItem(KEY, JSON.stringify(items.slice(0, 100)));
}

export function clearHistory() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(KEY);
}
