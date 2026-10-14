# Desempenho em grandes volumes — Gestão de Medição Sabesp

Resultados medidos em 14/10/2026. **Todos os dados de carga são sintéticos** e não
representam medições ou faturamento da empresa. Nenhuma estimativa de desempenho
é apresentada como medição. As setas das tabelas significam **anterior → otimizada**;
os tempos são segundos. Evidências completas em [measurements/scale](measurements/scale).

## Método e limites da comparação

- Referência anterior: commit `64119564f51fd58e8ce510f38a7e7c46df3a97d4`.
- Uma execução por tamanho/versão, em processos novos e sequenciais, com os mesmos
  bytes de entrada. Não são médias, percentis, testes de concorrência ou garantias
  de tempo para outro computador. Pequenas diferenças podem ser ruído da máquina.
- Importação real de XLSX: inspeção, leitura incremental, regras, fingerprint,
  arquivamento, índices, projeções e commit. Não foi usado INSERT artificial para
  simular o tempo de importar Excel. A criação dos arquivos sintéticos fica fora
  desse tempo. O perfil instrumentado é uma execução adicional e não entra nas tabelas.
- Arquivos de 20.000 linhas, 72 colunas (até 23 preenchidas e 49 vazias), textos
  sintéticos curtos; arquivos com textos extensos, fórmulas, sharedStrings ou muitas
  colunas preenchidas podem consumir mais tempo e RAM. Não é uma reprodução de
  todos os formatos de relatórios da Sabesp.
- Os dados cobrem 50 dias corridos, incluindo domingos propositais. Há feriados
  nacionais, estaduais e municipais, localidades reconhecidas, ambíguas e desconhecidas.
- 20 mil, 100 mil e 500 mil estão em setembro. Um milhão está dividido em setembro
  (600 mil) e outubro (400 mil). As consultas, filtros, navegação e exportação deste
  último cenário medem outubro, com 400 mil; a apuração financeira verifica ambos
  os meses. **Não foi medida exportação de um milhão de linhas em um único mês.**
- RAM: maior RSS do processo amostrada a cada 20 ms, em MiB. Não inclui cache de
  arquivos do sistema, navegador ou outros processos; pode não captar picos muito
  curtos. Não é memória virtual nem tamanho do banco.
- Navegação: Streamlit AppTest, execução dos scripts sem navegador/rede, depois da
  consulta inicial do mês. Inclui primeira entrada nas páginas com caches por revisão;
  não mede primeira instalação, tempo de abrir o Python ou renderização do navegador.
- Excel resumido/PDF medem serialização usando agregações já obtidas. O tempo de
  apuração e de produtividade é apresentado separadamente. Excel completo inclui
  snapshot SQLite, dados originais, conferência, gravação e compressão do mês.

Ambiente: Linux-6.18.44-x86_64-with-glibc2.41; Python 3.12.14; SQLite 3.53.1; AMD EPYC 9V74 80-Core Processor, limite de 4 CPUs e 32 GiB do ambiente. Dependências: streamlit 1.50.0, pandas 2.3.3, openpyxl 3.1.5, reportlab 4.4.4.

## Importação e geração de relatórios

| Registros armazenados | Linhas no mês do relatório | Importação Excel | Excel resumido | PDF | Excel completo |
| --- | --- | --- | --- | --- | --- |
| 20.000 | 20.000 | 8.551 → 7.849 | 0.013 → 0.011 | 0.039 → 0.041 | 8.384 → 5.188 |
| 100.000 | 100.000 | 44.264 → 38.336 | 0.013 → 0.011 | 0.040 → 0.044 | 42.430 → 28.089 |
| 500.000 | 500.000 | 223.361 → 200.507 | 0.015 → 0.013 | 0.039 → 0.040 | 214.561 → 143.160 |
| 1.000.000 | 400.000 | 443.296 → 402.914 | 0.015 → 0.013 | 0.040 → 0.040 | 170.409 → 113.337 |

## Consultas, filtros e cálculos

As consultas abaixo incluem abertura da conexão e agregação SQL, sem reutilizar o resultado mensal em cache no teste SQL. O banco pode estar no cache de disco do sistema operacional. O cálculo de todos os meses inclui as seis categorias.

| Armazenados | SQL mensal sem cache de resultado | Filtro por dia | Intervalo 1–15 | Produtividade (3 agrupamentos) | Apuração de todos os meses |
| --- | --- | --- | --- | --- | --- |
| 20.000 | 0.035 → 0.038 | 0.040 → 0.043 | 0.040 → 0.042 | 0.055 → 0.057 | 0.037 → 0.039 |
| 100.000 | 0.176 → 0.181 | 0.055 → 0.058 | 0.212 → 0.220 | 0.293 → 0.304 | 0.184 → 0.174 |
| 500.000 | 1.178 → 1.143 | 0.108 → 0.101 | 0.888 → 0.904 | 1.760 → 1.822 | 1.166 → 1.167 |
| 1.000.000 | 0.820 → 0.822 | 0.089 → 0.092 | 0.723 → 0.731 | 1.282 → 1.459 | 2.222 → 2.315 |

## Navegação pelas telas

| Tela | 20.000 registros | 100.000 registros | 500.000 registros | 1.000.000 registros |
| --- | --- | --- | --- | --- |
| Painel inicial | 0.055 → 0.057 | 0.056 → 0.057 | 0.067 → 0.057 | 0.056 → 0.056 |
| Importar planilhas | 0.085 → 0.107 | 0.789 → 0.326 | 27.617 → 1.881 | 14.644 → 1.276 |
| Fechamento mensal | 0.101 → 0.101 | 0.263 → 0.277 | 1.532 → 1.513 | 1.147 → 1.096 |
| Produtividade | 0.079 → 0.079 | 0.160 → 0.174 | 0.681 → 0.726 | 0.563 → 0.522 |
| Relatórios | 0.078 → 0.050 | 0.054 → 0.051 | 0.052 → 0.051 | 0.054 → 0.050 |

## Memória e integridade operacional

| Armazenados | RAM importação (MiB) | RAM Excel completo (MiB) | RAM navegação (MiB) | Excluir 20 mil + recalcular (s) | Restaurar 20 mil + recalcular (s) |
| --- | --- | --- | --- | --- | --- |
| 20.000 | 72.0 → 72.7 | 74.7 → 75.1 | 201.7 → 202.8 | 0.181 → 0.171 | 0.207 → 0.206 |
| 100.000 | 73.5 → 73.9 | 75.9 → 76.3 | 201.9 → 202.8 | 0.442 → 0.459 | 0.472 → 0.538 |
| 500.000 | 75.6 → 76.0 | 97.3 → 97.5 | 205.8 → 206.5 | 3.934 → 2.444 | 2.357 → 2.246 |
| 1.000.000 | 74.7 → 76.5 | 85.5 → 86.4 | 201.0 → 205.8 | 2.492 → 1.719 | 1.655 → 1.653 |

A conferência percorreu os registros em streaming e executou novamente o motor
original das cinco regras, comparando as quantidades agregadas salvas. O adicional
sintético foi conferido por uma implementação de referência específica das datas,
localidades e condições dessas fixtures. Todas as quantidades e todos os centavos
antes/depois coincidiram; após restaurar, o resultado completo voltou ao estado
anterior à exclusão. `integrity_check` retornou `ok` em cada banco de carga.

**47 testes passaram**, sem falhas ou testes ignorados nessa execução. A suíte automatizada também cobre feriados nacionais/estaduais/municipais, domingos,
localidades ambíguas, duplicidades, reimportação, exclusão/restauração, fechamento,
filtros, preços, cache, rollback e backup/recuperação em banco temporário. A saída
integral está em `measurements/scale/regression-tests.txt`. Os hashes do banco,
originais e backups de produção foram comparados antes/depois; permaneceram iguais.

## Gargalos e mudanças implementadas

1. **Listagem de importações:** havia um cálculo de impacto completo por arquivo a
   cada entrada na tela. Agora uma agregação retorna os faturamentos de todos os
   arquivos; o impacto hipotético e sua versão para confirmação só são calculados
   ao solicitar excluir/restaurar. Essa confirmação e a transação permanecem intactas.
2. **Interpretação repetida:** o trigger dos feriados chama a mesma função quatro
   vezes por registro. Um cache puro e limitado a 32 entradas reutiliza a interpretação
   do mesmo raw/mapeamento; não armazena decisões financeiras ou de calendário.
3. **Consultas:** indicadores e unidades passam a usar uma única agregação dos
   resultados salvos. Índices existentes por mês/data, importação e chave de negócio
   foram mantidos. `EXPLAIN QUERY PLAN` confirmou o uso de `metrics_month_day` nos
   filtros; não foi preciso adicionar índice ou migrar a estrutura.
4. **Exportação:** a escrita incremental evita objetos de célula para números e
   posições vazias. Textos continuam literais, inclusive se começam com `=`, e
   posições vazias/cabeçalhos são preservados. O detalhado permanece em segundo plano.
5. **Progresso:** a importação informa contagens reais por lote de mil linhas, sem
   presumir uma quantidade a partir de dimensões incorretas do XLSX. Os lotes fazem
   parte de uma transação única; uma falha cancela a importação inteira. A mensagem
   de conclusão só é mostrada depois do commit.
6. **Cache e memória:** a nova listagem usa o cache por caminho/revisão/mês/preços;
   importações, exclusões, restaurações e configurações invalidam pela revisão já
   transacional. Foram preservados consultas agregadas, páginas de até 500 registros,
   leitura incremental e gráficos/rankings agregados. Não se reabrem planilhas na navegação.

Nenhuma das seis condições de faturamento, preço ou regra territorial foi modificada.
Nenhuma vistoria foi adicionada. Não há nova migração; banco permanece na versão 5.

## Perfil instrumentado da importação

Em execução adicional de 20 mil linhas com `cProfile`, a função de interpretação
`identity` foi efetivamente executada **80.000 → 20.000 vezes**, com tempo acumulado
instrumentado **2,886 → 0,802 s**. A leitura incremental `iter_records` permaneceu
em aproximadamente **11,565 → 11,713 s** sob instrumentação: o parser de XML/Excel
continua sendo um custo importante. Tempos de funções são cumulativos, se sobrepõem
e não devem ser somados. Não são os tempos sem instrumentação da tabela acima.
A thread de amostragem de RAM foi desativada só durante essa importação instrumentada,
para não confundir o custo do medidor com o custo do aplicativo. A RAM desses dois
arquivos de perfil não é usada nas comparações; os oito ensaios normais mantêm a
amostragem a cada 20 ms.

Os resultados não indicam redução significativa da RAM nem ganho consistente nas
consultas SQL e filtros. O ganho mais relevante é a eliminação dos cálculos de
impacto por arquivo na navegação; a exportação detalhada também melhorou, mas continua
custosa em centenas de milhares de linhas. Nenhuma dessas diferenças é uma garantia
para outro computador ou uma estimativa para décadas de dados.

## Uso por vários anos

O banco sintético com um milhão ficou em **4.26 GiB**, antes de contar originais, backups e exportações. Esse tamanho foi medido; não é previsão para outras planilhas.

O ensaio demonstra operação com um milhão armazenado e um mês consultado de 400 mil,
mas não comprova desempenho com dezenas de milhões ou vários usuários concorrentes.
Os índices por mês evitam trazer todo o histórico para a memória das telas. Ainda assim:

- SQLite tem um escritor por vez. Importações são atômicas e podem disputar escrita;
  não foi executado teste de múltiplos importadores concorrentes.
- O detalhado faz snapshot do **banco inteiro** antes de exportar o mês. À medida que
  o histórico cresce, a cópia exige mais disco e tempo, embora a exportação seja em
  streaming. XML temporário, snapshot e arquivo final também ocupam disco. Programe
  detalhados e backups fora dos horários de importação e monitore espaço livre.
- Relatórios detalhados de centenas de milhares de linhas continuam demorados;
  as tabelas não prometem geração completa em poucos segundos. Resumidos são a
  opção para consulta diária; detalhados ficam em segundo plano.
- Excel permite 1.048.576 linhas por aba. Este exportador não divide automaticamente
  um mês que ultrapasse esse limite. O upload do aplicativo continua limitado a 200 MB
  por arquivo; importar arquivos diários evita consolidar anos em um único XLSX.
- O teste não mediu 10/50 milhões de registros, recuperação de bancos desse tamanho,
  SSD/HD do usuário ou RAM do navegador. Antes de chegar a esses volumes, repita os
  ensaios com meses antigos, planilhas representativas e concorrência real. Para muitos
  usuários/escritas simultâneas, planeje avaliar PostgreSQL e fila de importação,
  preservando os motores e a trilha de auditoria; isso não foi implementado aqui.

Não é necessário trocar o banco agora só por atingir um milhão, mas a capacidade de
vários anos deve ser validada no equipamento e no volume reais. Reserve espaço para
os originais e para mais de uma cópia consistente do banco, mantenha backups externos
rotativos e ensaie a recuperação. Veja [BACKUP_RECOVERY.md](BACKUP_RECOVERY.md).

## Reproduzir os ensaios (Linux)

`performance_suite.py` exige Linux para amostrar `/proc/self/status`. Não usa a
pasta de produção: cria SQLite e arquivos originais em diretório temporário novo,
removido ao final. Reserve espaço para banco, snapshot, XML temporário e XLSX final.
Os resultados ficam no caminho informado em `--output`.

```bash
.venv/bin/python performance_suite.py --generate --fixtures /tmp/sabesp-fixtures
.venv/bin/python performance_suite.py --fixtures /tmp/sabesp-fixtures --rows 20000 --output /tmp/resultado-20000.json
.venv/bin/python performance_suite.py --fixtures /tmp/sabesp-fixtures --rows 100000 --output /tmp/resultado-100000.json
.venv/bin/python performance_suite.py --fixtures /tmp/sabesp-fixtures --rows 500000 --output /tmp/resultado-500000.json
.venv/bin/python performance_suite.py --fixtures /tmp/sabesp-fixtures --rows 1000000 --output /tmp/resultado-1000000.json
```

Para a referência anterior, extraia o commit indicado em outra pasta e use
`--code /caminho/do/codigo-anterior`. Use o mesmo Python, dependências, arquivos e
sequência, sem carga concorrente. `--profile` captura funções da importação e altera
os tempos; seus resultados estão separados como `profile-*-20000.json`.

## Atualizar no Windows sem reinstalar Python

1. Pare o Streamlit e siga [BACKUP_RECOVERY.md](BACKUP_RECOVERY.md): copie o programa
   anterior e a pasta `data` inteira para fora da instalação, com aplicativo fechado.
2. Extraia a entrega em uma pasta temporária e copie os módulos Python, `tests/`,
   `reference_data/` e documentação para a instalação. Não substitua `data/`, `.venv/`,
   originais ou backups. Não reimporte planilhas. Dependências permanecem iguais.
3. No PowerShell da pasta instalada:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_optimization.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_holidays.py -v
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

Abra `http://localhost:8501` e confira um mês conhecido. O menu lateral mantém as
seis telas. Não foi publicado servidor na internet. As medições acima foram feitas
no Linux do ambiente de testes, não na instalação Windows do usuário.
