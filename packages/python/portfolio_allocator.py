from __future__ import annotations

from typing import Any

from packages.python.adaptive_params import get_adaptive_parameter_profile
from packages.python.position_sizing import apply_position_sizing
from packages.python.risk_engine import build_risk_profile
from packages.python.strategy_governor import build_strategy_governor


STRATEGY_LABELS = {
    'leader': '龙头策略',
    'hotmoney': '游资共振策略',
    'sentiment': '情绪策略',
    'composite': '综合策略',
}


def build_portfolio_plan(
    market: dict[str, Any],
    candidates: list[dict[str, Any]],
    use_history: bool = True,
) -> dict[str, Any]:
    stage = market.get('market_sentiment_stage', 'ice')

    if stage == 'ice':
        risk_mode = 'defensive_probe'
        execution_policy = 'paper_only'
        risk_budget = 20
        enabled_strategies = ['leader', 'hotmoney']
        max_positions = 3
        per_position_cap = 10
        max_theme_exposure_pct = 12
        notes = [
            '情绪冰点，以轻仓试错为主。',
            '优先保留高共振候选，不做弱共振扩散交易。',
        ]
    elif stage == 'repair':
        risk_mode = 'selective_attack'
        execution_policy = 'paper_only'
        risk_budget = 45
        enabled_strategies = ['leader', 'hotmoney', 'sentiment']
        max_positions = 4
        per_position_cap = 15
        max_theme_exposure_pct = 20
        notes = [
            '情绪修复阶段，允许适度提高仓位。',
            '优先主线前排与强共振候选。',
        ]
    elif stage == 'hot':
        risk_mode = 'active_attack'
        execution_policy = 'paper_only'
        risk_budget = 60
        enabled_strategies = ['leader', 'hotmoney', 'sentiment', 'composite']
        max_positions = 4
        per_position_cap = 20
        max_theme_exposure_pct = 25
        notes = [
            '情绪高潮阶段，允许主动进攻，但要提防次日一致性崩塌。',
            '避免后排补涨过度扩散。',
        ]
    else:
        risk_mode = 'risk_control'
        execution_policy = 'paper_only'
        risk_budget = 30
        enabled_strategies = ['leader', 'hotmoney']
        max_positions = 3
        per_position_cap = 12
        max_theme_exposure_pct = 15
        notes = [
            '分歧阶段优先保留核心，降低总暴露。',
            '回避纯跟风和低共振标的。',
        ]

    if use_history:
        strategy_governor = build_strategy_governor(history_limit=200)
        adaptive_profile = get_adaptive_parameter_profile(limit=160)
    else:
        strategy_governor = {
            'history_signal_count': 0,
            'trade_count': 0,
            'enabled_strategies': enabled_strategies,
            'frozen_strategies': [],
            'items': [],
            'notes': ['首页快速模式暂不运行历史回测治理。'],
        }
        adaptive_profile = {
            'active_profile': 'fast_default',
            'params': {},
            'notes': ['首页快速模式使用默认参数。'],
            'source': 'fast_dashboard',
        }
    adaptive_params = adaptive_profile.get('params') or {}
    enabled_by_governor = set(strategy_governor.get('enabled_strategies') or enabled_strategies)

    ranked = []
    for item in candidates:
        strategies = item.get('strategies') or []
        strategy_overlap = len(strategies)
        resonance_score = float(item.get('resonance_score') or 0)
        alloc_score = resonance_score + strategy_overlap * 6
        ranked.append({
            **item,
            'allocation_score': round(alloc_score, 1),
        })
    ranked = sorted(ranked, key=lambda x: x['allocation_score'], reverse=True)

    plan_items: list[dict[str, Any]] = []
    remaining_budget = risk_budget
    theme_exposure: dict[str, float] = {}
    strategy_exposure: dict[str, float] = {s: 0.0 for s in enabled_strategies}
    max_strategy_exposure_pct = max(risk_budget * 0.6, per_position_cap)

    for item in ranked:
        if remaining_budget <= 0 or len(plan_items) >= max_positions:
            break
        level = item.get('resonance_level', 'D')
        if level == 'D':
            continue
        strategies = [s for s in (item.get('strategies') or []) if s in enabled_strategies and s in enabled_by_governor]
        if not strategies:
            continue
        theme = item.get('theme') or '未分类'
        if theme_exposure.get(theme, 0.0) >= max_theme_exposure_pct:
            continue

        suggested = per_position_cap
        leader_weight = float(adaptive_params.get('signal_weight_leader') or 1.0)
        hotmoney_weight = float(adaptive_params.get('signal_weight_hotmoney') or 1.0)
        if level == 'B':
            suggested = min(suggested, 12 if risk_budget <= 45 else 16)
        elif level == 'C':
            suggested = min(suggested, 8)
        if len(strategies) >= 2:
            suggested += 2
        if 'leader' in strategies:
            suggested *= leader_weight
        if 'hotmoney' in strategies:
            suggested *= hotmoney_weight

        allowed_by_strategy = min(max_strategy_exposure_pct - strategy_exposure.get(s, 0.0) for s in strategies)
        allowed_by_theme = max_theme_exposure_pct - theme_exposure.get(theme, 0.0)
        suggested = min(suggested, remaining_budget, allowed_by_strategy, allowed_by_theme)
        if suggested < 4:
            continue

        remaining_budget -= suggested
        theme_exposure[theme] = theme_exposure.get(theme, 0.0) + suggested
        for strategy in strategies:
            strategy_exposure[strategy] = strategy_exposure.get(strategy, 0.0) + suggested

        plan_items.append({
            'symbol': item['symbol'],
            'name': item['name'],
            'display': item['display'],
            'theme': theme,
            'resonance_level': item.get('resonance_level', 'D'),
            'resonance_score': item.get('resonance_score', 0),
            'strategies': strategies,
            'target_weight_pct': round(suggested, 1),
            'role': item.get('resonance_role', 'noise'),
            'thesis': ' / '.join(item.get('resonance_reasons', [])[:3]),
        })

    no_trade = len(plan_items) == 0 or risk_budget == 0
    if no_trade:
        notes.append('当前未通过风险闸门，不建议开新仓。')

    strategy_weights = []
    if enabled_strategies:
        base = 100 / len(enabled_strategies)
        for strategy in enabled_strategies:
            adjust = 10 if strategy == 'leader' and stage in {'repair', 'hot'} else 0
            strategy_weights.append({
                'strategy': strategy,
                'label': STRATEGY_LABELS.get(strategy, strategy),
                'weight_pct': round(base + adjust, 1),
                'cap_pct': round(max_strategy_exposure_pct, 1),
                'planned_pct': round(strategy_exposure.get(strategy, 0.0), 1),
            })
        total = sum(item['weight_pct'] for item in strategy_weights) or 1
        for item in strategy_weights:
            item['weight_pct'] = round(item['weight_pct'] / total * 100, 1)

    if strategy_governor.get('notes'):
        notes.extend(strategy_governor['notes'])
    if adaptive_profile.get('notes'):
        notes.extend(adaptive_profile['notes'])

    base_plan = {
        'market_stage': stage,
        'risk_mode': risk_mode,
        'execution_policy': execution_policy,
        'risk_budget_pct': risk_budget,
        'max_positions': max_positions,
        'per_position_cap_pct': per_position_cap,
        'max_theme_exposure_pct': max_theme_exposure_pct,
        'enabled_strategies': sorted(enabled_by_governor),
        'strategy_governor': strategy_governor,
        'adaptive_profile': adaptive_profile,
        'strategy_weights': strategy_weights,
        'strategy_exposure': strategy_exposure,
        'theme_exposure': theme_exposure,
        'candidate_plan': plan_items,
        'no_trade': no_trade,
        'notes': notes,
    }
    if not use_history:
        base_plan['risk_profile'] = {
            'risk_mode': risk_mode,
            'market_stage': stage,
            'risk_discount': 1.0,
            'cooldown': False,
            'notes': ['快速组合模式已跳过重型历史回测，专门组合接口仍会生成完整风险画像。'],
        }
        return base_plan

    risk_profile = build_risk_profile(base_plan, plan_items)
    sized_plan = apply_position_sizing(base_plan, risk_profile)
    sized_plan['risk_profile'] = risk_profile
    return sized_plan
