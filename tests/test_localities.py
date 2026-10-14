"""Casos isolados: não apuram o relatório real de 07/09/2026, não fornecido."""
import test_holidays as fixtures
import unittest
from datetime import date
import json
import core,storage,holidays,localities,queries

class LocalityTests(unittest.TestCase):
    setUp=fixtures.HolidayTests.setUp
    tearDown=fixtures.HolidayTests.tearDown
    add=fixtures.HolidayTests.add
    qty=fixtures.HolidayTests.qty
    national=fixtures.HolidayTests.national
    def test_official_codes_and_normalization(self):
        for source in ('ATC AGUDOS','  atc   Agudos ','3500709'):
            self.assertEqual(localities.resolve(source)[:3],['agudos','SP','BR'])
        self.assertEqual(localities.resolve('ATC ARACARIGUAMA')[:3],['aracariguama','SP','BR'])
        self.assertEqual(localities.resolve('Araçariguama/SP')[:3],['aracariguama','SP','BR'])
        self.assertEqual(localities.resolve('ATC AGUDOS/RJ')[:3],['','',''])
        self.assertEqual(localities.resolve('ATC LOCAL INEXISTENTE')[:3],['','',''])

    def test_september_national_without_manual_binding(self):
        self.add(day='07/09/2026',city='ATC AGUDOS',month='2026-09')
        self.add(day='07/09/2026',city='ATC ARACARIGUAMA',supply='TESTE-2',month='2026-09')
        holidays.save('2026-09-07','Independência do Brasil','Nacional')
        self.assertEqual(holidays.overview('2026-09')['holiday_quantity'],2)
        self.assertEqual(holidays.overview('2026-09')['holiday_pending'],0)

    def test_scope_specific_proof_and_homonyms(self):
        self.add(city='ATC BOM JESUS')
        self.national();self.assertEqual(self.qty(),1)
        result=localities.resolve('ATC BOM JESUS');self.assertEqual(result[0],'');self.assertEqual(result[1],'')
        holidays.delete(holidays.calendar()[0]['id'])
        holidays.save('2026-10-12','Estadual de teste','Estadual','SP')
        self.assertEqual(self.qty(),0);self.assertEqual(holidays.overview('2026-10')['holiday_pending'],1)
        holidays.delete(holidays.calendar()[0]['id'])
        holidays.save('2026-10-12','Municipal de teste','Municipal','SP','Agudos')
        self.assertEqual(self.qty(),0)

    def test_state_only_and_documentary_country(self):
        entry=self.add(city='Origem sem identificação')
        self.national();self.assertEqual(self.qty(),0)
        localities.prove_brazil(entry,'Fixture: evidência documental brasileira conferida')
        self.assertEqual(self.qty(),1)
        holidays.delete(holidays.calendar()[0]['id']);holidays.save('2026-10-12','Estadual de teste','Estadual','SP')
        self.assertEqual(self.qty(),0)
        other=self.add(city='SP',supply='TESTE-2');self.assertEqual(self.qty(),1)
        holidays.delete(holidays.calendar()[0]['id']);holidays.save('2026-10-12','Municipal de teste','Municipal','SP','Agudos')
        self.assertEqual(self.qty(),0)

    def test_automatic_exclusion_restore_sunday_and_five_regression(self):
        entry=self.add(city='ATC AGUDOS')
        self.add(day='11/10/2026',city='ATC ARACARIGUAMA',supply='TESTE-2')
        prices=storage.month_info('2026-10')['prices'];base=core.summarize(storage.records('2026-10'),prices)
        self.national();holidays.save('2026-10-11','Domingo teste','Nacional')
        self.assertEqual(self.qty(),1)
        storage.set_import_deleted('2026-10',entry,True,'Teste');self.assertEqual(self.qty(),0)
        storage.set_import_deleted('2026-10',entry,False,'Restaurar teste');self.assertEqual(self.qty(),1)
        self.assertEqual(core.summarize(storage.records('2026-10'),prices),base)

    def test_legacy_city_header_resolution(self):
        raw={'Cidade/ATC':'ATC AGUDOS','Fatura Retida':'Não','Causas de Leitura/Não Leitura Atual':''}
        mapping={'city':None,'retained':'Fatura Retida','cause':'Causas de Leitura/Não Leitura Atual'}
        self.assertEqual(json.loads(holidays.identity(json.dumps(raw),json.dumps(mapping)))[2],'atc agudos')
        raw['Cidade']='Outra cidade'
        source=json.loads(holidays.identity(json.dumps(raw),json.dumps(mapping)))[2]
        self.assertEqual(localities.resolve(source)[:3],['','',''])
