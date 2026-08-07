/**
 * The wedge, on screen: what does binding this account do to my storm loss?
 *
 * The visual argument is the delta bar — the book you already hold, hatched and static, with
 * the candidate's contribution stacked on the end in chartreuse. An underwriter reads
 * "how much bigger did I just make my worst day" in one glance, which is the actual decision.
 */

import { useRef, useState } from "react";

import type { WhatIf } from "../lib/api";
import { eur, pct } from "../lib/format";

type Props = {
  disabled: boolean;
  disabledReason: string;
  busy: boolean;
  result: WhatIf | null;
  onRun: (csvText: string, accountName: string) => void;
  onLoadSample: () => Promise<string>;
  onClear: () => void;
};

export function WhatIfPanel({
  disabled,
  disabledReason,
  busy,
  result,
  onRun,
  onLoadSample,
  onClear,
}: Props) {
  const [csv, setCsv] = useState("");
  const [name, setName] = useState("Candidate account");
  const input = useRef<HTMLInputElement>(null);

  async function readFile(file: File) {
    setCsv(await file.text());
    setName(file.name.replace(/\.csv$/i, ""));
  }

  return (
    <>
      <div className="panel">
        <div className="panel-title">
          <span className="eyebrow">3 — Bind or decline</span>
          {busy && <span className="spinner" />}
        </div>

        {disabled ? (
          <div className="notice">{disabledReason}</div>
        ) : (
          <>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              style={{ marginBottom: "0.5rem" }}
              aria-label="Account name"
            />
            <textarea
              rows={5}
              value={csv}
              placeholder="Paste the submission's OED rows, or drop a CSV below"
              onChange={(e) => setCsv(e.target.value)}
            />
            <div style={{ display: "flex", gap: "0.4rem", marginTop: "0.5rem" }}>
              <button
                className="btn-ghost"
                onClick={() => input.current?.click()}
                style={{ flex: 1 }}
              >
                Open CSV
              </button>
              <button
                className="btn-ghost"
                style={{ flex: 1 }}
                onClick={async () => {
                  setCsv(await onLoadSample());
                  setName("Newco Logistics");
                }}
              >
                Sample account
              </button>
              <input
                ref={input}
                type="file"
                accept=".csv,text/csv"
                hidden
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) void readFile(file);
                  e.target.value = "";
                }}
              />
            </div>
            <button
              className="btn-primary"
              style={{ width: "100%", marginTop: "0.5rem" }}
              disabled={!csv.trim() || busy}
              onClick={() => onRun(csv, name)}
            >
              What does this add?
            </button>
          </>
        )}
      </div>

      {result && <WhatIfResult result={result} onClear={onClear} />}
    </>
  );
}

function WhatIfResult({ result, onClear }: { result: WhatIf; onClear: () => void }) {
  const before = result.portfolio_net_before;
  const after = result.portfolio_net_after;
  // Guard the degenerate case where the book itself takes no loss under this storm.
  const addedShare = after > 0 ? Math.max(0.02, result.delta_net / after) : 0;

  return (
    <div className="panel">
      <div className="panel-title">
        <span className="eyebrow">Marginal impact</span>
        <button className="btn-ghost" style={{ padding: "0.2rem 0.5rem" }} onClick={onClear}>
          Clear
        </button>
      </div>

      <div className="stat">
        <div className="stat-label">Loss this account adds</div>
        <div className="stat-value huge">{eur(result.delta_net)}</div>
      </div>

      <div className="delta-bar" role="img" aria-label="Portfolio loss before and after binding">
        <div className="before" style={{ width: `${(1 - addedShare) * 100}%` }} />
        <div className="added" style={{ width: `${addedShare * 100}%` }} />
      </div>
      <div
        className="mono"
        style={{
          display: "flex",
          justifyContent: "space-between",
          fontSize: 10,
          color: "var(--text-faint)",
        }}
      >
        <span>book {eur(before)}</span>
        <span style={{ color: "var(--candidate)" }}>+{pct(result.pct_increase)}</span>
      </div>

      <div style={{ marginTop: "0.75rem" }}>
        <Row label="Storm loss if you bind" value={eur(after)} />
        <Row label="Account TIV" value={eur(result.candidate_tiv)} />
        <Row label="Locations in the account" value={String(result.locations.length)} />
        <Row label="Computed in" value={`${result.compute_ms.toFixed(2)} ms`} />
      </div>

      {(result.report.n_errors > 0 || result.report.n_warnings > 0) && (
        <div className="notice" style={{ marginTop: "0.75rem" }}>
          {result.report.loaded}/{result.report.total_rows} submission rows usable —{" "}
          {result.report.n_errors} error(s), {result.report.n_warnings} warning(s). The impact
          above excludes unusable rows.
        </div>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "baseline",
        gap: "1rem",
        padding: "0.3rem 0",
        borderBottom: "1px solid var(--line)",
      }}
    >
      <span className="stat-label">{label}</span>
      <span className="mono" style={{ fontSize: 13 }}>
        {value}
      </span>
    </div>
  );
}
