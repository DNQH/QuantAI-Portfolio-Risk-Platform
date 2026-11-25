# QuantAI Data Sources, Permissions & Licensing ($0 Stack vs. Paid Tiers)

All provider permissions below were verified against official documentation as of November 2026. QuantAI never hardcodes API keys, never silently downgrades `LIVE` requests, and never claims universal real-time global coverage.

## 1. Official Provider Verification ($0 Free Stack)

| Provider | Official Docs | Authentication | Verified Free-Tier Permissions | Verified Limitations & Licensing | QuantAI Status Tag |
|---|---|---|---|---|---|
| **Finnhub** | [finnhub.io/docs/api](https://finnhub.io/docs/api) | Free `FINNHUB_API_KEY` | 60 calls/min (30/s burst); US `/quote`, `/search`, `/stock/symbol`, `/stock/market-status`, `/stock/market-holiday`, and WebSocket `wss://ws.finnhub.io` (1 concurrent connection/key) for real-time US trades. | Historical `/stock/candle` OHLCV and international exchanges require paid plans. Personal/development use on free tier. | `LIVE` (during open US session & fresh &le;120s), else `DELAYED` / `HISTORICAL` |
| **SSI FastConnect Data (API v2)** | [guide.ssi.com.vn](https://guide.ssi.com.vn/ssi-products/fastconnect-data) | SSI trading account + FC Data registration (one-year term); `SSI_CONSUMER_ID` & `SSI_CONSUMER_SECRET` (`POST api/v2/Market/AccessToken`, Bearer JWT) | Last matched trade from `Market/IntradayOhlc` (tick-level) and daily history from `Market/DailyOhlc` for HOSE/HNX/UPCOM. SignalR streaming (`X-TRADE`/`X-QUOTE`) is not used yet. Fees: confirm with SSI. | Requires an approved SSI account; unconfigured credentials return `DATA_UNAVAILABLE`. Illiquid symbols with no recent trade are reported `DELAYED`. | `LIVE` when the last trade is ≤ 3 min old during the session |
| **Vnstock v6** | [vnstocks.com/docs/vnstock/v6](https://vnstocks.com/docs/vnstock/v6) | Open-source Python client (`vnstock>=6.0`) + user Open API keys | Vietnam HOSE/HNX/UPCOM historical OHLCV, intraday board, index constituents, ICB sectors, corporate actions via VCI/TCBS/SSI/DNSE. | Historical/intraday snapshots are not treated as verified real-time streaming unless backed by broker stream. | `HISTORICAL` (OHLCV) / `DELAYED` (quotes) |
| **Frankfurter v2** | [frankfurter.dev](https://frankfurter.dev/) | None required (open-source, self-hostable) | 219 currencies (including all 15 QuantAI target currencies + VND) from 112 central banks & official sources; daily history since 1948. | Official daily reference midpoints only — **not** live FX dealing quotes and no bid/ask spreads. | `DAILY_REFERENCE` (always) |
| **Yahoo Finance (`yfinance`)** | Unofficial open-source library | None (reverse-engineered endpoints) | Broad historical EOD OHLCV coverage across US and global equities. | Unpublished rate limits, periodic breakage, 15–20m delayed quotes; **strictly educational/personal research** (commercial redistribution barred under Yahoo terms). | `HISTORICAL` / `DELAYED` (never `LIVE`) |

## 2. What Operates on $0 vs. What Requires Paid Subscriptions or Extra Credentials

### Operates Immediately on $0 (with free keys / local packages)
- **US Equities (NYSE, NASDAQ):** Live US quotes & WebSocket trade streaming (Finnhub free key); historical EOD OHLCV via explicitly labeled `yfinance` educational fallback.
- **Vietnam Equities (HOSE, HNX):** Historical OHLCV and reference metadata via Vnstock v6; effective-dated HNX-to-HOSE (December 28, 2026) exchange mapping.
- **Global FX (15 Target Currencies):** Daily reference rates and currency conversion via Frankfurter v2 (no API key required).
- **Core Platform Infrastructure:** SQLite persistence, exchange calendars (DST, holidays, lunch breaks), freshness state machine, and Market Data Coverage matrix.

### Requires Additional Credentials or Paid Subscriptions
- **Verified Real-Time Vietnam Streaming (`LIVE`):** Requires an SSI trading account and a FastConnect Data registration; configure the ConsumerID / ConsumerSecret as `SSI_CONSUMER_ID` / `SSI_CONSUMER_SECRET` (fees: confirm with SSI).
- **Licensed Historical US/Global OHLCV (Non-`yfinance`):** Requires a paid provider such as [EODHD](https://eodhd.com/pricing) ($19.99+/mo), [Twelve Data](https://twelvedata.com/news/march-2026-updates) ($79+/mo, student discount available), or [Massive](https://qveris.ai/guides/polygon-pricing-optimized) ($29–$199/mo for US).
- **Real-Time European, Asian, ASEAN & Australian Equities (Phase 7):** Requires paid exchange-licensed feeds (EODHD / Twelve Data) and commercial display licenses if deployed publicly.
- **Live Intraday FX Dealing Quotes (Bid/Ask):** Requires paid FX streaming tiers rather than Frankfurter v2 daily central-bank reference rates.
