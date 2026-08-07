/**
 * Typed client for the underwriting API.
 *
 * Two headers carry all the session state there is: a shared demo access code, and a
 * per-browser tenant id so two prospects clicking the same demo link never see each other's
 * uploads. Neither is authentication — see the note in backend/app/config.py.
 */

export type Storm = {
  slug: string;
  name: string;
  year: number;
  event_date: string | null;
  notes: string | null;
  bounds: [number, number, number, number];
  source: string;
  licence: string;
};

export type Issue = {
  row: number;
  loc_id: string;
  field: string;
  severity: "error" | "warning";
  message: string;
};

export type Report = {
  total_rows: number;
  loaded: number;
  n_errors: number;
  n_warnings: number;
  issues: Issue[];
};

export type Loc = { loc_id: string; lon: number; lat: number; tiv: number };

export type Portfolio = {
  id: number;
  name: string;
  n_locations: number;
  total_tiv: number;
  report: Report;
  locations: Loc[];
};

export type LocLoss = Loc & { gust_ms: number; ground_up: number; net: number };

export type Scenario = {
  storm_slug: string;
  storm_name: string;
  n_locations: number;
  total_tiv: number;
  total_ground_up: number;
  total_net: number;
  locations: LocLoss[];
  compute_ms: number;
};

export type WhatIf = {
  account_name: string;
  storm_slug: string;
  report: Report;
  candidate_tiv: number;
  delta_ground_up: number;
  delta_net: number;
  portfolio_net_before: number;
  portfolio_net_after: number;
  pct_increase: number;
  locations: LocLoss[];
  compute_ms: number;
};

const TENANT_KEY = "climate.tenant";
const CODE_KEY = "climate.accessCode";

function tenantId(): string {
  let id = localStorage.getItem(TENANT_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(TENANT_KEY, id);
  }
  return id;
}

export function getAccessCode(): string {
  return localStorage.getItem(CODE_KEY) ?? "";
}

export function setAccessCode(code: string): void {
  localStorage.setItem(CODE_KEY, code);
}

function headers(extra: Record<string, string> = {}): Record<string, string> {
  return { "X-Tenant-Id": tenantId(), "X-Access-Code": getAccessCode(), ...extra };
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function unwrap<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* non-JSON error body; the status text will do */
    }
    throw new ApiError(detail, res.status);
  }
  return res.json() as Promise<T>;
}

const LAST_PORTFOLIO_KEY = "climate.lastPortfolio";

export function rememberPortfolio(id: number): void {
  localStorage.setItem(LAST_PORTFOLIO_KEY, String(id));
}

export function forgetPortfolio(): void {
  localStorage.removeItem(LAST_PORTFOLIO_KEY);
}

export function lastPortfolioId(): number | null {
  const raw = localStorage.getItem(LAST_PORTFOLIO_KEY);
  const id = raw ? Number(raw) : NaN;
  return Number.isFinite(id) ? id : null;
}

export async function listStorms(): Promise<Storm[]> {
  return unwrap(await fetch("/api/storms", { headers: headers() }));
}

export async function getPortfolio(id: number): Promise<Portfolio> {
  return unwrap(await fetch(`/api/portfolios/${id}`, { headers: headers() }));
}

export function footprintUrl(slug: string): string {
  return `/api/storms/${encodeURIComponent(slug)}/footprint.png`;
}

export async function uploadPortfolio(file: File | Blob, name: string): Promise<Portfolio> {
  const form = new FormData();
  form.append("file", file, name);
  form.append("name", name);
  return unwrap(await fetch("/api/portfolios", { method: "POST", headers: headers(), body: form }));
}

export async function runScenario(portfolioId: number, stormSlug: string): Promise<Scenario> {
  return unwrap(
    await fetch(`/api/portfolios/${portfolioId}/scenario`, {
      method: "POST",
      headers: headers({ "Content-Type": "application/json" }),
      body: JSON.stringify({ storm_slug: stormSlug }),
    }),
  );
}

export async function whatIf(
  portfolioId: number,
  stormSlug: string,
  csvText: string,
  accountName: string,
): Promise<WhatIf> {
  return unwrap(
    await fetch(`/api/portfolios/${portfolioId}/what-if`, {
      method: "POST",
      headers: headers({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        storm_slug: stormSlug,
        csv_text: csvText,
        account_name: accountName,
      }),
    }),
  );
}
