# Engineering log: what broke while building this, and what changed

Written because the failures taught more than the successes. Each item was found by a test, an eval or an independent check.

1. **Planted signal drowned by noise.** First generated data gave Meta ROAS -4.6% instead of the intended ~-18% because random
   weekly pacing swamped the planted effect. Reduced noise and strengthened the scenario, then confirmed against an independent
   pandas calculation before building on it. *Lesson: validate the benchmark before trusting results on it.*
2. **Unrealistic economics.** Blended ROAS of 4.3 (brand search 21x) would make any reviewer distrust the data. Calibrated
   conversion rates (`CVR_SCALE`) to ~2.6 blended.
3. **Metric-chain validation bug.** The registry's own validator rejected my ROAS driver chain; my "telescoping" check
   assumed one ordering. Replaced with an order-independent product check.
4. **Funnel tool cried wolf (three layers).**
   - Many segment x stage tests at p<0.01 produced false positives -> Bonferroni correction.
   - A landing page was flagged for receiving lower-intent traffic (YouTube) -> compare against a traffic-mix-adjusted expectation.
   - Then *every mobile segment* was flagged (mobile always converts lower) -> stratify by campaign **and** device.
   - Still anti-conservative because the "expected" rate is itself estimated -> add its variance. Final false-alarm rate on
     defect-free runs: 1 in 30 (consistent with the ~1% family-wise target; reported, not hidden).
5. **Optimizer recommended +30% on Brand Search.** Correct under the model (highest marginal ROAS) but wrong as business
   advice: brand search captures existing demand, so last-click ROAS overstates incrementality. Added an explicit, documented
   hold-flat policy rather than hiding it, and corrected my own misleading scenario description.
6. **R^2 is the wrong confidence rule.** Held back 7/10 campaigns on noisy weekly data. Switched to a slope t-statistic and a
   longer window; bootstrap interval reported with every uplift figure.
7. **Money-parsing bug.** "$50,000 marketing budget" parsed as $50 billion ("m" in "marketing" read as a million suffix).
   Regression test added.
8. **Rounding broke a limit.** Rounding to cents pushed a campaign to +30.003% (limit 30%); then my fix re-rounded it back
   out. Now clamps inward and puts the cent remainder on a campaign with headroom.
9. **100% on my own benchmark meant little.** The interpretation benchmark was tuned alongside the rules. A held-out set,
   scored once before any change, gave **65%** (all misses safe refusals). One round of fixes -> 96%, reported as no longer held-out.
10. **A claim I had to retract.** I expected naive averaging of daily ROAS to be materially wrong; measured: median 0.9%,
    max 8.2% (low-volume campaigns). The test and report now say exactly that.
11. **`make` silently ate the budget.** `make ask Q='...$50,000...'` lets make expand `$5`, so the question reached the agent
    without an amount and it (correctly) asked for clarification. Found by trying the documented command, not by a test. Docs now
    show the CLI with single quotes for dollar amounts. *Lesson: run every command in the README exactly as written.*
