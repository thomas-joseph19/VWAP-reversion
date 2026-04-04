# Phase 09: Continuation Failure & Strategy Integration - Discussion Log

**Date:** 2026-04-03
**Phase:** 09 (continuation-failure-rejection)

## Q&A Audit Trail

### Multi-Target & Contracts
**Q: How do we handle scaling out and multi-contract support?**
- **Options presented:** Multi-contract (2 units) with split exits vs. Single unit with percentage exits.
- **User Selection:** "sure multi contract but do whatever you think best"
- **Decision:** Implemented as a 2-unit system with separate targets and break-even stop logic after T1.

### Rejection & Scoring
**Q: How do we define rejection and score confluence?**
- **the agent's Discretion:** Defined mandatory rejection gate based on 60s failure-to-make-new-high + displacement. Introduced 100-point confluence scoring system weighting sigma, structure, and alignment.
- **Rationale:** Aligns with professional orderflow-style reversion systems that wait for a "shift" in momentum rather than just a price level touch.

## Deferred Ideas
None.
