"use client";

// Export row shown under a completed analysis: GeoJSON / Shapefile / PDF /
// copy shareable link.

import { useState } from "react";
import { exportDataUrl, getReport } from "@/lib/api";

export default function ExportBar({
  jobId,
  cityName,
}: {
  jobId: string;
  cityName: string;
}) {
  const [pdfBusy, setPdfBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");

  const downloadPdf = async () => {
    setPdfBusy(true);
    setError("");
    try {
      const blob = await getReport(jobId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `urbanpulse_${cityName.replace(/, /g, "_").replace(/ /g, "_").toLowerCase()}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "PDF failed");
    } finally {
      setPdfBusy(false);
    }
  };

  const copyLink = async () => {
    const url = `${window.location.origin}/analysis/${jobId}`;
    await navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="panel p-3 flex flex-wrap items-center gap-2">
      <span className="stat-label mr-2">Export</span>
      <a className="btn-ghost" href={exportDataUrl(jobId, "geojson")}>
        GeoJSON
      </a>
      <a className="btn-ghost" href={exportDataUrl(jobId, "shapefile")}>
        Shapefile
      </a>
      <button className="btn-ghost" onClick={downloadPdf} disabled={pdfBusy}>
        {pdfBusy ? "Rendering PDF… (30–60s)" : "PDF Report"}
      </button>
      <button className="btn-ghost" onClick={copyLink}>
        {copied ? "Link copied ✓" : "Copy share link"}
      </button>
      {error && <span className="text-xs text-accent-risk font-mono">{error}</span>}
    </div>
  );
}
