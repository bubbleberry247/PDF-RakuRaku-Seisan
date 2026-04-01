"""Land Registry MCP Server — Claude Code から自社土地アプリを操作する。

7 tools:
  - search_properties: フィルタ検索
  - get_property_packet: 詳細一括取得（detail + notes + history + attachments）
  - lookup_market_price: 国交省APIで相場検索
  - save_property_draft: 下書き保存（新規 or 更新）
  - submit_for_approval: 承認フローへ送信
  - list_pending_approvals: 承認待ち一覧
  - review_approval: 承認 / 却下
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

API_BASE = os.environ.get("LAND_REGISTRY_API", "http://54.238.230.57:8000/api/v1")
DEFAULT_USER = os.environ.get("LAND_REGISTRY_USER", "claude-mcp")
MLIT_API_KEY = os.environ.get("MLIT_API_KEY", "04b062c964fb4d958607708d771c46c0")
MLIT_API_URL = "https://www.reinfolib.mlit.go.jp/ex-api/external/XIT001"

# 市区町村コード
CITY_CODES = {
    "刈谷市": "23210", "安城市": "23212", "知立市": "23225",
    "高浜市": "23227", "碧南市": "23209", "豊田市": "23211",
    "岡崎市": "23202", "西尾市": "23213", "豊明市": "23229",
}

mcp = FastMCP(
    "land-registry",
    instructions=(
        "自社土地台帳アプリ（Land Registry v3）を操作するMCPサーバー。"
        "愛知県刈谷市・安城市の不動産物件を検索・閲覧・更新申請できます。"
    ),
)


def _headers(user_id: str | None = None) -> dict[str, str]:
    return {
        "X-User-Id": user_id or DEFAULT_USER,
        "Content-Type": "application/json",
    }


async def _api(
    method: str,
    path: str,
    *,
    json: dict | None = None,
    params: dict | None = None,
    user_id: str | None = None,
) -> Any:
    """Call Land Registry REST API."""
    url = f"{API_BASE}{path}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.request(
            method, url, json=json, params=params, headers=_headers(user_id)
        )
        resp.raise_for_status()
        return resp.json()


# ---------- Tool 1: search_properties ----------


@mcp.tool()
async def search_properties(
    query: str | None = None,
    area_min_m2: float | None = None,
    area_max_m2: float | None = None,
    price_min: int | None = None,
    price_max: int | None = None,
    zoning: list[str] | None = None,
    sale_status: list[str] | None = None,
    ownership_status: list[str] | None = None,
    limit: int = 20,
) -> str:
    """土地を条件で検索する。住所キーワード、面積、価格、用途地域、販売状況で絞り込み可能。"""
    payload: dict[str, Any] = {"limit": min(limit, 100), "include_stale": True}
    if query:
        payload["query"] = query
    if area_min_m2 is not None:
        payload["area_min_m2"] = area_min_m2
    if area_max_m2 is not None:
        payload["area_max_m2"] = area_max_m2
    if price_min is not None:
        payload["price_min"] = price_min
    if price_max is not None:
        payload["price_max"] = price_max
    if zoning:
        payload["zoning"] = zoning
    if sale_status:
        payload["sale_status"] = sale_status
    if ownership_status:
        payload["ownership_status"] = ownership_status

    data = await _api("POST", "/lands/search", json=payload)
    total = data["total"]
    items = data["items"]

    lines = [f"検索結果: {total}件 (表示: {len(items)}件)"]
    for item in items:
        price = f"¥{item['price_jpy']:,}" if item.get("price_jpy") else "価格未設定"
        area = f"{item['area_m2']}m²" if item.get("area_m2") else ""
        status = item.get("sale_status", "")
        lines.append(
            f"  {item['land_id']} | {item['name']} | {item['address']} | {price} | {area} | {status}"
        )
    if data.get("has_more"):
        lines.append(f"  ... 他 {total - len(items)}件")
    return "\n".join(lines)


# ---------- Tool 2: get_property_packet ----------


@mcp.tool()
async def get_property_packet(land_id: str) -> str:
    """土地の詳細情報を一括取得する（基本情報 + メモ + 履歴 + 添付 + 申請）。"""
    detail, notes, history, attachments, requests = await _gather_property_data(land_id)

    lines = [f"=== {detail['name']} ({land_id}) ==="]
    lines.append(f"住所: {detail['address']}")
    lines.append(f"地番: {detail.get('parcel_number', '未設定')}")
    lines.append(
        f"面積: {detail.get('area_m2', '?')}m² | "
        f"価格: {_fmt_price(detail.get('price_jpy'))} | "
        f"坪単価: {_fmt_price(detail.get('price_per_tsubo'))}"
    )
    lines.append(
        f"用途地域: {detail.get('zoning', '未設定')} | "
        f"建蔽率: {detail.get('building_coverage_pct', '?')}% | "
        f"容積率: {detail.get('floor_area_ratio_pct', '?')}%"
    )
    lines.append(
        f"道路: {detail.get('road_direction', '?')} {detail.get('road_width_m', '?')}m "
        f"({detail.get('road_type', '?')}) | 間口: {detail.get('frontage_m', '?')}m"
    )
    lines.append(
        f"販売状況: {detail.get('sale_status', '?')} | "
        f"所有状況: {detail.get('ownership_status', '?')}"
    )
    lines.append(f"現況: {detail.get('current_state', '?')}")
    lines.append(f"更新日時: {detail.get('updated_at', '?')}")

    if notes:
        lines.append(f"\n--- メモ ({len(notes)}件) ---")
        for note in notes[:5]:
            lines.append(f"  [{note.get('note_type', '')}] {note['note_text'][:80]} ({note['created_by']}, {note['created_at'][:10]})")

    if history:
        lines.append(f"\n--- 履歴 ({len(history)}件) ---")
        for h in history[:5]:
            lines.append(f"  v{h.get('version', '?')} | {h.get('changed_at', '?')[:10]} | {h.get('changed_by', '?')}")

    if requests:
        lines.append(f"\n--- 申請 ({len(requests)}件) ---")
        for r in requests[:5]:
            lines.append(f"  {r.get('request_id', '?')} | {r.get('action', '?')} | {r.get('status', '?')}")

    if attachments:
        lines.append(f"\n--- 添付 ({len(attachments)}件) ---")

    return "\n".join(lines)


async def _gather_property_data(land_id: str) -> tuple:
    """Gather detail + notes + history + attachments + requests concurrently."""
    import asyncio

    results = await asyncio.gather(
        _api("GET", f"/lands/{land_id}"),
        _api("GET", f"/lands/{land_id}/notes"),
        _api("GET", f"/lands/{land_id}/history"),
        _api("GET", f"/lands/{land_id}/attachments"),
        _api("GET", f"/lands/{land_id}/requests"),
        return_exceptions=True,
    )
    return tuple(r if not isinstance(r, Exception) else [] for r in results)


def _fmt_price(price: int | None) -> str:
    if not price:
        return "未設定"
    if price >= 10000:
        return f"{price // 10000:,}万円"
    return f"¥{price:,}"


# ---------- Tool 3: lookup_market_price ----------


@mcp.tool()
async def lookup_market_price(
    city: str = "刈谷市",
    district: str | None = None,
    year: int = 2024,
) -> str:
    """国交省APIでエリアの不動産取引相場を検索する。city=市名、district=町名（任意）、year=年。"""
    city_code = CITY_CODES.get(city)
    if not city_code:
        return f"ERROR: '{city}' は未対応。対応都市: {', '.join(CITY_CODES.keys())}"

    params = {"year": str(year), "area": "23", "city": city_code}
    headers = {"Ocp-Apim-Subscription-Key": MLIT_API_KEY}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(MLIT_API_URL, params=params, headers=headers)
        if resp.status_code != 200:
            return f"ERROR: API returned {resp.status_code}"
        data = resp.json()

    items = data.get("data", [])
    lands = [i for i in items if "宅地(土地)" in i.get("Type", "")]

    if district:
        lands = [i for i in lands if district in i.get("DistrictName", "")]

    if not lands:
        area_label = f"{city}{district}" if district else city
        return f"{area_label}の{year}年の宅地取引データはありません。"

    # Compute stats
    prices = []
    areas = []
    tsubo_prices = []
    for item in lands:
        p = int(item.get("TradePrice", 0))
        a = float(item.get("Area", 0))
        if p > 0 and a > 0:
            prices.append(p)
            areas.append(a)
            tsubo_prices.append(p / (a / 3.30579))

    if not tsubo_prices:
        return "取引データはありますが、価格・面積が不明な件のみでした。"

    avg_tsubo = int(sum(tsubo_prices) / len(tsubo_prices))
    min_tsubo = int(min(tsubo_prices))
    max_tsubo = int(max(tsubo_prices))
    avg_price = int(sum(prices) / len(prices))
    avg_area = int(sum(areas) / len(areas))

    area_label = f"{city}{district}" if district else city
    lines = [
        f"=== {area_label} {year}年 宅地取引相場 ===",
        f"取引件数: {len(tsubo_prices)}件",
        f"平均坪単価: {avg_tsubo:,}円/坪（{avg_tsubo // 10000}万円/坪）",
        f"坪単価範囲: {min_tsubo:,}〜{max_tsubo:,}円/坪",
        f"平均取引価格: {avg_price:,}円（{avg_price // 10000}万円）",
        f"平均面積: {avg_area}m²",
        "",
        "--- 直近取引（最大5件） ---",
    ]
    for item in lands[:5]:
        p = int(item.get("TradePrice", 0))
        a = item.get("Area", "?")
        d = item.get("DistrictName", "?")
        z = item.get("CityPlanning", "?")
        period = item.get("Period", "?")
        direction = item.get("Direction", "")
        breadth = item.get("Breadth", "")
        road = f"{direction}{breadth}m" if direction and breadth else ""
        lines.append(
            f"  {d} | {p:,}円 | {a}m² | {z} | {road} | {period}"
        )

    return "\n".join(lines)


# ---------- Tool 4: save_property_draft ----------


@mcp.tool()
async def save_property_draft(
    land_id: str,
    changes: dict[str, Any],
    reason: str = "",
) -> str:
    """土地の更新申請（下書き）を作成する。changesに変更したいフィールドを指定。"""
    payload: dict[str, Any] = {
        "land_id": land_id,
        "action": "update",
        "changed_fields": changes,
    }
    if reason:
        payload["evidence"] = [{"field_name": "general", "source_type": "manual", "quote_text": reason}]

    result = await _api("POST", "/land-change-requests", json=payload)
    return (
        f"申請作成完了: {result['request_id']}\n"
        f"ステータス: {result['status']} | リスク: {result['risk_level']} | "
        f"承認要否: {result['approval_required']}"
    )


# ---------- Tool 5: submit_for_approval ----------


@mcp.tool()
async def submit_for_approval(request_id: str) -> str:
    """下書き申請を承認フローに提出する。"""
    result = await _api("POST", f"/land-change-requests/{request_id}/submit")
    return f"提出完了: {request_id}\nステータス: {result.get('status', 'submitted')}"


# ---------- Tool 6: list_pending_approvals ----------


@mcp.tool()
async def list_pending_approvals(limit: int = 20) -> str:
    """承認待ちの申請一覧を取得する。"""
    items = await _api("GET", "/approval-queue")
    if not items:
        return "承認待ちの申請はありません。"

    lines = [f"承認待ち: {len(items)}件"]
    for item in items[:limit]:
        lines.append(
            f"  {item.get('request_id', '?')} | {item.get('land_id', '?')} | "
            f"{item.get('action', '?')} | {item.get('status', '?')} | "
            f"{item.get('submitted_by', '?')}"
        )
    return "\n".join(lines)


# ---------- Tool 7: review_approval ----------


@mcp.tool()
async def review_approval(
    request_id: str,
    decision: str,
    comment: str = "",
) -> str:
    """申請を承認(approve)または却下(reject)する。decisionは 'approve' か 'reject'。"""
    if decision not in ("approve", "reject"):
        return "ERROR: decision は 'approve' または 'reject' を指定してください。"

    if decision == "approve":
        result = await _api("POST", f"/land-change-requests/{request_id}/approve")
    else:
        result = await _api(
            "POST",
            f"/land-change-requests/{request_id}/reject",
            params={"reason": comment or "却下"},
        )
    return f"{decision} 完了: {request_id}\nステータス: {result.get('status', decision + 'd')}"


# ---------- Entry point ----------

if __name__ == "__main__":
    mcp.run(transport="stdio")
