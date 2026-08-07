# Go-to-market

Everything here is a **hypothesis to falsify on calls**, not a finding. Nothing in this
document has been tested against a real buyer yet. The point of writing it down is that a
hypothesis you have written down can be proved wrong; one you carry around in your head
quietly bends to fit whatever the last conversation said.

Companion to `docs/PLAN.md` (what we build) — this is who pays for it and why.

---

## 1. The wedge, in the buyer's words

> "A submission lands at 10am. I have to price it by lunchtime. I know roughly where my
> Rhine-Ruhr aggregate is because I looked at the spreadsheet in January. I do not know what
> *this* account does to it, and by the time the cat team could tell me the broker has bound
> it elsewhere."

We answer that question in the time it takes to read the submission. That is the entire
product. Everything else — dashboards, event response, probabilistic curves — is a fall-out
of the same engine and should not be sold first.

**What we are explicitly not selling:** Solvency II capital numbers, regulatory filings, or a
replacement for Verisk Touchstone / Moody's-RMS. Their moat is decades of model validation,
and pretending otherwise loses the room with the only people qualified to buy.

---

## 2. Ideal customer profile

### Tier 1 — lead here: MGAs, coverholders, and Lloyd's binder writers

European commercial property, £20m–£150m GWP.

| Why them | |
|---|---|
| **Real pain** | They carry genuine accumulation risk on delegated authority and often find out about it at renewal. |
| **No incumbent** | A full Verisk/RMS licence is impossible to justify against their premium base, so they are not displacing anything — they are filling a hole currently occupied by a spreadsheet. |
| **One buyer** | The active underwriter or head of underwriting decides. No procurement committee, no 9-month enterprise cycle. |
| **Reachable** | Lloyd's publishes its coverholder list; the MGAA member directory is public. This is a nameable, finite target list — build it. |

Expected cycle: **6–12 weeks**. Expected ACV: **€25–60k**.

### Tier 2 — after two Tier 1 references: mid-size continental carriers and regional mutuals

Germany, Netherlands, Nordics, Austria. €50m–€500m GWP property. They have accumulation
obligations and typically buy cat modelling as an annual consultancy engagement. Bigger
deals (€60–150k) but procurement, IT security review, and a DPA — do not start here with
nothing to show.

### Tier 3 — later: reinsurance broker analytics teams

Aon, Gallagher Re, Howden. High value, but they have RMS licences and a habit of building
in-house. Revisit once the product is differentiated by proprietary vulnerability data.

### Anti-ICP — decline politely

Tier-1 global carriers (already have RMS; their requirement genuinely is regulatory-grade),
personal-lines insurers (different problem shape), and anyone whose opening question is about
Solvency II output. Selling into these burns the schedule and produces roadmap demands that
pull the product toward the incumbents' moat.

---

## 3. Pricing hypothesis

**Anchor.** Enterprise cat platform licences reportedly run from the low hundreds of thousands
into seven figures annually. That is the number already in the buyer's head, and it is the
number we are implicitly compared against. *Verify this range with the first five prospects
rather than repeating it — it is second-hand.*

**Position at roughly a tenth of that**, and — more importantly — under the threshold that
forces a board paper. At most MGAs that threshold is somewhere around €50–100k.

| Tier | Seats | Annual |
|---|---|---|
| Desk | 1–3 underwriters | €30,000 |
| Team | 4–10 underwriters | €65,000 |
| Portfolio | Unlimited + API access | €120,000 |

**Design partner terms (first three only):** free for six months, in exchange for (a) real
bordereaux under NDA, (b) a fortnightly hour of feedback, (c) a named reference on conversion.
Convert at 50% for year one, full price at renewal. Cap it at three and say so — scarcity is
real here, because more than three would swamp a small team's ability to act on the feedback.

**Pricing risks to watch for on calls:**
- Per-seat may be wrong. Underwriting teams flex; a per-portfolio or per-bound-account model
  may fit the buyer's mental accounting better. Listen for which unit they instinctively
  reach for when describing cost.
- Anchoring low is hard to undo. €30k is already a "just sign it" number; going lower to win
  the first deal sets a reference price the whole market will hear about, because this market
  talks.

---

## 4. Timing — the European reinsurance calendar

This is the single most actionable thing in this document, and it is time-boxed.

- **Early September — Monte Carlo Rendez-Vous.** The European reinsurance market is in one
  place for three days.
- **October — Baden-Baden.** Same, weighted toward continental European cedants and the
  mid-market. This is closer to the Tier 1 ICP than Monte Carlo is.
- **Q4 — the run-up to 1 January renewals.** Accumulation pain is most acute and budget for
  next year is being set.

A demo that exists in August has a shot at all three. One that exists in November has missed
the window and waits until Q2. **Treat the September date as the deadline the build is
actually working against** — not because a demo booth matters, but because it is the cheapest
possible way to have twenty of these conversations in a week.

---

## 5. Motion

Founder-led outbound. There is no other sensible option pre-revenue, and it is also the only
way to hear the objections firsthand.

1. **Build the named list.** Lloyd's coverholder register + MGAA directory, filtered to
   European property. Target 60 named firms, one named underwriter each.
2. **Warm where possible.** Insurance is a referral market to a degree that is hard to
   overstate. One introduction beats thirty cold emails.
3. **Lead with the question, not the product.** "How do you currently work out what an account
   does to your windstorm aggregate?" Their answer either validates or kills the wedge —
   which is worth more than a demo booking.
4. **The demo is the pitch.** Do not send a deck. Send the URL, or better, screen-share for
   five minutes.
5. **Ask for the bordereau, not the sale.** "Send me a book — anonymised or synthetic — and
   I'll show you your own accumulation next week." Converts a meeting into an evaluation.

**Funnel expectation:** ~60 approaches → ~20 conversations → ~6 demos → **3 design partners.**
If the middle number collapses, the problem is the pitch. If demos do not convert, the problem
is the product.

---

## 6. The five-minute demo script

Matches exactly what is built. Do not improvise beyond it — the parts not built yet are the
parts that will get asked about.

| | Beat | Say |
|---|---|---|
| 0:00 | Load the sample book | "500 locations, the kind of file a coverholder actually sends." |
| 0:30 | **Ingestion report** | "493 loaded. Seven rejected — missing geocodes, a zero TIV, transposed coordinates. It tells you *which rows and why* instead of dropping them quietly. That silence is a mispricing bug." |
| 1:15 | Map | "That's your accumulation. Not a summary of it." |
| 2:00 | **Kyrill** | "January 2007, roughly €4.5bn insured across the market. Watch where it lands — the Ruhr and the Randstad at once. That simultaneity is why windstorm is an accumulation peril." |
| 2:45 | Switch to Lothar | "Same book, completely different answer. Lothar ran across northern France into Baden-Württemberg — your German book barely notices." |
| 3:30 | **The what-if** | "Now the submission on your desk. Twelve logistics sites." *(paste)* |
| 4:00 | The number | "That account adds €X to your Kyrill loss — an N% increase on your worst day. Computed in under a millisecond. That's the decision you're making at 10am, and today you're making it blind." |
| 4:30 | Provenance, unprompted | "Footprints are XWS, open and CC-licensed. The damage curves are v1 and *not* calibrated to your claims — I'll tell you that before you ask, because the number's shape is right and its level is a hypothesis." |

Ending on the honest caveat is deliberate. This audience is professionally suspicious of
confident strangers with loss numbers, and volunteering the weakness buys more credibility
than the demo does.

---

## 7. Objections, with honest answers

**"Whose vulnerability curves are these?"**
A v1 gust-to-damage curve shaped after published European wind damage models. Not calibrated
to your claims. That is the first thing we would fix with you as a design partner, and it is
why we want your loss history more than we want your money right now.

**"Is it validated?"**
No, and it is not a filing tool. Advice at the point of quote carries a different validation
bar than a capital submission. If you need Solvency II numbers, keep your existing platform —
we are not trying to replace it.

**"We already have Touchstone / RMS."**
Good, keep it. How long does a marginal account run take you today, end to end? *(Usually days
to weeks via a cat modelling queue.)* This is for the couple of hundred accounts a year that
never get modelled at all because it isn't worth the queue.

**"25 km resolution is too coarse."**
Correct for site-level precision — and right for portfolio accumulation, which is the question
being asked. The Copernicus 1.6 km product is the documented upgrade path.

**"Our exposure data is confidential."**
Correct, and the public demo is explicitly not for live data — it is gated by a shared code,
which is not authentication. Before any real bordereau moves: proper auth, EU-region hosting,
a DPA, and your security review. Say this before they raise it.

**"What happens if you go under?"**
Fair. Your exposure data is stored in the OED industry standard and exportable at any time;
you are not locked into a proprietary schema. Source escrow is negotiable.

---

## 8. What would falsify this thesis

Write down what you expect to hear, so you notice when you don't.

- **Twenty conversations reveal accumulation is checked at bind, not at quote.** Then the wedge
  is aimed at the wrong moment in the workflow and should move.
- **They already have a fast enough answer** (an in-house tool, a broker who runs it free).
  Then the pain is imagined and the product needs a different job.
- **Everyone asks for Solvency II output in the first meeting.** Then the market will not buy
  advice-grade tooling separately, and the wedge does not exist as a standalone product.
- **They will not share a bordereau even under NDA.** Then the onboarding pitch is dead and the
  data problem is a wall, not a moat.

Any of these is worth finding out in six weeks for the price of some emails.

---

## 9. Open items

- **The name.** "Climate" is a working title and a bad one — it reads as carbon accounting, and
  the product is not about climate change. Fix before the first outbound email; the domain and
  the wordmark are cheap now and expensive later.
- **A real inbox.** `frontend/src/routes/Landing.tsx` still points at a placeholder address.
- **Entity, DPA template, and NDA** before a real bordereau is accepted.
- **Confirm the licence positions with a lawyer** — see the licensing section of
  `docs/PLAN.md`. The AGPL/OpenQuake constraint in particular is load-bearing on architecture.

---

*Author's note: this is written by an engineer, not an insurance professional or a lawyer.
The market structure, price points, and cycle lengths above are informed guesses. Replace each
one with something a real buyer told you as soon as you can.*
