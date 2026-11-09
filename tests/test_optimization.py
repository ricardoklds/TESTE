"""Regressões da otimização, sempre em SQLite temporário."""
import json
from pathlib import Path
import tempfile
import sqlite3
import unittest
from unittest.mock import patch
import core, holidays, queries, storage
import fast_reports, openpyxl
from io import BytesIO


class OptimizationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.previous=storage.DATA;storage.DATA=Path(self.temp.name)
        with storage.connect():pass
        self.mapping=dict(core.FIELDS)

    def tearDown(self):
        storage.DATA=self.previous;self.temp.cleanup()

    def raw(self,index):
        return dict(zip(core.FIELDS.values(),['Sim','Não',None,2,'1','Funcionário teste',
                    'ATC AGUDOS','2026-09-07',str(index),'Leitura','01']))

    def import_rows(self,name,count,progress=None,start=0):
        parsed={'sheet':'Teste','headers':list(core.FIELDS.values()),
                'records':({'line':i+2,'raw':self.raw(start+i)} for i in range(count))}
        return storage.import_sheet(name.encode(),name,parsed,self.mapping,'2026-09',on_progress=progress)

    def test_bounded_identity_cache_reuses_four_trigger_calls(self):
        holidays.identity.cache_clear()
        raw=json.dumps(self.raw(1));mapping=json.dumps(self.mapping)
        with patch.object(holidays.json,'loads',wraps=json.loads) as loads:
            results=[holidays.identity(raw,mapping) for _ in range(4)]
            self.assertEqual(loads.call_count,2)
        self.assertEqual(len(set(results)),1)
        for i in range(100):holidays.identity(json.dumps(self.raw(i)),mapping)
        self.assertLessEqual(holidays.identity.cache_info().currsize,32)

    def test_progress_batches_and_rollback(self):
        calls=[]
        self.assertEqual(self.import_rows('teste.xlsx',2001,lambda *x:calls.append(x)),(2001,0))
        self.assertEqual(calls,[(1000,1000,0),(2000,2000,0),(2001,2001,0)])
        def failure(*args):raise RuntimeError('cancelado')
        with self.assertRaises(RuntimeError):self.import_rows('cancelado.xlsx',2000,failure,start=5000)
        self.assertEqual(queries.overview('2026-09')['active_count'],2001)
        self.assertEqual(len(storage.imports('2026-09')),1)

    def test_listing_matches_preview_exclusion_restoration_and_freeze(self):
        holidays.save('2026-09-07','Teste','Nacional')
        self.import_rows('primeiro.xlsx',3)
        self.import_rows('segundo.xlsx',2,start=10)
        prices=storage.month_info('2026-09')['prices']
        def check():
            for row in queries.import_listing('2026-09',prices):
                preview=storage.import_preview('2026-09',row['id'])
                for key in ('record_count','active_count','total_cents'):
                    self.assertEqual(row[key],preview[key])
        check()
        before=queries.overview('2026-09');fees=holidays.overview('2026-09')
        storage.set_import_deleted('2026-09',1,True,'teste');check()
        storage.set_import_deleted('2026-09',1,False,'teste');check()
        self.assertEqual(queries.overview('2026-09'),before)
        self.assertEqual(holidays.overview('2026-09'),fees)
        storage.close_month('2026-09');check()

    def test_aggregate_month_and_day_match_saved_rules(self):
        self.import_rows('teste.xlsx',10)
        storage.exclude('2026-09',1,'teste')
        for start,end in [(None,None),('2026-09-07','2026-09-07'),('2026-09-08','2026-09-08')]:
            stats=queries.overview('2026-09',start,end)
            expected={key:0 for key in core.CATEGORIES}
            for row in storage.records('2026-09'):
                if not row['excluded'] and (not start or start<=row['raw'][core.FIELDS['date']]<=end):
                    for key in expected:expected[key]+=row['result']['units'][key]
            self.assertEqual(stats['units'],expected)

    def test_streaming_export_preserves_empty_cells_numbers_and_literal_formulas(self):
        workbook=openpyxl.Workbook(write_only=True);sheet=workbook.create_sheet('Teste')
        fast_reports.text_row(sheet,['Coluna 1','Coluna 2','Coluna 3','Coluna 4','Coluna 5'])
        fast_reports.text_row(sheet,['=1+1',None,3,False,None])
        content=BytesIO();workbook.save(content)
        result=openpyxl.load_workbook(BytesIO(content.getvalue()))['Teste']
        self.assertEqual([c.value for c in result[2]],['=1+1',None,3,False,None])
        self.assertEqual(result['A2'].data_type,'s')

    def test_sqlite_backup_and_recovery_keep_six_totals(self):
        holidays.save('2026-09-07','Teste','Nacional')
        self.import_rows('teste.xlsx',20)
        before=queries.overview('2026-09');holiday_before=holidays.overview('2026-09')
        backup=storage.DATA/'backup-teste.sqlite3'
        with storage.connect() as source,sqlite3.connect(backup) as target:
            source.backup(target)
            self.assertEqual(target.execute('PRAGMA integrity_check').fetchone()[0],'ok')
        storage.set_import_deleted('2026-09',1,True,'teste recuperação')
        # Restore to ANOTHER directory, never overwrite the only database copy.
        recovered=storage.DATA/'recuperado';recovered.mkdir()
        with sqlite3.connect(backup) as source,sqlite3.connect(recovered/'contrato.sqlite3') as target:
            source.backup(target)
        old=storage.DATA
        try:
            storage.DATA=recovered
            self.assertEqual(queries.overview('2026-09'),before)
            self.assertEqual(holidays.overview('2026-09'),holiday_before)
        finally:storage.DATA=old

    def test_listing_holiday_duplicate_owner_moves_and_cache_invalidates(self):
        import cached_queries
        holidays.save('2026-09-07','Teste','Nacional')
        self.import_rows('primeiro.xlsx',1)
        with patch.object(self,'raw',return_value={**self.raw(0),'Faturas Impressas':'Não'}):
            self.import_rows('segundo.xlsx',1)
        prices=storage.month_info('2026-09')['prices']
        def listing():
            return cached_queries.import_listing(str(storage.DATA),queries.revision(),'2026-09',prices)
        def check():
            for row in listing():
                self.assertEqual(row['total_cents'],storage.import_preview('2026-09',row['id'])['total_cents'])
        before=listing();check()
        self.assertEqual(holidays.overview('2026-09')['holiday_quantity'],1)
        storage.set_import_deleted('2026-09',1,True,'teste');check()
        self.assertEqual(listing()[0]['total_cents'],0)
        self.assertEqual(holidays.overview('2026-09')['holiday_quantity'],1)
        storage.set_import_deleted('2026-09',1,False,'teste');check()
        self.assertEqual(listing(),before)
