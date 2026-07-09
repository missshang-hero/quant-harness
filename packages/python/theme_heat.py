from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Any

from packages.python.core.models import StockSnapshot
from packages.python.data.real_collectors import load_market_data
from packages.python.strategies.sentiment import compute_market_overview


MARKET_STAGE_SCORE = {
    "ice": 42,
    "repair": 70,
    "split": 55,
    "hot": 64,
}

MARKET_STAGE_CN = {
    "ice": "冰点",
    "repair": "修复",
    "split": "分歧",
    "hot": "高潮",
}


def _theme_concepts(stock: StockSnapshot) -> list[str]:
    concepts = stock.concepts or ([stock.theme] if stock.theme else [])
    return [concept for concept in concepts[:3] if concept and concept != "题材待补全"]


def _stock_label(stock: StockSnapshot) -> str:
    return f"{stock.name}({stock.symbol})"


def _score_member(stock: StockSnapshot) -> float:
    return (
        max(stock.pct_change, 0) * 2.2
        + stock.volume_ratio * 6
        + stock.turnover_rate * 0.8
        + stock.board_height * 12
        + stock.auction_strength * 10
        + stock.seal_strength * 8
        + stock.narrative_score * 10
        + max(stock.hot_money_net_buy_million, 0) * 0.08
    )


def _predict_duration(
    *,
    continuation_score: float,
    heat_stage: str,
    market_stage: str,
    is_mainline: bool,
    count: int,
    avg_pct: float,
    avg_volume_ratio: float,
    top_board: int,
) -> tuple[str, dict[str, int], list[str], list[str], list[str]]:
    if heat_stage == "主升扩散":
        duration = {"min": 4, "max": 7}
        label = "4-7 个交易日"
    elif heat_stage == "发酵确认":
        duration = {"min": 2, "max": 4}
        label = "2-4 个交易日"
    elif heat_stage == "高潮分歧":
        duration = {"min": 1, "max": 2}
        label = "1-2 个交易日"
    elif heat_stage == "启动试探":
        duration = {"min": 1, "max": 3}
        label = "1-3 个交易日"
    else:
        duration = {"min": 0, "max": 1}
        label = "0-1 个交易日"

    if market_stage == "ice" and duration["max"] > 4:
        duration = {"min": max(1, duration["min"] - 1), "max": 4}
        label = f"{duration['min']}-{duration['max']} 个交易日"
    if avg_pct >= 8.0 or avg_volume_ratio >= 3.0:
        duration = {"min": max(0, duration["min"] - 1), "max": max(1, min(duration["max"], 2))}
        label = f"{duration['min']}-{duration['max']} 个交易日"

    reasons = [
        f"持续性分 {round(continuation_score, 1)}，当前处于{heat_stage}阶段。",
        f"市场情绪为{MARKET_STAGE_CN.get(market_stage, market_stage)}，对题材延续性形成{'支撑' if market_stage in {'repair', 'hot'} else '约束'}。",
        f"样本覆盖 {count} 只代表股，平均涨幅 {round(avg_pct, 2)}%，平均量比 {round(avg_volume_ratio, 2)}。",
    ]
    if is_mainline:
        reasons.append("热度排名进入前三，具备主线扩散基础。")
    if top_board >= 2:
        reasons.append(f"内部已有 {top_board} 板高度，短线辨识度较高。")
    if avg_pct >= 8.0:
        reasons.append("平均涨幅偏高，次日容易进入分歧兑现。")
    if count <= 1:
        reasons.append("扩散宽度不足，持续性依赖单一代表股承接。")

    invalidation_signals = [
        "代表股次日高开低走且无法回到分时均线上方。",
        "题材热度排名跌出前五，同时量比回落到 1 以下。",
        "同题材候选从多只扩散收缩到单一标的。",
    ]
    watch_points = [
        "观察代表股竞价强度、开盘承接和午后回流。",
        "观察是否从单一龙头扩散到同产业链后排。",
        "观察成交额放大后能否维持正反馈，而不是只放量滞涨。",
    ]
    return label, duration, reasons, invalidation_signals, watch_points


def _classify_heat_stage(
    continuation_score: float,
    *,
    avg_pct: float,
    avg_volume_ratio: float,
    top_board: int,
    is_mainline: bool,
) -> str:
    overheat = avg_pct >= 8.0 or avg_volume_ratio >= 3.0 or top_board >= 4
    if overheat and continuation_score >= 65:
        return "高潮分歧"
    if continuation_score >= 76 and is_mainline:
        return "主升扩散"
    if continuation_score >= 60:
        return "发酵确认"
    if continuation_score >= 44:
        return "启动试探"
    return "退潮观察"


def build_theme_heat_analysis(
    limit: int = 10,
    market_limit: int = 50,
    stocks: list[StockSnapshot] | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if stocks is None or meta is None:
        stocks, meta = load_market_data(limit=market_limit)
    market = compute_market_overview(stocks, meta["trade_date"])
    counter: Counter[str] = Counter()
    score_map: dict[str, float] = {}
    members: dict[str, dict[str, StockSnapshot]] = {}

    for stock in stocks:
        for idx, concept in enumerate(_theme_concepts(stock)):
            weight = 1.0 if idx == 0 else 0.6 if idx == 1 else 0.3
            counter[concept] += 1
            score_map[concept] = score_map.get(concept, 0.0) + (
                weight * (1 + max(stock.pct_change, 0) / 10 + stock.volume_ratio / 5)
            )
            members.setdefault(concept, {})[stock.symbol] = stock

    ranked = sorted(counter.items(), key=lambda item: (score_map.get(item[0], 0), item[1]), reverse=True)
    items: list[dict[str, Any]] = []

    for index, (theme, count) in enumerate(ranked[:limit]):
        theme_members = list(members.get(theme, {}).values())
        if not theme_members:
            continue

        leaders = sorted(theme_members, key=_score_member, reverse=True)[:4]
        heat_score = round(score_map.get(theme, 0.0), 2)
        avg_pct = mean(stock.pct_change for stock in theme_members)
        avg_volume_ratio = mean(stock.volume_ratio for stock in theme_members)
        avg_turnover = mean(stock.turnover_rate for stock in theme_members)
        top_board = max((stock.board_height for stock in theme_members), default=0)
        net_hot_money = sum(max(stock.hot_money_net_buy_million, 0) for stock in theme_members)
        is_mainline = index < 3

        breadth_score = min(100.0, count * 18 + min(heat_score, 12) * 4.5)
        leadership_score = min(
            100.0,
            top_board * 24
            + max(stock.auction_strength for stock in theme_members) * 18
            + max(stock.seal_strength for stock in theme_members) * 16
            + max(stock.narrative_score for stock in theme_members) * 22,
        )
        funding_score = min(100.0, net_hot_money * 0.55 + max(avg_volume_ratio - 1, 0) * 16)
        market_score = MARKET_STAGE_SCORE.get(market.market_sentiment_stage, 50)
        continuation_score = (
            breadth_score * 0.30
            + leadership_score * 0.28
            + funding_score * 0.22
            + market_score * 0.20
            + (8 if is_mainline else 0)
        )
        if avg_pct >= 8.0:
            continuation_score -= 8
        if avg_volume_ratio >= 3.0:
            continuation_score -= 6
        if market.market_sentiment_stage == "ice" and top_board <= 1:
            continuation_score -= 5
        continuation_score = round(max(0.0, min(100.0, continuation_score)), 1)

        heat_stage = _classify_heat_stage(
            continuation_score,
            avg_pct=avg_pct,
            avg_volume_ratio=avg_volume_ratio,
            top_board=top_board,
            is_mainline=is_mainline,
        )
        duration_label, duration_days, duration_reasons, invalidation_signals, watch_points = _predict_duration(
            continuation_score=continuation_score,
            heat_stage=heat_stage,
            market_stage=market.market_sentiment_stage,
            is_mainline=is_mainline,
            count=count,
            avg_pct=avg_pct,
            avg_volume_ratio=avg_volume_ratio,
            top_board=top_board,
        )

        items.append(
            {
                "theme": theme,
                "rank": index + 1,
                "count": count,
                "heat_score": heat_score,
                "is_mainline": is_mainline,
                "heat_stage": heat_stage,
                "continuation_score": continuation_score,
                "duration_label": duration_label,
                "duration_days": duration_days,
                "duration_reasons": duration_reasons,
                "invalidation_signals": invalidation_signals,
                "watch_points": watch_points,
                "leaders": [_stock_label(stock) for stock in leaders],
                "leader_symbols": [
                    {
                        "symbol": stock.symbol,
                        "name": stock.name,
                        "pct_change": stock.pct_change,
                        "volume_ratio": stock.volume_ratio,
                        "board_height": stock.board_height,
                        "theme": stock.theme,
                    }
                    for stock in leaders
                ],
                "stats": {
                    "avg_pct_change": round(avg_pct, 2),
                    "avg_volume_ratio": round(avg_volume_ratio, 2),
                    "avg_turnover_rate": round(avg_turnover, 2),
                    "top_board": top_board,
                    "net_hot_money_million": round(net_hot_money, 1),
                    "breadth_score": round(breadth_score, 1),
                    "leadership_score": round(leadership_score, 1),
                    "funding_score": round(funding_score, 1),
                    "market_stage": market.market_sentiment_stage,
                },
            }
        )

    return {
        "meta": {
            **meta,
            "market_stage": market.market_sentiment_stage,
            "market_stage_cn": MARKET_STAGE_CN.get(market.market_sentiment_stage, market.market_sentiment_stage),
        },
        "methodology": {
            "score_formula": "持续性分 = 扩散宽度 30% + 龙头强度 28% + 资金强度 22% + 市场情绪 20%，再根据主线地位、过热程度做修正。",
            "duration_note": "持续时间是短线题材研究估计，不是确定持仓周期；若失效信号出现，应按失效条件处理。",
        },
        "items": items,
    }
