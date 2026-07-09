from __future__ import annotations

from typing import Any

from packages.python.core.models import StockSnapshot
from packages.python.data.real_collectors import load_market_data
from packages.python.portfolio_allocator import build_portfolio_plan
from packages.python.reports.daily import build_daily_report
from packages.python.signals_aggregate import aggregate_signal_candidates
from packages.python.storage import save_pipeline_run
from packages.python.strategies.hotmoney import pick_hotmoney_signals
from packages.python.strategies.leader import pick_leader_signals
from packages.python.strategies.resonance import build_theme_heat_map
from packages.python.strategies.sentiment import compute_market_overview


def run_pipeline(
    limit: int = 50,
    persist: bool = False,
    include_portfolio: bool = True,
    portfolio_history: bool = True,
    stocks: list[StockSnapshot] | None = None,
    meta: dict[str, Any] | None = None,
):
    if stocks is None or meta is None:
        stocks, meta = load_market_data(limit=limit)
    trade_date = meta["trade_date"]
    market = compute_market_overview(stocks, trade_date)
    theme_heat = build_theme_heat_map(stocks)
    leader_signals = pick_leader_signals(stocks, market=market, theme_heat=theme_heat, limit=5)
    hotmoney_signals = pick_hotmoney_signals(stocks, market=market, theme_heat=theme_heat, limit=5)
    signals = sorted(leader_signals + hotmoney_signals, key=lambda s: (s.resonance_score, s.score), reverse=True)
    signal_dicts = [s.model_dump() for s in signals]
    candidates = aggregate_signal_candidates(signal_dicts)
    portfolio_plan = build_portfolio_plan(
        market.model_dump(),
        candidates,
        use_history=portfolio_history,
    ) if include_portfolio else None
    report = build_daily_report(trade_date, market, signals)

    payload = {
        "meta": meta,
        "trade_date": trade_date,
        "market": market.model_dump(),
        "signals": signal_dicts,
        "candidates": candidates,
        "portfolio_plan": portfolio_plan,
        "report": report.model_dump(),
        "theme_heat": theme_heat,
    }
    if persist:
        payload["run_id"] = save_pipeline_run(payload)
    return payload
