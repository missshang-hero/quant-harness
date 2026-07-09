from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from packages.python.analytics import strategy_performance_summary
from packages.python.lifecycle_analytics import trade_lifecycle_summary
from packages.python.strategy_governor import build_strategy_governor
from packages.python.auto_trading import auto_trade_snapshot, execution_control_matrix, run_auto_trading
from packages.python.backtest import backtest_signals
from packages.python.daily_jobs import run_daily_job
from packages.python.execution.pipeline import run_pipeline
from packages.python.paper_execution import list_paper_positions, list_paper_trades, paper_portfolio_summary
from packages.python.report_archive import list_archived_reports, read_archived_report
from packages.python.resonance_analytics import resonance_validation_summary
from packages.python.sector_growth_model import forecast_sector_growth
from packages.python.storage import list_runs, list_signals_by_run, list_validations
from packages.python.strategy_portfolios import strategy_portfolio_summary
from packages.python.portfolio_evaluator import evaluate_strategy_portfolios
from packages.python.experiment_lab import run_experiment_lab
from packages.python.theme_heat import build_theme_heat_analysis
from packages.python.validation import validate_run
from packages.python.data.real_collectors import load_market_data


app = FastAPI(title="极投雷达 API", version="0.6.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _paper_summary_payload(payload, market_stocks):
    portfolio = paper_portfolio_summary([s.model_dump() for s in market_stocks])
    return {
        **portfolio,
        "portfolio": portfolio,
        "plan": payload["portfolio_plan"],
        "candidate_count": len(payload.get("candidates") or []),
    }


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/api/meta")
def meta():
    payload = run_pipeline(include_portfolio=False)
    return payload["meta"]


@app.get("/api/market/overview")
def market_overview():
    payload = run_pipeline(include_portfolio=False)
    return payload["market"]


@app.get("/api/debug/raw-market")
def debug_raw_market(limit: int = 20):
    stocks, meta = load_market_data(limit=limit)
    return {
        "meta": meta,
        "items": [s.model_dump() for s in stocks],
    }


@app.get("/api/signals")
def signals():
    payload = run_pipeline(include_portfolio=False)
    return payload["signals"]


@app.get("/api/candidates")
def candidates():
    payload = run_pipeline(include_portfolio=False)
    return payload["candidates"]


@app.get("/api/portfolio-plan")
def portfolio_plan():
    payload = run_pipeline()
    return payload["portfolio_plan"]


@app.get("/api/paper/positions")
def paper_positions():
    return list_paper_positions()


@app.get("/api/paper/trades")
def paper_trades(limit: int = 100):
    return list_paper_trades(limit=limit)


@app.get("/api/paper/summary")
def paper_summary():
    market_stocks, market_meta = load_market_data(limit=50)
    payload = run_pipeline(stocks=market_stocks, meta=market_meta, portfolio_history=False)
    return _paper_summary_payload(payload, market_stocks)


@app.get("/api/dashboard/overview")
def dashboard_overview():
    market_stocks, market_meta = load_market_data(limit=50)
    payload = run_pipeline(stocks=market_stocks, meta=market_meta, portfolio_history=False)
    theme_heat_payload = build_theme_heat_analysis(stocks=market_stocks, meta=market_meta)
    return {
        "meta": payload["meta"],
        "market": payload["market"],
        "signals": payload["signals"],
        "candidates": payload["candidates"],
        "portfolio_plan": payload["portfolio_plan"],
        "paper_summary": _paper_summary_payload(payload, market_stocks),
        "paper_positions": list_paper_positions(),
        "paper_trades": list_paper_trades(limit=100),
        "report": payload["report"],
        "runs": list_runs(limit=20),
        "validations": list_validations(limit=50),
        "performance": strategy_performance_summary(limit=500),
        "theme_heat_meta": theme_heat_payload.get("meta"),
        "theme_heat_methodology": theme_heat_payload.get("methodology"),
        "theme_heat": theme_heat_payload.get("items") or [],
    }


@app.get("/api/auto-trading/meta")
def auto_trading_meta():
    return execution_control_matrix()


@app.get("/api/auto-trading/snapshot")
def auto_trading_snapshot(mode: str = "hybrid", limit: int = 50):
    return auto_trade_snapshot(mode=mode, limit=limit)


@app.post("/api/auto-trading/run")
def auto_trading_run(mode: str = "hybrid", limit: int = 50):
    return run_auto_trading(mode=mode, limit=limit)


@app.get("/api/strategy-portfolios/summary")
def strategy_portfolios_summary(limit: int = 20):
    return strategy_portfolio_summary(limit=limit)


@app.get("/api/strategy-portfolios/evaluator")
def strategy_portfolios_evaluator(limit: int = 120):
    return evaluate_strategy_portfolios(limit=limit)


@app.get("/api/themes/heat")
def themes_heat(limit: int = 10, market_limit: int = 50):
    return build_theme_heat_analysis(limit=limit, market_limit=market_limit)


@app.get("/api/research/sector-growth")
def research_sector_growth(
    limit: int = 12,
    include_market_heat: bool = True,
    market_limit: int = 120,
    mode: str = "early_alpha",
):
    return forecast_sector_growth(
        limit=limit,
        include_market_heat=include_market_heat,
        market_limit=market_limit,
        mode=mode,
    )


@app.get("/api/report/daily")
def daily_report():
    payload = run_pipeline(include_portfolio=False)
    return payload["report"]


@app.post("/api/pipeline/run")
def pipeline_run():
    return run_pipeline(persist=True)


@app.post("/api/jobs/daily-run")
def jobs_daily_run():
    return run_daily_job()


@app.get("/api/history/runs")
def history_runs(limit: int = 20):
    return list_runs(limit=limit)


@app.get("/api/history/runs/{run_id}/signals")
def history_run_signals(run_id: int):
    return list_signals_by_run(run_id)


@app.post("/api/history/runs/{run_id}/validate")
def history_run_validate(run_id: int):
    return validate_run(run_id)


@app.get("/api/history/validations")
def history_validations(limit: int = 50):
    return list_validations(limit=limit)


@app.get("/api/history/reports")
def history_reports(limit: int = 30):
    return list_archived_reports(limit=limit)


@app.get("/api/history/reports/{trade_date}")
def history_report_detail(trade_date: str):
    return read_archived_report(trade_date)


@app.get("/api/analytics/strategy-performance")
def analytics_strategy_performance(limit: int = 500):
    return strategy_performance_summary(limit=limit)


@app.get("/api/analytics/backtest")
def analytics_backtest(limit: int = 50, kline_days: int = 30):
    return backtest_signals(limit=limit, kline_days=kline_days)


@app.get("/api/analytics/resonance-validation")
def analytics_resonance_validation(limit: int = 500):
    return resonance_validation_summary(limit=limit)


@app.get("/api/analytics/trade-lifecycle")
def analytics_trade_lifecycle(limit: int = 200):
    return trade_lifecycle_summary(limit=limit)


@app.get("/api/analytics/strategy-governor")
def analytics_strategy_governor(limit: int = 200):
    return build_strategy_governor(history_limit=limit)


@app.get("/api/analytics/experiment-lab")
def analytics_experiment_lab(limit: int = 160):
    return run_experiment_lab(limit=limit)
