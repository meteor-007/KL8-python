# E2E Test Infra: Quant Trading System (KL8-python)

## Test Philosophy
- **Opaque-Box & Requirement-Driven**: Verify system capabilities from the entrypoints down to the output artifacts without coupling to internal hacks.
- **Methodology**: 4-Tier Test Architecture (Category-Partition, Boundary Value Analysis, Pairwise/Cross-Subsystem Combinations, Real-World Workload Testing).
- **Zero-Error Standard**: All 11 daily entrypoints, full pipeline, Excel processing, and test suites must pass with 0 errors and valid output schemas.

## Feature Inventory & Test Coverage
| # | Feature | Source | Tier 1 (Unit/Contract) | Tier 2 (Boundary) | Tier 3 (Cross-Subsystem) | Tier 4 (Workload E2E) |
|---|---------|--------|:----------------------:|:-----------------:|:------------------------:|:---------------------:|
| 1 | Full Pipeline Master Orchestration | ORIGINAL_REQUEST R4 | ✓ | ✓ | ✓ | ✓ (E2E-01) |
| 2 | DoubleLSTM Neural Network | ORIGINAL_REQUEST R4 | ✓ | ✓ | ✓ | ✓ (E2E-02) |
| 3 | Spatial Points Analysis | ORIGINAL_REQUEST R4 | ✓ | ✓ | ✓ | ✓ (E2E-03) |
| 4 | KillSeeker Negative Selection | ORIGINAL_REQUEST R4 | ✓ | ✓ | ✓ | ✓ (E2E-04) |
| 5 | Gemini Pick2 Quant Model | ORIGINAL_REQUEST R4 | ✓ | ✓ | ✓ | ✓ (E2E-05) |
| 6 | Gold Pick2 Decision Engine | ORIGINAL_REQUEST R4 | ✓ | ✓ | ✓ | ✓ (E2E-06) |
| 7 | Repeat & Follow Analysis | ORIGINAL_REQUEST R4 | ✓ | ✓ | ✓ | ✓ (E2E-07) |
| 8 | Formula Jingle Rule Engine | ORIGINAL_REQUEST R4 | ✓ | ✓ | ✓ | ✓ (E2E-08) |
| 9 | Point Suppression Rebound | ORIGINAL_REQUEST R4 | ✓ | ✓ | ✓ | ✓ (E2E-09) |
| 10 | Multi-Dimensional Consensus Aggregator | ORIGINAL_REQUEST R4 | ✓ | ✓ | ✓ | ✓ (E2E-10) |
| 11 | Excel Hot Numbers & Formatter ETL | ORIGINAL_REQUEST R1, R4 | ✓ | ✓ | ✓ | ✓ (E2E-11) |
| 12 | Backend Module Import Integrity | ORIGINAL_REQUEST R1 | ✓ (All modules) | - | - | - |
| 13 | Path Resolution & Directory Layout | ORIGINAL_REQUEST R1, R2 | ✓ | ✓ | - | ✓ |
| 14 | Safe Archiving Validation | ORIGINAL_REQUEST R3 | ✓ | - | - | ✓ |

## Test Architecture
- **Test Runner**: `pytest` running `tests/` and new `tests/e2e/` suites.
- **CLI Runner**: Independent python invocation scripts for all 11 daily entrypoints.
- **Schema & Artifact Assertions**: Validate presence, non-empty size, and JSON/TXT schema for generated artifacts in `outputs/`, `reports/`, `cache/`, `logs/`.

## Real-World Application Scenarios (Tier 4)
| # | Scenario | Features Exercised | Pass Criteria |
|---|----------|--------------------|---------------|
| 1 | `run_full_pipeline.py` Full Cycle | F01, F02, F05, F08, F11, F12 | Exit 0, 8 checkmarks in `reports/daily_analysis_report_*.md`, all subtasks complete |
| 2 | `run_lstm_daily.py` 5-period Backfill | F02, F05, F08, F12 | Exit 0, `outputs/predictions/` and `cache/models/best_model.pt` updated |
| 3 | `run_points_daily.py` + `run_suppression_daily.py` | F03, F05, F08, F12 | Exit 0, `outputs/spatial_points/` and `outputs/point_suppression/` generated |
| 4 | `run_killseeker_daily.py` Diagnosis & Full Run | F05, F06, F08, F12 | Exit 0, `kill_seeker/logs/kill_seeker_latest.json` generated, 0 import errors |
| 5 | `run_pick2_daily.py` + `run_geminixuan2_daily.py` | F05, F08, F12 | Exit 0, valid 2-ball combinations and self-learning state saved |
| 6 | `run_follow_daily.py` + `run_jingle_daily.py` | F05, F08, F12 | Exit 0, 90 rules evaluated, follow predictions output |
| 7 | `run_aggregation_daily.py` Consensus Run | F05, F08, F10, F12 | Exit 0, 7-stream consensus aggregated into `outputs/aggregation/` |
| 8 | Excel ETL (`process_hot_numbers.py` + `apply_formats.py`) | F05, F08, F11, F12 | Exit 0, `跟随+点位+开奖数据.xlsx` formatted without file lock corruption |

## Coverage Thresholds
- Tier 1: ≥20 test cases covering 100% backend modules and core function contracts.
- Tier 2: ≥10 test cases covering boundary data lengths, lock contention, and numerical stability.
- Tier 3: ≥10 test cases covering cross-system consensus, KillSeeker feedback, and ETL flow.
- Tier 4: 11 real-world workload execution validations covering all daily entrypoints.
