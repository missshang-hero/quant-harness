from __future__ import annotations

from datetime import date
import os
from typing import Any

import httpx

from packages.python.analysis_cache import get_or_compute
from packages.python.core.models import StockSnapshot
from packages.python.data.sample_loader import load_sample_market


THEME_KEYWORDS: list[tuple[str, str]] = [
    ('机器人', '机器人'),
    ('智能', '机器人'),
    ('智控', '机器人'),
    ('电力', '电力'),
    ('能源', '能源'),
    ('新材', '新材料'),
    ('材料', '新材料'),
    ('药', '医药'),
    ('生物', '医药'),
    ('医疗', '医药'),
    ('科技', '科技'),
    ('电子', '半导体'),
    ('芯', '半导体'),
    ('通信', '通信'),
    ('传媒', 'AI应用'),
    ('算力', '算力'),
    ('环保', '环保'),
    ('军工', '军工'),
    ('长虹', '军工'),
    ('北方', '军工'),
    ('低空', '低空经济'),
    ('汽车', '汽车'),
]

THEME_EXCLUDE_KEYWORDS = [
    '板块',
    '融资融券',
    '深股通',
    '沪股通',
    '机构重仓',
    '创业板综',
    '上证380',
    '标准普尔',
    'MSCI',
    '东方财富热股',
]

VALID_A_SHARE_PREFIXES = (
    '000', '001', '002', '003',
    '300', '301',
    '600', '601', '603', '605',
    '688',
)

MARKET_CACHE_TTL_SECONDS = 90.0
EASTMONEY_TIMEOUT = httpx.Timeout(6.0, connect=2.0, read=4.0)
CONCEPT_TIMEOUT_SECONDS = 1.5
CONCEPT_SYMBOL_LIMIT = 8


def _env_int(name: str, default: int) -> int:
    try:
        return max(0, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return max(0.0, float(os.getenv(name, str(default))))
    except ValueError:
        return default


def infer_theme(name: str, symbol: str = '') -> str:
    text = f'{name}{symbol}'
    for keyword, theme in THEME_KEYWORDS:
        if keyword in text:
            return theme
    return '题材待补全'


def get_market_prefix(symbol: str) -> str:
    if symbol.startswith(('600', '601', '603', '605', '688')):
        return 'SH'
    return 'SZ'


def should_exclude_board(board_name: str) -> bool:
    return any(keyword in board_name for keyword in THEME_EXCLUDE_KEYWORDS)


def simplify_board_name(board_name: str) -> str:
    replacements = {
        '医药生物': '医药',
        '化学制药': '医药',
        '原料药': '原料药',
        '电网设备': '电力设备',
        '通用设备': '高端制造',
        '专用设备': '高端制造',
    }
    return replacements.get(board_name, board_name)


def is_valid_a_share_symbol(symbol: str) -> bool:
    return symbol.isdigit() and len(symbol) == 6 and symbol.startswith(VALID_A_SHARE_PREFIXES)


def fetch_professional_concepts(symbol: str, client: httpx.Client) -> list[str]:
    market = get_market_prefix(symbol)
    url = f'https://emweb.securities.eastmoney.com/PC_HSF10/CoreConception/PageAjax?code={market}{symbol}'
    try:
        res = client.get(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0',
                'Referer': 'https://quote.eastmoney.com/',
            },
            timeout=CONCEPT_TIMEOUT_SECONDS,
        )
        res.raise_for_status()
        payload = res.json()
        boards = payload.get('ssbk') or []
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in boards:
            board_name = str(item.get('BOARD_NAME', '')).strip()
            if not board_name or should_exclude_board(board_name):
                continue
            normalized = simplify_board_name(board_name)
            if normalized in seen:
                continue
            seen.add(normalized)
            cleaned.append(normalized)
        return cleaned
    except Exception:
        return []


def _normalize_records(records: list[dict[str, Any]], professional_concept_map: dict[str, list[str]] | None = None) -> list[StockSnapshot]:
    result: list[StockSnapshot] = []
    professional_concept_map = professional_concept_map or {}
    for item in records:
        pct = float(item.get('涨跌幅', item.get('pct_change', 0)) or 0)
        turnover = float(item.get('换手率', item.get('turnover_rate', 0)) or 0)
        volume_ratio = float(item.get('量比', item.get('volume_ratio', 1)) or 1)
        symbol = str(item.get('代码', item.get('symbol', '')))
        name = str(item.get('名称', item.get('name', '未知标的')))
        if not is_valid_a_share_symbol(symbol) or not name or name == '未知标的':
            continue
        raw_theme = item.get('theme')
        theme = str(raw_theme).strip() if raw_theme not in (None, '') else ''
        concepts = professional_concept_map.get(symbol, [])
        if not theme or theme == '未分类':
            theme = concepts[0] if concepts else infer_theme(name, symbol)
        secondary_theme = concepts[1] if len(concepts) > 1 else ''
        result.append(
            StockSnapshot(
                symbol=symbol,
                name=name,
                theme=theme,
                secondary_theme=secondary_theme,
                concepts=concepts,
                close=float(item.get('最新价', item.get('close', 0)) or 0),
                pct_change=pct,
                volume_ratio=volume_ratio,
                turnover_rate=turnover,
                board_height=int(item.get('board_height', 0) or 0),
                is_limit_up=bool(item.get('is_limit_up', pct >= 9.8)),
                is_broken_board=bool(item.get('is_broken_board', False)),
                hot_money_net_buy_million=float(item.get('hot_money_net_buy_million', 0) or 0),
                auction_strength=float(item.get('auction_strength', 0.5) or 0.5),
                seal_strength=float(item.get('seal_strength', 0.5) or 0.5),
                narrative_score=float(item.get('narrative_score', 0.5) or 0.5),
            )
        )
    return result


def try_fetch_with_akshare(limit: int = 50) -> tuple[list[StockSnapshot], str]:
    try:
        import akshare as ak  # type: ignore

        df = ak.stock_zh_a_spot_em()
        df = df.head(limit)
        records = df.to_dict(orient='records')
        stocks = _normalize_records(records)
        return stocks, 'akshare'
    except Exception:
        return [], 'akshare_unavailable'


def try_fetch_with_eastmoney(limit: int = 50) -> tuple[list[StockSnapshot], str]:
    url = 'https://push2.eastmoney.com/api/qt/clist/get'
    params = {
        'pn': 1,
        'pz': limit,
        'po': 1,
        'np': 1,
        'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
        'fltt': 2,
        'invt': 2,
        'fid': 'f3',
        'fs': 'm:0+t:6,m:0+t:13,m:0+t:80,m:1+t:2,m:1+t:23',
        'fields': 'f12,f14,f2,f3,f8,f10',
    }
    try:
        with httpx.Client(timeout=EASTMONEY_TIMEOUT, headers={'User-Agent': 'Mozilla/5.0'}) as client:
            res = client.get(url, params=params)
            res.raise_for_status()
            payload = res.json()
            diff = payload.get('data', {}).get('diff', [])
            records = []
            symbols: list[str] = []
            for item in diff:
                symbol = str(item.get('f12') or '')
                if symbol:
                    symbols.append(symbol)
                records.append(
                    {
                        '代码': symbol,
                        '名称': item.get('f14'),
                        '最新价': item.get('f2', 0),
                        '涨跌幅': item.get('f3', 0),
                        '换手率': item.get('f8', 0),
                        '量比': item.get('f10', 1),
                    }
                )

            professional_concept_map: dict[str, list[str]] = {}
            concept_limit = _env_int('MARKET_CONCEPT_SYMBOL_LIMIT', CONCEPT_SYMBOL_LIMIT)
            for symbol in symbols[: min(len(symbols), concept_limit)]:
                concepts = fetch_professional_concepts(symbol, client)
                if concepts:
                    professional_concept_map[symbol] = concepts

            stocks = _normalize_records(records, professional_concept_map=professional_concept_map)
            return stocks, 'eastmoney'
    except Exception:
        return [], 'eastmoney_unavailable'


def _load_market_data_uncached(limit: int, provider_order: str) -> tuple[list[StockSnapshot], dict[str, str]]:
    providers = [item.strip().lower() for item in provider_order.split(',') if item.strip()]

    for provider in providers:
        if provider == 'eastmoney':
            stocks, source = try_fetch_with_eastmoney(limit=limit)
        elif provider == 'akshare':
            stocks, source = try_fetch_with_akshare(limit=limit)
        elif provider == 'sample':
            stocks, source = load_sample_market(), 'sample_fallback'
        else:
            continue

        if stocks:
            return stocks, {'source': source, 'trade_date': str(date.today())}

    return load_sample_market(), {'source': 'sample_fallback', 'trade_date': str(date.today())}


def load_market_data(limit: int = 50) -> tuple[list[StockSnapshot], dict[str, str]]:
    provider_order = os.getenv('MARKET_DATA_PROVIDER_ORDER', 'eastmoney,akshare,sample')
    ttl_seconds = _env_float('MARKET_DATA_CACHE_TTL_SECONDS', MARKET_CACHE_TTL_SECONDS)
    cache_key = f'market_data:{limit}:{provider_order}'
    return get_or_compute(
        cache_key,
        lambda: _load_market_data_uncached(limit=limit, provider_order=provider_order),
        ttl_seconds=ttl_seconds,
    )
