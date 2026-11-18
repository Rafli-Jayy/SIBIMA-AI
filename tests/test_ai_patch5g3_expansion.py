"""5G.3 regression: class sessions, refunds and schedule groupings.

Offline tests only: use exact production plan compiler and role-checked
repository. They do not claim a live PostgreSQL/Gemini integration test.
"""
import re
from decimal import Decimal
from contextlib import contextmanager
import sys
import types

import pytest

from app import session
from app.repositories.ai_dynamic_repo import compile_query, execute_dynamic
from app.repositories.ai_read_repo import AIReadRepository
from app.services.ai_dynamic_plan import DOMAINS, ROLE_DYNAMIC_NAMES, role_dynamic_schema, validate_role_dynamic_plan
from app.services.ai_tool_controller import AIToolController
from app.services.hybrid_evidence import HybridEvidence


def p(domain, metrik, kelompok=(), filt=None):
    return {'domain':domain,'metrik':metrik,'kelompok':list(kelompok),'filter':filt or {}}


@pytest.fixture(autouse=True)
def restore_session():
    old=session.get_user()
    session.logout()
    yield
    session.set_user(old)


@pytest.mark.parametrize('role,domain,metric,dimensions', [
    ('admin','pertemuan','jumlah_pertemuan',['status','bulan']),
    ('admin','pertemuan','jumlah_pertemuan_selesai',['program','tutor']),
    ('admin','pertemuan','jumlah_pertemuan_batal',['ruangan']),
    ('tutor','pertemuan','jumlah_pertemuan',['program','status']),
    ('tutor','pertemuan','jumlah_pertemuan_selesai',['ruangan','bulan']),
    ('admin','pengembalian','jumlah_pengembalian',['program','status']),
    ('admin','pengembalian','nominal_pengembalian_berhasil',['bulan']),
    ('siswa','pengembalian','jumlah_pengembalian_berhasil',['program','bulan']),
    ('siswa','pengembalian','nominal_pengembalian_berhasil',['status']),
    ('admin','jadwal','jumlah_jadwal_aktif',['ruangan','hari']),
    ('tutor','jadwal','jumlah_jadwal_aktif',['hari','program']),
])
def test_valid_scope_and_sql_contract(role,domain,metric,dimensions):
    plan=validate_role_dynamic_plan(p(domain,metric,dimensions),role)
    total, params, groups, listing, other=compile_query(plan,role=role,user_id=312 if role!='admin' else None)
    assert total.count('%s') == len(params)
    assert groups.count('%s') == len(other)
    assert listing.count('%s') == len(other)
    assert 'LIMIT 20' not in total
    assert 'LIMIT 20' in listing
    assert 'GROUP BY' in listing
    assert 'SELECT COUNT(*)::int AS banyak_kelompok' in groups
    assert not re.search(r'\b(?:INSERT|UPDATE|DELETE|DROP|ALTER|COPY|TRUNCATE)\b',total,re.I)
    if role!='admin':
        assert 312 in params and '312' not in total
    if domain=='pertemuan':
        assert 'FROM class_sessions cs JOIN schedules s' in total
        assert 'cs.tanggal' in DOMAINS[domain]['date']
        if role=='tutor':
            assert 's.tutor_id=%s' in total
            assert 's.aktif=TRUE' not in total
    if domain=='pengembalian':
        assert 'FROM payment_refunds pr JOIN payments py' in total
        assert 'JOIN enrollments e ON e.id=i.enrollment_id' in total
        if role=='siswa':
            assert 'e.student_id=%s' in total
    if domain=='jadwal':
        assert 'JOIN rooms r ON r.id=s.room_id' in total


@pytest.mark.parametrize('role,domain,metric', [
    ('tutor','pengembalian','jumlah_pengembalian'),
    ('tutor','pengembalian','nominal_pengembalian_berhasil'),
    ('siswa','pertemuan','jumlah_pertemuan'),
    ('siswa','jadwal','jumlah_jadwal_aktif'),
])
def test_cross_role_domain_rejected(role,domain,metric):
    with pytest.raises(PermissionError):
        validate_role_dynamic_plan(p(domain,metric),role)


@pytest.mark.parametrize('args', [
    p('pertemuan','jumlah_pertemuan_selesai',filt={'status':'batal'}),
    p('pertemuan','jumlah_pertemuan_batal',filt={'status':'selesai'}),
    p('pertemuan','jumlah_pertemuan',filt={'status':'tidak_ada'}),
    p('pengembalian','nominal_pengembalian_berhasil',filt={'status':'gagal'}),
    p('pengembalian','jumlah_pengembalian_berhasil',filt={'status':'direfund'}),
    p('pengembalian','jumlah_pengembalian',filt={'tanggal_dari':'2026-02-30'}),
    p('pengembalian','jumlah_pengembalian',filt={'program_id': '1 OR TRUE'}),
    p('pengembalian','jumlah_pengembalian',filt={'raw_sql':'DROP TABLE users'}),
    p('pertemuan','jumlah_pertemuan',kelompok=['jenis']),
    p('pengembalian','jumlah_pengembalian',kelompok=['tutor']),
    p('pertemuan','jumlah_pertemuan',kelompok=['ruangan','ruangan']),
    p('pertemuan','jumlah_pertemuan',kelompok=['program','bulan','status']),
    p('pertemuan','jumlah_pertemuan',filt={'tanggal_dari':'2026-12-01','tanggal_sampai':'2026-11-01'}),
])
def test_bad_plans_rejected(args):
    with pytest.raises((PermissionError,ValueError)):
        validate_role_dynamic_plan(args,'admin')


def test_fixed_status_used_to_filter_success_and_cancellation():
    for domain, metric, status in [
        ('pertemuan','jumlah_pertemuan_selesai','selesai'),
        ('pertemuan','jumlah_pertemuan_batal','batal'),
        ('pengembalian','nominal_pengembalian_berhasil','berhasil'),
        ('pengembalian','jumlah_pengembalian_berhasil','berhasil')]:
        plan=validate_role_dynamic_plan(p(domain,metric,['program']), 'admin')
        sql,params, *_=compile_query(plan)
        assert f'{DOMAINS[domain]["status"]} = %s' in sql
        assert status in params


def test_dynamic_declarations_only_advertise_authorized_families():
    admin=role_dynamic_schema('admin')
    tutor=role_dynamic_schema('tutor')
    siswa=role_dynamic_schema('siswa')
    assert set(admin['parameters']['properties']['domain']['enum']) == set(DOMAINS)
    assert 'pertemuan' in tutor['parameters']['properties']['domain']['enum']
    assert 'pengembalian' not in tutor['parameters']['properties']['domain']['enum']
    assert 'pengembalian' in siswa['parameters']['properties']['domain']['enum']
    assert 'pertemuan' not in siswa['parameters']['properties']['domain']['enum']
    for sch in (admin,tutor,siswa):
        assert 'sql' not in sch['parameters']['properties']
        assert 'user_id' not in sch['parameters']['properties']
        assert 'password' not in sch['description'].lower()


@pytest.mark.parametrize('role,allowed,denied', [
    ('admin',p('pertemuan','jumlah_pertemuan'),p('users','password_hash')),
    ('tutor',p('pertemuan','jumlah_pertemuan'),p('pengembalian','jumlah_pengembalian')),
    ('siswa',p('pengembalian','jumlah_pengembalian'),p('pertemuan','jumlah_pertemuan')),
])
def test_controller_does_not_expose_another_role(role,allowed,denied):
    class Repo:
        def execute(self,user_id,role,tool,args):
            assert tool==ROLE_DYNAMIC_NAMES[role]
            assert user_id==29
            return {'data':[{'nilai':5}], 'rencana':args}
    session.set_user({'id':29,'role':role,'status':'aktif'})
    ctl=AIToolController(role,repo=Repo(),rag_tool=False)
    own=ROLE_DYNAMIC_NAMES[role]
    assert ctl.execute(own,allowed)['data'][0]['nilai']==5
    with pytest.raises((ValueError,PermissionError)):
        ctl.execute(own,denied)
    for other in ROLE_DYNAMIC_NAMES.values():
        if other != own:
            with pytest.raises(PermissionError):
                ctl.execute(other,allowed)


class Cursor:
    def __init__(self, rows):
        self.results=list(rows)
        self.calls=[]
    def execute(self,sql,params=None):
        args=tuple(params or ())
        assert sql.count('%s')==len(args), (sql,args)
        self.calls.append((sql,args))
    def fetchone(self): return self.results.pop(0) if self.results else {}
    def fetchmany(self,n): return []
    def __enter__(self): return self
    def __exit__(self,*a): return False
class Conn:
    def __init__(self,c): self.c=c
    def __enter__(self): return self
    def __exit__(self,*a): return False
    @contextmanager
    def transaction(self): yield
    def cursor(self,**_): return self.c
class Pool:
    def __init__(self,c): self.c=c
    def connection(self,timeout):
        assert timeout==5
        return Conn(self.c)


@pytest.mark.parametrize('role,plan', [
    ('tutor',p('pertemuan','jumlah_pertemuan_selesai')),
    ('siswa',p('pengembalian','nominal_pengembalian_berhasil')),
])
def test_repository_uses_login_id_read_only(monkeypatch,role,plan):
    fake=types.ModuleType('psycopg'); rows=types.ModuleType('psycopg.rows');rows.dict_row=object()
    monkeypatch.setitem(sys.modules,'psycopg',fake)
    monkeypatch.setitem(sys.modules,'psycopg.rows',rows)
    cursor=Cursor([{'role':role,'status':'aktif'},{'nilai':Decimal('220.50')}])
    res=AIReadRepository(pool=Pool(cursor)).execute(29,role,ROLE_DYNAMIC_NAMES[role],plan)
    assert res['agregat_global']=='220.50'
    assert cursor.calls[0][0]=='SET TRANSACTION READ ONLY'
    assert cursor.calls[1][0].startswith('SET LOCAL statement_timeout')
    assert cursor.calls[2][1]==(29,)
    assert cursor.calls[3][1][0]==29 or 29 in cursor.calls[3][1]
    denied=Cursor([{'role':'admin','status':'aktif'}])
    with pytest.raises(PermissionError):
        AIReadRepository(pool=Pool(denied)).execute(29,role,ROLE_DYNAMIC_NAMES[role],plan)
    assert len(denied.calls)==3


def test_global_aggregate_keeps_full_source_count_for_refunds():
    q=validate_role_dynamic_plan(p('pengembalian','nominal_pengembalian_berhasil',['program']), 'admin')
    cur=Cursor([{'nilai':Decimal('250000.00')},{'banyak_kelompok':37}])
    result=execute_dynamic(cur,'admin',q)
    assert result['agregat_global']=='250000.00'
    assert result['total_kelompok']==37
    assert result['terpotong'] is True
    assert result['jumlah_ditampilkan']==0
    assert 'LIMIT 20' not in cur.calls[0][0]


@pytest.mark.parametrize('query,wrong,right,tool', [
    ('Berapa total refund saya?','pembayaran','pengembalian','student_dynamic_query'),
    ('Ringkasan pengembalian pembayaran saya','tagihan','pengembalian','student_dynamic_query'),
    ('Berapa jumlah pertemuan per program?','jadwal','pertemuan','admin_dynamic_query'),
    ('Berapa jumlah pertemuan kelas saya?','kehadiran','pertemuan','tutor_dynamic_query'),
])
def test_evidence_requires_domain_specific_tool(query,wrong,right,tool):
    ev=HybridEvidence(original_query=query)
    assert ev.refusal(query)
    ev.record(tool,{'data':[{'nilai':42}], 'rencana':{'domain':wrong}})
    assert ev.refusal(query)
    ev.record(tool,{'data':[{'nilai':42}], 'rencana':{'domain':right}})
    assert ev.refusal(query) is None


def test_missing_tool_data_is_not_proof():
    q='Berapa jumlah pertemuan per program?'
    ev=HybridEvidence(original_query=q)
    ev.record('admin_dynamic_query', {'rencana': {'domain': 'pertemuan'}, 'error': 'timeout'})
    assert ev.refusal(q)


def test_actual_schema_facts_present():
    # These 5G.3 query columns must come from the actual schema, not guesses.
    from pathlib import Path
    schema=(Path(__file__).parents[1]/'sql/schema.sql').read_text()
    for table,col in [
        ('class_sessions','schedule_id'), ('class_sessions','tanggal'),('class_sessions','status'),
        ('payment_refunds','payment_id'),('payment_refunds','jumlah'),('payment_refunds','status'),
        ('schedules','room_id'),('schedules','tutor_id'),('schedules','hari'),
        ('rooms','nama'),('enrollments','student_id'),('payments','invoice_id')]:
        body=schema.split(f'CREATE TABLE public.{table} (',1)[1].split('\n);',1)[0]
        assert re.search(r'^    '+col+r'\s',body,re.M), (table,col)
