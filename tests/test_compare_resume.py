from pathlib import Path
import hashlib
import json
import unittest
from unittest.mock import patch
import openpyxl
from contextlib import closing
import holidays
import storage
import validacao_independente as validation
import test_independent_validation as fixtures


def inventory(folder):
    return {str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob('*') if p.is_file()}


class ResumeTests(unittest.TestCase):
    setUp=fixtures.IndependentTests.setUp
    tearDown=fixtures.IndependentTests.tearDown
    row=fixtures.IndependentTests.row
    load=fixtures.IndependentTests.load
    output=fixtures.IndependentTests.output

    def saved(self):
        self.load([self.row(1),self.row(2,**{'Data da Leitura Atual':None})])
        holidays.save('2026-09-07','Sintético','Nacional')
        validation.run(self.output('saved'),data=storage.DATA,compare_app=False)
        return self.output('saved')

    def test_legacy_resume_does_not_open_excel_or_overwrite_any_inputs(self):
        saved=self.saved();before=inventory(saved);bank=inventory(storage.DATA)
        with (patch.object(validation,'original_rows',side_effect=AssertionError('Não reler Excel')),
              patch.object(openpyxl,'load_workbook',side_effect=AssertionError('Não abrir Excel'))):
            result=validation.compare_saved(storage.DATA,saved,self.output('resumed'))
        self.assertEqual(result['comparison']['delta_cents'],0)
        self.assertTrue(all(n==0 for n in result['comparison']['delta_quantities'].values()))
        self.assertFalse(result['comparison']['detail_comparison_available'])
        self.assertIsNone(result['comparison']['app_details_match_aggregates'])
        self.assertEqual(result['comparison']['app_records_transferred'],0)
        self.assertEqual(before,inventory(saved));self.assertEqual(bank,inventory(storage.DATA))
        with closing(openpyxl.load_workbook(self.output('resumed')/'comparacao.xlsx',read_only=True)) as x:
            self.assertEqual(len(list(x['Comparação seis serviços 1'].values)),7)
        with self.assertRaises(FileExistsError):validation.compare_saved(storage.DATA,saved,self.output('resumed'))
        with self.assertRaises(ValueError):validation.compare_saved(storage.DATA,saved,saved/'no')
        with self.assertRaises(ValueError):validation.compare_saved(storage.DATA,saved,storage.DATA/'no')

    def test_stale_revision_and_inconsistent_json_are_rejected(self):
        saved=self.saved();path=saved/'calculo_independente.json';original=path.read_bytes()
        result=json.loads(original);result['independent_quantities']['138']+=1
        path.write_text(json.dumps(result))
        with self.assertRaisesRegex(ValueError,'consistentes'):validation.compare_saved(storage.DATA,saved,self.output('bad'))
        path.write_bytes(original)
        holidays.save('2026-09-08','Novo feriado sintético','Nacional')
        with self.assertRaisesRegex(ValueError,'base mudou'):validation.compare_saved(storage.DATA,saved,self.output('stale'))
        self.assertEqual(path.read_bytes(),original)

    def test_wrong_bank_imports_and_manifest_changes_are_rejected(self):
        saved=self.saved();manifest=saved/'entradas.json';original=manifest.read_bytes()
        m=json.loads(original);m['month']='2026-08';manifest.write_text(json.dumps(m))
        with self.assertRaisesRegex(ValueError,'manifesto'):validation.compare_saved(storage.DATA,saved,self.output('bad_manifest'))
        manifest.write_bytes(original)
        with closing(storage.connect()) as c:
            c.execute("UPDATE imports SET name='Outro arquivo sintético.xlsx'");c.commit()
        with self.assertRaisesRegex(ValueError,'importações'):validation.compare_saved(storage.DATA,saved,self.output('wrong_bank'))

    def test_real_differences_are_reported_without_adjusting_saved_result(self):
        saved=self.saved();before=inventory(saved)
        with closing(storage.connect()) as c:
            c.execute('UPDATE record_metrics SET u138=u138+1 WHERE id=1');c.commit()
        result=validation.compare_saved(storage.DATA,saved,self.output('different'))
        self.assertEqual(result['comparison']['delta_quantities']['138'],-1)
        self.assertEqual(result['comparison']['delta_cents'],-138)
        self.assertEqual(before,inventory(saved))
