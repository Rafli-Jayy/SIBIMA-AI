"""Patch 6 regression: generic DB metadata + SQL AST + role scopes.

All tests are offline; a PostgreSQL/Gemini live check is still required.
"""
from __future__ import annotations

from decimal import Decimal
from datetime import date
import sys
import types

import pytest

from app import session
from app.repositories.ai_general_repo import execute_general
from app.repositories.ai_read_repo import AIReadRepository
from app.services.ai_general_query import (
    BLOCKED_TABLES, GENERAL_QUERY_TOOL, GENERAL_SCHEMA_TOOL,
    QUERY_DECL, SCHEMA_DECL, _role_scope, compile_plan, describe_catalog,
    read_catalog, validate_plan,
)
from app.services.ai_tool_controller import AIToolController
from app.services.hybrid_evidence import HybridEvidence


COLS = {
    'pengguna': {'id':'integer','role':'USER-DEFINED','status':'USER-DEFINED',
              'nama_lengkap':'character varying','email':'character varying',
              'password_hash':'text','created_at':'timestamp with time zone'},
    'siswa': {'user_id':'integer','role':'USER-DEFINED','no_hp':'character varying', 'nis':'character varying'},
    'tutor': {'user_id':'integer','role':'USER-DEFINED'},
    'pendaftaran': {'id':'integer','student_id':'integer','program_id':'integer',
                    'processed_by':'integer','status':'USER-DEFINED','created_at':'timestamp with time zone'},
    'program_bimbel': {'id':'integer','nama':'character varying','harga_bulanan':'numeric','status':'USER-DEFINED'},
    'nilai': {'id':'integer','enrollment_id':'integer','input_by':'integer','nilai':'numeric',
               'tanggal':'date','jenis':'USER-DEFINED'},
    'tagihan': {'id':'integer','enrollment_id':'integer','jumlah':'numeric','periode':'date', 'status':'USER-DEFINED'},
    'pembayaran': {'id':'integer','invoice_id':'integer','jumlah':'numeric','status':'USER-DEFINED'},
    'pengembalian_pembayaran': {'id':'integer','payment_id':'integer','jumlah':'numeric','status':'character varying'},
    'jadwal_kelas': {'id':'integer','tutor_id':'integer','program_id':'integer'},
    'pertemuan_kelas': {'id':'integer','schedule_id':'integer'},
    'kehadiran': {'session_id':'integer','student_id':'integer','enrollment_id':'integer', 'status':'USER-DEFINED'},
    'kode_otp': {'id':'integer','code_hash':'text','purpose':'USER-DEFINED'},
    'log_aktivitas': {'id':'bigint','user_id':'integer','aksi':'character varying','detail':'text'},
}


# Mock columns/relations use physical Indonesian identifiers, not the old views.
from pathlib import Path as _Path
import json as _json
_SCHEMA_MAP = _json.loads((_Path(__file__).resolve().parents[1]/'sql/peta_nama_lama_ke_perancangan.json').read_text())
_COLUMN_MAP = {v['new']: {c['old']: c['new'] for c in v['columns']} for v in _SCHEMA_MAP.values()}
COLS = {table: {_COLUMN_MAP[table].get(col, col): typ for col, typ in cols.items()}
        for table, cols in COLS.items()}

def fk(name, child, parent, src, dst):
    return {'name':name, 'child':child, 'parent':parent,
            'child_columns':tuple(_COLUMN_MAP[child].get(c, c) for c in src),
            'parent_columns':tuple(_COLUMN_MAP[parent].get(c, c) for c in dst)}

FKS = [
    fk('fk_pendaftaran_program','pendaftaran','program_bimbel',['program_id'],['id']),
    fk('fk_pendaftaran_siswa','pendaftaran','siswa',['student_id'],['user_id']),
    fk('fk_pendaftaran_pemroses','pendaftaran','pengguna',['processed_by'],['id']),
    fk('fk_siswa_pengguna','siswa','pengguna',['user_id','role'],['id','role']),
    fk('fk_nilai_pendaftaran','nilai','pendaftaran',['enrollment_id'],['id']),
    fk('fk_nilai_tutor','nilai','tutor',['input_by'],['user_id']),
    fk('fk_tutor_pengguna','tutor','pengguna',['user_id','role'],['id','role']),
    fk('fk_tagihan_pendaftaran','tagihan','pendaftaran',['enrollment_id'],['id']),
    fk('fk_pembayaran_tagihan','pembayaran','tagihan',['invoice_id'],['id']),
    fk('fk_pengembalian_pembayaran','pengembalian_pembayaran','pembayaran',['payment_id'],['id']),
    fk('fk_pertemuan_jadwal','pertemuan_kelas','jadwal_kelas',['schedule_id'],['id']),
    fk('fk_jadwal_program','jadwal_kelas','program_bimbel',['program_id'],['id']),
    fk('attendances_enrollment_id_fkey','kehadiran','pendaftaran',['enrollment_id'],['id']),
]


def raw_column_rows():
    return [dict(table_name=t,column_name=c,data_type=typ,udt_name='')
            for t, columns in COLS.items() for c, typ in columns.items()]


def raw_fk_rows():
    return [dict(child_table=e['child'],parent_table=e['parent'],constraint_name=e['name'],
                 child_columns=list(e['child_columns']),parent_columns=list(e['parent_columns'])) for e in FKS]


class Cursor:
    def __init__(self, *, total=None, group_rows=None):
        self.calls = []
        self.last_sql = None
        self.total = total or {'nilai_global': 12}
        self.group_rows = group_rows or []
    def execute(self,sql,params=()):
        args = tuple(params or ())
        assert sql.count('%s') == len(args), (sql, args)
        self.calls.append((sql,args))
        self.last_sql = sql
    def fetchall(self):
        if 'information_schema.columns' in self.last_sql:
            return raw_column_rows()
        if 'pg_catalog.pg_constraint' in self.last_sql:
            return raw_fk_rows()
        raise AssertionError(self.last_sql)
    def fetchone(self):
        return self.total
    def fetchmany(self,limit):
        return self.group_rows[:limit]


def catalog(role='admin'):
    return read_catalog(Cursor(),role)


def plan(root,fun='count',col=None,dims=None,filters=None,relations=None):
    return {'tabel_utama':root,'agregasi':{'fungsi':fun, **({'kolom':col} if col else {})},
            'dimensi':dims or [], 'filter': filters or [], 'relasi':relations or []}


def test_metadata_reads_actual_schema_and_sanitizes_secrets():
    cur=Cursor()
    cat=read_catalog(cur,'admin')
    assert 'kode_otp' not in cat['tables']
    assert 'password_hash' not in cat['tables']['pengguna']
    assert 'email' not in cat['tables']['pengguna']
    assert 'no_hp' not in cat['tables']['siswa']
    assert 'detail' not in cat['tables']['log_aktivitas']
    assert 'nilai' in cat['tables']['nilai']
    assert len(cat['edges']) > 0
    assert 'information_schema.columns' in cur.calls[0][0]
    assert 'pg_catalog.pg_constraint' in cur.calls[1][0]
    assert all('INSERT' not in s.upper() for s,_ in cur.calls)


def test_schema_tool_is_role_redacted_and_not_database_evidence():
    cat=catalog('siswa')
    response=describe_catalog(cat)
    assert 'log_aktivitas' not in response['tabel']
    assert response['role']=='siswa'
    ev=HybridEvidence()
    ev.record(GENERAL_SCHEMA_TOOL,response)
    assert ev.refusal('Berapa tagihan saya?') is not None


def test_general_dynamic_join_by_fk_not_manual_domain_map():
    cat=catalog()
    p=plan('nilai','avg','nilai.nilai',dims=['program_bimbel.nama','nilai.jenis'],
           filters=[{'kolom':'nilai.nilai','op':'gte','nilai':'70'}])
    total, group,_,args,dimensions=compile_plan(p,cat,user_id=11)
    assert 'FROM public."nilai" t0' in total
    assert 'LEFT JOIN public."pendaftaran" t1' in total
    assert 'LEFT JOIN public."program_bimbel" t2' in total
    assert 'AVG(t0."nilai")' in total
    assert 'AVG(t0."nilai")' in group
    assert 'GROUP BY' in group
    assert 'LIMIT 21' in group
    assert args==(Decimal('70'),)
    assert dimensions==['program_bimbel.nama','nilai.jenis']


def test_can_group_any_allowed_column_without_new_metric_name():
    cat=catalog()
    p=plan('pembayaran','sum','pembayaran.jumlah',dims=['program_bimbel.nama'],
           filters=[{'kolom':'pembayaran.status','op':'eq','nilai':'lunas'}])
    sql, group, _, args,_=compile_plan(p,cat,user_id=11)
    assert 'SUM(t0."jumlah")' in sql
    assert '"pembayaran" t0' in sql
    assert '"tagihan"' in sql and '"pendaftaran"' in sql and '"program_bimbel"' in sql
    assert 't0."status")::text = %s' in sql
    assert args==('lunas',)
    assert 'GROUP BY' in group


def test_parent_to_many_children_forbidden_prevents_fanout():
    with pytest.raises(ValueError, match='Relasi'):
        compile_plan(plan('program_bimbel','sum','tagihan.jumlah',dims=['program_bimbel.nama']),catalog(),user_id=1)


def test_ambiguous_user_relation_requires_explicit_fk_path():
    cat=catalog()
    with pytest.raises(ValueError,match='ambigu'):
        compile_plan(plan('pendaftaran',dims=['pengguna.nama_lengkap']),cat,user_id=1)
    q=plan('pendaftaran',dims=['pengguna.nama_lengkap'],
           relations=['fk_pendaftaran_siswa','fk_siswa_pengguna'])
    sql, grouped,_,args,_=compile_plan(q,cat,user_id=1)
    assert 'LEFT JOIN public."siswa"' in sql
    assert 'LEFT JOIN public."pengguna"' in sql
    assert '"role"=' in sql and 'GROUP BY' in grouped
    assert args==()


@pytest.mark.parametrize('bad',[
    {'tabel_utama':'pengguna; DROP TABLE pengguna','agregasi':{'fungsi':'count'}},
    plan('kode_otp'),
    plan('nilai','avg','pengguna.nama_lengkap'),
    plan('nilai','sum','nilai.jenis'),
    plan('pengguna','count',None,['pengguna.password_hash']),
    plan('nilai',filters=[{'kolom':'nilai.nilai','op':'eq','nilai':'1 OR TRUE'}]),
    plan('nilai',filters=[{'kolom':'nilai.tanggal','op':'gte','nilai':'2026-02-30'}]),
    plan('nilai',filters=[{'kolom':'nilai.nilai','op':'contains','nilai':'5'}]),
    plan('nilai',filters=[{'kolom':'nilai.jenis','op':'raw_sql','nilai':'x'}]),
    dict(plan('nilai'),sql='SELECT * FROM pengguna'),
])
def test_malicious_and_invalid_plans_fail_closed(bad):
    with pytest.raises((ValueError,PermissionError)):
        compile_plan(bad,catalog(),user_id=3)


def test_scope_tutor_is_inside_generated_query_and_uses_session_parameter():
    cat=catalog('tutor')
    sql, group, _, args, _=compile_plan(plan('nilai','avg','nilai.nilai'),cat,user_id=9397)
    assert 't0.id_tutor_penginput=%s' in sql
    assert '9397' not in sql
    assert args==(9397,)
    with pytest.raises((ValueError, PermissionError)):
        compile_plan(plan('tagihan'),cat,user_id=9397)


def test_scope_student_invoice_refund_and_academic_lock():
    cat=catalog('siswa')
    for root in ('tagihan','pembayaran','pengembalian_pembayaran'):
        sql, _, _, args,_=compile_plan(plan(root),cat,user_id=9397)
        assert 'scope_e.id_siswa=%s' in sql
        assert args==(9397,)
        assert '9397' not in sql
    for root in ('nilai','kehadiran'):
        sql,_,_, args,_=compile_plan(plan(root),cat,user_id=9397)
        assert 'NOT ' in sql
        assert 'e.status IN' in sql
        assert args==(9397,)
        assert '9397' not in sql


def test_role_cannot_pick_unsafe_root_by_metadata():
    for role,root in [('siswa','log_aktivitas'),('tutor','pembayaran'),('siswa','jadwal_kelas')]:
        with pytest.raises((PermissionError,ValueError)):
            compile_plan(plan(root),catalog(role),user_id=10)


def test_non_admin_can_join_only_parents_with_session_scoped_root():
    sql, *_=compile_plan(plan('pendaftaran',dims=['program_bimbel.nama']),catalog('tutor'),user_id=44)
    assert 't0.status=\'aktif\'' in sql
    assert 'scope_s.id_tutor=%s' in sql
    assert 'LEFT JOIN public."program_bimbel"' in sql


def test_repository_global_aggregate_not_first_twenty_groups():
    cur=Cursor(total={'nilai_global': Decimal('250000.00')},
               group_rows=[{'d0':'Program A', 'nilai':Decimal('200000.00')},
                           {'d0':'Program B', 'nilai':Decimal('50000.00')}])
    result=execute_general(cur,user_id=5,role='admin',name=GENERAL_QUERY_TOOL,
          args=plan('tagihan','sum','tagihan.jumlah',dims=['program_bimbel.nama']))
    assert result['agregat_global']=='250000.00'
    assert result['data'][0]=={'program_bimbel.nama':'Program A','nilai':'200000.00'}
    assert result['terpotong'] is False
    assert 'LIMIT' not in cur.calls[2][0].upper()
    assert 'LIMIT 21' in cur.calls[3][0]


def test_sql_parameter_count_for_multiple_ops_and_role_scope():
    for role,root in [('admin','nilai'),('tutor','nilai'),('siswa','nilai')]:
        p=plan(root,fun='count',filters=[
            {'kolom':'nilai.jenis','op':'in','nilai_daftar':['tugas','uts']},
            {'kolom':'nilai.nilai','op':'gte','nilai':'80'},
            {'kolom':'nilai.tanggal','op':'lte','nilai':'2026-11-09'},
        ])
        total,grp,_,args,_=compile_plan(p,catalog(role),user_id=9)
        assert total.count('%s')==len(args)
        assert grp==''
        assert args[0]==9 if role!='admin' else args[0]=='tugas'


def test_controller_exposes_two_generic_tools_with_active_login_check(monkeypatch):
    class Repo:
        def execute(self,user_id,role,name,args):
            return {'status':'ok', 'name':name, 'user_id':user_id, 'args':args}
    session.set_user({'id':19,'role':'tutor','status':'aktif'})
    try:
        ctrl=AIToolController('tutor',repo=Repo(),rag_tool=False)
        names={d['name'] for d in ctrl.declarations()}
        assert {GENERAL_SCHEMA_TOOL,GENERAL_QUERY_TOOL} <= names
        assert 'admin_find_users' not in names
        assert ctrl.execute(GENERAL_SCHEMA_TOOL,{})['user_id']==19
        session.set_user({'id':20,'role':'tutor','status':'aktif'})
        with pytest.raises(PermissionError):
            ctrl.execute(GENERAL_QUERY_TOOL,plan('nilai'))
    finally:
        session.logout()


def test_evidence_actual_general_result_counts_but_schema_does_not():
    ev=HybridEvidence()
    ev.record(GENERAL_SCHEMA_TOOL, {'status':'ok','tabel':{'tagihan':[]}})
    assert ev.refusal('Berapa tagihan saya?') is not None
    ev.record(GENERAL_QUERY_TOOL, {'status':'ok', 'rencana':{'tabel_utama':'tagihan'},'data':[{'nilai':3}]})
    assert ev.refusal('Berapa tagihan saya?') is None
    assert not HybridEvidence().general_query_roots


def test_function_schemas_do_not_accept_sql_or_user_id():
    for declaration in [QUERY_DECL,SCHEMA_DECL]:
        props=declaration['parameters']['properties']
        assert 'sql' not in props and 'user_id' not in props


def test_dynamic_monthly_bucket_from_any_datetime_column():
    cat=catalog()
    p=plan('pendaftaran',dims=['program_bimbel.nama'])
    p['periode']={'kolom':'pendaftaran.created_at','tingkat':'bulan'}
    p['filter']=[{'kolom':'pendaftaran.created_at','op':'lte','nilai':'2026-11-09'}]
    total, grouped, _, args, dims=compile_plan(p,cat,user_id=12)
    assert "date_trunc('month', t0.\"created_at\")::date" in grouped
    assert 't0."created_at")::date <= %s' in total
    assert dims==['program_bimbel.nama','pendaftaran.created_at:bulan']
    assert args==(date(2026,11,9),)


def detail_plan(root,columns,filters=None,order=None):
    q={'mode':'detail','tabel_utama':root,'kolom_output':columns,'filter':filters or []}
    if order:
        q['urutan']=order
    return q


def test_generic_detail_listing_with_filter_order_and_count():
    cat=catalog('admin')
    q=detail_plan('pengguna',['pengguna.nama_lengkap','pengguna.status'],
         filters=[{'kolom':'pengguna.role','op':'eq','nilai':'siswa'}],
         order={'kolom':'pengguna.nama_lengkap','arah':'asc'})
    total, detail, _, args, cols=compile_plan(q,cat,user_id=1)
    assert 'COUNT(*)::bigint AS nilai_global' in total
    assert 'LIMIT' not in total
    assert 'SELECT t0."nama_lengkap" AS "d0", t0."status" AS "d1"' in detail
    assert 'ORDER BY t0."nama_lengkap" ASC' in detail
    assert 'LIMIT 21' in detail
    assert cols==['pengguna.nama_lengkap','pengguna.status']
    assert args==('siswa',)


def test_generic_detail_lists_only_own_records_for_student():
    cat=catalog('siswa')
    q=detail_plan('tagihan',['tagihan.jumlah','tagihan.status'],
          filters=[{'kolom':'tagihan.status','op':'eq','nilai':'belum_dibayar'}])
    total, detail, _,args,_=compile_plan(q,cat,user_id=141)
    assert 'scope_e.id_siswa=%s' in total
    assert args==(141,'belum_dibayar')
    assert 'LIMIT' not in total
    assert 'LIMIT 21' in detail


def test_generic_detail_rejects_sensitive_and_invalid_options():
    cat=catalog('admin')
    for q in (
        detail_plan('pengguna',['pengguna.password_hash']),
        detail_plan('pengguna',['pengguna.email']),
        detail_plan('pengguna',['pengguna.nama_lengkap']*6),
        dict(detail_plan('pengguna',['pengguna.nama_lengkap']), agregasi={'fungsi':'count'}),
        dict(plan('pengguna'), kolom_output=['pengguna.nama_lengkap']),
        detail_plan('pengguna',['pengguna.nama_lengkap'],order={'kolom':'1; DROP','arah':'asc'}),
    ):
        with pytest.raises((ValueError,PermissionError)):
            compile_plan(q,cat,user_id=1)


def test_details_are_limited_but_total_is_full():
    cur=Cursor(total={'nilai_global':23},group_rows=[{'d0':'Tania','d1':'aktif'}, {'d0':'Zaki','d1':'aktif'}])
    out=execute_general(cur,user_id=5,role='admin',name=GENERAL_QUERY_TOOL,
            args=detail_plan('pengguna',['pengguna.nama_lengkap','pengguna.status']))
    assert out['jumlah_total']==23
    assert out['agregat_global'] is None
    assert out['data'][0]=={'pengguna.nama_lengkap':'Tania','pengguna.status':'aktif'}
    assert out['data'][1]=={'pengguna.nama_lengkap':'Zaki','pengguna.status':'aktif'}
    assert 'LIMIT' not in cur.calls[2][0].upper()


def test_model_provided_injection_cannot_become_sql_for_detail():
    cat=catalog('admin')
    q=detail_plan('pengguna',['pengguna.nama_lengkap'],
          [{'kolom':'pengguna.nama_lengkap','op':'contains','nilai':"a%' OR TRUE --"}])
    sql, detail, _,args,_=compile_plan(q,cat,user_id=1)
    assert 'OR TRUE' not in sql
    assert 'OR TRUE' not in detail
    assert "OR TRUE" in args[0]
    assert r'\%' in args[0]
