"""Compatibilidade de colunas históricas, sem exigir documentação do usuário."""
def audit_text(value=None):
    return str(value or '').strip() or 'Operação manual no aplicativo.'
