# Phase 5: Trade Simulation Engine - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md - this log preserves the alternatives considered.

**Date:** 2026-04-02
**Phase:** 05-trade-simulation-engine
**Areas discussed:** entry trigger, fill model, position management, exit and stop policy

---

## Entry trigger

| Option | Description | Selected |
|--------|-------------|----------|
| Immediate entry | Enter as soon as the Phase 4 setup event is emitted | x |
| Confirmation-based entry | Wait for an extra rejection or continuation-failure confirmation from BBO data | |

**User's choice:** Immediate entry
**Notes:** User asked to follow the model as closely as possible in the current repo, but preferred not to wait for extra confirmation in Phase 5.

---

## Fill model

| Option | Description | Selected |
|--------|-------------|----------|
| BBO-side fills with zero extra slippage | Fill on the quoted side of the book with no additional slippage buffer | x |
| BBO-side fills plus configured slippage | Apply spread-crossing and extra impact buffer | |
| Simpler trade-price proxy | Ignore quoted side and fill at a simpler derived price | |

**User's choice:** No slippage in the simulated prop-firm environment
**Notes:** The resulting context keeps quoted-side fills when available but sets additional slippage to zero.

---

## Position management

| Option | Description | Selected |
|--------|-------------|----------|
| One live position, skip overlaps | Ignore any new setup while a trade is active | x |
| Queue deferred setups | Hold later setups for entry after the active trade exits | |
| Allow overlapping positions | Permit multiple concurrent trades | |

**User's choice:** Only one live position
**Notes:** User explicitly rejected overlapping live positions.

---

## Exit and stop policy

| Option | Description | Selected |
|--------|-------------|----------|
| Daily VWAP target plus configurable fixed stop | Simple MVP baseline that matches the roadmap and avoids pretending to know the optimum | x |
| Multi-target exit logic | Add weekly VWAP or developing POC targets now | |
| Optimized stop chosen up front | Pick the "most profitable" threshold before backtesting | |

**User's choice:** "Whatever you think would be most profitable"
**Notes:** Since profitability cannot be known honestly before running the backtest, the captured decision is to use daily VWAP as the primary target and a configurable fixed stop as a documented baseline rather than a claimed optimum.

---

## the agent's Discretion

- Exact default commission amount.
- Exact fixed stop distance used as the initial baseline.
- Additional diagnostic outputs attached to each simulated trade.

## Deferred Ideas

- Continuation-failure confirmation belongs to Phase 9.
- Multi-target exits belong to later strategy-integration work.
- Slippage sensitivity testing can be added later if the research goal expands beyond the requested simulated-prop baseline.
