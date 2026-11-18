"""Patch 6.1: bounded, schema-driven multi-fact planning (no raw SQL).

Independent aggregations are evaluated against the same authenticated, read-only
PostgreSQL transaction, then merged in Python on *verified* grouping keys.
There is deliberately no generic arbitrary expression or parent-to-child join.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re

from app.services.ai_general_query import (MAX_ROWS, compile_plan, validate_plan)

MULTI_QUERY_TOOL = "query_sibima_multi"
_LABEL = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_MAX_PARTS = 3
_MAX_GUARDS = 2


def _plan_dimensions(plan: dict) -> set[str]:
    keys = set(plan["dimensi"])
    if plan.get("periode"):
        keys.add(f"{plan['periode']['kolom']}:{plan['periode']['tingkat']}")
    return keys


def _safe_group_value(value):
    if value is None or type(value) in (str, int, float, bool):
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise ValueError("Tipe kunci pengelompokan tidak didukung.")


def _key_tuple(values: tuple) -> tuple:
    # Numeric database IDs and dates have stable types in each group. Keep None
    # distinct from other data; never coerce identifiers to numeric strings.
    return tuple(_safe_group_value(v) for v in values)


def validate_multi_args(args: object, catalog: dict, *, user_id: int) -> dict:
    if not isinstance(args, dict) or set(args) - {"analisis", "gabung", "cek_entitas", "perhitungan"}:
        raise ValueError("Parameter multi-query tidak dikenal.")
    parts = args.get("analisis")
    if not isinstance(parts, list) or not 2 <= len(parts) <= _MAX_PARTS:
        raise ValueError("Multi-query memerlukan 2–3 analisis terpisah.")
    cleaned = []
    seen_names = set()
    for item in parts:
        if not isinstance(item, dict) or set(item) != {"nama", "rencana"}:
            raise ValueError("Komponen analisis tidak dikenal.")
        name = item["nama"]
        if type(name) is not str or not _LABEL.fullmatch(name) or name in seen_names:
            raise ValueError("Nama analisis harus unik dan sederhana.")
        seen_names.add(name)
        plan = validate_plan(item["rencana"], catalog)
        if plan["mode"] != "agregasi" or not _plan_dimensions(plan):
            raise ValueError("Setiap analisis gabungan harus berupa agregasi berkelompok.")
        # Fail closed BEFORE running any business data SQL.
        compile_plan(plan, catalog, user_id=user_id)
        cleaned.append({"nama": name, "rencana": item["rencana"], "validated": plan})
    join = args.get("gabung")
    if not isinstance(join, dict) or set(join) != {"kunci", "pemetaan", "jenis"}:
        raise ValueError("Penggabungan membutuhkan kunci, pemetaan, dan jenis.")
    keys = join["kunci"]
    if (not isinstance(keys, list) or not 1 <= len(keys) <= 3 or
            any(type(k) is not str or not _LABEL.fullmatch(k) for k in keys) or
            len(set(keys)) != len(keys)):
        raise ValueError("Kunci penggabungan harus unik dan valid.")
    if join["jenis"] not in ("inner", "outer"):
        raise ValueError("Gabungan hanya menerima inner atau outer.")
    mapping = join["pemetaan"]
    if not isinstance(mapping, dict) or set(mapping) != seen_names:
        raise ValueError("Pemetaan harus tersedia untuk semua analisis.")
    origins: dict[str, list[str]] = {k: [] for k in keys}
    for part in cleaned:
        own = mapping[part["nama"]]
        if not isinstance(own, dict) or set(own) != set(keys):
            raise ValueError("Setiap analisis harus memiliki semua kunci.")
        # Reject grouping by a hidden third dimension: two rows could otherwise
        # collide on the join key and result in a misleading arbitrary winner.
        if any(type(v) is not str for v in own.values()):
            raise ValueError("Pemetaan dimensi tidak valid.")
        if set(own.values()) != _plan_dimensions(part["validated"]):
            raise ValueError("Kunci penggabungan tidak sesuai dimensi analisis.")
        for key in keys:
            val = own[key]
            if type(val) is not str:
                raise ValueError("Pemetaan dimensi tidak valid.")
            origins[key].append(val)
    for key, columns in origins.items():
        if len(set(columns)) == 1:
            continue
        # Dates from different fact tables can be aligned on the SAME calendar
        # granularity (with a shared app/DB timezone). Other dimensions must be
        # exactly the same catalog column: no model-invented semantic equivalence.
        if not all(re.fullmatch(r"[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*:(hari|bulan|tahun)", c)
                   for c in columns) or len({c.rsplit(":", 1)[1] for c in columns}) != 1:
            raise ValueError("Kunci antar-fakta berbeda; gunakan kolom/tingkat periode yang sama.")
    guards = args.get("cek_entitas", [])
    if not isinstance(guards, list) or len(guards) > _MAX_GUARDS:
        raise ValueError("Pemeriksaan entitas maksimal dua.")
    guards_clean = []
    for guard in guards:
        if not isinstance(guard, dict) or set(guard) != {"nama", "rencana"}:
            raise ValueError("Parameter cek entitas tidak valid.")
        name = guard["nama"]
        if type(name) is not str or not _LABEL.fullmatch(name):
            raise ValueError("Nama entitas tidak valid.")
        gp = validate_plan(guard["rencana"], catalog)
        if (gp["mode"] != "agregasi" or gp["agregasi"] != {"fungsi": "count", "kolom": None}
                or gp["dimensi"] or gp["periode"] or not gp["filter"]
                or any(f["op"] != "eq" for f in gp["filter"])):
            raise ValueError("Cek entitas wajib COUNT dengan filter identitas exact dan tanpa pengelompokan.")
        compile_plan(gp, catalog, user_id=user_id)
        guards_clean.append({"nama": name, "rencana": guard["rencana"]})
    derived = args.get("perhitungan", [])
    if not isinstance(derived, list) or len(derived) > 2:
        raise ValueError("Maksimal dua perhitungan turunan.")
    used_names = seen_names | set(keys)
    for item in derived:
        if not isinstance(item, dict) or set(item) != {"nama", "jenis", "a", "b"}:
            raise ValueError("Perhitungan turunan tidak dikenal.")
        name = item["nama"]
        if type(name) is not str or not _LABEL.fullmatch(name) or name in used_names:
            raise ValueError("Nama perhitungan harus unik.")
        used_names.add(name)
        if item["jenis"] not in ("selisih", "rasio_persen") or item["a"] not in seen_names or item["b"] not in seen_names:
            raise ValueError("Perhitungan hanya boleh menggunakan dua metrik yang sudah dihitung.")
    return {"analisis": cleaned, "gabung": join, "cek_entitas": guards_clean,
            "perhitungan": derived}


def execute_multi(cur, *, role: str, user_id: int, args: dict) -> dict:
    if role == "siswa":
        raise PermissionError("Analisis lintas-tabel umum tidak tersedia untuk Siswa.")
    from app.repositories.ai_general_repo import execute_general
    from app.services.ai_general_query import read_catalog

    catalog = read_catalog(cur, role)
    request = validate_multi_args(args, catalog, user_id=user_id)
    checks = []
    for guard in request["cek_entitas"]:
        result = execute_general(cur, user_id=user_id, role=role, name="query_sibima_general",
                                 args=guard["rencana"], catalog=catalog)
        count = result["agregat_global"]
        found = isinstance(count, int) and count > 0
        checks.append({"entitas": guard["nama"], "ditemukan": found})
        if not found:
            return {"status": "entitas_tidak_ditemukan", "cek_entitas": checks,
                    "data": [], "analisis": [], "terpotong": False,
                    "catatan": "Objek yang diminta tidak ditemukan dalam cakupan akses. "
                               "Jangan menafsirkannya sebagai jumlah pembayaran 0."}
    results = []
    for part in request["analisis"]:
        result = execute_general(cur, user_id=user_id, role=role, name="query_sibima_general",
                                 args=part["rencana"], catalog=catalog)
        if result["terpotong"]:
            return {"status": "perlu_persempit_filter", "cek_entitas": checks,
                    "data": [], "analisis": [], "terpotong": True,
                    "catatan": "Salah satu agregasi melebihi batas 20 grup. "
                               "Gabungan tidak dibuat supaya ranking tidak salah. Persempit filter/periode."}
        results.append((part["nama"], result))
    keys = request["gabung"]["kunci"]
    mapping = request["gabung"]["pemetaan"]
    joined: dict[tuple, dict] = {}
    seen_per_part: dict[str, set[tuple]] = {}
    for name, result in results:
        own = mapping[name]
        seen = set()
        for row in result["data"]:
            key = _key_tuple(tuple(row[own[k]] for k in keys))
            if key in seen:
                raise ValueError("Kunci pengelompokan duplikat; gabungan dibatalkan.")
            seen.add(key)
            record = joined.setdefault(key, {**dict(zip(keys, key)),
                                              **{part["nama"]: None for part in request["analisis"]}})
            record[name] = row["nilai"]
        seen_per_part[name] = seen
    if request["gabung"]["jenis"] == "inner":
        joined = {k: v for k, v in joined.items() if all(k in s for s in seen_per_part.values())}
    if len(joined) > MAX_ROWS:
        return {"status": "perlu_persempit_filter", "cek_entitas": checks,
                "data": [], "analisis": [], "terpotong": True,
                "catatan": "Gabungan melebihi 20 grup. Persempit filter sebelum membandingkan."}
    for record in joined.values():
        for calc in request["perhitungan"]:
            a, b = record[calc["a"]], record[calc["b"]]
            if a is None or b is None:
                record[calc["nama"]] = None
                continue
            try:
                a_num, b_num = Decimal(str(a)), Decimal(str(b))
            except InvalidOperation as exc:
                raise ValueError("Perhitungan turunan membutuhkan angka.") from exc
            if not a_num.is_finite() or not b_num.is_finite():
                raise ValueError("Angka perhitungan turunan tidak finite.")
            if calc["jenis"] == "rasio_persen":
                record[calc["nama"]] = (str((a_num / b_num * Decimal(100)).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP)) if b_num != 0 else None)
            else:
                record[calc["nama"]] = str(a_num - b_num)
    # Sorting is deterministic but is NOT a business ranking, since different
    # metrics may have different units. The model may explain a ranking only
    # if the underlying numbers support it.
    ordered = sorted(joined.items(), key=lambda item: tuple((v is None, str(v)) for v in item[0]))
    return {
        "status": "ok", "cek_entitas": checks, "data": [record for _, record in ordered],
        "jumlah_grup": len(ordered), "terpotong": False, "role": role,
        "analisis": [{"nama": name, "tabel_utama": res["rencana"]["tabel_utama"],
                      "agregasi": res["rencana"]["agregasi"],
                      "agregat_global": res["agregat_global"]} for name, res in results],
        "kunci": keys,
        "perhitungan": request["perhitungan"],
        "catatan": "Masing-masing fakta dihitung terpisah lalu diselaraskan pada kunci berkelompok. "
                   "Nilai null berarti tidak ada grup pada fakta itu, BUKAN otomatis nol. "
                   "Persentase tidak boleh dibagi dari rata-rata persentase tanpa pembobotan. "
                   "Tidak ada JOIN antartabel fakta dan tidak ada perhitungan dari sampel 20 baris.",
    }


# Schema accepts only fixed JSON object shapes; reused embedded plan fields
# are *already* validated against the fresh PostgreSQL schema by the backend.
from app.services.ai_general_query import QUERY_DECL
MULTI_DECL = {
    "type": "function", "name": MULTI_QUERY_TOOL,
    "description": (
        "Gabungkan 2-3 agregasi PostgreSQL independen (mis. nilai dan kehadiran) "
        "pada kunci yang sama tanpa JOIN antartabel fakta. Gunakan setelah describe_sibima_schema. "
        "Setiap analisis berisi nama + rencana agregasi query_sibima_general lengkap dengan dimensi. "
        "gabung.kunci nama alias grup, gabung.pemetaan memetakan alias ke dimensi asli tiap rencana; "
        "kolom biasa harus identik lintas rencana, kalender hari/bulan/tahun dapat cocok antar tabel berbeda. "
        "inner hanya grup yang ada di SEMUA analisis, outer semua grup dengan null untuk data hilang. "
        "Gunakan cek_entitas COUNT exact pada program/pengguna sebelum menjawab nominal 0 untuk nama yang mungkin tidak ada. "
        "Untuk rasio/selisih numerik gunakan perhitungan turunan (a,b) dengan denominator yang benar. "
        "Maksimal 20 grup; jika terpotong, persempit filter. Jangan mengarang atau menambah baris yang tidak dikembalikan."
    ),
    "parameters": {"type": "object", "properties": {
        "analisis": {"type": "array", "minItems": 2, "maxItems": 3, "items": {"type": "object", "properties": {
            "nama": {"type": "string"}, "rencana": QUERY_DECL["parameters"]
        }, "required": ["nama", "rencana"]}},
        "gabung": {"type": "object", "properties": {
            "kunci": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 3},
            "jenis": {"type": "string", "enum": ["inner", "outer"]},
            "pemetaan": {"type": "object", "description": "Map nama analisis ke alias kunci -> dimensi dari rencana"}
        }, "required": ["kunci", "jenis", "pemetaan"]},
        "cek_entitas": {"type": "array", "maxItems": 2, "items": {"type": "object", "properties": {
            "nama": {"type": "string"}, "rencana": QUERY_DECL["parameters"]
        }, "required": ["nama", "rencana"]}},
        "perhitungan": {"type": "array", "maxItems": 2, "items": {"type": "object", "properties": {
            "nama": {"type": "string"}, "jenis": {"type": "string", "enum": ["selisih", "rasio_persen"]},
            "a": {"type": "string", "description": "nama analisis sebagai pembilang / minuend"},
            "b": {"type": "string", "description": "nama analisis sebagai penyebut / subtrahend"},
        }, "required": ["nama", "jenis", "a", "b"]}}
    }, "required": ["analisis", "gabung"]}
}
