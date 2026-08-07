/**
 * The page a prospect lands on before they ever see the tool.
 *
 * Written for one reader: a European property underwriter or their head of portfolio. It
 * leads with the moment of pain (you are quoting an account and cannot see what it does to
 * your accumulation), states the wedge plainly, and puts real measured numbers on the page
 * rather than adjectives. It does not claim to replace Verisk or Moody's-RMS, because it
 * doesn't, and claiming so is how you lose the room.
 */

import { Link } from "react-router-dom";

const DEMO_EMAIL = "hello@example.com"; // TODO: swap for a real inbox before sending this out.

export function Landing() {
  return (
    <div className="landing grid-ground">
      <div className="landing-inner">
        <nav className="nav">
          <div className="wordmark">
            Climate<span>.</span>
          </div>
          <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
            <span className="eyebrow" style={{ marginRight: "0.5rem" }}>
              European windstorm
            </span>
            <Link to="/app">
              <button className="btn-primary">Open the demo</button>
            </Link>
          </div>
        </nav>

        <header className="hero">
          <div className="rise">
            <div className="eyebrow" style={{ marginBottom: "1.5rem" }}>
              Accumulation control for property underwriters
            </div>
            <h1>
              You are quoting the account now.
              <br />
              Your cat model answers <em>next week</em>.
            </h1>
            <p className="lede">
              Drop a bordereau in, put a real European windstorm over it, and see exactly what
              binding one more account does to your loss — before the quote goes back to the
              broker. Not a capital model. A decision, in the time it takes to read the
              submission.
            </p>
            <div className="hero-actions">
              <Link to="/app">
                <button className="btn-primary">Run a live scenario</button>
              </Link>
              <a href={`mailto:${DEMO_EMAIL}?subject=Design%20partner%20conversation`}>
                <button className="btn">Talk to us</button>
              </a>
            </div>
          </div>

          <dl className="spec rise" style={{ animationDelay: "140ms" }}>
            <div className="spec-row">
              <dt>Full book, one storm</dt>
              <dd>7 ms</dd>
            </div>
            <div className="spec-row">
              <dt>Book size measured</dt>
              <dd>100,000 loc.</dd>
            </div>
            <div className="spec-row">
              <dt>Marginal account impact</dt>
              <dd>0.02 ms</dd>
            </div>
            <div className="spec-row">
              <dt>Onboarding</dt>
              <dd>One CSV</dd>
            </div>
            <div className="spec-row">
              <dt>Exposure standard</dt>
              <dd>OED</dd>
            </div>
          </dl>
        </header>

        <section className="section">
          <div className="eyebrow">The loop</div>
          <h2 style={{ marginTop: "0.75rem" }}>Four steps, no implementation project.</h2>
          <div className="steps">
            <div className="step">
              <div className="n">01</div>
              <h3>Ingest the mess</h3>
              <p>
                Real bordereaux are dirty. Every row that fails is reported with the reason —
                missing geocode, zero TIV, transposed coordinates — instead of being silently
                dropped and quietly mispriced.
              </p>
            </div>
            <div className="step">
              <div className="n">02</div>
              <h3>See the concentration</h3>
              <p>
                Your book on a map, weighted by insured value. The accumulation you are
                carrying, not a spreadsheet summary of it.
              </p>
            </div>
            <div className="step">
              <div className="n">03</div>
              <h3>Put a storm on it</h3>
              <p>
                Kyrill, Lothar, Daria. One extratropical storm hits the Ruhr, the Randstad and
                the North of England at once — which is precisely why windstorm is an
                accumulation peril and not a collection of independent risks.
              </p>
            </div>
            <div className="step">
              <div className="n">04</div>
              <h3>Ask the question</h3>
              <p>
                Paste the submission. See the marginal loss the account adds, where it stacks
                on top of what you already hold, and what your storm loss becomes if you bind
                it.
              </p>
            </div>
          </div>
        </section>

        <section className="section">
          <div className="split">
            <div>
              <div className="eyebrow">What this is not</div>
              <h2 style={{ fontSize: "1.5rem", marginTop: "0.75rem", marginBottom: "1.25rem" }}>
                It is not your capital model.
              </h2>
              <p>
                Solvency II reporting rests on decades of model validation, and that is the
                incumbents' moat — not their user interface. Keep Verisk or Moody's-RMS for the
                filing.
              </p>
              <p>
                This sits earlier, at the desk, where the question is not "what is our 1-in-200"
                but "can I write this and stay inside my line". That question gets answered
                today with judgement and a spreadsheet, because the real model takes a week.
              </p>
            </div>
            <div>
              <div className="eyebrow">Where the numbers come from</div>
              <h2 style={{ fontSize: "1.5rem", marginTop: "0.75rem", marginBottom: "1.25rem" }}>
                Open science, stated plainly.
              </h2>
              <p>
                Hazard footprints come from the XWS catalogue of extreme European windstorms
                (Met Office, Reading, Exeter — CC BY 4.0). Vulnerability is a v1 gust-to-damage
                curve shaped after published European wind damage models.
              </p>
              <div className="callout">
                v1 curves are indicative, not calibrated to your claims. We would rather tell
                you that than have you find out.
              </div>
            </div>
          </div>
        </section>

        <section className="section">
          <div
            style={{
              border: "1px solid var(--line)",
              background: "var(--ink-850)",
              padding: "2.5rem",
              display: "flex",
              justifyContent: "space-between",
              gap: "2rem",
              flexWrap: "wrap",
              alignItems: "center",
            }}
          >
            <div>
              <h2 style={{ fontSize: "1.7rem" }}>Looking for three design partners.</h2>
              <p style={{ color: "var(--text-dim)", margin: "0.75rem 0 0", maxWidth: "52ch" }}>
                European property books, windstorm-exposed. You bring real submissions and tell
                us where the answer is wrong; you get the tool and a direct line to the people
                building it.
              </p>
            </div>
            <a href={`mailto:${DEMO_EMAIL}?subject=Design%20partner%20conversation`}>
              <button className="btn-primary">Start a conversation</button>
            </a>
          </div>
        </section>

        <footer className="foot">
          <div>
            Storm footprints:{" "}
            <a href="https://www.europeanwindstorms.org/" style={{ color: "var(--text-dim)" }}>
              XWS catalogue
            </a>{" "}
            — Roberts et al. (2014), Met Office / University of Reading / University of Exeter,
            CC BY 4.0.
          </div>
          <div>Demo environment. Do not upload live client data.</div>
        </footer>
      </div>
    </div>
  );
}
