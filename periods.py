"""Filtros de visualização; não gravam nem recalculam registros importados."""
from calendar import monthrange
from datetime import date, datetime
import json


def parse_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        return datetime.strptime(text, '%d/%m/%Y').date()
    except ValueError:
        try:
            return datetime.fromisoformat(text).date()
        except ValueError:
            return None


def month_bounds(month):
    first = date.fromisoformat(month + '-01')
    return first, first.replace(day=monthrange(first.year, first.month)[1])


def validate_bounds(month, start, end):
    first, last = month_bounds(month)
    if start > end:
        raise ValueError('A data inicial deve ser anterior ou igual à data final.')
    if start < first or end > last:
        raise ValueError('Escolha um período dentro do mês de referência.')


def import_mappings(imports):
    return {item['id']: json.loads(item['mapping']) for item in imports}


def record_date(row, mappings):
    mapping = mappings.get(row.get('import_id'), {})
    column = mapping.get('date')
    return parse_date(row['raw'].get(column)) if column else None


def filter_period(rows, mappings, month, start, end):
    """Limites inclusivos. Pendências/excluídos ficam visíveis para conferência."""
    validate_bounds(month, start, end)
    return [row for row in rows
            if (actual := record_date(row, mappings)) is not None and start <= actual <= end]


def valid_records(rows):
    return [row for row in rows if not row.get('excluded') and not row['result']['errors']]


def visible_conflicts(groups, rows):
    # Identify duplicates over the complete month before restricting the view.
    ids = {row['id'] for row in rows}
    return [group for group in groups if ids.intersection(group)]
