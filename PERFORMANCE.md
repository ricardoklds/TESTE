# Medições de desempenho

Ambiente: Linux, Python 3.12.14. Tempos em segundos. Streamlit AppTest mede processamento no servidor, não a renderização completa no navegador ou a rede. São observações desta máquina, não garantias no Windows.

## Base real fornecida: 19.668 registros

| Operação | Antes | Depois |
|---|---:|---:|
| initial_screen | 2.3878 | 0.5565 |
| Importar planilhas | 2.2575 | 0.0443 |
| Fechamento mensal | 1.8545 | 0.0626 |
| Produtividade | 1.1832 | 0.0564 |
| Relatórios | 1.2837 | 0.0556 |

Pico de RSS do processo do benchmark: antes 1126.34 MiB; depois 188.86 MiB. O benchmark anterior incluía carga/decodificação integral e troca das telas; o posterior usa consultas agregadas. Não é uma medição isolada da memória do navegador.

O faturamento real permanece exatamente R$ 30.454,12 (3.045.412 centavos). As cinco quantidades antes/depois são 15.942, 3.379, 142, 5.346 e 2.523, respectivamente para R$ 1,38, R$ 1,28, R$ 1,37, impressão e apontamento. Os 46 registros sem data continuam no acumulado; 19.622 datados somam R$ 30.410,24.

## Carga ARTIFICIAL temporária: 400.000 linhas

Modelos derivados da base fornecida, com identificadores artificiais únicos apenas para o teste. Todas as linhas e projeções ficam em um banco temporário, descartado ao terminar. Isso não são os 174 mil registros do computador do usuário e não representa faturamento da empresa. Não houve medição financeira real de 400 mil serviços.

| Operação | Tempo |
|---|---:|
| monthly_sql_cold | 0.2454 |
| monthly_cache_hit | 0.0002 |
| record_page_100 | 0.0394 |
| record_last_page_100 | 0.1311 |
| ranking_employee | 0.1942 |
| ranking_city | 0.1852 |
| ranking_group | 0.1827 |
| initial_screen | 0.7590 |
| Importar planilhas | 0.1541 |
| Fechamento mensal | 0.1064 |
| Produtividade | 0.3343 |
| Relatórios | 0.0400 |
| day_filter_ui | 0.3618 |
| summary_excel | 0.0124 |
| summary_pdf | 0.0291 |

Construção da fixture: 16.092 s. Pico RSS: 261.17 MiB (inclui construção da fixture).

## XLSX real: prévia, importação e exportação completa

| Operação | Tempo |
|---|---:|
| legacy_full_excel_parse | 9.971 |
| small_excel_preview | 0.037 |
| streamed_excel_import | 14.278 |
| complete_excel_background_worker | 11.753 |

A prévia de 15 linhas é uma operação menor que a leitura integral: os tempos não comprovam que todo o processo de importação ficou mais rápido na mesma proporção. A importação lê todas as linhas uma vez em fluxo e grava lotes; a diferença principal é memória limitada e ausência de leitura integral durante a prévia/navegação. Os tempos de importação/exportação completa foram coletados enquanto a suíte também executava, podendo incluir contenção.

O Excel completo conserva todas as colunas e é gerado em segundo plano com snapshot consistente e escrita incremental. Foi medido na base real de 19.668 linhas; **não foi medido o tempo do Excel completo com 400.000 linhas**. Esse relatório pode levar minutos e precisa de espaço/memória para o download. Somente os relatórios agregados foram medidos na carga de 400 mil.

## Gargalos identificados e mudanças

- Antes: leitura/decodificação integral a cada interação (0,4915 s para 19.668 linhas); conferência de uma importação carregava e serializava todos os JSONs (0,9389 s); filtros Python, gráficos e tabelas completas, mesmo em expansores recolhidos; leitura automática dos originais para download.
- Agora: projeção SQL dos resultados existentes, índices por mês/data/importação/chave operacional, soma/agrupamento em SQL, cache limitado por revisão transacional, paginação de 100–500 linhas, seleção de IDs antes de buscar JSONs, inspeção por chave primária, prévia XLSX pequena e downloads sob demanda.
- A última página da carga de 400 mil inicialmente levou 3,1644 s. A consulta foi alterada para paginar IDs antes dos joins de payload; a nova medição foi 0,1311 s.
- Relatórios agregados não leem todos os registros; o relatório completo faz uma única leitura sequencial de snapshot fora do fluxo de navegação.

## Reproduzir

Use o Python da .venv: `python benchmark.py --output benchmark-local.json`. Para fixture isolada, `python benchmark.py --load 400000 --output benchmark-400000.json`. A opção de carga exige a base modelo de outubro/2026 e espaço livre. O benchmark de consulta aceita o mês de outubro/2026, que foi o mês usado nas medições. Consulte README para atualizar o código sem reinstalar Python.

Testes: `python -m unittest discover -s tests -v`. As integrações dependem da base original fornecida; fixtures financeiras nunca são adicionadas à base de produção. Há testes de igualdade por categoria/período, produtividade, paginação, revisão do cache, restauração, rollback após lote parcial, exportação completa e navegação sem leitura integral.
