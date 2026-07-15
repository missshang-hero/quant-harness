from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESKTOP_REPORT_DIR = os.getenv("QUANT_HARNESS_REPORT_DIR")
REPORT_DIR = Path(DESKTOP_REPORT_DIR) if DESKTOP_REPORT_DIR else Path("/tmp/quant-harness/reports/daily") if os.getenv("VERCEL") else ROOT / "reports" / "daily"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def archive_daily_report(result: dict[str, Any]) -> dict[str, str]:
    trade_date = result["trade_date"]
    json_path = REPORT_DIR / f"{trade_date}.json"
    md_path = REPORT_DIR / f"{trade_date}.md"

    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_to_markdown(result), encoding="utf-8")

    return {
        "json_path": str(json_path),
        "md_path": str(md_path),
    }


def list_archived_reports(limit: int = 30) -> list[dict[str, str]]:
    items = []
    for md_file in sorted(REPORT_DIR.glob("*.md"), reverse=True)[:limit]:
        trade_date = md_file.stem
        json_file = REPORT_DIR / f"{trade_date}.json"
        items.append(
            {
                "trade_date": trade_date,
                "md_path": str(md_file),
                "json_path": str(json_file),
            }
        )
    return items


def read_archived_report(trade_date: str) -> dict[str, str]:
    md_path = REPORT_DIR / f"{trade_date}.md"
    json_path = REPORT_DIR / f"{trade_date}.json"
    return {
        "trade_date": trade_date,
        "md": md_path.read_text(encoding="utf-8") if md_path.exists() else "",
        "json": json_path.read_text(encoding="utf-8") if json_path.exists() else "",
    }


def _to_markdown(result: dict[str, Any]) -> str:
    report = result["report"]
    lines = [
        f"# 极投雷达盘后研究报告 - {result['trade_date']}",
        "",
        f"- 数据源: {result['source']}",
        f"- 运行 ID: {result['run_id']}",
        f"- 信号数: {result['signal_count']}",
        f"- 验证数: {result['validation_count']}",
        "",
        "## 中文摘要",
        report["summary_cn"],
        "",
        "## 结构化日报",
        f"- 主线题材: {'、'.join(report.get('mainline_themes', [])) or '暂无'}",
        f"- 强共振候选: {'、'.join(report.get('focus_candidates', [])) or '暂无'}",
        f"- 观察名单: {'、'.join(report.get('observe_candidates', [])) or '暂无'}",
        f"- 回避名单: {'、'.join(report.get('avoid_candidates', [])) or '暂无'}",
        "",
        "### 明日计划",
    ]

    for item in report.get('tomorrow_plan', []):
        lines.append(f"- {item}")

    lines.extend([
        "",
        "## 核心信号",
    ])

    for signal in report.get("top_signals", []):
        lines.extend(
            [
                f"### {signal['name']} ({signal['symbol']})",
                f"- 策略: {signal['strategy']}",
                f"- 分数: {signal['score']}",
                f"- 风险: {signal['risk_level']}",
                f"- 题材: {signal['theme']}",
                f"- 理由: {'；'.join(signal['reasons'])}",
                f"- 入场: {signal['entry_note']}",
                f"- 退出: {signal['exit_note']}",
                f"- 失效: {signal['invalidation_note']}",
                "",
            ]
        )

    return "\n".join(lines)
