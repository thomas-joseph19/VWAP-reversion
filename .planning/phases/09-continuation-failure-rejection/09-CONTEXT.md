# Phase 09: Continuation Failure & Strategy Integration - Context

**Gathered:** 2026-04-03
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase upgrades the setup detector with price-action-based rejection filters and confluence scoring, and modifies the simulation engine to support multi-contract entries with sequential exit targets (Daily, Weekly, Monthly VWAP).

</domain>

<decisions>
## Implementation Decisions

### Continuation Failure (Rejection) Logic
- **D-01: Mandatory Gate.** Rejection is a prerequisite for trade emission. A "setup candidate" is identified by Phase 4 logic, but a "trade signal" is only emitted if price action confirms rejection.
- **D-02: Mechanical Rejection Definition.** 
    - **Failure:** N seconds (default 60) without a new extreme (high for shorts, low for longs) after the setup candidate becomes active.
    - **Displacement:** Price must then move M ticks (default 8 ticks / 2 points) away from the extreme in the direction of the trade to confirm the "rejection."
    - **Timeout:** If the setup candidate remains active for T seconds (default 300) without confirming rejection, the setup is canceled.

### Confluence Scoring
- **D-03: Weighted Scoring (0-100).** Instead of binary filters, setups carry a confluence score.
    - **Sigma (40%):** Scaled between 1.7σ (0 pts) and 3.0σ+ (40 pts).
    - **Structure (40%):** 20 pts per unique structural level "hit" within proximity (Daily VAH/VAL/POC, Overnight VA, HTF Balance Area).
    - **Alignment (20%):** 10 pts per alignment with HTF VWAP (Weekly/Monthly) where price is on the correct side for reversion.
- **D-04: Minimum Threshold.** A default score threshold of 40 is required to trigger a trade signal.

### Multi-Target Trade Management
- **D-05: Multi-Unit Simulator.** The simulator will now track positions by unit count (default 2 units).
- **D-06: Exit Hierarchy.**
    - **Target 1 (50%):** Exit 1 contract at the nearest logical reversion level (usually Daily VWAP).
    - **Target 2 (50%):** Exit 2nd contract at a secondary level (Weekly VWAP or far Structural level).
- **D-07: Stop-Loss Management.** When Target 1 is hit, the Stop-Loss for the remaining unit is automatically adjusted to **Break-even (Entry Price + Slippage)**.

### the agent's Discretion
- **D-08: Default N/M values.** The agent is authorized to tune the rejection time window (N) and displacement threshold (M) based on standard NQ volatility if research suggests better defaults.
- **D-09: Score Weighting.** The agent can adjust the relative weights of Sigma vs. Structure if implementation reveals data-density issues (e.g., too many levels crowding scores).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Strategy & Requirements
- `.planning/REQUIREMENTS.md` §SGNL-04, SGNL-05, TSIM-06 — Core strategy integration requirements.
- `.planning/ROADMAP.md` §Phase 9 — Implementation goal and sequence.

### Precursor Indicators
- `src/vwap_revert/indicators/setup_detection.py` — Current Phase 4 event logic to be extended.
- `src/vwap_revert/simulation.py` — Replay engine to be upgraded to multi-contract.

</canonical_refs>
