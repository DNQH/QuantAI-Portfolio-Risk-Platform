# Contributing to QuantAI

Thank you for contributing to **QuantAI**! This project is built as a rigorous, transparent quantitative finance research platform. All contributions must uphold mathematical accuracy, genuine data provenance, and clean modular software engineering.

## Mandatory Contribution Rules
1. **No Fabricated Data:** Never introduce synthetic or hardcoded prices as real market data. Any synthetic fixtures must live strictly inside `backend/tests/` and be explicitly labeled as test fixtures.
2. **No Fake AI Claims:** Never label heuristics or random noise as machine learning models.
3. **Mathematical Verification:** Every new quantitative function must include unit tests in `backend/tests/` validated against independently computed reference values, plus documented formulas and assumptions in `docs/financial_formulas.md`.
4. **Zero Secrets:** Never commit `.env` files, API keys, or brokerage credentials.

## Local Development Workflow
```bash
# 1. Backend lint & tests
cd backend
pip install -r requirements-dev.txt   # runtime deps + pytest + ruff
ruff check .
python -m pytest -q

# 2. Frontend type-check & build
cd ../frontend
npm install
npm run build
```

## Pull Request Checklist
- [ ] Code is modular and follows existing directory boundaries (`core/`, `data/`, `analytics/`, `portfolio/`, `risk/`, `fx/`, `forecasting/`, `backtesting/`).
- [ ] All existing and new unit/integration tests pass.
- [ ] `docs/financial_formulas.md`, `CHANGELOG.md`, and `PROJECT_STATUS.md` are updated where applicable.
