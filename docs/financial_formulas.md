# QuantAI Financial Formulas & Methodology (v4.1.0)

All formulas implemented in `backend/app/analytics/` follow established institutional conventions. Defaults are explicit and configurable via API parameters.

## 1. Return Calculations
- **Simple Return:** $r_t = \frac{P_t - P_{t-1}}{P_{t-1}}$
- **Logarithmic Return:** $r^{\log}_t = \ln\left(\frac{P_t}{P_{t-1}}\right)$
- **Cumulative Return:** $R_{\text{cum}}(t) = \prod_{i=1}^{t}(1 + r_i) - 1 = \frac{P_t}{P_0} - 1$
- **Annualized Return (CAGR):** $R_{\text{ann}} = \left(1 + R_{\text{cum}}\right)^{N / T} - 1$, where $N$ is the annualization factor and $T$ is the number of return observations.
- **Annualization factor $N$ (v4.1):** explicit `periods_per_year` if supplied; otherwise by interval (`1d` = 252, `1wk` = 52, `1mo` = 12); otherwise (e.g. intraday) inferred empirically as $N = (n - 1) / (\text{calendar days} / 365.25)$. Portfolio backtests always use the empirical calendar frequency of the aligned dates (≈252 for US, ≈250 for Vietnam, 365 for 7-day calendars) and measure CAGR in calendar years.

## 2. Volatility & Risk-Adjusted Metrics
- **Sample Volatility (Annualized):** $\sigma_{\text{ann}} = s_r \cdot \sqrt{N}$, where $s_r$ is the sample standard deviation (`ddof=1`).
- **Sharpe Ratio:** $\text{Sharpe} = \frac{\bar{r} \cdot N - R_f}{\sigma_{\text{ann}}}$, where $R_f$ is the annualized risk-free rate (default `0.0` unless specified by the user). Returns `null` when the dispersion is numerical noise ($s_r \le 10^{-10} \max|r_t|$); previously a constant series produced Sharpe ≈ $10^{16}$.
- **Sortino Ratio:** $\text{Sortino} = \frac{\bar{r} \cdot N - R_f}{\sigma_{\text{down}} \cdot \sqrt{N}}$, where $\sigma_{\text{down}} = \sqrt{\frac{1}{T}\sum_{t=1}^{T}\min(0, r_t - r_{f,\text{daily}})^2}$ (semi-deviation below the daily MAR/risk-free threshold).
- **Drawdown Series:** $DD_t = \frac{P_t - \max_{0 \le s \le t} P_s}{\max_{0 \le s \le t} P_s} \le 0$. Missing / non-finite prices repeat the previous drawdown value and never reset the running peak.
- **Maximum Drawdown:** $\text{MDD} = \min_t DD_t$. Recovery period counts trading bars from the trough until price regains the prior peak (or `null` if unrecovered).

## 3. Trend, Momentum & Volatility Indicators
- **Simple Moving Average (SMA$_k$):** $\frac{1}{k}\sum_{i=0}^{k-1} P_{t-i}$ for $t \ge k - 1$.
- **Exponential Moving Average (EMA$_k$):** $\alpha = \frac{2}{k+1}$, $\text{EMA}_t = \alpha P_t + (1 - \alpha)\text{EMA}_{t-1}$.
- **RSI (14, Wilder's Smoothing):** Initial average gain/loss over first 14 price differences, then $\overline{G}_t = \frac{13 \overline{G}_{t-1} + G_t}{14}$ and $\overline{L}_t = \frac{13 \overline{L}_{t-1} + L_t}{14}$. If $\overline{L}_t = 0$ and $\overline{G}_t > 0$, $\text{RSI} = 100$; if both are $0$, $\text{RSI} = 50$; otherwise $\text{RSI} = 100 - \frac{100}{1 + \overline{G}_t/\overline{L}_t}$.
- **MACD (12, 26, 9):** $\text{MACD} = \text{EMA}_{12} - \text{EMA}_{26}$, $\text{Signal} = \text{EMA}_9(\text{MACD})$, $\text{Histogram} = \text{MACD} - \text{Signal}$.
- **Rate of Change (ROC$_k$):** $\frac{P_t - P_{t-k}}{P_{t-k}} \times 100$.
- **Bollinger Bands (20, 2σ):** $\text{Middle} = \text{SMA}_{20}$, $\text{Upper/Lower} = \text{SMA}_{20} \pm 2 \cdot \sigma_{20,\text{sample}}$ (`ddof=1`, explicitly documented).
- **Average True Range (ATR 14):** $\text{TR}_t = \max(H_t - L_t, |H_t - C_{t-1}|, |L_t - C_{t-1}|)$, smoothed via Wilder's 14-period recursion. (v4.1) $H$, $L$, $C$ are all expressed on the adjusted basis $X^{adj}_t = X_t \cdot \frac{C^{adj}_t}{C_t}$; mixing raw highs/lows with adjusted closes produced spurious True-Range spikes at every split/dividend.

## 4. Distribution & Multi-Asset Statistics
- **Skewness & Excess Kurtosis:** Unbiased Fisher-Pearson sample skewness and Fisher excess kurtosis (`scipy.stats.skew(..., bias=False)` and `scipy.stats.kurtosis(..., fisher=True, bias=False)`).
- **Correlation & Covariance Matrices:** Computed on inner-joined common trading dates across assets using daily simple returns; covariance is annualized by multiplying daily sample covariance (`ddof=1`) by $N = 252$.

- **Ledoit-Wolf shrinkage (v4.1):** $\hat\Sigma_{LW} = (1-\delta) S + \delta\,\mu I$, $\mu = \operatorname{tr}(S)/N$, with the analytic optimal intensity $\delta \in [0,1]$ (Ledoit & Wolf, 2004; identical estimator to `sklearn.covariance.ledoit_wolf`). Used automatically by the optimizer (`covariance_method="auto"`) when $T \le N$ or $\kappa(S) > 10^8$; can be forced with `"ledoit_wolf"`.

## 5. Risk Management (VaR / CVaR)
All figures are reported as positive loss fractions of portfolio value for confidence $\alpha$ and horizon $T$ days.
- **Parametric (Normal):** $\text{VaR} = z_\alpha \sigma\sqrt{T} - \mu T$, $\text{ES} = \sigma\sqrt{T}\,\frac{\varphi(z_\alpha)}{1-\alpha} - \mu T$ (sample mean and `ddof=1` std of daily returns).
- **Historical:** $\text{VaR} = -Q_{1-\alpha}(\tilde r)$ (linear interpolation) on horizon-scaled returns $\tilde r_t = \mu T + (r_t - \mu)\sqrt{T}$ (v4.1: drift scales with $T$ consistently with the parametric method; for $T = 1$ this is the raw empirical distribution).
- **Expected Shortfall estimator (historical & Monte Carlo, v4.1):** Acerbi-Tasche $\widehat{\text{ES}} = -\frac{1}{n a}\left[\sum_{i=1}^{k} x_{(i)} + (n a - k)\,x_{(k+1)}\right]$, $a = 1 - \alpha$, $k = \lfloor n a \rfloor$ — always averages exactly the worst $a$ probability mass.
- **Monte Carlo (Normal):** seeded `numpy.random.default_rng(seed)` draws from $N(\mu T, \sigma^2 T)$; same quantile / ES estimators as above.
- **Input hygiene:** non-finite returns (and the aligned benchmark observations) are dropped and reported; returns below −100 % are rejected; ≥ 10 finite observations required; confidence levels validated in (0.5, 1).

## 6. Portfolio Optimization
- **Efficient frontier (v4.1):** target returns span $[\mu_{GMV},\ \mu_{\max}]$ where $\mu_{\max} = \max_w \{ w^\top\mu : \mathbf 1^\top w = 1,\ w_{\min} \le w_i \le w_{\max} \}$ is solved as a linear program. (Previously the upper target was $\max_i \mu_i$, which is infeasible whenever $w_{\max} < 1$, so most frontier points were silently dropped.) Non-converged points are reported in `optimizer_warnings`.
- **Max-Sharpe:** multi-start SLSQP (equal weight and GMV starts); non-convergence falls back to equal weight and is reported.
- **FX attribution:** $(1 + r_{base}) = (1 + r_{local})(1 + r_{fx})$; both inputs validated $\ge -100\%$.

## 7. Backtesting
- **Single asset:** signal at close $t-1$ is executed at close $t$ (T+1) with commission and slippage. The Buy-and-Hold benchmark is filled under the identical T+1 execution and cost model (v4.1; it was previously filled one bar earlier).
- **Multi-asset portfolio (v4.1, no look-ahead):** for `min_variance` / `max_sharpe`, the first $\min(252, \max(30, n/4))$ returns form an estimation-only warm-up; weights are re-estimated at every rebalance from the trailing 252 returns known at that close (walk-forward). Rebalancing happens on the first trading day of each new calendar quarter / year. Transaction costs $= (c + s)\sum_i |\Delta h_i|$ on the full traded notional (buys + sells), including the initial purchase, for both the portfolio and the equal-weight benchmark. Calendar-year return of year $y$ is measured from the last close of $y-1$ (when inside the window) to the last close of $y$.
- **Forward scenarios (v4.1):** log-normal paths $W_T = W_0 \exp(gT + \sigma\sqrt{T}Z)$ with $g = \ln(1 + \text{CAGR}_{shrunk})$, $\text{CAGR}_{shrunk} = \text{clip}(0.75 \cdot \text{CAGR}_{hist}, -5\%, 16\%)$. Because CAGR is already a geometric (median) rate, no further $-\sigma^2/2$ drag is applied (the previous formula double-counted it, biasing every percentile down by ≈ $\sigma^2/2$ per year).

## 8. Corporate Credit Models
- **Altman Z (1968):** $Z = 1.2\,X_1 + 1.4\,X_2 + 3.3\,X_3 + 0.6\,X_4 + 1.0\,X_5$ (unchanged).
- **Ohlson O-Score (1980):** standard 9-factor coefficients; (v4.1) $\text{SIZE} = \ln(\text{TA}_{USD} / \text{GNP price index})$ with index (1968 = 100) ≈ 626 and $\text{TA}_{USD}$ converted with approximate reference FX rates. Previously $\ln(\text{TA}/1000)$ in reporting-currency units shifted the O-score by ≈ 4.1 for VND-reporting firms.
- **Merton (naive, Bharath & Shumway 2008, v4.1):** $F = 0.75\,D$, $V = E + F$, $\sigma_D = 0.05 + 0.25\,\sigma_E$, $\sigma_V = \frac{E}{V}\sigma_E + \frac{F}{V}\sigma_D$, $DD = \frac{\ln(V/F) + (r - \sigma_V^2/2)T}{\sigma_V\sqrt T}$, $PD = N(-DD)$. The previous $\sigma_V = \sigma_E E/V$ treated debt as riskless and understated PD for levered firms.
- **Ratio guards (v4.1):** ratios with a zero denominator are capped (e.g. interest coverage and DSCR at 999×) instead of dividing by one currency unit; logistic PD mappings use a numerically stable sigmoid (debt-free firms previously raised `OverflowError` → HTTP 500).
- Altman / DSCR / Interest-Coverage PD mappings are monotone logistic heuristics, not empirically calibrated default frequencies.

## Assumptions & Limitations
- Calculations assume adjusted closing prices when corporate actions (splits/dividends) are present.
- Intraday observations are never mixed with end-of-day observations without explicit interval separation.
- Historical volatility, Sharpe, and Sortino ratios are backward-looking descriptors and do not guarantee future performance.
