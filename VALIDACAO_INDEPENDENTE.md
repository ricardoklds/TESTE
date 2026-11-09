# Validação independente pelos Excel originais

Se o cálculo terminou e a comparação foi interrompida, consulte [RETOMAR_COMPARACAO.md](RETOMAR_COMPARACAO.md). O novo modo `--somente-comparacao` reutiliza os agregados salvos sem reler Excel nem sobrescrever o cálculo original.

## O que esta ferramenta comprova

`validacao_independente.py` implementa novamente os seis critérios, relendo os originais arquivados. Não usa `core.evaluate`, os resultados JSON dos registros, as projeções SQL financeiras ou a ferramenta de auditoria para calcular quantidades. Nem R$ 596.906,23 nem 19.951 são constantes do programa ou condições de parada. O cálculo também não importa os motores financeiros do aplicativo: módulos de referência do aplicativo só são carregados **depois**, para comparação opcional.

Há três etapas explícitas:

1. Exportar as **entradas**, sem consultar resultados financeiros: arquivos/abas associados ao mês, mapeamentos de colunas, preços configurados, calendário, confirmações municipais, comprovações de execução no Brasil e exclusões lógicas. SQLite é aberto em `mode=ro`; nenhuma migração é executada.
2. Fechar a conexão, conferir o SHA-256 dos originais e reler seus valores em modo incremental. A interpretação das colunas, o recálculo, a identificação geográfica e as duplicidades são executados em um banco temporário separado. Gravar **`calculo_independente.json` antes da comparação**.
3. Opcionalmente, abrir novamente a base em somente leitura e comparar as seis quantidades. Uma mudança de revisão ou de preços entre as etapas cancela a comparação. O resultado independente já gravado não é ajustado para coincidir com nada.

O mês de referência, o calendário, os preços e as exclusões continuam sendo entradas documentadas da empresa; independência do cálculo não significa inventar outro calendário ou desconsiderar os controles do contrato. `entradas.json` e os arquivos auxiliares permitem executar a etapa de cálculo em outra pasta, sem acesso ao banco.

Os valores de referência do fechamento manual existentes na auditoria anterior são usados apenas em quadros de comparação; não são insumos de suas somas SQL. Esta nova ferramenta não importa aquela auditoria nem suas constantes. Um teste altera artificialmente as projeções financeiras de um banco temporário: o recálculo dos originais permanece igual e a divergência é apontada.

## Regras e conferências preservadas

- As três leituras usam retenção, impressão e causa nos mesmos critérios vigentes. Os adicionais de impressão e CO1 Atual também são apurados nas faturas retidas; zero numérico/textual em CO1 Atual é preenchimento, conforme a regra existente. Os códigos não geram vistorias.
- As validações gerais existentes são reproduzidas: fórmulas nas cinco colunas financeiras, Sim/Não inválido, quantidade de comunicados inválida e data inválida/fora do mês impedem os cinco serviços daquela linha. Ausência de data permanece incluída no mês escolhido. Não se tenta corrigir o dado.
- A interpretação estrita de data dos cinco serviços é preservada separadamente da interpretação de data do adicional de feriado. Por exemplo, um horário ISO com frações pode ser aceito na projeção de feriados e rejeitado no motor dos cinco serviços; a ferramenta não muda esse comportamento.
- Feriado exige data coincidente, retida Não e causa vazia, sem filtro de impressão. Nacional exige comprovação de Brasil; estadual, UF segura; municipal, município e UF seguros. A referência IBGE é verificada por hash, e a confirmação documental de ATC BOCAINA/SP é preservada somente no contexto municipal já existente. Não se inventam correspondências.
- Domingo não é cobrado automaticamente. Sobreposições de feriados não multiplicam cobranças. Fornecimento/data/execução recebe no máximo um adicional; localidades divergentes na mesma execução ficam para conferência.
- Duplicatas integrais são identificadas pelo conteúdo original completo, em ordem de importação/linha. Não se elimina automaticamente uma linha diferente apenas por compartilhar fornecimento: ela continua identificável no Excel. Exclusões lógicas são entradas de controle e permanecem documentadas. Nada é excluído/reimportado no sistema.

Se o mês estiver fechado e seu calendário atual tiver sido alterado depois, o aplicativo pode preservar cobranças congeladas. O recálculo independente usa o calendário exportado atual e **não copia as cobranças congeladas**. Eventual diferença deve ser investigada, sem correção automática ou alegação de que um lado está necessariamente errado.

## Registros sem data e atribuição a setembro

A aba “Sem data válida” identifica arquivo, aba, linha original, grupo, município, funcionário, fornecimento, execução, data original e critérios financeiros. O JSON separa todas as linhas dos originais dos fingerprints ativos únicos, e distingue data vazia, inválida/não reconhecida, fora do mês, válida e coluna não mapeada. Data fora do mês é listada em “Registros originais”, mesmo quando existe uma data válida em outro mês.

**Sem data de leitura não se comprova a ocorrência em setembro apenas pelo mês selecionado na importação.** O relatório mostra quais valores entram por essa associação documental e quais registros possuem data de leitura comprovável no mês. Não presume que os 1.606 casos sejam todos vazios, nem que uma importação em setembro prove a data de execução. Se forem necessárias provas adicionais, devem vir de documentos de origem identificáveis; datas não são preenchidas automaticamente.

`active_missing_date` é a contagem de registros ativos únicos sem data interpretável para a projeção. `active_date_classes` explica as situações; `missing_date_attribution.quantities_in_monthly_by_import_provenance` informa suas contribuições ao acumulado. O campo `confirmed_by_reading_date: 0` refere-se exclusivamente aos registros sem data, não às demais leituras do mês.

## Instalação mais simples e segura no Windows

Não é necessário substituir o aplicativo nem reinstalar Python. Extraia o ZIP da ferramenta na pasta do sistema: ele cria a subpasta **`validacao_independente`**, mantendo os arquivos de suporte juntos e separados do código instalado. Preserve `data`, `.venv`, originais e backups. Feche o Streamlit durante a execução, para evitar alterações concorrentes. Faça seu backup habitual com o aplicativo fechado; a ferramenta não modifica o banco.

No terminal aberto na pasta do sistema, execute:

```powershell
.\.venv\Scripts\python.exe .\validacao_independente\validacao_independente.py --data .\data --month 2026-09 --output .\validacao-setembro-2026
```

Se usar a versão completa do repositório e o script estiver diretamente na pasta do aplicativo:

```powershell
.\.venv\Scripts\python.exe validacao_independente.py --data data --month 2026-09 --output validacao-setembro-2026
```

Informe o caminho correto em `--data` se a instalação usa `APP_DATA_DIR` personalizado. A pasta de saída deve ser **nova e fora de `data`**; para repetir, escolha outro nome. Todos os arquivos arquivados referenciados devem existir em `data\originais`. Original ausente, hash divergente, cabeçalho incompatível ou mês ausente cancela a validação. Uma pasta parcialmente gerada não representa uma execução concluída.

O pacote isolado inclui cópias dos módulos necessários apenas para a comparação posterior. Não sobrescreve os módulos da instalação. O único pacote externo necessário é `openpyxl`, já presente no ambiente do aplicativo.

## Como ler os resultados

- **`calculo_independente.json`**: as seis quantidades e o total, gravados antes de consultar resultados financeiros do aplicativo.
- **`validacao.xlsx`**: resumo dos seis serviços com quantidades, preços, valores e diferenças; registros originais e suas unidades; registros sem data; conferência de feriados cobrados e não cobrados; motivos; divergências com identificação das linhas; entradas e proveniência.
- **`resultado.json` e `RELATORIO.md`**: resultado final, conferências de retidas/causas/impressões/apontamentos, motivos de feriados, limites e comparação posterior. Diferença de quantidade por serviço e valor fica no resumo. Nas divergências individuais, confira os campos originais, erros independentes e motivo do feriado; quando a evidência não provar a causa de uma projeção diferente, a ferramenta não inventa uma justificativa histórica.
- **`entradas.json`, `exclusoes.jsonl` e referências municipais**: insumos da execução, sem quantidades anteriores. O manifesto registra hashes e referências aos Excel; não duplica nem modifica as planilhas.

Se `comparison.delta_cents` for zero, isso significa igualdade dos valores somados, mas confira também todas as `delta_quantities`, `different_records`, `app_details_match_aggregates` e `detail_delta_matches_totals`. Um total igual pode ocultar diferenças compensatórias entre registros. O relatório não presume coincidência com os valores informados pelo usuário.

Para comparar também o JSON da auditoria anterior, acrescente o parâmetro abaixo ao comando. O arquivo será lido somente após gravar o cálculo independente:

```powershell
--auditoria-anterior .\auditoria-setembro-2026\resultado.json
```

O resultado fica em `previous_audit_comparison`. Essa comparação é agregada: o JSON anterior não possui todas as linhas originais. A identificação individual é feita entre originais e banco atual; um histórico diferente exige seus relatórios correspondentes.

## Execução sem consultar resultados ou sem banco

Acrescente `--sem-comparacao` ao comando com `--data` para exportar somente as entradas e calcular, sem ler resultados financeiros do banco em nenhuma etapa. Para repetir usando o manifesto exportado, sem abrir o banco:

```powershell
.\.venv\Scripts\python.exe .\validacao_independente\validacao_independente.py --manifest .\validacao-setembro-2026\entradas.json --output .\repeticao-independente-setembro
```

Mantenha junto ao manifesto `exclusoes.jsonl`, `municipalities.json` e `municipal_confirmations.json`. Os Excel precisam continuar disponíveis no caminho registrado em `originals`; se forem copiados para outro computador, ajuste esse caminho explicitamente e registre a nova versão do manifesto. Não há um total-alvo a informar.

## Resultados neste ambiente e limites

Não estão disponíveis aqui os 20 grupos de setembro, os 1.606 casos ou seu calendário local. Portanto, **ainda não foi validado independentemente R$ 596.906,23 nem a quantidade de 19.951 adicionais**. Esses resultados só poderão ser confirmados após executar a ferramenta na base e nos originais reais.

No original de outubro disponível, 19.668 linhas foram recalculadas, resultando em 15.942 leituras de R$ 1,38, 3.379 de R$ 1,28, 142 de R$ 1,37, 5.346 comunicados e 2.523 apontamentos: **R$ 30.454,12**. O calendário desta instalação não contém adicional aplicável a essas linhas; o resultado de feriado foi zero. A comparação posterior com o aplicativo apresentou zero diferença por serviço e por registro. As 46 datas vazias foram identificadas sem preencher nenhuma data.

Os testes usam bancos e originais sintéticos separados: combinatória dos cinco critérios e validações, três abrangências de feriado, Bocaina, domingos, duplicatas, localidades ambíguas/divergentes, comprovação de Brasil, exclusão/restauração, calendário congelado, integridade de arquivos, banco artificialmente divergente e recálculo sem banco/motor do aplicativo. Evidências da suíte e da execução real disponível ficam em `measurements/validacao-independente`.

O processamento usa leitura incremental de XLSX, hashes por blocos, índices em SQLite temporário e exportação incremental com divisão automática no limite do Excel. Não carrega todo o banco ou todos os Excel na RAM. Reserve espaço temporário para os detalhes e espaço de saída para o Excel, que pode ser grande. Não foram realizados novos benchmarks de milhões de linhas nesta entrega.

Nada neste procedimento modifica preços, calendário, regras, dados, backups ou a interface do aplicativo. Não há migração nem módulo de vistorias.
