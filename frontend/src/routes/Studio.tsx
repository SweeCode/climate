/**
 * The tool. Left rail is exposure and scenario, centre is the map, right rail is the wedge.
 *
 * All state is held here and passed down, because there are exactly four things to track
 * (portfolio, storm, scenario, what-if) and a state library would be more code than the
 * problem has.
 */

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { AccumulationMap } from "../components/AccumulationMap";
import {
  IngestionReport,
  PortfolioSummary,
  PortfolioUpload,
  Stat,
  StormPicker,
} from "../components/Panels";
import { WhatIfPanel } from "../components/WhatIfPanel";
import {
  ApiError,
  type Portfolio,
  type Scenario,
  type Storm,
  type WhatIf,
  forgetPortfolio,
  getAccessCode,
  getPortfolio,
  lastPortfolioId,
  listStorms,
  rememberPortfolio,
  runScenario,
  setAccessCode,
  uploadPortfolio,
  whatIf,
} from "../lib/api";
import { eur, pct } from "../lib/format";

const SAMPLE_BOOK = "/api/samples/demo_book_oed.csv";
const SAMPLE_ACCOUNT = "/api/samples/candidate_account_oed.csv";

export function Studio() {
  const [storms, setStorms] = useState<Storm[]>([]);
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [stormSlug, setStormSlug] = useState<string | null>(null);
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [impact, setImpact] = useState<WhatIf | null>(null);

  const [busy, setBusy] = useState<"" | "upload" | "scenario" | "whatif">("");
  const [error, setError] = useState<string | null>(null);
  const [locked, setLocked] = useState(false);

  useEffect(() => {
    listStorms()
      .then(setStorms)
      .catch((e) => {
        if (e instanceof ApiError && e.status === 401) setLocked(true);
        else setError(describe(e));
      });

    // Reload the last book. Persisting the portfolio is the entire reason there is a
    // database behind this; losing it on refresh would make the storage pointless.
    const last = lastPortfolioId();
    if (last !== null) {
      getPortfolio(last)
        .then(setPortfolio)
        .catch(() => forgetPortfolio()); // gone, or another tenant's — just start clean
    }
  }, []);

  // Both entry points below call this directly rather than reacting to state, because an
  // effect that retries whenever `scenario` is null spins forever the moment a run fails.
  const runFor = useCallback(async (portfolioId: number, slug: string) => {
    setBusy("scenario");
    setError(null);
    try {
      setScenario(await runScenario(portfolioId, slug));
    } catch (e) {
      setError(describe(e));
    } finally {
      setBusy("");
    }
  }, []);

  const load = useCallback(
    async (file: File | Blob, name: string) => {
      setBusy("upload");
      setError(null);
      try {
        const result = await uploadPortfolio(file, name);
        setPortfolio(result);
        rememberPortfolio(result.id);
        // A new book invalidates everything computed against the old one.
        setScenario(null);
        setImpact(null);
        setBusy("");
        if (stormSlug) await runFor(result.id, stormSlug);
      } catch (e) {
        setError(describe(e));
        setBusy("");
      }
    },
    [stormSlug, runFor],
  );

  const selectStorm = useCallback(
    async (slug: string) => {
      setStormSlug(slug);
      setImpact(null);
      setScenario(null);
      if (portfolio) await runFor(portfolio.id, slug);
    },
    [portfolio, runFor],
  );

  const runWhatIf = useCallback(
    async (csvText: string, accountName: string) => {
      if (!portfolio || !stormSlug) return;
      setBusy("whatif");
      setError(null);
      try {
        setImpact(await whatIf(portfolio.id, stormSlug, csvText, accountName));
      } catch (e) {
        setError(describe(e));
      } finally {
        setBusy("");
      }
    },
    [portfolio, stormSlug],
  );

  if (locked) return <AccessGate onUnlock={() => window.location.reload()} />;

  const storm = storms.find((s) => s.slug === stormSlug) ?? null;
  const lossRatio =
    scenario && scenario.total_tiv > 0 ? (scenario.total_net / scenario.total_tiv) * 100 : 0;

  return (
    <div className="studio">
      <aside className="rail">
        <div className="rail-head">
          <Link to="/" style={{ textDecoration: "none" }}>
            <div className="wordmark">
              Climate<span>.</span>
            </div>
          </Link>
          <div className="eyebrow" style={{ marginTop: 2 }}>
            Windstorm accumulation
          </div>
        </div>

        <PortfolioUpload
          busy={busy === "upload"}
          onFile={(file) => void load(file, file.name)}
          onSample={async () => {
            const res = await fetch(SAMPLE_BOOK);
            await load(await res.blob(), "Demo book — European property");
          }}
        />

        {portfolio && (
          <>
            <PortfolioSummary
              nLocations={portfolio.n_locations}
              totalTiv={portfolio.total_tiv}
            />
            <IngestionReport report={portfolio.report} name={portfolio.name} />
          </>
        )}

        <StormPicker
          storms={storms}
          selected={stormSlug}
          busy={busy === "scenario"}
          onSelect={(slug) => void selectStorm(slug)}
        />

        {storm && (
          <div className="panel" style={{ borderBottom: "none" }}>
            <div className="eyebrow" style={{ marginBottom: 6 }}>
              Footprint provenance
            </div>
            <div style={{ fontSize: 11, color: "var(--text-dim)", lineHeight: 1.45 }}>
              {storm.notes && <p style={{ margin: "0 0 0.5rem" }}>{storm.notes}</p>}
              <div style={{ color: "var(--text-faint)" }}>{storm.source}</div>
              <div style={{ color: "var(--text-faint)" }}>{storm.licence}</div>
            </div>
          </div>
        )}
      </aside>

      <div className="map-wrap">
        <AccumulationMap
          exposure={portfolio?.locations ?? []}
          losses={scenario?.locations ?? null}
          candidate={impact?.locations ?? null}
          storm={storm}
        />
        <div className="map-overlay">
          {storm && (
            <div className="legend">
              <div className="eyebrow" style={{ marginBottom: 4 }}>
                Gust · 3s max
              </div>
              <div className="legend-bar" />
              <div className="legend-scale">
                <span>20 m/s</span>
                <span>35</span>
                <span>50+</span>
              </div>
            </div>
          )}
          <div className="attrib">
            v1 indicative model — losses are not calibrated to claims experience. Demo
            environment: do not upload live client data.
            <br />
            Basemap © CARTO, © OpenStreetMap contributors.
          </div>
        </div>
      </div>

      <aside className="rail rail-right">
        <div className="rail-head" style={{ display: "flex", justifyContent: "space-between" }}>
          <span className="eyebrow">Scenario result</span>
          {scenario && (
            <span className="mono" style={{ fontSize: 10, color: "var(--text-faint)" }}>
              {scenario.compute_ms.toFixed(1)} ms
            </span>
          )}
        </div>

        {error && (
          <div className="panel">
            <div className="notice error">{error}</div>
          </div>
        )}

        {scenario ? (
          <div className="panel">
            <Stat label={`${scenario.storm_name} — net loss`} value={eur(scenario.total_net)} tone="hot" />
            <Stat label="Ground-up loss" value={eur(scenario.total_ground_up)} />
            <Stat label="Loss ratio on TIV" value={pct(lossRatio)} />
          </div>
        ) : (
          <div className="panel">
            <div className="notice">
              {portfolio
                ? "Pick a storm to place it over the book."
                : "Load a book to begin. The sample is synthetic — no client data."}
            </div>
          </div>
        )}

        <WhatIfPanel
          disabled={!scenario}
          disabledReason="Run a storm over the book first — the marginal impact is measured against that result."
          busy={busy === "whatif"}
          result={impact}
          onRun={(csv, name) => void runWhatIf(csv, name)}
          onLoadSample={async () => (await fetch(SAMPLE_ACCOUNT)).text()}
          onClear={() => setImpact(null)}
        />
      </aside>
    </div>
  );
}

function AccessGate({ onUnlock }: { onUnlock: () => void }) {
  const [code, setCode] = useState(getAccessCode());
  return (
    <div className="gate grid-ground">
      <div className="gate-card">
        <div className="wordmark" style={{ marginBottom: "0.25rem" }}>
          Climate<span>.</span>
        </div>
        <div className="eyebrow" style={{ marginBottom: "1.5rem" }}>
          Private demo
        </div>
        <label className="stat-label" htmlFor="code">
          Access code
        </label>
        <input
          id="code"
          type="password"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              setAccessCode(code);
              onUnlock();
            }
          }}
          style={{ marginTop: "0.4rem" }}
        />
        <button
          className="btn-primary"
          style={{ width: "100%", marginTop: "0.75rem" }}
          onClick={() => {
            setAccessCode(code);
            onUnlock();
          }}
        >
          Enter
        </button>
      </div>
    </div>
  );
}

function describe(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  return e instanceof Error ? e.message : String(e);
}
