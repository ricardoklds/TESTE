# Classificação municipal de ATC BOCAINA

A referência versionada contém **Bocaina/PI (2201804)** e **Bocaina/SP (3506805)**.
O nome isolado era corretamente tratado como homônimo. Em 14/10/2026, o usuário
confirmou expressamente que a origem contratual **ATC BOCAINA é Bocaina/SP**.
A confirmação está em `reference_data/municipal_confirmations.json`, com o código
e a UF validados contra o cadastro distribuído. Não se criou uma correspondência
por aproximação; o nome Bocaina sem esse contexto continua ambíguo, e Bocaina/PI
com UF explícita continua sendo PI. A procedência do cadastro está em
[reference_data/PROVENANCE.md](reference_data/PROVENANCE.md).

Essa confirmação é aplicada por consulta SQL, sem escrever no banco, apenas no
contexto municipal em datas sem feriado nacional/estadual concomitante. Identificações
manuais existentes têm prioridade. Datas com outras abrangências mantêm a resolução
e o comportamento anteriores; a atualização não transforma essa confirmação
municipal em uma nova autorização de cobrança estadual ou nacional.

## Resultado da classificação

Um feriado municipal exige **mesma data + mesmo município + mesma UF**.
Quando município ou UF seguros impossibilitam correspondência com todos os feriados
municipais daquela data, o motivo agora é **Não aplicável — outro município**:
não cobra adicional e não incrementa pendências. Se a localização ainda puder
corresponder ao feriado, a pendência permanece. Não se supõe que toda origem ATC é SP.

Para a confirmação de Bocaina/SP e o calendário informado:

| Data | Município do feriado | Leitura de Bocaina/SP |
| --- | --- | --- |
| 08/09/2026 | Anhembi/SP | Não aplicável — outro município |
| 09/09/2026 | Bofete/SP | Não aplicável — outro município |
| 14/09/2026 | Cesário Lange/SP | Não aplicável — outro município |
| 15/09/2026 | Ibiúna/SP | Não aplicável — outro município |

Os registros ficam disponíveis em **Situação → Não cobrados** e **Todos**, com
município/UF e comprovação da correspondência. O resumo e o Excel de **Pendências**
deixam de incluir esses registros. Paginação, filtros de período, grupo e funcionário
continuam funcionando. Nenhuma leitura, importação ou histórico é excluído.

Em meses fechados, uma projeção somente leitura pode reclassificar essas pendências
municipais quando o calendário comprova outro município. O snapshot gravado e os
IDs/valores financeiros congelados permanecem intactos. Não reabra um mês só para
mostrar essa correção. A consulta usa o calendário atualmente cadastrado; se ele
for diferente do calendário informado, confira as datas/abrangências antes de concluir
que todas as 834 linhas devem mudar de situação.

Não há migração. As cinco regras originais, preços e critérios de elegibilidade do
adicional permanecem iguais. Cache de consultas foi atualizado pela revisão do código,
sem incrementar a revisão ou alterar dados no banco. Reinicie o aplicativo ao atualizar.

## Testes antes/depois

O ambiente possui apenas outubro/2026 e 365 registros de ATC BOCAINA nesse mês.
**A base real de setembro com 834 registros não está disponível.** Não se afirma
que o fechamento local de 19.951 adicionais já foi reproduzido aqui.

Foi criada uma fixture isolada com **834 linhas sintéticas de Bocaina** distribuídas
nas quatro datas, mais quatro leituras corretamente elegíveis dos municípios do
calendário. O cenário anterior foi reproduzido sem a nova confirmação contratual.

| Indicador na fixture sintética | Antes | Depois |
| --- | ---: | ---: |
| Pendências de Bocaina | 834 | 0 |
| Bocaina com adicional cobrado | 0 | 0 |
| Cobranças corretas de controle | 4 | 4 |
| Leituras da categoria R$ 1,38 | 838 | 838 |
| Total das seis categorias (centavos) | 116064 | 116064 |

Os testes também cobrem meses fechados sem alterar o arquivo SQLite, UF diferente,
localidades realmente ambíguas, correspondência exata de data/município/UF, feriados
nacionais/estaduais e sobrepostos, exclusão/restauração, paginação e exportação.
**60 testes passaram**. A suíte completa e evidências ficam em `measurements/bocaina/`.

O ensaio SQL com um milhão de registros sintéticos continuou retornando apenas 100
linhas por página. Primeira consulta da interface: **3,721 s**; seleção de Pendências
com contagens em cache: **1,769 s**; mesma página em cache: **0,000353 s**. Os totais
financeiros e `integrity_check` permaneceram corretos. É uma execução Linux, sem
navegador ou medição de importação; não é garantia para outro computador.
Os hashes do banco, originais e backups de produção permaneceram idênticos.

## Atualizar e validar no Windows

1. Pare o Streamlit. Copie o programa e toda a pasta `data` para um backup externo,
   com o aplicativo fechado, conforme [BACKUP_RECOVERY.md](BACKUP_RECOVERY.md).
2. Copie todos os arquivos atualizados do programa, incluindo **municipal_review.py**,
   **validar_bocaina_local.py**, `reference_data/municipal_confirmations.json`, os módulos
   atualizados e `tests/`. **Preserve `data`, `.venv`, originais e backups.**
3. Não reinstale Python ou dependências. No PowerShell da instalação:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_bocaina.py -v
.\.venv\Scripts\python.exe validar_bocaina_local.py --data data --month 2026-09 --output conferencia-bocaina.json
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

Se `APP_DATA_DIR` apontar para outro local, passe esse caminho em `--data`. O relatório
de validação deve ficar **fora de `data`**. O verificador abre o SQLite com `mode=ro`,
não migra, não confirma municípios, não reimporta e não atualiza snapshots.
Ele cria um arquivo JSON novo; se o nome já existir, escolha outro, sem sobrescrever
o relatório anterior. Retorna código 2 se encontrar alteração dos IDs cobrados.

Confira `financial_unchanged: true`, `charged_ids_changed: 0`, os totais antes/depois
e `bocaina_by_day_status`. Na base descrita pelo usuário, os 834 registros das quatro
datas devem aparecer sem cobrança e com motivo de outro município; confirme também
que as cobranças corretas continuam 19.951, se nenhum outro dado/calendário mudou.
Se setembro não existir na base selecionada, o verificador informa `available: false`
e não declara o teste realizado. O cenário “antes” é a consulta sem a confirmação
contratual nova, usando os mesmos dados e calendário atuais.

No navegador, selecione setembro, mês completo e filtros de localidade/grupo/funcionário
em Todos. Em **Fechamento mensal**, confira os indicadores e **Situação → Não cobrados**.
Não exclua nem reimporte leituras para aplicar essa correção.
