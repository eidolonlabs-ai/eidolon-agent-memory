# Benchmark Score Summary

## Current Status: April 20, 2026

### Executive Summary
The memory system's **retrieval is strong** (0.856 PASS) and **graceful omission is perfect** (1.0 PASS), but **extraction quality is the bottleneck** limiting roundtrip performance. The system never inappropriately surfaces sensitive content, but misses ~36% of emotionally-salient facts during extraction.

---

## Latest Run Scores

**Timestamp**: 2026-04-20T05:05:04Z

### EMBER Benchmark (Primary)
| Tier | Aspect | Score | Threshold | Status | Notes |
|------|--------|-------|-----------|--------|-------|
| **Tier 1** | Extraction Quality | 0.6429 | 0.80 | ✗ FAIL | Salience-weighted: HIGH 62%, MED 67%, LOW 80% |
| **Tier 2** | Retrieval Quality | 0.8562 | 0.75 | ✓ PASS | Strong semantic search + ranking |
| **Tier 2b** | Graceful Omission | 1.0000 | 0.75 | ✓ PASS | Perfect: never surfaces crisis content |
| **Tier 3** | Roundtrip (E→R) | 0.4521 | 0.60 | ✗ FAIL | Limited by Tier 1 extraction losses |

### Supporting Benchmarks
- **LOCOMO** (5-question QA): F1 = 0.3168
- **LongMemEval** (25-query): Accuracy = 0.4800 (12/25)

---

## Detailed Tier 1 Breakdown

### Extraction Quality (0.6429)
12 conversations, 58 total facts, 38 successfully extracted

**By Emotional Salience**:
```
HIGH (Grief, Loss, Trauma):     18/29 found (62%)
                                11 facts missed
                                
MED (Milestones, Events):       16/24 found (67%)
                                8 facts missed
                                
LOW (Preferences, Trivia):      4/5 found (80%)
                                1 fact missed
```

**Weighted Salience Score**: 0.6429
- HIGH misses cost 3x more than MED
- MED misses cost 1.5x more than LOW

---

## Trend Analysis

### Historical Progression
| Date | Tier 1 | Tier 2 | Tier 3 | Status |
|------|--------|--------|--------|--------|
| 2026-04-18 | 0.593 | 0.856 | 0.442 | Baseline |
| 2026-04-19 | 0.607 | 0.856 | 0.406 | Stable extraction |
| 2026-04-20 | 0.643 | 0.856 | 0.452 | +5.9% extraction |

**Key Insight**: Retrieval and graceful omission are consistently stable. Extraction shows improvement but still below target.

---

## Performance by Metric

### Strong Areas ✓
1. **Retrieval (0.856 PASS)**: Vector search and ranking working well
2. **Graceful Omission (1.0 PASS)**: Never inappropriately surfaces sensitive facts
3. **Tier 2b Consistency**: Perfect score maintained across all runs

### Improvement Areas ✗
1. **HIGH Salience Recall (62%)**: Missing trauma/loss/grief facts
2. **MED Salience Recall (67%)**: Missing milestone and event facts
3. **Roundtrip Integration (0.452)**: Limited by extraction bottleneck

---

## Improvement Strategy

### Priority 1: Extraction Quality
**Goal**: Increase Tier 1 from 0.643 → 0.80+
- Enhance fact extraction prompt to better capture emotional salience markers
- Implement second-pass refinement for missed HIGH/MED facts
- Add explicit patterns for common grief/loss/breakup scenarios

### Priority 2: Roundtrip
**Goal**: Increase Tier 3 from 0.452 → 0.60+
- Will improve automatically as Tier 1 improves (extraction→retrieval pipeline)
- Verify ranking doesn't degrade extracted facts

### Priority 3: Supporting Benchmarks
- LOCOMO (0.3168): May require context-specific ranking adjustments
- LongMemEval (0.4800): Long-context retention strategy refinement

---

## Artifact Locations

Latest results available at:
- **EMBER Full**: `docs/evals/artifacts/ember_20260420T050504Z.json`
- **LOCOMO**: `docs/evals/artifacts/locomo_20260420T050348Z.json`
- **LongMemEval**: `docs/evals/artifacts/longmemeval_20260420T050357Z.json`

Complete history: `docs/evals/BENCHMARK_RUN_TRACKER.md`

---

## How to Re-run Benchmarks

### Quick Check (30s)
```bash
docker compose up -d --build
sleep 10
python scripts/evals/run_memory_benchmarks.py --server-url http://localhost:3100
```

### Full Suite (with extraction)
```bash
LOCOMO_EXTRACT_FACTS=1 LONGMEMEVAL_EXTRACT_FACTS=1 \
  python scripts/evals/run_memory_benchmarks.py --server-url http://localhost:3100
```

Results automatically saved to `docs/evals/artifacts/` with UTC timestamp.

---

## Interpretation Guide

### Score Meanings
- **0.8-1.0**: PASS — Good enough for production use
- **0.6-0.8**: MARGINAL — Acceptable but room for improvement
- **<0.6**: FAIL — Requires optimization

### Tier Definitions
- **Tier 1**: Can we extract facts accurately?
- **Tier 2**: Can we retrieve facts accurately?
- **Tier 2b**: Do we avoid surfacing sensitive content inappropriately?
- **Tier 3**: Can we extract → retrieve reliably end-to-end?

### Why Roundtrip is Lower
Tier 3 combines Tier 1 extraction losses with retrieval. If extraction gets 64% of facts, retrieval can only work with those 64% even if perfect. Tier 3 threshold (0.60) is lower than Tier 1 (0.80) to account for this compounding effect.

---

## Updated: 2026-04-20 05:05:04 UTC
