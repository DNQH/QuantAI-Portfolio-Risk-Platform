# QuantAI Phase 1 Acceptance Criteria & Verification Matrix

| ID | Requirement | Verification Method | Status |
|---|---|---|---|
| **AC-1** | Modular repository (`frontend/`, `backend/`, `docs/`, `.env.example`, `.gitignore`, `LICENSE`, `README.md`) with zero hardcoded secrets | Directory & config audit + `Settings` env loading | Verified |
| **AC-2** | Exchange-qualified symbology (`MIC:TICKER`) disambiguating cross-exchange collisions (e.g., `XSTC:VNM` vs `XNYS:VNM`) | `TestSymbologyAndMigration.test_ticker_collision_disambiguation_vnm` & `test_unqualified_ticker_rejected` | Verified |
| **AC-3** | Effective-dated HNX-to-HOSE migration (active on `XHAI` through `2026-12-23`, suspended `2026-12-24..25`, active on `XSTC` from `2026-12-28`) | `TestSymbologyAndMigration.test_hnx_to_hose_effective_dated_migration` | Verified |
| **AC-4** | Global exchange calendar handles US DST/holidays and Vietnam lunch break (`11:30–13:00 ICT`) / weekends without misclassifying closures as API errors | `TestExchangeCalendar` | Verified |
| **AC-5** | Strict Freshness State Machine distinguishes `LIVE`, `DELAYED`, `HISTORICAL`, `DAILY_REFERENCE`, and `DATA_UNAVAILABLE` with both `market_timestamp` and `retrieval_timestamp` | `TestFreshnessAndIntegrity` | Verified |
| **AC-6** | Zero silent fallback: requesting `require_live=true` without live credentials returns `DATA_UNAVAILABLE` (never silently falls back to `yfinance` or synthetic data) | `TestProvidersAndFastAPI.test_no_silent_fallback_for_vietnam_live_without_ssi_keys` & `test_websocket_enforces_strict_live_status` | Verified |
| **AC-7** | Frankfurter v2 FX covers all 15 target currencies (`USD..THB`) strictly tagged `DAILY_REFERENCE` | `TestProvidersAndFastAPI.test_fx_reference_rates_and_conversion` | Verified |
| **AC-8** | Market Data Coverage matrix honestly separates Phase 1 active exchanges (`XNYS`, `XNAS`, `XSTC`, `XHAI`) from Phase 7 planned exchanges (`NOT_SUPPORTED`) | `TestProvidersAndFastAPI.test_health_and_coverage_endpoints` | Verified |
| **AC-9** | English-only React + TypeScript + Tailwind UI with extensible `src/i18n/en.ts`, zero API keys in frontend, and honest N/A states for Phase 2–7 modules | Static inspection of `frontend/src/` | Verified |
