# QuantAI Financial Formulas & Methodology (Phase 2)

All formulas implemented in `backend/app/analytics/` follow established institutional conventions. Defaults are explicit and configurable via API parameters.

## 1. Return Calculations
- **Simple Return:** $r_t = \frac{P_t - P_{t-1}}{P_{t-1}}$
- **Logarithmic Return:** $r^{\log}_t = \ln\left(\frac{P_t}{P_{t-1}}\right)$
- **Cumulative Return:** $R_{\text{cum}}(t) = \prod_{i=1}^{t}(1 + r_i) - 1 = \frac{P_t}{P_0} - 1$
- **Annualized Return (CAGR):** $R_{\text{ann}} = \left(1 + R_{\text{cum}}\right)^{N / T} - 1$, where $N = 252$ trading days/year (configurable) and $T$ is the number of return observations.

## 2. Volatility & Risk-Adjusted Metrics
- **Sample Volatility (Annualized):** $\sigma_{\text{ann}} = s_r \cdot \sqrt{N}$, where $s_r$ is the sample standard deviation (`ddof=1`).
- **Sharpe Ratio:** $\text{Sharpe} = \frac{\bar{r} \cdot N - R_f}{\sigma_{\text{ann}}}$, where $R_f$ is the annualized risk-free rate (default `0.0` unless specified by the user).
- **Sortino Ratio:** $\text{Sortino} = \frac{\bar{r} \cdot N - R_f}{\sigma_{\text{down}} \cdot \sqrt{N}}$, where $\sigma_{\text{down}} = \sqrt{\frac{1}{T}\sum_{t=1}^{T}\min(0, r_t - r_{f,\text{daily}})^2}$ (semi-deviation below the daily MAR/risk-free threshold).
- **Drawdown Series:** $DD_t = \frac{P_t - \max_{0 \le s \le t} P_s}{\max_{0 \le s \le t} P_s} \le 0$.
- **Maximum Drawdown:** $\text{MDD} = \min_t DD_t$. Recovery period counts trading bars from the trough until price regains the prior peak (or `null` if unrecovered).

## 3. Trend, Momentum & Volatility Indicators
- **Simple Moving Average (SMA$_k$):** $\frac{1}{k}\sum_{i=0}^{k-1} P_{t-i}$ for $t \ge k - 1$.
- **Exponential Moving Average (EMA$_k$):** $\alpha = \frac{2}{k+1}$, $\text{EMA}_t = \alpha P_t + (1 - \alpha)\text{EMA}_{t-1}$.
- **RSI (14, Wilder's Smoothing):** Initial average gain/loss over first 14 price differences, then $\overline{G}_t = \frac{13 \overline{G}_{t-1} + G_t}{14}$ and $\overline{L}_t = \frac{13 \overline{L}_{t-1} + L_t}{14}$. If $\overline{L}_t = 0$ and $\overline{G}_t > 0$, $\text{RSI} = 100$; if both are $0$, $\text{RSI} = 50$; otherwise $\text{RSI} = 100 - \frac{100}{1 + \overline{G}_t/\overline{L}_t}$.
- **MACD (12, 26, 9):** $\text{MACD} = \text{EMA}_{12} - \text{EMA}_{26}$, $\text{Signal} = \text{EMA}_9(\text{MACD})$, $\text{Histogram} = \text{MACD} - \text{Signal}$.
- **Rate of Change (ROC$_k$):** $\frac{P_t - P_{t-k}}{P_{t-k}} \times 100$.
- **Bollinger Bands (20, 2σ):** $\text{Middle} = \text{SMA}_{20}$, $\text{Upper/Lower} = \text{SMA}_{20} \pm 2 \cdot \sigma_{20,\text{sample}}$ (`ddof=1`, explicitly documented).
- **Average True Range (ATR 14):** $\text{TR}_t = \max(H_t - L_t, |H_t - C_{t-1}|, |L_t - C_{t-1}|)$, smoothed via Wilder's 14-period recursion.

## 4. Distribution & Multi-Asset Statistics
- **Skewness & Excess Kurtosis:** Unbiased Fisher-Pearson sample skewness and Fisher excess kurtosis (`scipy.stats.skew(..., bias=False)` and `scipy.stats.kurtosis(..., fisher=True, bias=False)`).
- **Correlation & Covariance Matrices:** Computed on inner-joined common trading dates across assets using daily simple returns; covariance is annualized by multiplying daily sample covariance (`ddof=1`) by $N = 252$.

## Assumptions & Limitations
- Calculations assume adjusted closing prices when corporate actions (splits/dividends) are present.
- Intraday observations are never mixed with end-of-day observations without explicit interval separation.
- Historical volatility, Sharpe, and Sortino ratios are backward-looking descriptors and do not guarantee future performance.
