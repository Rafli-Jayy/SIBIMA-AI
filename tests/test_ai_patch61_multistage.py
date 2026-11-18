"""Offline Patch 6.1: generic multi-fact query, HAVING, entity presence,
role scope, and one bounded safe replan. No PostgreSQL or Gemini network calls.
"""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace as NS

import pytest

from app.services.ai_general_query import compile_plan, QUERY_DECL
from app.services.ai_multi_query import MULTI_QUERY_TOOL, MULTI_DECL, execute_multi, validate_multi_args
from app.services.ai_db_chat import DatabaseFunctionChat
from app.services.hybrid_evidence import HybridEvidence
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from test_ai_patch6_general_query import Cursor, catalog


def aggregation(table, fn='count', column=None, dimensions=None, filters=None):
    return {'tabel_utama': table, 'agregasi': {'fungsi': fn, **({'kolom': column} if column else {})},
            'dimensi': dimensions or [], 'filter': filters or [], 'limit': 20}


def multi_request():
    return {'analisis': [
        {'nama': 'nilai', 'rencana': aggregation('nilai', 'avg', 'nilai.nilai', ['program_bimbel.id_program'])},
        {'nama': 'absensi', 'rencana': aggregation('kehadiran', 'count', dimensions=['program_bimbel.id_program'])},
    ], 'gabung': {'kunci': ['program'], 'jenis': 'outer',
                 'pemetaan': {'nilai': {'program': 'program_bimbel.id_program'},
                              'absensi': {'program': 'program_bimbel.id_program'}}}}


class FactsCursor(Cursor):
    def __init__(self, missing=False, truncated=False):
        super().__init__()
        self.missing = missing
        self.truncated = truncated

    def fetchone(self):
        if 'FROM public."program_bimbel" t0' in self.last_sql:
            return {'nilai_global': 0 if self.missing else 1}
        if 'FROM public."nilai" t0' in self.last_sql:
            return {'nilai_global': Decimal('85.5')}
        if 'FROM public."kehadiran" t0' in self.last_sql:
            return {'nilai_global': 12}
        return {'nilai_global': 0}

    def fetchmany(self, limit):
        if 'FROM public."nilai" t0' in self.last_sql:
            return [{'d0': 1, 'nilai': Decimal('85.5')}, {'d0': 2, 'nilai': Decimal('70')}]
        if 'FROM public."kehadiran" t0' in self.last_sql:
            if self.truncated:
                return [{'d0': i, 'nilai': i} for i in range(21)][:limit]
            return [{'d0': 1, 'nilai': 8}, {'d0': 3, 'nilai': 4}]
        return []


def test_independent_fact_aggregates_merge_without_fanout():
    cur = FactsCursor()
    result = execute_multi(cur, role='admin', user_id=1, args=multi_request())
    assert result['status'] == 'ok'
    assert result['jumlah_grup'] == 3
    assert result['data'] == [
        {'program': 1, 'nilai': '85.5', 'absensi': 8},
        {'program': 2, 'nilai': '70', 'absensi': None},
        {'program': 3, 'nilai': None, 'absensi': 4},
    ]
    data_sql = [sql for sql, _ in cur.calls if 'FROM public.' in sql]
    assert any('FROM public."nilai" t0' in sql for sql in data_sql)
    assert any('FROM public."kehadiran" t0' in sql for sql in data_sql)
    assert not any('public."nilai"' in sql and 'public."kehadiran"' in sql for sql in data_sql)
    assert all('INSERT ' not in sql and ' UPDATE ' not in sql for sql in data_sql)


def test_safe_derived_ratio_and_difference_are_computed_by_python_not_model():
    req = multi_request()
    req['perhitungan'] = [
        {'nama': 'rasio', 'jenis': 'rasio_persen', 'a': 'absensi', 'b': 'nilai'},
        {'nama': 'selisih', 'jenis': 'selisih', 'a': 'nilai', 'b': 'absensi'},
    ]
    result = execute_multi(FactsCursor(), role='admin', user_id=1, args=req)
    assert result['data'][0]['rasio'] == '9.36'
    assert result['data'][0]['selisih'] == '77.5'
    assert result['data'][1]['rasio'] is None
    assert result['data'][2]['rasio'] is None
    bad = multi_request()
    bad['perhitungan'] = [{'nama': 'hack', 'jenis': 'raw_sql', 'a': 'nilai', 'b': 'absensi'}]
    with pytest.raises(ValueError):
        validate_multi_args(bad, catalog(), user_id=1)


def test_inner_merge_keeps_only_common_keys_and_does_not_invent_zeros():
    req = multi_request()
    req['gabung']['jenis'] = 'inner'
    result = execute_multi(FactsCursor(), role='admin', user_id=1, args=req)
    assert result['data'] == [{'program': 1, 'nilai': '85.5', 'absensi': 8}]


def test_guard_returns_entity_not_found_before_any_fact_query():
    req = multi_request()
    req['cek_entitas'] = [{'nama': 'program', 'rencana': aggregation('program_bimbel', filters=[
        {'kolom': 'program_bimbel.nama', 'op': 'eq', 'nilai': 'PROGRAM_TIDAK_ADA_98765'}])}]
    cur = FactsCursor(missing=True)
    result = execute_multi(cur, role='admin', user_id=1, args=req)
    assert result['status'] == 'entitas_tidak_ditemukan'
    assert result['cek_entitas'] == [{'entitas': 'program', 'ditemukan': False}]
    assert not any('FROM public."nilai"' in sql or 'FROM public."kehadiran"' in sql
                   for sql, _ in cur.calls)
    assert 'Rp0' not in result['catatan']


def test_multi_refuses_truncated_groups_instead_of_wrong_ranking():
    result = execute_multi(FactsCursor(truncated=True), role='admin', user_id=1, args=multi_request())
    assert result['status'] == 'perlu_persempit_filter'
    assert result['data'] == []
    assert result['terpotong'] is True


def test_mismatched_key_and_hidden_dimension_rejected_before_fact_query():
    wrong = multi_request()
    wrong['analisis'][1]['rencana']['dimensi'] = ['pendaftaran.id_pendaftaran']
    wrong['gabung']['pemetaan']['absensi']['program'] = 'pendaftaran.id_pendaftaran'
    cur = FactsCursor()
    with pytest.raises(ValueError, match='Kunci antar-fakta'):
        execute_multi(cur, role='admin', user_id=1, args=wrong)
    assert not any('FROM public.' in sql for sql, _ in cur.calls)
    wrong = multi_request()
    wrong['analisis'][0]['rencana']['dimensi'].append('nilai.jenis')
    with pytest.raises(ValueError, match='Kunci penggabungan'):
        validate_multi_args(wrong, catalog(), user_id=1)


def test_tutor_scope_and_student_generic_denial_fail_closed():
    req = multi_request()
    cur = FactsCursor()
    result = execute_multi(cur, role='tutor', user_id=73, args=req)
    assert result['status'] == 'ok'
    statements = [(sql, params) for sql, params in cur.calls if 'FROM public."nilai"' in sql or
                  'FROM public."kehadiran"' in sql]
    assert statements
    assert all(73 in params for _, params in statements)

    # Security hotfix: Student may use role-scoped student_dynamic_query and
    # get_my_* but cannot enumerate the internal schema or use generic SQL plans.
    student_cur = FactsCursor()
    with pytest.raises(PermissionError):
        execute_multi(student_cur, role='siswa', user_id=73, args=req)
    assert student_cur.calls == []
    wrong = multi_request()
    wrong['analisis'][0]['rencana'] = aggregation('tagihan', 'sum', 'tagihan.jumlah', ['program_bimbel.id_program'])
    cur = FactsCursor()
    with pytest.raises((ValueError, PermissionError)):
        execute_multi(cur, role='tutor', user_id=73, args=wrong)
    assert not any('FROM public.' in sql for sql, _ in cur.calls)


def test_having_general_count_distinct_uses_parameter_and_does_not_affect_total():
    plan = aggregation('jadwal_kelas', 'count_distinct', 'jadwal_kelas.id_tutor', ['program_bimbel.id_program'])
    plan['syarat_agregat'] = {'op': 'gt', 'nilai': 1}
    total, grouped, additional, base, dims = compile_plan(plan, catalog(), user_id=12)
    assert 'HAVING' not in total
    assert 'HAVING COUNT(DISTINCT t0."id_tutor") > %s' in grouped
    assert additional == (Decimal('1'),)
    assert base == ()
    assert dims == ['program_bimbel.id_program']
    bad = {**plan, 'syarat_agregat': {'op': 'gt', 'nilai': '1 OR true'}}
    with pytest.raises(ValueError):
        compile_plan(bad, catalog(), user_id=12)


def test_new_schema_has_only_sanitized_generic_fields():
    assert MULTI_DECL['name'] == MULTI_QUERY_TOOL
    assert 'sql' not in MULTI_DECL['parameters']['properties']
    assert 'sql' not in QUERY_DECL['parameters']['properties']
    ev = HybridEvidence(original_query='Berapa nilai saya?')
    ev.record(MULTI_QUERY_TOOL, {'status': 'ok', 'analisis': [
        {'nama': 'nilai', 'tabel_utama': 'nilai'},
        {'nama': 'absensi', 'tabel_utama': 'kehadiran'}]})
    assert ev.refusal('Berapa nilai saya?') is None


def ev(kind, **k):
    return NS(event_type=kind, **k)


def tool_stream(call_id, name, args):
    step = {'type': 'function_call', 'id': call_id, 'name': name, 'arguments': args}
    return [ev('step.start', index=0, step=step),
            ev('step.stop', index=0, step=step),
            ev('interaction.completed', interaction=NS(status='requires_action'))]


def final_stream(text):
    return [ev('step.start', index=0, step={'type': 'model_output'}),
            ev('step.delta', index=0, delta=NS(type='text', text=text)),
            ev('step.stop', index=0, step={'type': 'model_output',
                                           'content': [{'type': 'text', 'text': text}]}),
            ev('interaction.completed', interaction=NS(status='completed'))]


class SDK:
    def __init__(self, streams):
        self.streams = list(streams)
        self.calls = []
        self.interactions = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return iter(self.streams.pop(0))


class Gemini:
    def __init__(self, streams):
        self._client = SDK(streams)
        self.options = NS(model='gemini-3.5-flash-lite', thinking_level='low')

    def _code(self, exc):
        return None


class Controller:
    def __init__(self, fail_count=1, error=ValueError('Relasi tidak valid')):
        self.calls = []
        self.fail_count = fail_count
        self.error = error
        self.role = 'admin'

    def declarations(self):
        return [MULTI_DECL]

    def execute(self, name, args):
        self.calls.append((name, args))
        if len(self.calls) <= self.fail_count:
            raise self.error
        return {'status': 'ok', 'rencana': {'tabel_utama': 'pendaftaran'},
                'data': [{'nilai': 9}]}


def test_one_bounded_safe_retry_then_answer_from_real_result():
    sdk = Gemini([tool_stream('fc1', MULTI_QUERY_TOOL, {'unsafe': 'SECRET-TEST-KEY'}),
                  tool_stream('fc2', MULTI_QUERY_TOOL, {'safe': True}),
                  final_stream('Ditemukan 9.')])
    ctrl = Controller()
    events = list(DatabaseFunctionChat(sdk, ctrl).stream([], 'Berapa pendaftaran?', 'system'))
    assert len(ctrl.calls) == 2
    assert events[-1].kind == 'completed'
    history = sdk._client.calls[1]['input']
    feedback = next(r for r in history if r['type'] == 'function_result')['result'][0]['text']
    assert 'rencana_ditolak' in feedback and 'jalur_relasi' in feedback
    assert 'SECRET-TEST-KEY' not in feedback
    assert all(call['store'] is False for call in sdk._client.calls)


def test_refuse_model_hallucination_when_retry_not_successful():
    sdk = Gemini([tool_stream('fc1', MULTI_QUERY_TOOL, {}), final_stream('Nominal Rp999999.')])
    ctrl = Controller()
    events = list(DatabaseFunctionChat(sdk, ctrl).stream([], 'Berapa nominal?', 'system'))
    assert events[-1].kind == 'completed'
    assert '999999' not in events[-1].payload['content']
    assert 'Tidak ada angka' in events[-1].payload['content']
    assert any(e.kind == 'text_reset' for e in events)


def test_permission_denial_is_not_sent_back_as_recoverable_plan():
    sdk = Gemini([tool_stream('fc1', MULTI_QUERY_TOOL, {})])
    ctrl = Controller(error=PermissionError('Jangan baca data lain'))
    events = list(DatabaseFunctionChat(sdk, ctrl).stream([], 'Data siswa lain?', 'system'))
    assert events[-1].kind == 'error'
    assert len(ctrl.calls) == 1 and len(sdk._client.calls) == 1
    assert 'Jangan baca' not in str(events[-1].payload)
