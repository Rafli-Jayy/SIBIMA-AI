"""Execution endpoint for Patch 6 schema-driven, read-only analytics.

Caller MUST already have verified login role and opened READ ONLY transaction.
This module is also independently fail-closed on role/root/scope/field checks.
"""
from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

from app.services.ai_general_query import (
    GENERAL_QUERY_TOOL, GENERAL_SCHEMA_TOOL,
    MAX_ROWS, compile_plan, describe_catalog, read_catalog, validate_plan,
)


def _safe(value):
    if value is None or type(value) in (int, float, bool):
        return value
    if isinstance(value, (date, datetime, time, Decimal)):
        return str(value)
    if isinstance(value, str):
        return "".join(c for c in value if ord(c) >= 32 and ord(c) != 127)[:120]
    # No JSON/object/bytea/blob values flow through the tool.
    return None


def execute_general(cur, *, user_id: int, role: str, name: str, args: dict,
                    catalog: dict | None = None) -> dict:
    if name not in (GENERAL_SCHEMA_TOOL, GENERAL_QUERY_TOOL):
        raise PermissionError("Tool query umum tidak dikenal.")
    if role == "siswa":
        raise PermissionError("Metadata dan query database umum tidak tersedia untuk Siswa.")
    if role not in {"admin", "tutor"} or type(user_id) is not int or user_id <= 0:
        raise PermissionError("Sesi atau role tidak valid.")
    if not isinstance(args, dict):
        raise ValueError("Argumen harus objek JSON.")
    if catalog is None:
        catalog = read_catalog(cur, role)
    if catalog.get("role") != role:
        raise PermissionError("Metadata role tidak sesuai sesi.")
    if name == GENERAL_SCHEMA_TOOL:
        if set(args) - {"tabel"}:
            raise ValueError("Argumen metadata tidak dikenal.")
        return describe_catalog(catalog, selected=args.get("tabel"))
    plan = validate_plan(args, catalog)
    total_sql, detail_sql, detail_params, params, dims = compile_plan(plan, catalog, user_id=user_id)
    cur.execute(total_sql, params)
    aggregate_row = cur.fetchone() or {}
    grand_total = _safe(aggregate_row.get("nilai_global"))
    data = []
    truncated = False
    if detail_sql:
        cur.execute(detail_sql, detail_params if detail_params is not None else params)
        data_all = cur.fetchmany(plan["limit"] + 1)
        truncated = len(data_all) > plan["limit"]
        for row in data_all[:plan["limit"]]:
            rendered = {d: _safe(row.get(f"d{i}")) for i, d in enumerate(dims)}
            if plan["mode"] == "agregasi":
                rendered["nilai"] = _safe(row.get("nilai"))
            data.append(rendered)
    else:
        data = [{"nilai": grand_total}]
    return {
        "status": "ok", "data": data,
        "rencana": {"tabel_utama": plan["tabel_utama"], "mode": plan["mode"], "agregasi": plan["agregasi"],
                    "dimensi": plan["dimensi"], "periode": plan.get("periode"),
                    "syarat_agregat": ({"op": plan["syarat_agregat"]["op"],
                                        "nilai": str(plan["syarat_agregat"]["nilai"])}
                                       if plan["syarat_agregat"] else None), "filter": [
                        {"kolom": f["kolom"], "op": f["op"]} for f in plan["filter"]]},
        "agregat_global": grand_total if plan["mode"] == "agregasi" else None,
        "data_kosong": grand_total is None if plan["mode"] == "agregasi" else grand_total == 0,
        "keberadaan_entitas": "belum_diperiksa",
        "jumlah_total": grand_total if plan["mode"] == "detail" else None,
        "jumlah_ditampilkan": len(data), "batas_baris": plan["limit"],
        "terpotong": truncated, "role": role,
        "basis": "Agregasi berdasarkan tabel fakta utama; JOIN hanya mengikuti FK anak-ke-induk sehingga tidak menggandakan baris fakta.",
        "catatan": "Agregat global mencakup semua baris sesuai filter; rincian dapat terpotong. "
                   "Agregat nol bukan bukti entitas yang disebut memang ada. "
                   "Status pembayaran, pendaftaran, dan pertemuan tetap berbeda. "
                   "Jangan tafsirkan gabungan SUM beberapa pembayaran sebagai saldo net tanpa aturan bisnis.",
    }
