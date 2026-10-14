"""Integração isolada com registros reais já fornecidos, sem tocar a produção."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from io import BytesIO
import openpyxl
import core,storage,periods
from exports import productivity,excel_report

SOURCE=storage.DATA/'contrato.sqlite3'

@unittest.skipUnless(SOURCE.exists(),'Requer a base real fornecida')
class ImportActions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with sqlite3.connect(SOURCE) as c:
            cls.raw=[json.loads(r[0]) for r in c.execute('SELECT raw FROM records ORDER BY id LIMIT 3')]

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.old=storage.DATA;storage.DATA=Path(self.temp.name)

    def tearDown(self):
        storage.DATA=self.old;self.temp.cleanup()

    def add(self,rows,name='arquivo.xlsx',month='2026-10'):
        w=openpyxl.Workbook();s=w.active;s.append(list(rows[0]))
        for r in rows:s.append(list(r.values()))
        out=BytesIO();w.save(out)
        parsed=core.parse_excel(out.getvalue())[0]
        storage.import_sheet(out.getvalue(),name,parsed,parsed['mapping'],month)
        return storage.imports(month)[-1]['id']

    def total(self):
        return sum(r['total_cents'] for r in core.summarize(storage.records('2026-10'),storage.month_info('2026-10')['prices']))

    def test_delete_restore_finance_filters_and_other_imports(self):
        a=self.add(self.raw[:1]);b=self.add(self.raw[1:]);self.add(self.raw[:1],month='2026-11')
        baseline=self.total();other=storage.records('2026-11');originals={p.name:p.read_bytes() for p in (storage.DATA/'originais').iterdir()}
        preview=storage.import_preview('2026-10',a)
        storage.set_import_deleted('2026-10',a,True,'Teste de exclusão',preview['version'])
        self.assertEqual(self.total(),baseline-preview['total_cents'])
        self.assertEqual(storage.records('2026-11'),other)
        self.assertFalse(any(r['excluded'] for r in storage.records('2026-10') if r['import_id']==b))
        rows=storage.records('2026-10');prices=storage.month_info('2026-10')['prices']
        for by in ('employee','city','group'):
            self.assertEqual(sum(r['total_cents'] for r in productivity(rows,prices,by)),self.total())
        dated=periods.valid_records(periods.filter_period(rows,periods.import_mappings(storage.imports('2026-10')),'2026-10',*periods.month_bounds('2026-10')))
        self.assertEqual(len(dated),2)
        x=excel_report('2026-10',rows,prices,storage.imports('2026-10'),storage.audit('2026-10'),{},False)
        report=openpyxl.load_workbook(BytesIO(x),data_only=True)
        self.assertEqual(round(report['Fechamento']['E11'].value*100),self.total())
        storage.set_import_deleted('2026-10',a,False,'Teste de restauração')
        self.assertEqual(self.total(),baseline)
        self.assertEqual({p.name:p.read_bytes() for p in (storage.DATA/'originais').iterdir()},originals)
        self.assertEqual(len(storage.audit('2026-10')),4)

    def test_reimport_restore_conflict_atomic_and_manual_exclusion(self):
        a=self.add(self.raw[:2]);baseline=self.total();row=storage.records('2026-10')[0]
        storage.exclude('2026-10',row['id'],'Decisão individual')
        storage.set_import_deleted('2026-10',a,True,'Substituir arquivo')
        b=self.add(self.raw[:3],'corrigido.xlsx')
        before=storage.records('2026-10');events=storage.audit('2026-10')
        with self.assertRaisesRegex(ValueError,'bloqueada'):storage.set_import_deleted('2026-10',a,False,'Restaurar')
        self.assertEqual(storage.records('2026-10'),before);self.assertEqual(storage.audit('2026-10'),events)
        storage.set_import_deleted('2026-10',b,True,'Desfazer substituição')
        storage.set_import_deleted('2026-10',a,False,'Restaurar original')
        self.assertTrue(storage.records('2026-10')[0]['record_excluded'])
        self.assertLess(self.total(),baseline)

    def test_closed_month_reason_and_stale_confirmation(self):
        a=self.add(self.raw[:1]);preview=storage.import_preview('2026-10',a)
        with self.assertRaises(ValueError):storage.set_import_deleted('2026-10',a,True,'')
        storage.update_month_prices('2026-10',storage.month_info('2026-10')['prices'])
        storage.exclude('2026-10',storage.records('2026-10')[0]['id'],'Conferência')
        with self.assertRaisesRegex(ValueError,'mudaram'):storage.set_import_deleted('2026-10',a,True,'Excluir',preview['version'])
        storage.exclude('2026-10',storage.records('2026-10')[0]['id'],'Reincluir',False)
        storage.close_month('2026-10')
        with self.assertRaisesRegex(ValueError,'fechado'):storage.set_import_deleted('2026-10',a,True,'Excluir')

    def test_migration_backup_and_exact_records(self):
        self.add(self.raw[:2])
        with sqlite3.connect(storage.DATA/'contrato.sqlite3') as old:
            for name, in old.execute("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall():
                old.execute('DROP TRIGGER "'+name+'"')
            old.execute('DROP TABLE record_metrics')
            old.execute('DROP TABLE cache_revision')
            for table in ('holidays','municipality_bindings','holiday_identity_records','holiday_freeze','holiday_frozen_records','holiday_frozen_review'):
                old.execute('DROP TABLE '+table)
            for table in ('automatic_localities','import_brazil_proofs'):
                old.execute('DROP TABLE '+table)
            for index in ('records_import','records_month_id','audit_month'):
                old.execute('DROP INDEX '+index)
            old.execute('DROP INDEX active_fingerprints')
            old.execute('ALTER TABLE records DROP COLUMN import_deleted')
            old.execute('ALTER TABLE imports DROP COLUMN deleted')
            old.execute('CREATE UNIQUE INDEX legacy_fingerprints ON records(month,fingerprint)')
            old.execute('PRAGMA user_version=0')
        c=storage.connect();c.close()
        backups=list((storage.DATA/'backups').glob('*.sqlite3'))
        self.assertTrue(backups)
        with sqlite3.connect(backups[0]) as before,storage.connect() as after:
            cols='id,month,import_id,line,fingerprint,raw,result,excluded,reason'
            self.assertEqual(before.execute('SELECT '+cols+' FROM records ORDER BY id').fetchall(),
                             [tuple(r) for r in after.execute('SELECT '+cols+' FROM records ORDER BY id')])
            self.assertEqual(after.execute('PRAGMA integrity_check').fetchone()[0],'ok')
