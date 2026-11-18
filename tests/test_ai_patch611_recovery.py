"""Patch 6.1.1: rejected-plan recovery, safe schema hints, real FK paths.

Only offline checks; Gemini and PostgreSQL live credentials are not used.
"""
from copy import deepcopy
from types import SimpleNamespace as NS
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.ai_db_chat import DatabaseFunctionChat
from app.services.ai_general_query import compile_plan, QUERY_DECL, SCHEMA_DECL
from app.services.ai_multi_query import MULTI_DECL, validate_multi_args

from test_ai_patch6_general_query import catalog, fk
from test_ai_patch61_multistage import Gemini, tool_stream, final_stream


class RecoveringController:
    role = 'admin'

    def __init__(self, failures=1):
        self.failures = failures
        self.actual_calls = []
        self.metadata_calls = 0

    def declarations(self):
        return [MULTI_DECL, SCHEMA_DECL]

    def execute(self, name, args):
        if name == 'describe_sibima_schema':
            self.metadata_calls += 1
            return {'status': 'ok', 'role': 'admin', 'tabel': {
                'tutor': {'id_pengguna': 'integer', 'role': 'USER-DEFINED'},
                'jadwal_kelas': {'id_jadwal': 'integer', 'id_tutor': 'integer', 'id_program': 'integer', 'aktif': 'boolean'},
                'pengguna': {'id_pengguna': 'integer', 'role': 'USER-DEFINED'},
            }, 'relasi': [
                {'name':'fk_jadwal_tutor','child':'jadwal_kelas','parent':'tutor',
                 'child_columns':['id_tutor'], 'parent_columns':['id_pengguna']},
                {'name':'fk_tutor_pengguna','child':'tutor','parent':'pengguna',
                 'child_columns':['id_pengguna','role'], 'parent_columns':['id_pengguna','role']},
            ]}
        self.actual_calls.append((name, args))
        if len(self.actual_calls) <= self.failures:
            raise ValueError('Tabel atau kolom tidak tersedia untuk role ini.')
        return {'status': 'ok', 'rencana': {'tabel_utama':'jadwal_kelas','mode':'agregasi'},
                'data':[{'tutor.id_pengguna':1,'nilai':2}], 'agregat_global':2, 'terpotong':False}


def test_schema_mismatch_recovers_with_role_safe_metadata_not_raw_arguments():
    raw = {'tabel_utama':'jadwal_kelas','dimensi':['tutor.id'], 'value':'SECRET-DO-NOT-ECHO'}
    sdk = Gemini([tool_stream('f1','query_sibima_general',raw),
                  tool_stream('f2','query_sibima_general',{'tabel_utama':'jadwal_kelas'}),
                  final_stream('Data berhasil diverifikasi.')])
    ctrl = RecoveringController(failures=1)
    events = list(DatabaseFunctionChat(sdk,ctrl).stream([], 'Tutor lebih dari satu program', 'system'))
    assert events[-1].kind == 'completed'
    assert ctrl.metadata_calls == 1
    assert len(ctrl.actual_calls) == 2
    feed = next(x for x in sdk._client.calls[1]['input'] if x['type']=='function_result')['result'][0]['text']
    assert 'skema_tidak_cocok' in feed
    assert 'tutor' in feed and 'id_pengguna' in feed and 'fk_jadwal_tutor' in feed
    assert 'SECRET-DO-NOT-ECHO' not in feed
    assert 'password' not in feed


def test_exhausted_replan_finishes_with_clear_error_not_generic_valueerror():
    sdk = Gemini([tool_stream('f1','query_sibima_general',{'tabel_utama':'jadwal_kelas'}),
                  tool_stream('f2','query_sibima_general',{'tabel_utama':'jadwal_kelas'})])
    ctrl = RecoveringController(failures=2)
    events = list(DatabaseFunctionChat(sdk,ctrl).stream([], 'Tutor paling banyak program', 'system'))
    assert events[-1].kind == 'completed'
    assert 'skema_tidak_cocok' in events[-1].payload['content']
    assert 'belum berhasil diverifikasi' in events[-1].payload['content']
    assert not any(e.kind == 'error' for e in events)
    assert len(sdk._client.calls) == 2


def rich_schema():
    cat = deepcopy(catalog())
    cat['tables']['jadwal_kelas']['aktif'] = 'boolean'
    cat['tables']['pertemuan_kelas']['status'] = 'USER-DEFINED'
    cat['tables']['pertemuan_kelas']['tanggal'] = 'date'
    cat['edges'] += [
        fk('fk_jadwal_tutor','jadwal_kelas','tutor',['tutor_id'],['user_id']),
        fk('fk_kehadiran_pertemuan','kehadiran','pertemuan_kelas',['session_id'],['id']),
        fk('fk_pertemuan_jadwal','pertemuan_kelas','jadwal_kelas',['schedule_id'],['id']),
        fk('fk_jadwal_program','jadwal_kelas','program_bimbel',['program_id'],['id']),
    ]
    return cat


def test_real_schema_tutor_distinct_program_plan_accepted_without_special_metric():
    plan = {
        'tabel_utama':'jadwal_kelas', 'agregasi':{'fungsi':'count_distinct','kolom':'jadwal_kelas.id_program'},
        'dimensi':['tutor.id_pengguna'],
        'filter':[{'kolom':'jadwal_kelas.aktif','op':'eq','nilai':'true'}],
        'relasi':['fk_jadwal_tutor'],
        'syarat_agregat':{'op':'gt','nilai':1},
    }
    total, detail, detail_params, params, dims = compile_plan(plan,rich_schema(),user_id=1)
    assert 'COUNT(DISTINCT t0."id_program")' in total
    assert 'LEFT JOIN public."tutor"' in total
    assert 'HAVING COUNT(DISTINCT t0."id_program") > %s' in detail
    assert params == (True,) and detail_params[-1] == 1
    assert dims == ['tutor.id_pengguna']


def test_attendance_session_route_ambiguity_requires_explicit_fk():
    cat=rich_schema()
    plan = {'tabel_utama':'kehadiran','agregasi':{'fungsi':'count'},
            'dimensi':['program_bimbel.id_program'], 'filter':[
                {'kolom':'pertemuan_kelas.status','op':'eq','nilai':'selesai'},
                {'kolom':'kehadiran.status','op':'eq','nilai':'A'}]}
    import pytest
    with pytest.raises(ValueError,match='Relasi'):
        compile_plan(plan,cat,user_id=1)
    plan['relasi'] = ['fk_kehadiran_pertemuan','fk_pertemuan_jadwal', 'fk_jadwal_program']
    total,group, _,params,dims=compile_plan(plan,cat,user_id=1)
    assert all(x in total for x in ('public."pertemuan_kelas"','public."jadwal_kelas"','public."program_bimbel"'))
    assert params == ('selesai','A')
    assert dims == ['program_bimbel.id_program']


def test_multistage_attendance_rate_and_grade_avg_validates_without_fanout():
    cat=rich_schema()
    att={'tabel_utama':'kehadiran','agregasi':{'fungsi':'count'},'dimensi':['program_bimbel.id_program'],
         'relasi':['fk_kehadiran_pertemuan','fk_pertemuan_jadwal','fk_jadwal_program'],
         'filter':[{'kolom':'pertemuan_kelas.status','op':'eq','nilai':'selesai'}]}
    alpa=deepcopy(att)
    alpa['filter'].append({'kolom':'kehadiran.status','op':'eq','nilai':'A'})
    grade={'tabel_utama':'nilai','agregasi':{'fungsi':'avg','kolom':'nilai.nilai'},
           'dimensi':['program_bimbel.id_program']}
    request={
        'analisis':[{'nama':'alpa','rencana':alpa},{'nama':'total','rencana':att},{'nama':'nilai','rencana':grade}],
        'gabung':{'jenis':'inner','kunci':['program'], 'pemetaan':{
            'alpa':{'program':'program_bimbel.id_program'},'total':{'program':'program_bimbel.id_program'},'nilai':{'program':'program_bimbel.id_program'}}},
        'perhitungan':[{'nama':'persentase_alpa','jenis':'rasio_persen','a':'alpa','b':'total'}]
    }
    validated=validate_multi_args(request,cat,user_id=1)
    assert len(validated['analisis']) == 3
    assert validated['perhitungan'][0]['jenis'] == 'rasio_persen'
