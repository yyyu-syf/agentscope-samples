# -*- coding: utf-8 -*-
"""Stock claim domain service used by MCP tools and chat prompt routing."""

from __future__ import annotations

import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

STOCK_CLAIM_SYSTEM_PROMPT = (
    "你是股票索赔助手。你的职责只有两件事：收集计算所需信息，并转述工具返回的索赔金额结果。\n\n"
    "【函数与流程】\n"
    "1) 先识别用户是否提供股票代码；若提供，先调用 get_stock_claim_reference_by_code。\n"
    "2) get_stock_claim_reference_by_code 的 stock_code 必须是6位数字字符串。\n"
    "3) 你会得到立案日期 基准日 基准价等信息。\n"
    "4) 继续向用户收集股票交易信息包括买入和卖出信息。\n"
    "5) 仅当买入和卖出信息齐全时进行分析，哪些在立案日前买入，哪些在基准日前卖出，哪些在基准日后卖出。\n"
    "6) 调用calculate_stock_claim_compensation。\n"
    "6) 最终金额只可使用 calculate_stock_claim_compensation 返回的 claim_amount_total 字段。\n\n"
    "【必须收集的信息】\n"
    "- 股票代码\n"
    "- 买入日期 买入股数 买入价格\n"
    "- 卖出日期 卖出股数 卖出价格\n"
    "买入日期用于判断是否立案日之前 要计算在立案日前的买入均价和买入股数作为调用calculate_stock_claim_compensation的参数。\n"
    "卖出日期用于判断是否基准日前卖出 然后要计算基准日前卖出部分的股数和均价作为调用calculate_stock_claim_compensation的参数。不要在回答中提到基准日基准价等专业名字。用通俗易懂的语言提问用户卖出时间。\n"
    "【基准价处理】\n"
    "- 若get_stock_claim_reference_by_code。返回 benchmark_status=ready 且有 benchmark_price，则直接使用作为calculate_stock_claim_compensation的参数。。\n"
    "- 若 benchmark_status=pending，说明还未到基准日，调用 calculate_stock_claim_compensation 时不要传 benchmark_price 字段（省略该键）。\n"
    "所有用户已经卖出的部分则是基准日前卖出的部分。若基准日还未到且有未卖出部分，则需要用户提供预计卖出价。然后进行卖出均价计算填入calculate_stock_claim_compensation进行预估索赔金额。\n"
    "【硬性规则（最高优先级）】\n"
    "1. 严格按照 function/tool 返回的股票信息/索赔金额进行输出。\n"
    "2. 严禁自行计算、估算、推导、心算索赔金额。\n"
    "3. 不解释计算过程、不展示公式、不输出推理细节。\n"
    "4. 回复必须简短清晰，以2-5句为主。\n"
    "5. 调用函数时，arguments 必须是合法 JSON；可选字段缺失时直接省略该字段。\n\n"
    "【缺少信息时的回复案例】\n"
    "- 我检索到{股票名称/代码}在{立案日期}被立案。\n"
    "- 您在{买入日期}买入{股票}{买入股数}股，均价{买入均价}。\n"
    "- 如需计算索赔金额，请提供卖出日期，卖出股数和卖出均价。\n\n"
    "【信息完整并拿到工具金额时的回复案例】\n"
    "根据您提供的信息：\n"
    "- 您在{买入日期}买入{股票}{买入股数}股，均价{买入均价}；\n"
    "- 您在{卖出日期或未卖出}卖出{卖出股数}股，均价{卖出均价或-}。\n"
    "预估索赔额：{claim_amount_total}元。\n\n"
    "【异常场景】\n"
    "- 若计算工具未返回 claim_amount_total（为空、报错或缺字段），只回复：当前无法给出索赔金额，请联系律师进行咨询。\n"
    "- 若用户要求展示计算过程，只回复：索赔金额暂不展示计算过程，请联系律师进行咨询。\n"
    "计算规则（calculate_stock_claim_compensation的具体内容）：\n"
    "- 前置条件：立案前买入，且核心数字有效；\n"
    "- 剩余股数 = 买入总股数 - 基准日前卖出股数；\n"
    "- 基准日前卖出部分 = max(买入均价 - 基准日前卖出均价, 0) * 基准日前卖出股数；\n"
    "- 剩余部分（含基准日后卖出或未卖出）= max(买入均价 - 基准价, 0) * 剩余股数；\n"
    "- 总索赔额 = 两部分之和；\n"
    "- 若非立案前买入，则索赔额为0；\n"
    "- 任何计算结果若为负值，一律按0处理。\n\n"
)

DEFAULT_DB_PATH = (
    Path(__file__).resolve().parent / "data" / "stock_claim" / "stock_claim.sqlite"
)


def resolve_stock_claim_db_path(config_db_path: Optional[str] = None) -> Path:
    """Resolve db path by priority: env -> config -> fallback."""
    env_db_path = os.getenv("STOCK_CLAIM_DB_PATH", "").strip()
    if env_db_path:
        return Path(env_db_path).expanduser().resolve()

    if config_db_path:
        cfg_db_path = str(config_db_path).strip()
        if cfg_db_path:
            return Path(cfg_db_path).expanduser().resolve()

    return DEFAULT_DB_PATH.resolve()


class StockClaimReferenceStore:
    def __init__(self, db_path: Optional[str | Path] = None):
        resolved = (
            Path(db_path).expanduser().resolve() if db_path else DEFAULT_DB_PATH.resolve()
        )
        resolved.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = resolved

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def ensure_schema(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS stock_claim_reference (
                    stock_code TEXT PRIMARY KEY,
                    stock_name TEXT,
                    filing_date TEXT,
                    benchmark_date TEXT,
                    benchmark_price REAL,
                    benchmark_rule TEXT,
                    benchmark_status TEXT,
                    announcement_title TEXT,
                    announcement_time TEXT,
                    source TEXT,
                    updated_at TEXT
                )
                """,
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS stock_claim_sync_state (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
                """,
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_stock_claim_status "
                "ON stock_claim_reference(benchmark_status)",
            )

    def get_reference(self, stock_code: str) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                SELECT
                    stock_code,
                    stock_name,
                    filing_date,
                    benchmark_date,
                    benchmark_price,
                    benchmark_rule,
                    benchmark_status,
                    announcement_title,
                    announcement_time,
                    source,
                    updated_at
                FROM stock_claim_reference
                WHERE stock_code = ?
                """,
                (stock_code,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return dict(row)


def _round_2(value: float) -> float:
    return float(f"{value:.2f}")


def _read_non_negative_number(
    args: Dict[str, Any],
    key: str,
    errors: List[str],
    *,
    required: bool = True,
) -> Optional[float]:
    if key not in args or args.get(key) is None:
        if required:
            errors.append(f"缺少必填参数: {key}")
        return None

    raw = args.get(key)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        errors.append(f"参数 {key} 必须是数字")
        return None

    if value < 0:
        errors.append(f"参数 {key} 不能为负数")
        return None

    return value


def query_stock_claim_reference(
    stock_code: str,
    store: Optional[StockClaimReferenceStore] = None,
) -> Dict[str, Any]:
    code = stock_code if isinstance(stock_code, str) else ""
    if not re.fullmatch(r"\d{6}", code):
        return {
            "found": False,
            "stock_code": code,
            "stock_name": None,
            "filing_date": None,
            "benchmark_date": None,
            "benchmark_price": None,
            "benchmark_status": "not_found",
            "notes": [],
            "errors": ["参数 stock_code 必须是6位数字字符串"],
        }

    ref_store = store or StockClaimReferenceStore()
    row = ref_store.get_reference(code)
    if not row:
        return {
            "found": False,
            "stock_code": code,
            "stock_name": None,
            "filing_date": None,
            "benchmark_date": None,
            "benchmark_price": None,
            "benchmark_status": "not_found",
            "notes": ["未命中该股票的立案告知书记录"],
            "errors": [],
        }

    benchmark_status = row.get("benchmark_status") or (
        "ready"
        if row.get("benchmark_date") and row.get("benchmark_price") is not None
        else "pending"
    )

    notes: List[str] = []
    if benchmark_status == "pending":
        notes.append("尚未到基准日或基准价尚未形成，需要继续补充卖出信息进行阶段性测算。")

    return {
        "found": True,
        "stock_code": row.get("stock_code"),
        "stock_name": row.get("stock_name"),
        "filing_date": row.get("filing_date"),
        "benchmark_date": row.get("benchmark_date"),
        "benchmark_price": row.get("benchmark_price"),
        "benchmark_status": benchmark_status,
        "notes": notes,
        "errors": [],
    }


def compute_stock_claim_compensation(args: Dict[str, Any]) -> Dict[str, Any]:
    errors: List[str] = []
    notes: List[str] = []

    is_pre_filing_bought = args.get("is_pre_filing_bought")
    if not isinstance(is_pre_filing_bought, bool):
        errors.append("参数 is_pre_filing_bought 必须为布尔值")

    avg_buy_price = _read_non_negative_number(args, "avg_buy_price", errors)
    total_shares = _read_non_negative_number(args, "total_shares", errors)
    pre_benchmark_sold_shares = _read_non_negative_number(
        args,
        "pre_benchmark_sold_shares",
        errors,
    )
    pre_benchmark_avg_sell_price = _read_non_negative_number(
        args,
        "pre_benchmark_avg_sell_price",
        errors,
    )
    benchmark_price = _read_non_negative_number(
        args,
        "benchmark_price",
        errors,
        required=False,
    )
    principal_loss = _read_non_negative_number(
        args,
        "principal_loss",
        errors,
        required=False,
    )

    if (
        total_shares is not None
        and pre_benchmark_sold_shares is not None
        and pre_benchmark_sold_shares > total_shares
    ):
        errors.append("基准日前卖出股数不能大于买入总股数")

    if errors:
        return {
            "eligible": bool(is_pre_filing_bought),
            "claim_amount_total": 0.0,
            "claim_amount_pre_benchmark": 0.0,
            "claim_amount_remaining": 0.0,
            "remaining_shares": 0.0,
            "notes": notes,
            "errors": errors,
        }

    if not is_pre_filing_bought:
        notes.append("用户不属于立案前买入条件，按规则索赔额为0。")
        return {
            "eligible": False,
            "claim_amount_total": 0.0,
            "claim_amount_pre_benchmark": 0.0,
            "claim_amount_remaining": 0.0,
            "remaining_shares": _round_2(total_shares or 0.0),
            "notes": notes,
            "errors": [],
        }

    remaining_shares = max(
        (total_shares or 0.0) - (pre_benchmark_sold_shares or 0.0),
        0.0,
    )

    claim_amount_pre_benchmark = max(
        (avg_buy_price or 0.0) - (pre_benchmark_avg_sell_price or 0.0),
        0.0,
    ) * (pre_benchmark_sold_shares or 0.0)

    claim_amount_remaining = max(
        (avg_buy_price or 0.0) - (benchmark_price or 0.0),
        0.0,
    ) * remaining_shares

    claim_amount_total = claim_amount_pre_benchmark + claim_amount_remaining

    if principal_loss is not None:
        notes.append("principal_loss 仅作为参考输入，不参与核心计算公式。")
        if claim_amount_total > principal_loss:
            notes.append("测算索赔额高于输入的本金亏损，请核对本金亏损口径。")

    return {
        "eligible": True,
        "claim_amount_total": _round_2(claim_amount_total),
        "claim_amount_pre_benchmark": _round_2(claim_amount_pre_benchmark),
        "claim_amount_remaining": _round_2(claim_amount_remaining),
        "remaining_shares": _round_2(remaining_shares),
        "notes": notes,
        "errors": [],
    }
