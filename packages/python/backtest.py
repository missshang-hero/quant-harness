from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any

from packages.python.analysis_cache import get_or_compute
from packages.python.data.history_collectors import fetch_eastmoney_kline
from packages.python.storage import list_all_signal_details


HOLDING_WINDOWS = [1, 3, 5]


def _forward_returns(trade_date: str, rows: list[dict[str, Any]]) -> dict[int, float | None]:
    if not rows:
        return {window: None for window in HOLDING_WINDOWS}

    ordered = sorted(rows, key=lambda x: x['date'])
    future = [row for row in ordered if row['date'] > trade_date]
    if not future:
        return {window: None for window in HOLDING_WINDOWS}

    entry_price = float(future[0]['open'])
    if entry_price <= 0:
        return {window: None for window in HOLDING_WINDOWS}

    result: dict[int, float | None] = {}
    for window in HOLDING_WINDOWS:
        idx = window - 1
        if idx >= len(future):
            result[window] = None
            continue
        exit_price = float(future[idx]['close'])
        result[window] = round((exit_price / entry_price - 1) * 100, 2)
    return result


def _max_drawdown_pct(entry_price: float, rows: list[dict[str, Any]], bars: int = 5) -> float | None:
    if entry_price <= 0 or not rows:
        return None
    lows = [float(item.get('low') or 0) for item in rows[:bars] if float(item.get('low') or 0) > 0]
    if not lows:
        return None
    trough = min(lows)
    return round((trough / entry_price - 1) * 100, 2)


def _backtest_signals_uncached(limit: int = 200, kline_days: int = 30) -> dict[str, Any]:
    signal_rows = list_all_signal_details(limit=limit)

    trades: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for row in signal_rows:
        signal = row.get('signal') or {}
        symbol = row['symbol']
        trade_date = row['trade_date']
        try:
            rows = fetch_eastmoney_kline(symbol, days=kline_days)
            ordered = sorted(rows, key=lambda x: x['date'])
            future = [item for item in ordered if item['date'] > trade_date]
            if not future:
                skipped.append({'symbol': symbol, 'trade_date': trade_date, 'reason': 'no_future_bars'})
                continue
            entry_price = float(future[0]['open'])
            returns = _forward_returns(trade_date, ordered)
            trade = {
                'signal_id': row['id'],
                'run_id': row['run_id'],
                'trade_date': trade_date,
                'source': row.get('source', ''),
                'symbol': symbol,
                'name': row['name'],
                'strategy': row['strategy'],
                'score': row.get('score', 0),
                'risk_level': row.get('risk_level', 'medium'),
                'theme': row.get('theme', ''),
                'market_stage': str((row.get('market') or {}).get('market_sentiment_stage') or ''),
                'resonance_score': signal.get('resonance_score', 0),
                'resonance_level': signal.get('resonance_level', 'D'),
                'resonance_role': signal.get('resonance_role', 'noise'),
                'strategy_count': int(signal.get('strategy_count') or len(signal.get('strategies') or []) or 1),
                'entry_price': entry_price,
                'return_1d': returns[1],
                'return_3d': returns[3],
                'return_5d': returns[5],
                'max_drawdown_5d': _max_drawdown_pct(entry_price, future, bars=5),
            }
            trades.append(trade)
        except Exception as exc:
            errors.append({'symbol': symbol, 'trade_date': trade_date, 'error': str(exc)})

    scoreboard = build_backtest_scoreboard(trades)
    available_dates = sorted({str(row.get('trade_date') or '') for row in signal_rows if row.get('trade_date')})
    return {
        'date_range': {
            'start': available_dates[0] if available_dates else None,
            'end': available_dates[-1] if available_dates else None,
        },
        'history_signal_count': len(signal_rows),
        'trade_count': len(trades),
        'skipped_count': len(skipped),
        'error_count': len(errors),
        'trades': trades,
        'scoreboard': scoreboard,
        'skipped': skipped,
        'errors': errors,
    }


def backtest_signals(limit: int = 200, kline_days: int = 30) -> dict[str, Any]:
    return get_or_compute(
        f'backtest_signals:{limit}:{kline_days}',
        lambda: _backtest_signals_uncached(limit=limit, kline_days=kline_days),
        ttl_seconds=300.0,
    )


def _summarize_bucket(items: list[dict[str, Any]], key: str, value: str) -> dict[str, Any]:
    valid_1d = [x['return_1d'] for x in items if x.get('return_1d') is not None]
    valid_3d = [x['return_3d'] for x in items if x.get('return_3d') is not None]
    valid_5d = [x['return_5d'] for x in items if x.get('return_5d') is not None]
    drawdowns = [x['max_drawdown_5d'] for x in items if x.get('max_drawdown_5d') is not None]

    avg_1d = round(mean(valid_1d), 2) if valid_1d else None
    avg_3d = round(mean(valid_3d), 2) if valid_3d else None
    avg_5d = round(mean(valid_5d), 2) if valid_5d else None
    avg_dd = round(mean(drawdowns), 2) if drawdowns else None
    win_rate_1d = round(sum(1 for x in valid_1d if x > 0) / len(valid_1d) * 100, 2) if valid_1d else None
    win_rate_5d = round(sum(1 for x in valid_5d if x > 0) / len(valid_5d) * 100, 2) if valid_5d else None

    return {
        key: value,
        'count': len(items),
        'avg_return_1d': avg_1d,
        'avg_return_3d': avg_3d,
        'avg_return_5d': avg_5d,
        'avg_max_drawdown_5d': avg_dd,
        'win_rate_1d_pct': win_rate_1d,
        'win_rate_5d_pct': win_rate_5d,
    }


def build_backtest_scoreboard(trades: list[dict[str, Any]]) -> dict[str, Any]:
    strategy_bucket: dict[str, list[dict[str, Any]]] = defaultdict(list)
    level_bucket: dict[str, list[dict[str, Any]]] = defaultdict(list)
    role_bucket: dict[str, list[dict[str, Any]]] = defaultdict(list)
    risk_bucket: dict[str, list[dict[str, Any]]] = defaultdict(list)
    overlap_bucket: dict[str, list[dict[str, Any]]] = defaultdict(list)
    stage_bucket: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for item in trades:
        strategy_bucket[str(item.get('strategy') or 'unknown')].append(item)
        level_bucket[str(item.get('resonance_level') or 'unknown')].append(item)
        role_bucket[str(item.get('resonance_role') or 'unknown')].append(item)
        risk_bucket[str(item.get('risk_level') or 'unknown')].append(item)
        overlap_bucket[str(item.get('strategy_count') or 1)].append(item)
        stage_bucket[str(item.get('market_stage') or 'unknown')].append(item)

    summary_5d = [x['return_5d'] for x in trades if x.get('return_5d') is not None]
    drawdowns = [x['max_drawdown_5d'] for x in trades if x.get('max_drawdown_5d') is not None]

    return {
        'portfolio_view': {
            'avg_return_5d': round(mean(summary_5d), 2) if summary_5d else None,
            'win_rate_5d_pct': round(sum(1 for x in summary_5d if x > 0) / len(summary_5d) * 100, 2) if summary_5d else None,
            'avg_max_drawdown_5d': round(mean(drawdowns), 2) if drawdowns else None,
        },
        'by_strategy': sorted([
            _summarize_bucket(items, 'strategy', key)
            for key, items in strategy_bucket.items()
        ], key=lambda x: (x.get('avg_return_5d') or -999, x['count']), reverse=True),
        'by_resonance_level': sorted([
            _summarize_bucket(items, 'resonance_level', key)
            for key, items in level_bucket.items()
        ], key=lambda x: (x.get('avg_return_5d') or -999, x['count']), reverse=True),
        'by_role': sorted([
            _summarize_bucket(items, 'resonance_role', key)
            for key, items in role_bucket.items()
        ], key=lambda x: (x.get('avg_return_5d') or -999, x['count']), reverse=True),
        'by_risk_level': sorted([
            _summarize_bucket(items, 'risk_level', key)
            for key, items in risk_bucket.items()
        ], key=lambda x: (x.get('avg_return_5d') or -999, x['count']), reverse=True),
        'by_strategy_overlap': sorted([
            _summarize_bucket(items, 'strategy_count', key)
            for key, items in overlap_bucket.items()
        ], key=lambda x: (x.get('avg_return_5d') or -999, x['count']), reverse=True),
        'by_market_stage': sorted([
            _summarize_bucket(items, 'market_stage', key)
            for key, items in stage_bucket.items()
        ], key=lambda x: (x.get('avg_return_5d') or -999, x['count']), reverse=True),
    }
