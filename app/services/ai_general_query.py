"""Patch 6: schema-driven SELECT builder for SIBIMA-AI.

No business-specific metric/domain registry. Schema and FK links come from live
PostgreSQL metadata. Only audited column classes, row scopes, and FK directions
can be used. Gemini supplies a JSON *plan*, never SQL.
"""
from __future__ import annotations

from collections import deque
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import re

# Security policy is intentionally static; analytics fields and JOIN routes are not.
# Authorization boundary: no newly created table becomes visible automatically.
# Discover columns and relationships dynamically *within* these audited tables.
AUDITED_TABLES = frozenset({
    "log_aktivitas", "pembacaan_pengumuman", "target_pengumuman", "pengumuman",
    "kehadiran", "pertemuan_kelas", "pendaftaran", "nilai", "tagihan",
    "pengembalian_pembayaran", "pembayaran", "program_bimbel", "ruangan", "jadwal_kelas",
    "siswa", "tutor", "pengguna",
})
BLOCKED_TABLES = frozenset({"kode_otp"})
BLOCKED_COLUMN_WORDS = re.compile(
    r"password|hash|secret|token|otp|api.?key|credential|"
    r"(^|_)(email|no_hp|nama_wali|locked_until|failed_attempts|"
    r"reject_reason|alasan_tolak|alasan_batal|detail|isi|ringkasan|"
    r"deskripsi|keterangan|sekolah|event_key|batch_key|notif_monitor_from)(_|$)", re.I,
)
IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
VALID_TYPES = frozenset({
    "smallint", "integer", "bigint", "numeric", "decimal", "real", "double precision",
    "boolean", "date", "timestamp without time zone", "timestamp with time zone",
    "character varying", "character", "text", "time without time zone", "USER-DEFINED",
})
NUMERIC_TYPES = frozenset({"smallint", "integer", "bigint", "numeric", "decimal", "real", "double precision"})
DATE_TYPES = frozenset({"date", "timestamp without time zone", "timestamp with time zone"})
TEXT_TYPES = frozenset({"character varying", "character", "text", "USER-DEFINED"})

# Roots may be extended after an authorization review, independent from metric definitions.
ROLE_ROOTS = {
    "admin": None,
    "tutor": frozenset({"tutor", "program_bimbel", "jadwal_kelas", "pertemuan_kelas", "kehadiran", "pendaftaran", "nilai"}),
    "siswa": frozenset({"pengguna", "siswa", "pendaftaran", "tagihan", "pembayaran", "pengembalian_pembayaran", "nilai", "kehadiran"}),
}
ROLE_JOIN_TABLES = {
    "admin": None,
    "tutor": frozenset({"tutor", "siswa", "pengguna", "program_bimbel", "ruangan", "jadwal_kelas", "pertemuan_kelas", "kehadiran", "pendaftaran", "nilai"}),
    "siswa": frozenset({"pengguna", "siswa", "tutor", "program_bimbel", "ruangan", "jadwal_kelas", "pertemuan_kelas", "kehadiran", "pendaftaran", "nilai", "tagihan", "pembayaran", "pengembalian_pembayaran"}),
}
MAX_FILTERS = 6
MAX_GROUPS = 3
MAX_JOIN_EDGES = 6
MAX_ROWS = 20

# Base tables only (no views, sequences, or cross-schema object names).
COLUMN_SQL = """
SELECT c.table_name, c.column_name, c.data_type, c.udt_name
FROM information_schema.columns c
JOIN pg_catalog.pg_namespace n ON n.nspname=c.table_schema
JOIN pg_catalog.pg_class t ON t.relname=c.table_name AND t.relnamespace=n.oid
WHERE c.table_schema='public' AND t.relkind IN ('r','p')
ORDER BY c.table_name, c.ordinal_position
"""
FK_SQL = """
SELECT child.relname AS child_table, parent.relname AS parent_table,
       con.conname AS constraint_name,
       array_agg(ca.attname ORDER BY pairs.ordinality) AS child_columns,
       array_agg(pa.attname ORDER BY pairs.ordinality) AS parent_columns
FROM pg_catalog.pg_constraint con
JOIN pg_catalog.pg_class child ON child.oid=con.conrelid
JOIN pg_catalog.pg_namespace cn ON cn.oid=child.relnamespace
JOIN pg_catalog.pg_class parent ON parent.oid=con.confrelid
JOIN pg_catalog.pg_namespace pn ON pn.oid=parent.relnamespace
CROSS JOIN LATERAL unnest(con.conkey, con.confkey)
    WITH ORDINALITY AS pairs(child_attnum, parent_attnum, ordinality)
JOIN pg_catalog.pg_attribute ca ON ca.attrelid=child.oid AND ca.attnum=pairs.child_attnum
JOIN pg_catalog.pg_attribute pa ON pa.attrelid=parent.oid AND pa.attnum=pairs.parent_attnum
WHERE con.contype='f' AND cn.nspname='public' AND pn.nspname='public'
GROUP BY child.relname, parent.relname, con.conname
ORDER BY child.relname, con.conname
"""


def _ident(name: str) -> str:
    if type(name) is not str or not IDENTIFIER.fullmatch(name):
        raise ValueError("Identifier skema tidak aman.")
    return '"' + name + '"'


def _column_allowed(table: str, column: str, data_type: str) -> bool:
    if not IDENTIFIER.fullmatch(table) or not IDENTIFIER.fullmatch(column):
        return False
    if table not in AUDITED_TABLES or table in BLOCKED_TABLES or BLOCKED_COLUMN_WORDS.search(column):
        return False
    # Unbounded text is excluded even when named innocuously; it may contain secrets.
    if data_type == "text":
        return False
    return data_type in VALID_TYPES


def read_catalog(cur, role: str) -> dict:
    """Read metadata every invocation, so the engine follows the actual schema."""
    if role not in ROLE_ROOTS:
        raise PermissionError("Role tidak dikenal.")
    cur.execute(COLUMN_SQL)
    columns = cur.fetchall()
    all_tables: dict[str, dict[str, str]] = {}
    for row in columns:
        table, col, data_type = row["table_name"], row["column_name"], row["data_type"]
        if _column_allowed(table, col, data_type):
            all_tables.setdefault(table, {})[col] = data_type
    joins = ROLE_JOIN_TABLES[role]
    if joins is not None:
        all_tables = {name: cols for name, cols in all_tables.items() if name in joins}
    # Metadata FK columns do not need to be exposed as data to form authorized JOINs.
    cur.execute(FK_SQL)
    edges = []
    for row in cur.fetchall():
        child, parent, name = row["child_table"], row["parent_table"], row["constraint_name"]
        src, dst = list(row["child_columns"]), list(row["parent_columns"])
        if (child not in all_tables or parent not in all_tables or child == parent or
                not IDENTIFIER.fullmatch(name) or len(src) != len(dst) or not src or
                any(not IDENTIFIER.fullmatch(k) for k in src + dst)):
            continue
        edges.append({"name": name, "child": child, "parent": parent,
                      "child_columns": tuple(src), "parent_columns": tuple(dst)})
    return {"tables": all_tables, "edges": edges, "role": role}


def describe_catalog(catalog: dict, *, selected: object = None) -> dict:
    if selected is None:
        names = sorted(catalog["tables"])
    else:
        if (not isinstance(selected, list) or len(selected) > 18 or
                any(type(t) is not str or t not in catalog["tables"] for t in selected)):
            raise ValueError("Daftar tabel harus berasal dari katalog yang diizinkan.")
        names = sorted(set(selected))
    return {
        "status": "ok",
        "tabel": {t: catalog["tables"][t] for t in names},
        "relasi": [e for e in catalog["edges"] if e["child"] in names and e["parent"] in names],
        "role": catalog["role"],
        "aturan": "Relasi hanya mengikuti FK dari anak ke induk. Rahasia/OTP dan kolom sensitif disembunyikan. "
                  "Jumlah baris hasil maksimal 20. Hindari penjumlahan pada JOIN satu-ke-banyak.",
    }


def _split_col(value: object, catalog: dict) -> tuple[str, str, str]:
    if type(value) is not str or value.count(".") != 1:
        raise ValueError("Kolom harus menggunakan nama tabel.kolom dari katalog.")
    table, col = value.split(".")
    typ = catalog["tables"].get(table, {}).get(col)
    if typ is None:
        raise ValueError("Tabel atau kolom tidak tersedia untuk role ini.")
    return table, col, typ


def _validate_scalar(value, data_type: str, operator: str):
    if operator == "contains":
        if data_type not in TEXT_TYPES or type(value) is not str or not 1 <= len(value) <= 80:
            raise ValueError("Filter mengandung teks tidak valid.")
        return "%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    if value is None:
        raise ValueError("Nilai kosong hanya dapat digunakan dengan is_null.")
    if data_type in NUMERIC_TYPES:
        if type(value) not in (int, float, str):
            raise ValueError("Nilai angka tidak valid.")
        try:
            number = Decimal(str(value))
            if not number.is_finite() or len(str(number)) > 40:
                raise ValueError("Angka tidak valid.")
            return number
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Nilai angka tidak valid.") from exc
    if data_type in DATE_TYPES:
        if type(value) is not str or len(value) > 35:
            raise ValueError("Tanggal tidak valid.")
        try:
            if data_type == "date" or len(value) == 10:
                parsed = date.fromisoformat(value)
                if parsed.isoformat() != value:
                    raise ValueError
            else:
                parsed = datetime.fromisoformat(value)
            return parsed
        except ValueError as exc:
            raise ValueError("Tanggal harus ISO (YYYY-MM-DD atau timestamp ISO).") from exc
    if data_type == "boolean":
        if type(value) is str and value.lower() in ("true", "false"):
            value = value.lower() == "true"
        if type(value) is not bool:
            raise ValueError("Filter boolean harus true/false.")
        return value
    if type(value) is not str or not 1 <= len(value) <= 100 or any(ord(c) < 32 for c in value):
        raise ValueError("Nilai teks tidak valid.")
    return value


def validate_plan(plan: object, catalog: dict) -> dict:
    """Never accept SQL expressions, arbitrary aliases, or non-catalog columns."""
    if not isinstance(plan, dict) or set(plan) - {
        "tabel_utama", "mode", "kolom_output", "urutan", "dimensi", "periode", "agregasi", "filter", "relasi", "urut", "limit", "syarat_agregat"
    }:
        raise ValueError("Format query terstruktur tidak dikenal.")
    root = plan.get("tabel_utama")
    if type(root) is not str or root not in catalog["tables"]:
        raise ValueError("Tabel utama tidak tersedia.")
    role = catalog["role"]
    roots = ROLE_ROOTS[role]
    if roots is not None and root not in roots:
        raise PermissionError("Tabel utama tidak diizinkan untuk role ini.")
    mode = plan.get("mode", "agregasi")
    if mode not in ("agregasi", "detail"):
        raise ValueError("Mode harus agregasi atau detail.")
    outputs = plan.get("kolom_output", [])
    if mode == "detail":
        if (not isinstance(outputs, list) or not 1 <= len(outputs) <= 5 or
                any(type(field) is not str for field in outputs) or len(set(outputs)) != len(outputs)):
            raise ValueError("Detail harus memilih 1–5 kolom unik dari katalog.")
        for field in outputs:
            _split_col(field, catalog)
    elif outputs:
        raise ValueError("Kolom output hanya digunakan untuk mode detail.")
    order_column = plan.get("urutan")
    if mode == "detail":
        if order_column is not None:
            if (not isinstance(order_column, dict) or set(order_column) != {"kolom", "arah"}
                    or order_column["arah"] not in ("asc", "desc")):
                raise ValueError("Urutan detail tidak valid.")
            _split_col(order_column["kolom"], catalog)
    elif order_column is not None:
        raise ValueError("Urutan kolom hanya untuk mode detail.")
    dimensions = plan.get("dimensi", [])
    if (not isinstance(dimensions, list) or len(dimensions) > MAX_GROUPS or
            len(set(map(str, dimensions))) != len(dimensions)):
        raise ValueError("Dimensi maksimal tiga tanpa duplikasi.")
    for column in dimensions:
        _split_col(column, catalog)
    periode = plan.get("periode")
    if periode is not None:
        if (not isinstance(periode, dict) or set(periode) != {"kolom", "tingkat"} or
                periode.get("tingkat") not in ("hari", "bulan", "tahun")):
            raise ValueError("Dimensi periode harus kolom tanggal dan tingkat hari/bulan/tahun.")
        _, _, per_type = _split_col(periode["kolom"], catalog)
        if per_type not in DATE_TYPES or len(dimensions) + 1 > MAX_GROUPS:
            raise ValueError("Periode hanya untuk kolom tanggal; total maksimal tiga dimensi.")
    agg = plan.get("agregasi")
    if mode == "detail":
        if agg is not None or dimensions or periode is not None:
            raise ValueError("Detail tidak boleh digabung dengan agregasi atau pengelompokan.")
        func, agg_col = None, None
    else:
        if not isinstance(agg, dict) or set(agg) - {"fungsi", "kolom"}:
            raise ValueError("Agregasi harus objek terstruktur.")
        func = agg.get("fungsi")
        if func not in ("count", "count_distinct", "sum", "avg", "min", "max"):
            raise ValueError("Fungsi agregasi tidak tersedia.")
        agg_col = agg.get("kolom")
        if func == "count":
            if agg_col is not None:
                raise ValueError("COUNT seluruh baris tidak memerlukan kolom.")
        else:
            _, _, typ = _split_col(agg_col, catalog)
            if func in ("sum", "avg") and typ not in NUMERIC_TYPES:
                raise ValueError("SUM/AVG hanya untuk angka.")
            if func in ("min", "max") and typ not in NUMERIC_TYPES | DATE_TYPES:
                raise ValueError("MIN/MAX hanya untuk angka/tanggal.")
    having = plan.get("syarat_agregat")
    if having is not None:
        if (mode != "agregasi" or not dimensions and periode is None or
                not isinstance(having, dict) or set(having) != {"op", "nilai"} or
                having["op"] not in {"eq", "lt", "lte", "gt", "gte"}):
            raise ValueError("Syarat agregat memerlukan grup, operator, dan angka.")
        having = {"op": having["op"],
                  "nilai": _validate_scalar(having["nilai"], "numeric", "eq")}
    filters = plan.get("filter", [])
    if not isinstance(filters, list) or len(filters) > MAX_FILTERS:
        raise ValueError("Filter maksimal enam.")
    validated_filters = []
    for item in filters:
        if not isinstance(item, dict) or set(item) - {"kolom", "op", "nilai", "nilai_daftar"}:
            raise ValueError("Filter tidak valid.")
        table, col, typ = _split_col(item.get("kolom"), catalog)
        op = item.get("op")
        if op not in {"eq", "ne", "lt", "lte", "gt", "gte", "contains", "in", "is_null"}:
            raise ValueError("Operator tidak didukung.")
        if op == "contains" and typ not in TEXT_TYPES:
            raise ValueError("Pencarian teks hanya untuk kolom teks.")
        if op in {"lt", "lte", "gt", "gte"} and typ not in NUMERIC_TYPES | DATE_TYPES:
            raise ValueError("Perbandingan urutan hanya untuk tanggal/angka.")
        if op == "in":
            v = item.get("nilai_daftar", item.get("nilai"))
            if not isinstance(v, list) or not 1 <= len(v) <= 10:
                raise ValueError("IN harus memiliki 1–10 nilai.")
            val = [_validate_scalar(x, typ, "eq") for x in v]
        elif op == "is_null":
            v = item.get("nilai", True)
            if type(v) is str and v.lower() in ("true", "false"):
                v = v.lower() == "true"
            if type(v) is not bool:
                raise ValueError("Filter null harus boolean.")
            val = v
        else:
            val = _validate_scalar(item.get("nilai"), typ, op)
        validated_filters.append({"kolom": f"{table}.{col}", "op": op, "nilai": val})
    relations = plan.get("relasi", [])
    if (not isinstance(relations, list) or len(relations) > MAX_JOIN_EDGES or
            any(type(n) is not str or not IDENTIFIER.fullmatch(n) for n in relations)
            or len(set(relations)) != len(relations)):
        raise ValueError("Relasi harus daftar nama foreign key unik.")
    order = plan.get("urut", "nilai_terbesar")
    if order not in ("nilai_terbesar", "nilai_terkecil", "dimensi_naik"):
        raise ValueError("Urutan tidak dikenal.")
    limit = plan.get("limit", MAX_ROWS)
    if type(limit) is not int or not 1 <= limit <= MAX_ROWS:
        raise ValueError("Batas baris harus antara 1 dan 20.")
    return {"tabel_utama": root, "mode": mode,
            "kolom_output": outputs, "urutan": order_column,
            "dimensi": dimensions, "periode": periode,
            "agregasi": {"fungsi": func, "kolom": agg_col} if func else None,
            "filter": validated_filters,
            "relasi": relations, "urut": order, "limit": limit,
            "syarat_agregat": having}


def _paths(start: str, goal: str, edges: list[dict]) -> list[list[dict]]:
    """Walk FK child->parent only. Each parent contributes <=1 row per child."""
    queue = deque([(start, [], {start})])
    found = []
    while queue:
        node, path, visited = queue.popleft()
        if node == goal:
            found.append(path)
            continue
        if len(path) >= MAX_JOIN_EDGES:
            continue
        for edge in edges:
            if edge["child"] == node and edge["parent"] not in visited:
                queue.append((edge["parent"], path + [edge], visited | {edge["parent"]}))
    return found


def _choose_edges(plan: dict, catalog: dict) -> list[dict]:
    root = plan["tabel_utama"]
    edges_by_name = {edge["name"]: edge for edge in catalog["edges"]}
    result = []
    joined = {root}
    for name in plan["relasi"]:
        edge = edges_by_name.get(name)
        if not edge or edge["child"] not in joined or edge["parent"] in joined:
            raise ValueError("Jalur relasi tidak sah, tidak berurutan, atau mengulang tabel.")
        result.append(edge)
        joined.add(edge["parent"])
    used_tables = {c.split(".")[0] for c in plan["dimensi"]}
    if plan.get("periode"):
        used_tables.add(plan["periode"]["kolom"].split(".")[0])
    used_tables.update(c.split(".")[0] for c in plan.get("kolom_output", []))
    if plan.get("urutan"):
        used_tables.add(plan["urutan"]["kolom"].split(".")[0])
    if plan["agregasi"] and plan["agregasi"]["kolom"]:
        used_tables.add(plan["agregasi"]["kolom"].split(".")[0])
    used_tables.update(f["kolom"].split(".")[0] for f in plan["filter"])
    for target in sorted(used_tables - joined):
        paths = _paths(root, target, catalog["edges"])
        if len(paths) != 1:
            raise ValueError("Relasi antar tabel ambigu/tidak tersedia; gunakan nama FK pada parameter relasi.")
        for edge in paths[0]:
            if edge["parent"] not in joined:
                if edge["child"] not in joined:
                    raise ValueError("Jalur JOIN tidak terhubung.")
                result.append(edge)
                joined.add(edge["parent"])
    if len(result) > MAX_JOIN_EDGES:
        raise ValueError("Terlalu banyak JOIN.")
    return result


def _role_scope(root: str, role: str) -> tuple[str, bool]:
    """Peran selalu dibatasi pada baris fakta; bukan pada permintaan Gemini."""
    if role == "admin":
        return "", False
    if role == "tutor":
        clauses = {
            "tutor": "t0.id_pengguna=%s",
            "jadwal_kelas": "t0.id_tutor=%s",
            "pertemuan_kelas": "EXISTS (SELECT 1 FROM jadwal_kelas scope_s WHERE scope_s.id_jadwal=t0.id_jadwal AND scope_s.id_tutor=%s)",
            "kehadiran": "EXISTS (SELECT 1 FROM pertemuan_kelas scope_cs JOIN jadwal_kelas scope_s ON scope_s.id_jadwal=scope_cs.id_jadwal WHERE scope_cs.id_pertemuan=t0.id_pertemuan AND scope_s.id_tutor=%s)",
            "nilai": "t0.id_tutor_penginput=%s",
            "pendaftaran": "t0.status='aktif' AND EXISTS (SELECT 1 FROM jadwal_kelas scope_s WHERE scope_s.id_program=t0.id_program AND scope_s.id_tutor=%s AND scope_s.aktif=TRUE)",
            "program_bimbel": "EXISTS (SELECT 1 FROM jadwal_kelas scope_s WHERE scope_s.id_program=t0.id_program AND scope_s.id_tutor=%s AND scope_s.aktif=TRUE)",
        }
    else:
        # The legacy access predicate still uses English compatibility views,
        # intentionally: its business policy is unchanged from the original app.
        from app.repositories.class_access_sql import AKSES_TERKUNCI_SQL, ENROLLMENT_TERAKHIR_TERSEDIA_SQL
        grade_scope = ("EXISTS (SELECT 1 FROM enrollments e WHERE e.id=t0.id_pendaftaran AND e.student_id=%s "
                       f"AND {ENROLLMENT_TERAKHIR_TERSEDIA_SQL} AND NOT {AKSES_TERKUNCI_SQL})")
        attendance_scope = ("EXISTS (SELECT 1 FROM enrollments e JOIN class_sessions scope_cs ON scope_cs.id=t0.id_pertemuan "
                            "JOIN schedules scope_s ON scope_s.id=scope_cs.schedule_id "
                            "WHERE e.id=t0.id_pendaftaran AND e.student_id=t0.id_siswa AND e.student_id=%s "
                            "AND scope_s.program_id=e.program_id AND scope_cs.tanggal>=e.created_at::date "
                            f"AND {ENROLLMENT_TERAKHIR_TERSEDIA_SQL} AND NOT {AKSES_TERKUNCI_SQL})")
        clauses = {
            "pengguna": "t0.id_pengguna=%s",
            "siswa": "t0.id_pengguna=%s",
            "pendaftaran": "t0.id_siswa=%s",
            "tagihan": "EXISTS (SELECT 1 FROM pendaftaran scope_e WHERE scope_e.id_pendaftaran=t0.id_pendaftaran AND scope_e.id_siswa=%s)",
            "pembayaran": "EXISTS (SELECT 1 FROM tagihan scope_i JOIN pendaftaran scope_e ON scope_e.id_pendaftaran=scope_i.id_pendaftaran WHERE scope_i.id_tagihan=t0.id_tagihan AND scope_e.id_siswa=%s)",
            "pengembalian_pembayaran": "EXISTS (SELECT 1 FROM pembayaran scope_py JOIN tagihan scope_i ON scope_i.id_tagihan=scope_py.id_tagihan JOIN pendaftaran scope_e ON scope_e.id_pendaftaran=scope_i.id_pendaftaran WHERE scope_py.id_pembayaran=t0.id_pembayaran AND scope_e.id_siswa=%s)",
            "nilai": grade_scope,
            "kehadiran": attendance_scope,
        }
    if root not in clauses:
        raise PermissionError("Sumber data tidak memiliki kebijakan pembatasan role.")
    return clauses[root], True


def compile_plan(plan: dict, catalog: dict, *, user_id: int) -> tuple[str, str, str | None, tuple, list[str]]:
    """Construct parameterized queries from metadata; never interpolates tool strings."""
    role = catalog["role"]
    if type(user_id) is not int or user_id <= 0:
        raise PermissionError("Sesi tidak valid.")
    plan = validate_plan(plan, catalog)
    edges = _choose_edges(plan, catalog)
    aliases = {plan["tabel_utama"]: "t0"}
    from_sql = "FROM public." + _ident(plan["tabel_utama"]) + " t0"
    for i, edge in enumerate(edges, start=1):
        alias = f"t{i}"
        child_alias = aliases[edge["child"]]
        on = " AND ".join(
            f"{child_alias}.{_ident(child)}={alias}.{_ident(parent)}"
            for child, parent in zip(edge["child_columns"], edge["parent_columns"])
        )
        from_sql += f" LEFT JOIN public.{_ident(edge['parent'])} {alias} ON {on}"
        aliases[edge["parent"]] = alias
    def col_expr(key: str) -> str:
        table, col = key.split(".")
        return f"{aliases[table]}.{_ident(col)}"
    def filter_expr(key: str, value=None) -> str:
        table, col, typ = _split_col(key, catalog)
        expression = col_expr(key)
        if typ == "USER-DEFINED":
            return f"({expression})::text"
        # A calendar-date comparison on timestamptz must include the whole day,
        # not only midnight when the user asks <= YYYY-MM-DD.
        if typ in DATE_TYPES and type(value) is date:
            return f"({expression})::date"
        return expression

    cond, role_param = _role_scope(plan["tabel_utama"], role)
    where = [cond] if cond else []
    params = [user_id] if role_param else []
    comparisons = {"eq": "=", "ne": "<>", "lt": "<", "lte": "<=", "gt": ">", "gte": ">="}
    for filt in plan["filter"]:
        op, value = filt["op"], filt["nilai"]
        col = filter_expr(filt["kolom"], value)
        if op in comparisons:
            where.append(f"{col} {comparisons[op]} %s")
            params.append(value)
        elif op == "contains":
            where.append(f"{col} ILIKE %s ESCAPE '\\'")
            params.append(value)
        elif op == "in":
            where.append(f"{col} IN ({', '.join(['%s'] * len(value))})")
            params.extend(value)
        elif op == "is_null":
            where.append(f"{col} IS {'NULL' if value else 'NOT NULL'}")
    tail = from_sql + (" WHERE " + " AND ".join(f"({p})" for p in where) if where else "")
    if plan["mode"] == "detail":
        cols = plan["kolom_output"]
        select_cols = ", ".join(f"{col_expr(col)} AS {_ident('d'+str(i))}" for i, col in enumerate(cols))
        if plan["urutan"]:
            order_sql = (col_expr(plan["urutan"]["kolom"]) +
                         (" ASC" if plan["urutan"]["arah"] == "asc" else " DESC") + " NULLS LAST")
        else:
            order_sql = col_expr(cols[0]) + " ASC NULLS LAST"
        detail_sql = f"SELECT {select_cols} {tail} ORDER BY {order_sql} LIMIT {plan['limit'] + 1}"
        total_sql = f"SELECT COUNT(*)::bigint AS nilai_global {tail}"
        return total_sql, detail_sql, None, tuple(params), cols
    agg = plan["agregasi"]
    function = agg["fungsi"]
    target = col_expr(agg["kolom"]) if agg["kolom"] else "*"
    if function == "count_distinct":
        aggregate = f"COUNT(DISTINCT {target})"
    else:
        aggregate = f"{function.upper()}({target})"
    total_sql = f"SELECT {aggregate} AS nilai_global {tail}"
    dimensions = list(plan["dimensi"])
    exprs = [col_expr(dim) for dim in dimensions]
    if plan.get("periode"):
        per = plan["periode"]
        pg_level = {"hari": "day", "bulan": "month", "tahun": "year"}[per["tingkat"]]
        # pg_level is selected ONLY from these hard-coded literals.
        exprs.append(f"date_trunc('{pg_level}', {col_expr(per['kolom'])})::date")
        dimensions.append(f"{per['kolom']}:{per['tingkat']}")
    if not dimensions:
        return total_sql, "", None, tuple(params), []
    projection = ", ".join(f"{expr} AS {_ident('d' + str(i))}" for i, expr in enumerate(exprs))
    grouping = ", ".join(exprs)
    ordered = ("nilai DESC NULLS LAST" if plan["urut"] == "nilai_terbesar" else
               "nilai ASC NULLS LAST" if plan["urut"] == "nilai_terkecil" else
               ", ".join(f"d{i} ASC NULLS LAST" for i in range(len(dimensions))))
    having = plan.get("syarat_agregat")
    comparators = {"eq": "=", "lt": "<", "lte": "<=", "gt": ">", "gte": ">="}
    having_sql = f" HAVING {aggregate} {comparators[having['op']]} %s" if having else ""
    detail_params = tuple(params) + (having["nilai"],) if having else None
    detailed_sql = (f"SELECT {projection}, {aggregate} AS nilai {tail} "
                    f"GROUP BY {grouping}{having_sql} ORDER BY {ordered} LIMIT {plan['limit'] + 1}")
    return total_sql, detailed_sql, detail_params, tuple(params), dimensions


GENERAL_SCHEMA_TOOL = "describe_sibima_schema"
GENERAL_QUERY_TOOL = "query_sibima_general"

SCHEMA_DECL = {
    "type": "function", "name": GENERAL_SCHEMA_TOOL,
    "description": "Lihat metadata database SIBIMA yang aman untuk role ini: tabel, kolom, tipe data, dan nama relasi foreign key. WAJIB baca katalog sebelum query umum baru. Bukan hasil data aktual.",
    "parameters": {"type": "object", "properties": {
        "tabel": {"type": "array", "items": {"type": "string"}, "description": "Opsional: nama tabel saja dari katalog."}
    }},
}
QUERY_DECL = {
    "type": "function", "name": GENERAL_QUERY_TOOL,
    "description": (
        "Analisis PostgreSQL generik tanpa daftar metrik manual. Setelah describe_sibima_schema, "
        "pilih tabel_utama (satu baris fakta); mode agregasi menggunakan dimensi kolom tabel.kolom, periode opsional untuk hari/bulan/tahun, dan agregasi count/count_distinct/sum/avg/min/max; "
        "mode detail memilih 1–5 kolom_output dari katalog, filter, serta urutan kolom. "
        "filter berparameter, HAVING opsional dengan syarat_agregat untuk hitungan tiap grup, serta jalur nama constraint FK jika ambigu. JOIN hanya dari tabel anak ke induk; "
        "tidak bisa JOIN induk ke banyak anak dalam satu operasi (pilih anak sebagai root). "
        "Jangan meminta password, OTP, email, atau nomor HP; hasil dibatasi 20 grup, total tetap dihitung global. "
        "Untuk status dan angka bisnis, periksa definisi populasi; nilai rata-rata adalah rata-rata baris. "
        "JANGAN asumsikan semua tabel mempunyai kolom id: metadata menentukan PK yang sebenarnya. "
        "Saat menyaring Tutor dengan lebih dari satu program, gunakan jadwal_kelas sebagai fakta, "
        "COUNT DISTINCT jadwal_kelas.id_program, grup tutor.id_pengguna, JOIN fk_jadwal_tutor, "
        "filter jadwal_kelas.aktif=true, dan syarat_agregat gt 1. "
        "Untuk kehadiran pada sesi selesai, gunakan kehadiran sebagai fakta dan pilih FK "
        "fk_kehadiran_pertemuan -> fk_pertemuan_jadwal -> fk_jadwal_program "
        "bila ingin mengelompokkan menurut program jadwal pertemuan (bukan program enrollment). "
        "Cek nama FK aktual lewat describe_sibima_schema dahulu."
    ),
    "parameters": {"type": "object", "properties": {
        "tabel_utama": {"type": "string"},
        "mode": {"type": "string", "enum": ["agregasi", "detail"]},
        "kolom_output": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
        "urutan": {"type": "object", "properties": {
            "kolom": {"type": "string"}, "arah": {"type": "string", "enum": ["asc", "desc"]}
        }, "required": ["kolom", "arah"]},
        "dimensi": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
        "periode": {"type": "object", "properties": {
            "kolom": {"type": "string", "description": "Kolom date/timestamp dari katalog"},
            "tingkat": {"type": "string", "enum": ["hari", "bulan", "tahun"]},
        }, "required": ["kolom", "tingkat"]},
        "agregasi": {"type": "object", "properties": {
            "fungsi": {"type": "string", "enum": ["count", "count_distinct", "sum", "avg", "min", "max"]},
            "kolom": {"type": "string", "description": "tabel.kolom; hilangkan saat count"},
        }, "required": ["fungsi"]},
        "filter": {"type": "array", "maxItems": 6, "items": {"type": "object", "properties": {
            "kolom": {"type": "string"}, "op": {"type": "string", "enum": ["eq", "ne", "lt", "lte", "gt", "gte", "in", "contains", "is_null"]},
            "nilai": {"type": "string", "description": "Nilai scalar (angka/tanggal/status/teks sebagai string); is_null: true/false"},
            "nilai_daftar": {"type": "array", "items": {"type": "string"},
                             "description": "Wajib untuk operator in; maksimal 10 nilai"},
        }, "required": ["kolom", "op"]}},
        "relasi": {"type": "array", "items": {"type": "string"}, "maxItems": 6,
                   "description": "Nama FK berurutan dari tabel utama saat rute ambigu"},
        "syarat_agregat": {"type": "object", "description": "HAVING pada hasil per grup, misal COUNT DISTINCT > 1; bukan filter baris sebelum GROUP BY.",
                           "properties": {"op": {"type": "string", "enum": ["eq", "lt", "lte", "gt", "gte"]},
                                          "nilai": {"type": "number"}}, "required": ["op", "nilai"]},
        "urut": {"type": "string", "enum": ["nilai_terbesar", "nilai_terkecil", "dimensi_naik"]},
        "limit": {"type": "integer", "description": "Maksimal 20 grup"},
    }, "required": ["tabel_utama"]},
}
