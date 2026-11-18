"""Patch 6.1.2: safe filter metadata feedback, bounded multi-step, stream diagnostics."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from app.services.ai_db_chat import (DatabaseFunctionChat, MAX_TOOL_CALLS_PER_TURN,
                                      _planner_feedback, _runtime_code)
from test_ai_patch61_multistage import Gemini, tool_stream, final_stream
from test_ai_patch611_recovery import RecoveringController


class FilterRejectingController(RecoveringController):
    def execute(self, name, args):
        if name == 'describe_sibima_schema':
            return super().execute(name, args)
        self.actual_calls.append((name, args))
        if len(self.actual_calls) == 1:
            raise ValueError('Filter tidak valid.')
        return {'status': 'ok', 'rencana': {'tabel_utama': 'jadwal_kelas', 'mode': 'agregasi'},
                'data': [{'tutor.id_pengguna': 2, 'nilai': 3}], 'agregat_global': 3,
                'terpotong': False}


def test_invalid_filter_returns_safe_column_types_and_shape_for_one_retry():
    invalid = {'tabel_utama': 'jadwal_kelas', 'filter': [
        {'kolom': 'jadwal_kelas.aktif', 'op': 'eq', 'nilai': 'SECRET-NEVER-ECHO'}]}
    valid = {'tabel_utama': 'jadwal_kelas', 'filter': [
        {'kolom': 'jadwal_kelas.aktif', 'op': 'eq', 'nilai': 'true'}]}
    gem = Gemini([tool_stream('one', 'query_sibima_general', invalid),
                  tool_stream('two', 'query_sibima_general', valid),
                  final_stream('Hasil telah diperiksa dari database.')])
    ctrl = FilterRejectingController()
    events = list(DatabaseFunctionChat(gem, ctrl).stream([], 'Program aktif per tutor', 'system'))
    assert events[-1].kind == 'completed'
    assert len(ctrl.actual_calls) == 2
    feedback = next(x for x in gem._client.calls[1]['input']
                    if x.get('type') == 'function_result')
    payload = json.loads(feedback['result'][0]['text'])
    assert payload['kode'] == 'filter_tidak_valid'
    assert payload['katalog_diizinkan']['tabel']['jadwal_kelas']['aktif'] == 'boolean'
    assert 'SECRET-NEVER-ECHO' not in json.dumps(payload)
    assert 'nilai_daftar' in payload['petunjuk']


def test_multi_step_queries_get_more_than_old_six_calls_without_infinite_loop():
    gem = Gemini([tool_stream(f'call-{idx}', 'query_sibima_general', {'tabel_utama': 'jadwal_kelas'})
                  for idx in range(8)] + [final_stream('Selesai berdasarkan data.')])
    ctrl = RecoveringController(failures=0)
    events = list(DatabaseFunctionChat(gem, ctrl).stream([], 'Analisis beberapa tahapan', 'system'))
    assert MAX_TOOL_CALLS_PER_TURN >= 8
    assert events[-1].kind == 'completed'
    assert not any(e.kind == 'error' for e in events)
    assert len(ctrl.actual_calls) == 8


def test_limit_reached_stops_with_clear_message_without_extra_database_execution():
    gem = Gemini([tool_stream(f'call-{idx}', 'query_sibima_general', {'tabel_utama': 'jadwal_kelas'})
                  for idx in range(9)])
    ctrl = RecoveringController(failures=0)
    events = list(DatabaseFunctionChat(gem, ctrl).stream([], 'Analisis tidak selesai', 'system'))
    assert events[-1].kind == 'completed'
    assert 'batas_tool_atau_putaran' in events[-1].payload['content']
    assert 'data parsial' not in events[-1].payload['content'].lower()
    assert len(ctrl.actual_calls) == 8


def test_stream_runtime_reason_is_allowlisted_not_raw():
    assert _runtime_code(RuntimeError('Gemini mencampur jawaban parsial dengan panggilan fungsi.')) == 'teks-dan-function-call'
    assert _runtime_code(RuntimeError('SECRET mysql password private information')) == 'tidak-ada'
    assert _runtime_code(ValueError('Filter tidak valid.')) == 'tidak-ada'
    assert _planner_feedback(ValueError('Filter tidak valid.'))['kode'] == 'filter_tidak_valid'
