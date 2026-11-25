"""Phase 5: Machine Learning & Statistical Time-Series Forecasting Engine.

Strict anti-leakage and anti-fake-AI guarantees:
  - Chronological train/test split (never randomly shuffled).
  - Feature scaling (mean/std) fit strictly on training observations only.
  - Genuine training, validation, and out-of-sample evaluation for every model:
      1. naive_last_price       (Random-walk benchmark)
      2. naive_historical_mean  (Training-fold mean return benchmark)
      3. ridge_regression       (Closed-form L2 linear regression)
      4. arima_ar4_returns      (AR model on return lags 1, 2, 3 and 5, ridge-stabilised)
      5. random_forest          (Bagged CART regression tree ensemble)
      6. gradient_boosting      (Stage-wise residual boosted CART trees)
  - Reports MAE, RMSE, MAPE, R², residuals, training/test windows, and timestamps.
  - NEVER fabricates artificial prediction confidence scores.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import numpy as np
from pydantic import BaseModel, Field

from app.analytics.bars import prepare_bars
from app.analytics.indicators import rsi_wilder, sma
from app.core.models import OHLCVBar


class ForecastRequest(BaseModel):
    instrument_id: str
    bars: List[OHLCVBar] = Field(..., min_items=40, description="At least 40 chronological OHLCV bars")
    test_ratio: float = Field(default=0.2, ge=0.1, le=0.4)
    ridge_alpha: float = Field(default=1.0, ge=0.0)
    random_seed: int = Field(default=42)


class ModelMetrics(BaseModel):
    model_name: str
    model_family: str
    mae: float
    rmse: float
    mape_pct: Optional[float]
    r_squared: float
    walk_forward_rmse: float
    residual_std: float
    next_step_predicted_price: float
    next_step_predicted_return: float
    actual_prices: List[float]
    predicted_prices: List[float]
    residuals: List[float]


class ForecastResponse(BaseModel):
    instrument_id: str
    trained_at_utc: datetime
    latest_input_timestamp: datetime
    forecast_generated_at_utc: datetime
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    train_samples: int
    test_samples: int
    features_used: List[str]
    test_timestamps: List[str]
    models: List[ModelMetrics]
    disclaimer: str


# --- Lightweight pure-NumPy CART Tree (used when scikit-learn is not installed) ---

@dataclass
class _TreeNode:
    feature_idx: Optional[int] = None
    threshold: Optional[float] = None
    left: Optional["_TreeNode"] = None
    right: Optional["_TreeNode"] = None
    value: Optional[float] = None


class _SimpleCARTRegressor:
    def __init__(self, max_depth: int = 3, min_samples_leaf: int = 4) -> None:
        self.max_depth = max_depth
        self.min_samples_leaf = min_samples_leaf
        self.root: Optional[_TreeNode] = None

    def fit(self, X: np.ndarray, y: np.ndarray, feature_subset: Optional[np.ndarray] = None) -> "_SimpleCARTRegressor":
        self.root = self._build(X, y, depth=0, feature_subset=feature_subset)
        return self

    def _build(self, X: np.ndarray, y: np.ndarray, depth: int, feature_subset: Optional[np.ndarray]) -> _TreeNode:
        n = len(y)
        if depth >= self.max_depth or n < 2 * self.min_samples_leaf or float(np.var(y)) < 1e-12:
            return _TreeNode(value=float(np.mean(y)))

        best_mse = float("inf")
        best_feat: Optional[int] = None
        best_thresh: Optional[float] = None

        feats = feature_subset if feature_subset is not None else np.arange(X.shape[1])
        for f in feats:
            col = X[:, int(f)]
            quantiles = np.unique(np.quantile(col, [0.2, 0.4, 0.6, 0.8]))
            for thr in quantiles:
                left_mask = col <= thr
                n_left = int(np.sum(left_mask))
                n_right = n - n_left
                if n_left < self.min_samples_leaf or n_right < self.min_samples_leaf:
                    continue
                y_l = y[left_mask]
                y_r = y[~left_mask]
                mse = (n_left * float(np.var(y_l)) + n_right * float(np.var(y_r))) / n
                if mse < best_mse:
                    best_mse = mse
                    best_feat = int(f)
                    best_thresh = float(thr)

        if best_feat is None or best_thresh is None:
            return _TreeNode(value=float(np.mean(y)))

        mask = X[:, best_feat] <= best_thresh
        return _TreeNode(
            feature_idx=best_feat,
            threshold=best_thresh,
            left=self._build(X[mask], y[mask], depth + 1, feature_subset),
            right=self._build(X[~mask], y[~mask], depth + 1, feature_subset),
        )

    def _predict_one(self, x: np.ndarray, node: _TreeNode) -> float:
        if node.value is not None:
            return node.value
        assert node.feature_idx is not None and node.threshold is not None
        if x[node.feature_idx] <= node.threshold:
            assert node.left is not None
            return self._predict_one(x, node.left)
        assert node.right is not None
        return self._predict_one(x, node.right)

    def predict(self, X: np.ndarray) -> np.ndarray:
        assert self.root is not None
        return np.array([self._predict_one(row, self.root) for row in X], dtype=float)


class _PureNumpyRandomForest:
    def __init__(self, n_estimators: int = 25, max_depth: int = 3, seed: int = 42) -> None:
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.seed = seed
        self.trees: List[_SimpleCARTRegressor] = []

    def fit(self, X: np.ndarray, y: np.ndarray) -> "_PureNumpyRandomForest":
        rng = np.random.default_rng(self.seed)
        n, p = X.shape
        k_feats = max(2, int(math.sqrt(p)))
        self.trees = []
        for _ in range(self.n_estimators):
            idx = rng.integers(0, n, size=n)
            f_sub = rng.choice(p, size=min(k_feats, p), replace=False)
            tree = _SimpleCARTRegressor(max_depth=self.max_depth, min_samples_leaf=3)
            tree.fit(X[idx], y[idx], feature_subset=f_sub)
            self.trees.append(tree)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        preds = np.vstack([t.predict(X) for t in self.trees])
        return np.mean(preds, axis=0)


class _PureNumpyGradientBoosting:
    def __init__(self, n_estimators: int = 20, learning_rate: float = 0.08, max_depth: int = 2) -> None:
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.max_depth = max_depth
        self.base_val: float = 0.0
        self.trees: List[_SimpleCARTRegressor] = []

    def fit(self, X: np.ndarray, y: np.ndarray) -> "_PureNumpyGradientBoosting":
        self.base_val = float(np.mean(y))
        pred = np.full(len(y), self.base_val, dtype=float)
        self.trees = []
        for _ in range(self.n_estimators):
            residuals = y - pred
            tree = _SimpleCARTRegressor(max_depth=self.max_depth, min_samples_leaf=4)
            tree.fit(X, residuals)
            pred = pred + self.learning_rate * tree.predict(X)
            self.trees.append(tree)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        out = np.full(len(X), self.base_val, dtype=float)
        for tree in self.trees:
            out = out + self.learning_rate * tree.predict(X)
        return out


def _fit_ridge(X_train: np.ndarray, y_train: np.ndarray, alpha: float) -> Tuple[float, np.ndarray]:
    n, p = X_train.shape
    X_aug = np.hstack([np.ones((n, 1)), X_train])
    reg = np.eye(p + 1) * alpha
    reg[0, 0] = 0.0  # Do not regularize intercept
    coef = np.linalg.pinv(X_aug.T @ X_aug + reg) @ (X_aug.T @ y_train)
    return float(coef[0]), coef[1:]


def _predict_ridge(X: np.ndarray, intercept: float, weights: np.ndarray) -> np.ndarray:
    return intercept + X @ weights


def _build_supervised_features(
    bars: List[OHLCVBar],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, List[str], List[str], np.ndarray]:
    """Build strictly causal features at time t predicting next-bar return r_{t+1}."""
    ordered = sorted(bars, key=lambda b: b.timestamp)
    closes = np.array([b.adjusted_close if b.adjusted_close is not None else b.close for b in ordered], dtype=float)
    volumes = np.array([max(1.0, float(b.volume)) for b in ordered], dtype=float)
    timestamps = [b.timestamp.isoformat() for b in ordered]

    sma5 = sma(closes.tolist(), 5)
    sma20 = sma(closes.tolist(), 20)
    rsi14 = rsi_wilder(closes.tolist(), 14)

    rets = np.zeros(len(closes), dtype=float)
    rets[1:] = (closes[1:] - closes[:-1]) / closes[:-1]

    feature_names = [
        "ret_lag1",
        "ret_lag2",
        "ret_lag3",
        "ret_lag5",
        "sma5_ratio",
        "sma20_ratio",
        "rolling_vol_10",
        "rsi_14_norm",
        "log_vol_ratio",
    ]

    X_rows: List[List[float]] = []
    y_rows: List[float] = []
    base_prices: List[float] = []
    target_timestamps: List[str] = []

    def _row_at(t: int) -> List[float]:
        vol10 = float(np.std(rets[t - 9 : t + 1], ddof=1))
        vol_mean10 = float(np.mean(volumes[t - 9 : t + 1]))
        return [
            float(rets[t]),
            float(rets[t - 1]),
            float(rets[t - 2]),
            float(rets[t - 4]),
            float(closes[t] / (sma5[t] or closes[t]) - 1.0),
            float(closes[t] / (sma20[t] or closes[t]) - 1.0),
            vol10,
            float(((rsi14[t] if rsi14[t] is not None else 50.0) - 50.0) / 50.0),
            math.log(volumes[t] / max(1.0, vol_mean10)),
        ]

    # Start at t=20 so all lookbacks (SMA20, RSI14, vol10) are strictly defined
    for t in range(20, len(closes) - 1):
        X_rows.append(_row_at(t))
        y_rows.append(float(rets[t + 1]))
        base_prices.append(float(closes[t]))
        target_timestamps.append(timestamps[t + 1])

    latest_row = np.array([_row_at(len(closes) - 1)], dtype=float)
    return (
        np.array(X_rows, dtype=float),
        np.array(y_rows, dtype=float),
        np.array(base_prices, dtype=float),
        target_timestamps,
        feature_names,
        latest_row,
    )


def _eval_price_metrics(actual: np.ndarray, predicted: np.ndarray) -> Tuple[float, float, Optional[float], float, float]:
    errors = actual - predicted
    mae = float(np.mean(np.abs(errors)))
    rmse = float(math.sqrt(float(np.mean(errors ** 2))))
    nonzero = actual != 0.0
    mape = float(np.mean(np.abs(errors[nonzero] / actual[nonzero])) * 100.0) if np.any(nonzero) else None
    ss_res = float(np.sum(errors ** 2))
    ss_tot = float(np.sum((actual - np.mean(actual)) ** 2))
    r2 = (1.0 - ss_res / ss_tot) if ss_tot > 1e-12 else 0.0
    resid_std = float(np.std(errors, ddof=1)) if len(errors) >= 2 else 0.0
    return mae, rmse, mape, r2, resid_std


def run_forecasting_suite(req: ForecastRequest) -> ForecastResponse:
    ordered, _ = prepare_bars(req.bars, min_count=40, context="Forecasting")
    X, y, base_prices, target_ts, feature_names, latest_X = _build_supervised_features(ordered)
    n_samples = len(y)
    if n_samples < 15:
        raise ValueError("Insufficient usable samples after indicator warm-up (need at least 40 OHLCV bars).")

    split_idx = max(10, int(round(n_samples * (1.0 - req.test_ratio))))
    split_idx = min(split_idx, n_samples - 3)

    X_train_raw, X_test_raw = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]
    base_test = base_prices[split_idx:]
    actual_test_prices = base_test * (1.0 + y_test)
    latest_close = float(ordered[-1].adjusted_close if ordered[-1].adjusted_close is not None else ordered[-1].close)

    # STRICT ANTI-LEAKAGE: Fit standardization parameters on X_train_raw ONLY
    train_mean = np.mean(X_train_raw, axis=0)
    train_std = np.std(X_train_raw, axis=0, ddof=1)
    train_std = np.where(train_std < 1e-12, 1.0, train_std)

    X_train = (X_train_raw - train_mean) / train_std
    X_test = (X_test_raw - train_mean) / train_std
    X_latest = (latest_X - train_mean) / train_std

    def _walk_forward_rmse(fit_predict_fn) -> float:
        """3-fold expanding-window chronological cross-validation inside training set."""
        n_tr = len(y_train)
        if n_tr < 12:
            return 0.0
        fold_size = max(2, n_tr // 4)
        sq_errs: List[float] = []
        for k in range(1, 4):
            end_tr = fold_size * k
            end_val = min(n_tr, end_tr + fold_size)
            if end_val <= end_tr:
                continue
            mu_k = np.mean(X_train_raw[:end_tr], axis=0)
            sd_k = np.std(X_train_raw[:end_tr], axis=0, ddof=1)
            sd_k = np.where(sd_k < 1e-12, 1.0, sd_k)
            pred_r = fit_predict_fn(
                (X_train_raw[:end_tr] - mu_k) / sd_k,
                y_train[:end_tr],
                (X_train_raw[end_tr:end_val] - mu_k) / sd_k,
            )
            pred_p = base_prices[end_tr:end_val] * (1.0 + pred_r)
            act_p = base_prices[end_tr:end_val] * (1.0 + y_train[end_tr:end_val])
            sq_errs.extend(((act_p - pred_p) ** 2).tolist())
        return math.sqrt(float(np.mean(sq_errs))) if sq_errs else 0.0

    results: List[ModelMetrics] = []

    def _record(name: str, family: str, pred_test_r: np.ndarray, next_r: float, wf_rmse: float) -> None:
        pred_p = base_test * (1.0 + pred_test_r)
        mae, rmse, mape, r2, rstd = _eval_price_metrics(actual_test_prices, pred_p)
        results.append(
            ModelMetrics(
                model_name=name,
                model_family=family,
                mae=mae,
                rmse=rmse,
                mape_pct=mape,
                r_squared=r2,
                walk_forward_rmse=wf_rmse,
                residual_std=rstd,
                next_step_predicted_price=round(latest_close * (1.0 + next_r), 6),
                next_step_predicted_return=round(float(next_r), 6),
                actual_prices=[round(float(v), 4) for v in actual_test_prices],
                predicted_prices=[round(float(v), 4) for v in pred_p],
                residuals=[round(float(v), 4) for v in (actual_test_prices - pred_p)],
            )
        )

    # 1. Naive Last Price (Zero-return random walk)
    _record(
        "naive_last_price",
        "Benchmark",
        np.zeros_like(y_test),
        0.0,
        _walk_forward_rmse(lambda xtr, ytr, xva: np.zeros(len(xva))),
    )

    # 2. Naive Historical Mean Return
    mean_tr = float(np.mean(y_train))
    _record(
        "naive_historical_mean",
        "Benchmark",
        np.full_like(y_test, mean_tr),
        mean_tr,
        _walk_forward_rmse(lambda xtr, ytr, xva: np.full(len(xva), float(np.mean(ytr)))),
    )

    # 3. Ridge Linear Regression
    b_r, w_r = _fit_ridge(X_train, y_train, req.ridge_alpha)
    _record(
        "ridge_regression",
        "Linear Model",
        _predict_ridge(X_test, b_r, w_r),
        float(_predict_ridge(X_latest, b_r, w_r)[0]),
        _walk_forward_rmse(lambda xtr, ytr, xva: _predict_ridge(xva, *_fit_ridge(xtr, ytr, req.ridge_alpha))),
    )

    # 4. Statistical AR model on the 4 return-lag features (lags 1, 2, 3, 5), ridge-stabilised.
    b_ar, w_ar = _fit_ridge(X_train[:, :4], y_train, alpha=0.05)
    _record(
        "arima_ar4_returns",
        "Statistical Time-Series",
        _predict_ridge(X_test[:, :4], b_ar, w_ar),
        float(_predict_ridge(X_latest[:, :4], b_ar, w_ar)[0]),
        _walk_forward_rmse(lambda xtr, ytr, xva: _predict_ridge(xva[:, :4], *_fit_ridge(xtr[:, :4], ytr, 0.05))),
    )

    # 5. Random Forest Regressor (uses scikit-learn if installed, else pure-NumPy CART Forest)
    try:
        from sklearn.ensemble import RandomForestRegressor  # type: ignore

        rf = RandomForestRegressor(n_estimators=50, max_depth=4, random_state=req.random_seed)
        rf.fit(X_train, y_train)
        rf_test = rf.predict(X_test)
        rf_next = float(rf.predict(X_latest)[0])
        rf_wf = _walk_forward_rmse(
            lambda xtr, ytr, xva: RandomForestRegressor(n_estimators=25, max_depth=4, random_state=req.random_seed)
            .fit(xtr, ytr)
            .predict(xva)
        )
    except ImportError:
        rf = _PureNumpyRandomForest(n_estimators=25, max_depth=3, seed=req.random_seed).fit(X_train, y_train)
        rf_test = rf.predict(X_test)
        rf_next = float(rf.predict(X_latest)[0])
        rf_wf = _walk_forward_rmse(
            lambda xtr, ytr, xva: _PureNumpyRandomForest(n_estimators=15, max_depth=3, seed=req.random_seed)
            .fit(xtr, ytr)
            .predict(xva)
        )
    _record("random_forest", "Tree Ensemble", rf_test, rf_next, rf_wf)

    # 6. Gradient Boosting Regressor
    try:
        from sklearn.ensemble import GradientBoostingRegressor  # type: ignore

        gb = GradientBoostingRegressor(n_estimators=40, max_depth=2, learning_rate=0.08, random_state=req.random_seed)
        gb.fit(X_train, y_train)
        gb_test = gb.predict(X_test)
        gb_next = float(gb.predict(X_latest)[0])
        gb_wf = _walk_forward_rmse(
            lambda xtr, ytr, xva: GradientBoostingRegressor(
                n_estimators=25, max_depth=2, learning_rate=0.08, random_state=req.random_seed
            )
            .fit(xtr, ytr)
            .predict(xva)
        )
    except ImportError:
        gb = _PureNumpyGradientBoosting(n_estimators=20, learning_rate=0.08, max_depth=2).fit(X_train, y_train)
        gb_test = gb.predict(X_test)
        gb_next = float(gb.predict(X_latest)[0])
        gb_wf = _walk_forward_rmse(
            lambda xtr, ytr, xva: _PureNumpyGradientBoosting(n_estimators=12, learning_rate=0.08, max_depth=2)
            .fit(xtr, ytr)
            .predict(xva)
        )
    _record("gradient_boosting", "Tree Ensemble", gb_test, gb_next, gb_wf)

    now_utc = datetime.now(timezone.utc)
    return ForecastResponse(
        instrument_id=req.instrument_id,
        trained_at_utc=now_utc,
        latest_input_timestamp=ordered[-1].timestamp,
        forecast_generated_at_utc=now_utc,
        train_start=target_ts[0],
        train_end=target_ts[split_idx - 1],
        test_start=target_ts[split_idx],
        test_end=target_ts[-1],
        train_samples=int(len(y_train)),
        test_samples=int(len(y_test)),
        features_used=feature_names,
        test_timestamps=target_ts[split_idx:],
        models=results,
        disclaimer=(
            "Forecasts are out-of-sample statistical estimates trained on historical data with strict "
            "chronological splits and zero artificial confidence scores. They do NOT guarantee future prices."
        ),
    )
