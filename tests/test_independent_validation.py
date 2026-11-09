"""Validação por originais artificiais, sem referências de fechamento manual."""
from contextlib import closing
from io import BytesIO
import itertools
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import openpyxl
import core
import holidays
import storage
import validacao_independente as independent


class IndependentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.previous=storage.DATA
        storage.DATA=Path(self.temp.name)/'data'
        with closing(storage.connect()):pass

    def tearDown(self):storage.DATA=self.previous;self.temp.cleanup()

    def row(self,number,**changes):
        raw={v:'' for v in core.FIELDS.values()}
        raw.update({'Faturas Impressas':'Sim','Fatura Retida':'Não','Quantidade comunicados impressos':2,'CO1 Atual':'0',
                    'Data da Leitura Atual':'07/09/2026','ATC':'ATC AGUDOS','Codigo do Fornecimento':str(number),'Tarefa':'Leitura',
                    'Grupo':'01','Nome do TACE':'Funcionário sintético'})
        raw.update(changes);return raw

    def load(self,rows,name='originais.xlsx'):
        book=openpyxl.Workbook();s=book.active;headers=list(rows[0]);s.append(headers)
        for raw in rows:s.append([raw.get(h) for h in headers])
        b=BytesIO();book.save(b);parsed=core.parse_excel(b.getvalue())[0]
        storage.import_sheet(b.getvalue(),name,parsed,parsed['mapping'],'2026-09')

    def output(self,name):return Path(self.temp.name)/name

    def test_five_rules_regression_cross_product_and_validation_errors(self):
        mapping={k:v for k,v in core.FIELDS.items()}
        for printed,retained,cause,copies,operational,day in itertools.product(
                ['Sim','Não',''],['Sim','Não'],['','1'],[0,2,'inválido'],['',0,'1'],['07/09/2026','', '2026-10-01']):
            raw=self.row(1,**{'Faturas Impressas':printed,'Fatura Retida':retained,'Causas de Leitura/Não Leitura Atual':cause,
                'Quantidade comunicados impressos':copies,'CO1 Atual':operational,'Data da Leitura Atual':day})
            expected=core.evaluate(raw,mapping,'2026-09')['units']
            actual,errors=independent.five(raw,mapping,'2026-09')
            self.assertEqual({k:actual[k] for k in expected},expected)
        for value in ['=1+1','2026-09-07T10:00:00.123',45000]:
            raw=self.row(1,**{'Data da Leitura Atual':value})
            actual,_=independent.five(raw,mapping,'2026-09')
            self.assertEqual({k:actual[k] for k in core.CATEGORIES},core.evaluate(raw,mapping,'2026-09')['units'])

    def test_originais_and_holidays_scopes_bocaina_sunday_and_duplicates(self):
        rows=[self.row(1),self.row(2,**{'Faturas Impressas':'inválida'}),
            self.row(3,**{'Fatura Retida':'Sim'}),self.row(4,**{'Causas de Leitura/Não Leitura Atual':'1'}),
            self.row(5,**{'Data da Leitura Atual':None}),self.row(6,**{'Data da Leitura Atual':'06/09/2026'}),
            self.row(7,**{'Data da Leitura Atual':'08/09/2026','ATC':'ATC BOCAINA'}),
            self.row(8,**{'Data da Leitura Atual':'08/09/2026','ATC':'Anhembi/SP'}),
            self.row(9,**{'Data da Leitura Atual':'09/09/2026'}),
            self.row(10,**{'Data da Leitura Atual':'09/09/2026','ATC':'Rio de Janeiro/RJ'}),
            self.row(11,**{'Data da Leitura Atual':'2026-09-07T10:00:00.123'})]
        for r in rows:r['Observação']=''
        duplicate=dict(rows[0]);duplicate['Observação']='Outra linha da mesma execução'
        rows.extend([duplicate,dict(rows[0])]);self.load(rows)
        holidays.save('2026-09-07','Teste','Nacional');holidays.save('2026-09-06','Domingo','Nacional')
        holidays.save('2026-09-08','Municipal','Municipal','SP','Anhembi');holidays.save('2026-09-09','Estadual','Estadual','SP')
        before=(storage.DATA/'contrato.sqlite3').read_bytes()
        result=independent.run(self.output('validacao'),data=storage.DATA)
        self.assertEqual(result['independent_quantities']['feriado'],5)
        self.assertEqual(result['comparison']['delta_cents'],0)
        self.assertTrue(result['comparison']['detail_delta_matches_totals'])
        self.assertTrue(result['comparison']['app_details_match_aggregates'])
        self.assertEqual(result['holiday_reasons']['Não aplicável — outro município'],1)
        self.assertEqual(result['holiday_reasons']['Domingo: conferir'],1)
        self.assertEqual(result['holiday_reasons']['Duplicata de execução de feriado'],1)
        self.assertEqual(result['active_missing_date'],1)
        self.assertEqual((storage.DATA/'contrato.sqlite3').read_bytes(),before)
        with closing(openpyxl.load_workbook(self.output('validacao')/'validacao.xlsx',read_only=True)) as x:
            self.assertEqual(len(list(x['Registros originais 1'].values)),14)
            self.assertEqual(len(list(x['Divergências 1'].values)),1)

    def test_independence_from_saved_results_and_no_database_manifest_mode(self):
        self.load([self.row(1)])
        with closing(storage.connect()) as c:
            c.execute('UPDATE record_metrics SET u138=9999');c.commit()
        before=(storage.DATA/'contrato.sqlite3').read_bytes()
        result=independent.run(self.output('distorted'),data=storage.DATA)
        self.assertEqual(result['independent_quantities']['138'],1)
        self.assertEqual(result['comparison']['app_quantities']['138'],9999)
        self.assertEqual(result['comparison']['different_records'],1)
        self.assertEqual((storage.DATA/'contrato.sqlite3').read_bytes(),before)
        with (patch.object(independent,'ro',side_effect=AssertionError('Não pode consultar banco')),
              patch.object(core,'evaluate',side_effect=AssertionError('Não pode usar motor'))):
            again=independent.run(self.output('offline'),manifest=self.output('distorted')/'entradas.json')
        self.assertEqual(again['independent_quantities']['138'],1)
        self.assertNotIn('comparison',again)
        sealed=json.loads((self.output('distorted')/'calculo_independente.json').read_text())
        self.assertNotIn('comparison',sealed)
        self.assertEqual(sealed['independent_quantities'],again['independent_quantities'])
        old=self.output('auditoria-anterior.json')
        old.write_text(json.dumps({'month':'2026-09','available':True,'official_total_cents':1,
                                   'official_quantities':dict.fromkeys(independent.KEYS,0)}))
        later=independent.run(self.output('previous'),manifest=self.output('distorted')/'entradas.json',previous_audit=old)
        self.assertEqual(later['independent_quantities'],again['independent_quantities'])
        self.assertEqual(later['previous_audit_comparison']['delta_cents'],later['independent_total_cents']-1)

    def test_ambiguous_locality_brazil_proof_and_conflicting_execution(self):
        self.load([self.row(1),self.row(1,**{'ATC':'Guarulhos/SP'}),
                   self.row(2,**{'ATC':'ATC BOCAINA'}),self.row(3,**{'ATC':'Localidade sem nome conhecido'})])
        holidays.save('2026-09-07','Teste','Nacional')
        import localities
        localities.prove_brazil(1,'Evidência sintética documentada')
        result=independent.run(self.output('localidades'),data=storage.DATA)
        self.assertEqual(result['independent_quantities']['feriado'],2)
        self.assertEqual(result['holiday_reasons']['Execução com localidades divergentes'],2)
        self.assertEqual(result['comparison']['delta_cents'],0)

    def test_delete_restore_and_frozen_calendar_difference_is_not_corrected(self):
        self.load([self.row(1)])
        holidays.save('2026-09-07','Teste','Nacional')
        storage.set_import_deleted('2026-09',1,True,'Teste')
        deleted=independent.run(self.output('deleted'),data=storage.DATA)
        self.assertEqual(deleted['independent_total_cents'],0)
        storage.set_import_deleted('2026-09',1,False,'Teste')
        storage.exclude('2026-09',1,'Exclusão sintética')
        excluded=independent.run(self.output('excluded'),data=storage.DATA)
        self.assertEqual(excluded['independent_total_cents'],0)
        self.assertEqual(excluded['comparison']['delta_cents'],0)
        storage.exclude('2026-09',1,'Restaurar teste',False);storage.close_month('2026-09')
        restored=independent.run(self.output('restored'),data=storage.DATA)
        self.assertEqual(restored['comparison']['delta_cents'],0)
        holidays.delete(holidays.calendar()[0]['id'])
        frozen=independent.run(self.output('frozen'),data=storage.DATA)
        self.assertEqual(frozen['independent_quantities']['feriado'],0)
        self.assertEqual(frozen['comparison']['app_quantities']['feriado'],1)
        self.assertEqual(frozen['comparison']['delta_cents'],-105)

    def test_source_integrity_output_protection_and_absent_month(self):
        self.load([self.row(1)])
        with self.assertRaises(ValueError):independent.run(storage.DATA/'nao',data=storage.DATA)
        with self.assertRaises(ValueError):independent.run(self.output('absent'),data=storage.DATA,month='2026-08')
        result=independent.run(self.output('first'),data=storage.DATA,compare_app=False)
        with self.assertRaises(FileExistsError):independent.run(self.output('first'),data=storage.DATA)
        original=next((storage.DATA/'originais').glob('*.xlsx'));original.write_bytes(b'Alteracao artificial de teste')
        with self.assertRaises(ValueError):independent.run(self.output('corrupt'),manifest=self.output('first')/'entradas.json')
