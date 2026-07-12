"use client";

// Past jobs launched from this browser (localStorage job ids — deliberately
// local until real auth exists; see brief §4.3).

import { useEffect, useState } from "react";
import Link from "next/link";
import { clearHistory, listHistory, HistoryEntry } from "@/lib/history";

export default function HistoryPage() {
  const [items, setItems] = useState<HistoryEntry[]>([]);
  useEffect(() => setItems(listHistory()), []);

  return (
    <main className="mx-auto max-w-3xl px-4 py-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="font-mono text-sm uppercase tracking-widest text-ink-dim">
          Analysis History
        </h1>
        {items.length > 0 && (
          <button
            className="btn-ghost !text-xs"
            onClick={() => {
              clearHistory();
              setItems([]);
            }}
          >
            Clear
          </button>
        )}
      </div>
      {items.length === 0 ? (
        <div className="panel p-8 text-center text-sm text-ink-dim">
          No analyses yet from this browser.{" "}
          <Link href="/" className="text-accent-transport">
            Run one →
          </Link>
          <p className="text-[11px] text-ink-faint mt-2">
            History is stored locally until accounts are live.
          </p>
        </div>
      ) : (
        <div className="panel divide-y divide-edge">
          {items.map((e) => (
            <Link
              key={e.jobId}
              href={`/analysis/${e.jobId}`}
              className="flex items-center justify-between px-4 py-3 hover:bg-panel-2 transition-colors"
            >
              <div>
                <div className="text-sm text-ink">{e.cityName}</div>
                <div className="font-mono text-[10px] text-ink-faint">
                  {e.kind} · {new Date(e.createdAt).toLocaleString()}
                </div>
              </div>
              <span className="text-ink-faint text-xs font-mono">open →</span>
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}
