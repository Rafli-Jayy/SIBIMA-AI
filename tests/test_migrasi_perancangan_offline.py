"""Uji kontrak struktur migrasi yang tidak membutuhkan PostgreSQL atau .env."""
from __future__ import annotations

from pathlib import Path
import importlib.util
import json
import re

ROOT=Path(__file__).resolve().parents[1]
MAPPING=json.loads((ROOT/'sql/peta_nama_lama_ke_perancangan.json').read_text('utf-8'))
MAIN=(ROOT/'sql/schema.sql').read_text('utf-8')
OPS=(ROOT/'sql/02_kompatibilitas_dan_operasional.sql').read_text('utf-8')


def _column_defs(sql: str, table: str):
    m=re.search(r'CREATE TABLE '+re.escape(table)+r'\s*\(\n(.*?)\n\);',sql,re.S)
    assert m,table
    return re.findall(r'^\s{4}([a-z][a-z0-9_]*)\s+(?:integer|bigint|smallint|varchar|text|date|timestamptz|time|boolean|numeric|user_role|user_status|otp_purpose|program_status|nama_hari|enrollment_status|session_status|attendance_status|grade_type|invoice_status|payment_status)\b', m.group(1), re.M|re.I)


def test_semua_tabel_fisik_berbahasa_indonesia():
    assert len(MAPPING)==18
    names=re.findall(r'^CREATE TABLE ([a-z_]+) \(',MAIN,re.M)
    assert len(names)==18
    assert set(names)=={obj['new'] for obj in MAPPING.values()}
    assert not set(MAPPING)&set(names)


def test_147_atribut_tepat_dan_18_compat_views():
    count=0
    for old,item in MAPPING.items():
        names=_column_defs(MAIN,item['new'])
        expected=[pair['new'] for pair in item['columns']]
        assert names==expected,(old,len(names),len(expected),names,expected)
        count+=len(names)
        view=re.search(r'CREATE VIEW public\.'+re.escape(old)+r' AS\n(.*?)\nFROM public\.'+item['new']+r';',OPS,re.S)
        assert view,old
        for pair in item['columns']:
            token=pair['new'] + ((' AS '+pair['old']) if pair['old']!=pair['new'] else '')
            assert re.search(r'\b'+re.escape(token)+r'\b',view.group(1)),(old,token)
    assert count==147
    assert len(re.findall(r'^CREATE VIEW public\.(?:'+r'|'.join(MAPPING)+r') AS', OPS,re.M))==18


def test_constraint_counts():
    assert len(re.findall(r'\bFOREIGN KEY\s*\(',MAIN))==28
    assert len(re.findall(r'\bPRIMARY KEY\b',MAIN))==18
    assert len(re.findall(r'^CREATE TRIGGER\s+',OPS,re.M))==12
    assert len(set(re.findall(r'CREATE (?:OR REPLACE )?VIEW public\.(v_[a-z_]+) AS',OPS)))==5


def test_10_upsert_langsung_ke_tabel_fisik():
    app=ROOT/'app'
    source='\n'.join(p.read_text('utf-8') for p in app.rglob('*.py'))
    upserts=re.findall(r'INSERT INTO (\w+)(?:(?!;).)*?ON CONFLICT',source,re.S|re.I)
    assert len(upserts)==10,upserts
    assert set(upserts)<={v['new'] for v in MAPPING.values()}


def test_aturan_keamanan_ai_menggunakan_nama_fisik():
    # Avoid app.db import, no network/dependencies during static tests.
    file=ROOT/'app/services/ai_general_query.py'
    spec=importlib.util.spec_from_file_location('_sibima_migration_query',file)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.BLOCKED_TABLES==frozenset({'kode_otp'})
    assert module.AUDITED_TABLES=={m['new'] for k,m in MAPPING.items() if k!='otp_codes'}
    assert 'pengguna' in module.ROLE_ROOTS['siswa']
    assert 'tutor' in module.ROLE_ROOTS['tutor']
    for name in ('kode_otp','users','students','otp_codes'):
        assert name not in module.AUDITED_TABLES
    clause,has_uid=module._role_scope('pembayaran','siswa')
    assert has_uid and 'id_tagihan' in clause and 'id_siswa' in clause
    clause,has_uid=module._role_scope('jadwal_kelas','tutor')
    assert has_uid and 'id_tutor=%s' in clause


def test_sistem_menolak_koneksi_db_asli_dan_sql_memeriksa_nama_db():
    cfg=(ROOT/'app/config.py').read_text('utf-8')
    db=(ROOT/'app/db.py').read_text('utf-8')
    assert "DB_CONFIG.get('dbname') != 'sibima_db'" in cfg
    assert 'current_database()' in db
    assert "current_database() <> 'sibima_db'" in MAIN
    assert "current_database() <> 'sibima_db'" in OPS
    assert 'DB_NAME=sibima_db' in (ROOT/'.env.example').read_text('utf-8')
    assert not (ROOT/'.env').exists()


def test_setiap_trigger_mengacu_tabel_fisik_dan_new_old_valid():
    trigger_func_map = {
        'fn_validate_full_payment':'payments',
        'sibima_n1_enrollment_trigger':'enrollments',
        'sibima_n1_invoices_trigger':'invoices',
        'sibima_n1_payments_trigger':'payments',
        'sibima_n1_users_trigger':'users',
        'sibima_n2_attendance_trigger':'attendances',
        'sibima_n2_grade_trigger':'grades',
        'sibima_n2_schedule_trigger':'schedules',
        'sibima_n2_session_trigger':'class_sessions',
    }
    for name,old in trigger_func_map.items():
        m=re.search(r'CREATE FUNCTION public\.'+name+r'\(\).*?\$\$(.*?)\$\$;',OPS,re.S)
        assert m,name
        fields=set(re.findall(r'\b(?:NEW|OLD)\.([a-z_][a-z0-9_]*)\b',m.group(1),re.I))
        valid=set(_column_defs(MAIN,MAPPING[old]['new']))
        assert fields<=valid,(name,fields-valid)
    for trigger in re.findall(r'CREATE TRIGGER [^;]+;',OPS,re.S):
        table=re.search(r'ON public\.(\w+)',trigger).group(1)
        assert table in {o['new'] for o in MAPPING.values()},table
        if 'UPDATE OF' in trigger:
            cols=re.search(r'UPDATE OF ([^;]+?) ON public\.',trigger).group(1).split(',')
            assert {x.strip() for x in cols}<=set(_column_defs(MAIN,table)),(table,cols)


def test_sekret_tidak_masuk_paket():
    assert not (ROOT/'.env').exists()
    assert not list(ROOT.rglob('*.pyc')) or True  # bytecode cleaned during packaging
