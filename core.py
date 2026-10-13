"""Regras confirmadas pelo usuário. Valores financeiros em centavos inteiros."""
from collections import Counter
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
import hashlib
import json
import unicodedata
import openpyxl

FIELDS = {
    'printed': 'Faturas Impressas', 'retained': 'Fatura Retida',
    'cause': 'Causas de Leitura/Não Leitura Atual',
    'copies': 'Quantidade comunicados impressos', 'operational': 'CO1 Atual',
    'employee': 'Nome do TACE', 'city': 'ATC', 'date': 'Data da Leitura Atual',
    'supply': 'Codigo do Fornecimento', 'task': 'Tarefa', 'group': 'Grupo',
}
REQUIRED = ['printed', 'retained', 'cause', 'copies', 'operational']
CATEGORIES = {
    '138': ('200014094', 'Leitura com fatura impressa', 138),
    '128': ('200014096', 'Leitura sem fatura impressa', 128),
    '137': ('200014095', 'Leitura com causa preenchida', 137),
    'impressao': ('200014102', 'Adicional de impressão', 50),
    'apontamento': ('200014103', 'Apontamento operacional', 50),
}

def norm(v):
    text = str(v if v is not None else '').strip().casefold()
    return ''.join(c for c in unicodedata.normalize('NFD', text) if not unicodedata.combining(c))

def serial(v):
    return v.isoformat() if isinstance(v, (datetime, date)) else v

def fingerprint(row):
    return hashlib.sha256(json.dumps(row, ensure_ascii=False, sort_keys=True, default=serial).encode()).hexdigest()

def parse_excel(content):
    # Some Sabesp exports incorrectly declare A1 as the whole used range.
    book = openpyxl.load_workbook(BytesIO(content), read_only=True, data_only=False)
    result = []
    try:
        for sheet in book:
            sheet.reset_dimensions()
            headers = None
            records = []
            for number, values in enumerate(sheet.iter_rows(values_only=True), 1):
                if headers is None:
                    names = [str(x).strip() if x is not None else '' for x in values]
                    if sum(norm(v) in {norm(x) for x in FIELDS.values()} for v in names) >= 3:
                        if len(set(names)) != len(names) or any(not x for x in names):
                            raise ValueError(f'{sheet.title}: cabeçalhos vazios ou repetidos; corrija a exportação na origem.')
                        headers = names
                        header_row = number
                    elif number >= 40:
                        break
                    continue
                if not any(v is not None and v != '' for v in values):
                    continue
                if len(values) > len(headers) and any(v is not None for v in values[len(headers):]):
                    raise ValueError(f'{sheet.title}, linha {number}: dados fora do cabeçalho.')
                row = {h: serial(values[i]) if i < len(values) else None for i, h in enumerate(headers)}
                records.append({'line': number, 'raw': row})
            if headers is not None:
                mapping = {k: next((h for h in headers if norm(h) == norm(v)), None) for k, v in FIELDS.items()}
                result.append({'sheet': sheet.title, 'headers': headers, 'header_row': header_row, 'records': records, 'mapping': mapping})
    finally:
        book.close()
    if not result:
        raise ValueError('Nenhuma aba com cabeçalhos reconhecíveis nas primeiras 40 linhas.')
    return result

def reading_month(v):
    if not norm(v):
        return None
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%Y-%m-%dT%H:%M:%S'):
        try:
            return datetime.strptime(str(v), fmt).strftime('%Y-%m')
        except ValueError:
            pass
    return 'inválida'

def evaluate(raw, mapping, month):
    get = lambda key: raw.get(mapping.get(key))
    printed, retained, cause = norm(get('printed')), norm(get('retained')), norm(get('cause'))
    units = {k: 0 for k in CATEGORIES}
    errors, alerts = [], []
    # Formula strings are not silently interpreted as business data.
    if any(isinstance(get(k), str) and get(k).startswith('=') for k in REQUIRED):
        errors.append('Fórmula em coluna de cálculo: exportar valores calculados da origem.')
    if retained not in ('sim', 'nao'):
        errors.append('Fatura Retida diferente de Sim/Não.')
    if printed not in ('sim', 'nao'):
        errors.append('Faturas Impressas diferente de Sim/Não.')
    if retained == 'nao':
        if cause:
            units['137'] = 1
        elif printed == 'sim':
            units['138'] = 1
        elif printed == 'nao':
            units['128'] = 1
    try:
        value = get('copies')
        copies = Decimal(str(value).strip().replace(',', '.')) if norm(value) else Decimal(0)
        if not copies.is_finite() or copies < 0 or copies != copies.to_integral_value():
            raise ValueError()
        units['impressao'] = int(copies)
    except (InvalidOperation, ValueError):
        errors.append('Quantidade de comunicados inválida: exige inteiro não negativo.')
    units['apontamento'] = int(bool(norm(get('operational'))))
    if retained == 'sim':
        alerts.append('Fatura retida: sem serviço de leitura; adicionais mantidos.')
    actual_month = reading_month(get('date'))
    if actual_month is None:
        alerts.append('Sem data: incluído no mês escolhido, conforme regra confirmada.')
    elif actual_month != month:
        errors.append('Data inválida ou fora do mês de referência selecionado.')
    if not mapping.get('date'):
        errors = [e for e in errors if not e.startswith('Data inválida')]
    if '6-releitura' in norm(raw.get('Tipo de Tarefa')):
        alerts.append('Releitura incluída pelas regras confirmadas.')
    # Rows with errors stay visible but cannot enter financial totals.
    if errors:
        units = {k: 0 for k in CATEGORIES}
    return {'units': units, 'errors': errors, 'alerts': alerts,
            'employee': str(get('employee') or 'Não informado'),
            'city': str(get('city') or 'Não informado'),
            'group': str(get('group') or 'Não informado'),
            'key': '|'.join(str(get(k) or '') for k in ('supply', 'date', 'task')) if get('supply') and get('task') else None}

def summarize(records, prices):
    quantities = Counter()
    for row in records:
        if not row.get('excluded'):
            quantities.update(row['result']['units'])
    return [{'Código': code, 'Categoria': label, 'Quantidade': quantities[k],
             'unit_cents': prices[k], 'total_cents': quantities[k] * prices[k], 'key': k}
            for k, (code, label, _) in CATEGORIES.items()]
