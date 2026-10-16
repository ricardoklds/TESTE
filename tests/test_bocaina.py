"""Correção municipal sem alterações na base real. Fixture de 834 não é a base local."""
from contextlib import closing
from io import BytesIO
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import openpyxl
import core,storage,holidays,localities,holiday_review,queries,cached_queries


DATES=[('2026-09-08','Anhembi'),('2026-09-09','Bofete'),('2026-09-14','Cesário Lange'),('2026-09-15','Ibiúna')]


class BocainaTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.old=storage.DATA;storage.DATA=Path(self.temp.name)
        with closing(storage.connect()):pass
        for day,town in DATES:holidays.save(day,'Feriado sintético','Municipal','SP',town)

    def tearDown(self):storage.DATA=self.old;self.temp.cleanup()

    def add(self,count=1,city='ATC BOCAINA',day=None,prefix='TESTE',task='Leitura'):
        raw=dict(zip(core.FIELDS.values(),['Sim','Não',None,0,None,'Funcionário de teste',city,day or DATES[0][0],prefix,task,'01']))
        rows=[{'line':i+2,'raw':{**raw,'Codigo do Fornecimento':f'{prefix}-{i}',
               'Data da Leitura Atual':day or DATES[i%4][0]}} for i in range(count)]
        parsed={'sheet':'Fixture','headers':list(raw),'records':rows}
        storage.import_sheet((prefix+city+str(count)).encode(),'SINTETICO.xlsx',parsed,core.FIELDS,'2026-09')

    def finance(self):
        stats=queries.overview('2026-09');holiday=holidays.overview('2026-09')
        prices=storage.month_info('2026-09')['prices']
        return stats['units'],holiday['holiday_quantity'],sum(r['total_cents'] for r in queries.summary({**stats,**holiday},prices))

    def test_reference_and_confirmation_are_contract_specific(self):
        self.assertEqual({r['state'] for r in localities.reference()[0]['bocaina']},{'SP','PI'})
        self.assertEqual(localities.reference()[1]['3506805'],{'id':'3506805','name':'Bocaina','state':'SP'})
        self.assertEqual(localities.municipal_confirmations()[0][:3],('atc bocaina','bocaina','SP'))
        self.assertEqual(localities.resolve('Bocaina')[:2],['',''])
        self.assertEqual(localities.resolve('ATC BOCAINA/PI')[:2],['bocaina','PI'])

    def test_834_synthetic_before_after_finance_pagination_and_exports(self):
        self.add(834)
        for i,(day,town) in enumerate(DATES):self.add(city='ATC '+town.upper(),day=day,prefix=f'CORRETO-{i}')
        with patch.object(localities,'municipal_confirmations',return_value=()):
            before=self.finance();old=holidays.overview('2026-09')
            self.assertEqual(old,{'holiday_quantity':4,'holiday_pending':834})
        db=storage.DATA/'contrato.sqlite3';bytes_before=db.read_bytes()
        after=self.finance()
        self.assertEqual(after,before)
        self.assertEqual(holidays.overview('2026-09'),{'holiday_quantity':4,'holiday_pending':0})
        self.assertEqual(holiday_review.page('2026-09',situation='Pendências')[0],0)
        n,page=holiday_review.page('2026-09',situation='Não cobrados',limit=100)
        self.assertEqual(n,834);self.assertEqual(len(page),100)
        self.assertTrue(all(r['status']=='Não aplicável — outro município' and r['municipality']=='bocaina' and r['state']=='SP' and not r['Cobrado'] for r in page))
        self.assertEqual(holiday_review.page('2026-09',situation='Não cobrados',offset=800)[0],834)
        self.assertEqual(holiday_review.page('2026-09',situation='Elegíveis cobrados')[0],4)
        self.assertEqual(holiday_review.pending_summary('2026-09'),[])
        from validar_bocaina_local import validate
        result=validate(storage.DATA)
        self.assertTrue(result['available'])
        self.assertEqual(result['before'],{'charged':4,'pending':834})
        self.assertEqual(result['after'],{'charged':4,'pending':0})
        self.assertEqual(result['charged_ids_changed'],0)
        self.assertEqual(result['financial_before_cents'],result['financial_after_cents'])
        self.assertEqual(holiday_review.page('2026-09','2026-09-09','2026-09-09',municipality='bocaina/SP',situation='Não cobrados')[0],209)
        export=holiday_review.pending_excel(db,queries.revision(),'2026-09')
        with closing(openpyxl.load_workbook(export,read_only=True)) as book:
            self.assertEqual(len(list(book['Pendências 1'].values)),1)
        self.assertEqual(db.read_bytes(),bytes_before)

    def test_closed_snapshot_reclassified_without_database_changes(self):
        self.add(834)
        with patch.object(localities,'municipal_confirmations',return_value=()):
            storage.close_month('2026-09')
            before=self.finance();self.assertEqual(holidays.overview('2026-09')['holiday_pending'],834)
        db=storage.DATA/'contrato.sqlite3';old=db.read_bytes()
        self.assertEqual(self.finance(),before)
        self.assertEqual(holidays.overview('2026-09')['holiday_pending'],0)
        self.assertEqual(holiday_review.page('2026-09',situation='Não cobrados')[0],834)
        self.assertEqual(holiday_review.page('2026-09',situation='Pendências')[0],0)
        self.assertIn('bocaina/SP',holidays.filter_options('2026-09')['municipality'])
        self.assertEqual(db.read_bytes(),old)
        # Historical snapshot itself remains intact; only its read projection changes.
        with closing(storage.connect()) as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM holiday_frozen_review WHERE json_extract(detail,'$.status')='Município/UF não confirmado'").fetchone()[0],834)

    def test_really_ambiguous_locality_remains_pending_and_wrong_state_not_pending(self):
        self.add(city='Origem desconhecida',prefix='INCERTO')
        self.add(city='RJ',prefix='OUTRA-UF')
        self.assertEqual(holidays.overview('2026-09')['holiday_pending'],1)
        self.assertEqual(holiday_review.page('2026-09',situation='Pendências')[0],1)
        self.assertEqual(holiday_review.page('2026-09',situation='Não cobrados')[0],2)
        # A homonymous town that may match stays pending; no guessed UF.
        holidays.save('2026-09-08','Teste homônimo','Municipal','PI','Bocaina')
        self.add(city='Bocaina',prefix='HOMONIMO')
        self.assertEqual(holiday_review.page('2026-09',situation='Pendências')[0],2)

    def test_date_municipality_uf_match_and_duplicate_control(self):
        holidays.save('2026-09-09','Teste Bocaina','Municipal','SP','Bocaina')
        self.add(day='2026-09-09')
        self.add(city='ATC BOCAINA/PI',day='2026-09-09',prefix='PI')
        self.add(day='2026-09-08',prefix='DATA-ERRADA')
        self.assertEqual(holidays.overview('2026-09')['holiday_quantity'],1)
        self.assertEqual(holidays.overview('2026-09')['holiday_pending'],0)

    def test_national_state_and_mixed_scope_behavior_unchanged(self):
        self.add(4)
        for scope,state in [('Nacional',''),('Estadual','SP')]:
            holidays.save('2026-09-08','Teste adicional',scope,state)
            with patch.object(localities,'municipal_confirmations',return_value=()):
                old=self.finance();pending=holidays.overview('2026-09','2026-09-08','2026-09-08')
            self.assertEqual(self.finance(),old)
            self.assertEqual(holidays.overview('2026-09','2026-09-08','2026-09-08'),pending)
            holidays.delete(next(h['id'] for h in holidays.calendar() if h['day']=='2026-09-08' and h['scope']==scope))

    def test_exclusion_restore_still_preserves_monthly_finance(self):
        self.add(10)
        before=self.finance();import_id=storage.imports('2026-09')[0]['id']
        storage.set_import_deleted('2026-09',import_id,True,'Teste')
        self.assertEqual(holiday_review.page('2026-09')[0],0)
        storage.set_import_deleted('2026-09',import_id,False,'Teste')
        self.assertEqual(self.finance(),before)
        self.assertEqual(holiday_review.page('2026-09',situation='Não cobrados')[0],10)
