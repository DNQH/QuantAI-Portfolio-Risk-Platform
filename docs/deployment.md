# Deploying QuantAI to the web

QuantAI ships as **one Docker container** that serves both the FastAPI backend and the
built React UI on a single port, so the deployed app has exactly one public URL
(e.g. `https://quantai.onrender.com`). Any host that runs a Dockerfile works; this guide
uses **Render** because the repository already contains a Render Blueprint (`render.yaml`).

## What is in the image

| Piece | Where | Notes |
|---|---|---|
| React UI | `/` and `/assets/*` | Built in a Node stage; hashed assets cached for a year, `index.html` never cached |
| API | `/api/v1/*` | Same origin as the UI, so no CORS setup is needed |
| Health check | `/api/v1/health` | Used by Docker `HEALTHCHECK` and Render |
| Database | SQLite at `/data/quantai.db` | **Ephemeral** unless a persistent disk is mounted at `/data` |
| Market data | yfinance (installed via `requirements-deploy.txt`) | Labelled "educational fallback", never LIVE |

The server listens on `$PORT` (set automatically by Render/Railway/Cloud Run), runs as a
non-root user, and trusts `X-Forwarded-For` from the platform's proxy so rate limits are
applied per real visitor IP.

## Option A — Render (Blueprint)

1. Sign in at <https://render.com> with your GitHub account.
2. **New → Blueprint**, pick the `QuantAI-Portfolio-Risk-Platform` repository, branch `main`.
3. Render reads `render.yaml` and asks for the secret values. All are optional; any market
   without a key falls back to yfinance and shows **DELAYED** in *Market Data Coverage*:

   | Variable | Unlocks |
   |---|---|
   | `GEMINI_API_KEY` | AI portfolio assistant |
   | `FINNHUB_API_KEY` | **LIVE** status for NYSE / NASDAQ |
   | `TWELVEDATA_API_KEY` | Backup source for historical daily bars when yfinance has none (does **not** make non-US markets LIVE) |
   | `EODHD_API_KEY` | Reserved for a future paid real-time adapter; currently unused |
   | `SSI_CONSUMER_ID` + `SSI_CONSUMER_SECRET` | **LIVE** status for HOSE / HNX / UPCOM (SSI trading account + FastConnect Data registration) |

   LSE, Xetra, TSE, HKEX, SGX and ASX always show **DELAYED**: their quotes come from yfinance,
   and the badge only says LIVE when the app really has a real-time quote source.

   Keys can also be added or changed later under the service's **Environment** tab
   (saving triggers a redeploy).
4. Click **Apply** / **Deploy**. The first build takes a few minutes; progress is in the
   service's **Logs** tab. The log line
   `QuantAI API initialized (... env=production, ui=on, rate_limit=on)` means it is up.
5. Open the `https://<service-name>.onrender.com` URL shown at the top of the service page.

Every push to `main` redeploys automatically (`autoDeploy: true`).

> Free-tier web services on Render can spin down when idle, so the first visit after a
> quiet period may take a while to load. Check Render's current plan limits before relying
> on it; they change over time.

## Option B — any Docker host

```bash
docker build -t quantai .
docker run -d -p 8000:8000 \
  -e GEMINI_API_KEY=your-key \
  -v quantai-data:/data \
  quantai
# open http://localhost:8000
```

## Configuration

All settings are environment variables (see `.env.example`). Those relevant to a public
deployment:

| Variable | Default in image | Purpose |
|---|---|---|
| `QUANTAI_ENV` | `production` | Turns rate limiting on by default |
| `QUANTAI_FRONTEND_DIST` | `/app/frontend/dist` | Serve the UI from the API process (unset = API only) |
| `QUANTAI_DB_PATH` | `/data/quantai.db` | SQLite location |
| `QUANTAI_RATE_LIMIT_ENABLED` | on in production | Force rate limiting on/off |
| `QUANTAI_RATE_LIMIT_PER_MINUTE` | `240` | All `/api` calls, per client IP |
| `QUANTAI_RATE_LIMIT_HEAVY_PER_MINUTE` | `20` | Simulations, backtests, forecasts, sentiment, credit, tracker |
| `QUANTAI_ASSISTANT_PER_MINUTE` | `6` | Gemini assistant, per client IP |
| `QUANTAI_ASSISTANT_DAILY_BUDGET` | `200` | Gemini assistant, **all visitors combined**, per UTC day |
| `GEMINI_API_KEY`, `FINNHUB_API_KEY`, `TWELVEDATA_API_KEY`, `EODHD_API_KEY`, `SSI_CONSUMER_ID`, `SSI_CONSUMER_SECRET` | unset | Optional provider keys (see table above); set them as host secrets, never in Git |

A value of `0` disables a limit. Throttled requests get HTTP `429` with a `Retry-After`
header and a human-readable `detail` message that the UI displays.

## Limitations to know before sharing the link

* **No authentication.** Anyone with the URL can use every feature. The rate limits keep a
  single visitor from exhausting the server or your Gemini quota, but they are not access
  control.
* **Limits are per process.** The image runs one worker; if you scale to several
  instances each enforces its own limits (use a shared store such as Redis for that).
* **Saved portfolios are lost on redeploy** unless `/data` is on a persistent disk.
* **yfinance from cloud IPs** can be throttled or blocked by Yahoo; the app then reports
  missing data rather than inventing prices.
