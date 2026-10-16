# Simplificação sem exigências documentais

Esta atualização remove os campos de documento, justificativa, responsável e evidência das interfaces e elimina a dependência desses textos nas funções internas. Não altera preços, classificações, quantidades ou regras comerciais. Não migra o banco nem modifica os registros existentes ao instalar.

## Fluxo de uso

- **Serviços, preços, TSS, critérios por OS e municípios:** selecionar/editar, calcular impacto e confirmar em um único botão. A prévia financeira e as verificações de vigência continuam obrigatórias; não há documento ou checkbox adicional de confirmação.
- **Vistorias:** aprovar com um botão após a conferência dos indicadores. A aprovação continua bloqueada se houver inconsistências, pendências, projeção desatualizada ou Geolocalização não confirmada. Não é necessário gerar ou baixar um arquivo de conciliação para habilitar a aprovação; a geração dos relatórios continua disponível.
- **Conferência individual de OS:** escolher a decisão e salvar, sem justificativa textual. Permanecem as validações de competência e código contratual.
- **Leituras:** exclusão/restauração de importação continua mostrando arquivo, mês, registros e impacto, seguida do botão Confirmar operação. Justificativa e checkbox foram retirados. Decisões individuais e reabertura também não pedem texto. Importação e fechamento usam seus próprios botões; integridade, chaves repetidas, erros e bloqueios continuam validados pelo servidor.
- **Feriados e localidades:** UF/município e correspondências continuam sujeitos às regras existentes. A confirmação de execução no Brasil é uma ação factual explícita, sem descrição documental. Só ocorre ao clicar no botão; não atribui país, UF ou município automaticamente a registros desconhecidos. Não altera as regras de feriados nacionais, estaduais, municipais ou domingos.
- **Fechamento Geral:** validar em um botão, com os mesmos requisitos de consistência dos componentes. Composição, subtotais, prévias PDF/Excel e simulação gerencial de 1% permanecem.

Checkboxes que representam opções funcionais, como incluir detalhes em relatórios ou aplicar filtros, continuam disponíveis. O que foi removido são exigências documentais e confirmações redundantes.

## Glosa

O controle **Aplicar multa de 1%** continua sendo apenas uma simulação em memória. Não grava desconto nem altera o fechamento oficial. Foram removidos os formulários de aplicação/registro de multa nas interfaces; os registros históricos anteriores continuam disponíveis somente para consulta.

As funções legadas de registro foram mantidas para compatibilidade, com suas condições e confirmação explícita anteriores, mas não são chamadas pelo controle de simulação nem disponibilizadas como ação de aplicação definitiva nas telas. A atualização não apaga nenhuma glosa anterior.

## Compatibilidade e histórico

As colunas antigas de evidência/justificativa permanecem no banco. Para novas operações sem texto, o aplicativo grava uma descrição interna neutra, como **Operação manual no aplicativo**. Isso não representa documento, assinatura ou comprovação inventada. Textos históricos existentes não são apagados ou reescritos. Chamadas legadas com evidência/justificativa ainda são aceitas; parâmetros omitidos, vazios ou None não bloqueiam a operação.

Cada gravação continua registrando a ação, data/hora e detalhes já disponíveis no histórico. Foram preservados: transações, rollback, validação da prévia por revisão/assinatura, verificação de alterações concorrentes, duplicidades e bloqueios de competências aprovadas. Um erro de consistência continua impedindo a operação; ausência de justificativa não é mais um erro.

Menu expansível, seis serviços de Leituras, feriados, importadores, produtividade, meta de 99%, municípios fora do contrato, cobrança única por OS, Geolocalização simplificada e tabela editável mantêm seus cálculos. Nenhum preço é redefinido para um valor inicial durante a atualização.

## Validação

**161 testes aprovados em 45,877s.** Incluem oito testes novos para ausência de campos documentais, cálculo e confirmação de impacto sem texto, métodos legados com valores vazios/None, aprovação por botão, histórico preservado, reabertura/exclusão/restauração, confirmação factual de país sem inventar município/UF e glosa somente simulada na interface. Os testes anteriores de preços, classificações, escopo, OS, períodos, feriados, relatórios e desempenho continuam passando.

Comparação com a revisão anterior `d4f91e1`, em bancos temporários separados com **500.000 Leituras e 100.000 Vistorias sintéticas**: diferença **R$0,00** em Leituras, Vistorias, Geolocalização e bruto; seis quantidades de Leituras idênticas. SHA-256 do banco sintético de Leituras preservado. Simulação e exportações não modificaram os bancos. Nenhuma base de produção, Excel original, importação ou backup existente foi alterado nos testes.

| Operação | Antes | Depois |
|---|---:|---:|
| Leituras em cache, mediana de 3 | 0,0198 s | 0,0192 s |
| Primeira entrada em Vistorias | 1,888 s | 1,711 s |
| Fechamento Geral sem cache, mediana de 3 | 2,107 s | 2,163 s |
| Fechamento Geral em cache, mediana de 3 | 0,0101 s | 0,0125 s |
| Alternar simulação, mediana de 4 | 0,0102 s | 0,0211 s |
| Salvar Geolocalização | 0,0201 s | 0,0091 s |

As pequenas variações não indicam regressão relevante nesta medição; não há garantia de tempo universal em outro computador. AppTest mede servidor, não navegador/rede ou importação Excel nesse volume. Não foi refeita uma auditoria real dos 20 Excel de setembro nesta etapa. Logs e medições estão em `measurements/no-documents`.

O benchmark reutiliza o script existente: no Linux, em checkout Git com a referência disponível, execute `python -c "import benchmark_price_reports as b; b.BASELINE='d4f91e1'; b.run('pasta-nova')"`. Os testes completos podem ser executados com `python -m unittest discover -s tests -v`, usando as dependências de desenvolvimento já descritas em `requirements-dev.txt` para validar o texto dos PDFs.

## Atualizar no Windows

1. Pare o aplicativo com Ctrl+C.
2. Faça cópia completa de `data` e do código instalado para backup externo. Preserve todos os backups anteriores.
3. Extraia o ZIP consolidado em uma pasta temporária e atualize o código, preservando **`data`, `.venv`, `.streamlit` e backups**. Inclua o novo arquivo `audit_text.py`. Não exclua arquivos e não reimporte Excel.
4. Se utiliza Git, atualize a branch `codex/sistema-fechamento-pr` com `git fetch origin` e `git pull --ff-only`, sem descartar alterações locais.
5. Inicie normalmente:

```bat
.venv\Scripts\python.exe -m streamlit run app.py
```

Não precisa reinstalar Python ou dependências para usar o aplicativo. Não há migração nova nesta etapa. Quem ainda usa uma versão anterior à consolidação financeira v2 mantém o procedimento anterior de backup/migração; não é necessário instalar versões intermediárias.

Para recuperação, pare o aplicativo e volte ao código e à cópia completa de `data` guardados juntos, preservando a instalação atual separadamente. Não misture um banco antigo com importações posteriores.

Arquivos de aplicação alterados: `inspection_billing.py`, `inspection_module_ui.py`, `inspection_settings_ui.py`, `contract_finance.py`, `contract_ui.py`, `inspections.py`, `inspections_ui.py`, `storage.py`, `readings_ui.py` e `localities.py`. Novo auxiliar: `audit_text.py`. Também foram adaptados os testes dos formulários e acrescentados `tests/test_no_documents.py`, esta documentação e as medições. Menu e motores de cálculo dos seis serviços, feriados, escopo e cobrança por OS não foram reescritos.
