/**
 * The small pieces of the studio: upload, ingestion report, storm picker, stat readouts.
 *
 * Kept in one file because each is a handful of lines and splitting them into six modules
 * would be filing, not architecture.
 */

import { useRef, useState } from "react";

import type { Report, Storm } from "../lib/api";
import { count, eur } from "../lib/format";

export function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "hot" | "huge";
}) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className={`stat-value${tone ? ` ${tone}` : ""}`}>{value}</div>
    </div>
  );
}

export function PortfolioUpload({
  onFile,
  onSample,
  busy,
}: {
  onFile: (file: File) => void;
  onSample: () => void;
  busy: boolean;
}) {
  const [over, setOver] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  return (
    <div className="panel">
      <div className="panel-title">
        <span className="eyebrow">1 — Exposure</span>
      </div>
      <div
        className={`dropzone${over ? " over" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          const file = e.dataTransfer.files?.[0];
          if (file) onFile(file);
        }}
        onClick={() => input.current?.click()}
      >
        <input
          ref={input}
          type="file"
          accept=".csv,text/csv"
          hidden
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) onFile(file);
            e.target.value = "";
          }}
        />
        Drop an OED location CSV
        <div style={{ color: "var(--text-faint)", fontSize: 11, marginTop: 4 }}>
          or click to browse
        </div>
      </div>
      <button
        className="btn"
        style={{ width: "100%", marginTop: "0.6rem" }}
        onClick={onSample}
        disabled={busy}
      >
        {busy ? <span className="spinner" /> : "Load the sample book"}
      </button>
    </div>
  );
}

export function IngestionReport({ report, name }: { report: Report; name: string }) {
  // Collapsed by default. "493 of 500 loaded, seven rejected" is the line that lands; the
  // per-row detail is the proof you pull up when someone asks which seven and why. Keeping it
  // folded also keeps the storm picker above the fold, so the demo never has to scroll to
  // find its next step.
  const [expanded, setExpanded] = useState(false);
  const clean = report.n_errors === 0 && report.n_warnings === 0;
  return (
    <div className="panel">
      <div className="panel-title">
        <span className="eyebrow">Ingestion</span>
        <span className="mono" style={{ fontSize: 11, color: "var(--text-faint)" }}>
          {name}
        </span>
      </div>

      <div className="mono" style={{ fontSize: 13, marginBottom: "0.75rem" }}>
        {count(report.loaded)}
        <span style={{ color: "var(--text-faint)" }}>/{count(report.total_rows)}</span> loaded
        {report.n_errors > 0 && (
          <span className="sev sev-error" style={{ marginLeft: 8 }}>
            {report.n_errors} error{report.n_errors > 1 ? "s" : ""}
          </span>
        )}
        {report.n_warnings > 0 && (
          <span className="sev sev-warning" style={{ marginLeft: 6 }}>
            {report.n_warnings} warning{report.n_warnings > 1 ? "s" : ""}
          </span>
        )}
      </div>

      {clean ? (
        <div style={{ fontSize: 12, color: "var(--text-dim)" }}>
          Every row usable. Unusual for a real bordereau.
        </div>
      ) : (
        <>
          {expanded && (
          <div className="scroll-cap">
          <table className="issues">
            <thead>
              <tr>
                <th>Location</th>
                <th>Issue</th>
              </tr>
            </thead>
            <tbody>
              {report.issues.map((issue, i) => (
                <tr key={`${issue.row}-${i}`}>
                  <td className="id">
                    <span className={`sev sev-${issue.severity}`}>{issue.severity[0]}</span>{" "}
                    {issue.loc_id}
                  </td>
                  <td>
                    {issue.message}
                    <div style={{ color: "var(--text-faint)", fontSize: 10 }}>{issue.field}</div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
          )}
          <button
            className="btn-ghost"
            style={{ width: "100%", marginTop: expanded ? "0.5rem" : 0 }}
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? "Hide detail" : `Which ${report.issues.length} rows, and why?`}
          </button>
        </>
      )}
    </div>
  );
}

export function StormPicker({
  storms,
  selected,
  onSelect,
  busy,
}: {
  storms: Storm[];
  selected: string | null;
  onSelect: (slug: string) => void;
  busy: boolean;
}) {
  return (
    <div className="panel">
      <div className="panel-title">
        <span className="eyebrow">2 — Scenario</span>
        {busy && <span className="spinner" />}
      </div>
      {storms.length === 0 ? (
        <div className="notice">
          No storms loaded. Run <span className="mono">scripts/seed_placeholder_storms.py</span>{" "}
          or the XWS converter.
        </div>
      ) : (
        storms.map((s) => (
          <button
            key={s.slug}
            className="storm-btn"
            aria-pressed={selected === s.slug}
            onClick={() => onSelect(s.slug)}
            disabled={busy}
          >
            <div className="nm">{s.name}</div>
            <div className="yr">
              {s.year}
              {s.event_date ? ` · ${s.event_date}` : ""}
            </div>
          </button>
        ))
      )}
    </div>
  );
}

export function PortfolioSummary({
  nLocations,
  totalTiv,
}: {
  nLocations: number;
  totalTiv: number;
}) {
  return (
    <div className="panel" style={{ display: "flex", gap: "1.5rem" }}>
      <div style={{ flex: 1 }}>
        <div className="stat-label">Locations</div>
        <div className="mono" style={{ fontSize: "1.15rem" }}>
          {count(nLocations)}
        </div>
      </div>
      <div style={{ flex: 1 }}>
        <div className="stat-label">Total TIV</div>
        <div className="mono" style={{ fontSize: "1.15rem" }}>
          {eur(totalTiv)}
        </div>
      </div>
    </div>
  );
}
