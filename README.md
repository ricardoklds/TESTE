# Gestão de medição e fechamento mensal

Aplicação local em português para serviços de leitura de hidrômetros. Importação de Excel, fechamento mensal, produtividade por funcionário e ATC, metas informadas pelo usuário, conferência por registro, preços configuráveis e exportação Excel/PDF.

## Executar no computador

Instale Python 3.12 ou 3.13. Extraia o projeto e abra um terminal na pasta.

Windows (PowerShell):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

Linux/macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py --server.address 127.0.0.1
```

No computador, abra o endereço apresentado pelo Streamlit no terminal. Para encerrar, pressione Ctrl+C. Não é necessário Excel instalado.

## Fluxo

1. Selecione o mês de referência na lateral. Configure a empresa e o número do contrato em Configurações.
2. Em Importar planilhas, envie o XLSX, escolha a aba e confira a correspondência das colunas. O cabeçalho da exportação fornecida está na linha 4; as 72 colunas são preservadas.
3. Confirme o mês e importe. Cada aba é importada separadamente. Faça isso também para os outros grupos quando estiverem disponíveis. O original completo, incluindo todas as abas, fica arquivado por SHA-256 e pode ser baixado novamente.
4. Confira as categorias e os registros em Fechamento mensal. Inspecione os valores originais pelo ID. Exclusão e reinclusão exigem justificativa e ficam no histórico; não alteram o arquivo original.
5. Em Produtividade, acompanhe funcionário ou ATC e informe metas mensais de leituras faturáveis. Zero remove a meta; não há metas fictícias predefinidas.
6. Em Relatórios, gere e baixe Excel e PDF. O Excel contém os dados importados, rastreabilidade, histórico, produtividade e metas. O PDF contém indicadores, gráfico, tabelas de produtividade e metas informadas. Metas em branco não recebem valores presumidos.
7. Confirme o fechamento após a conferência. O mês fechado bloqueia importação, exclusões e preços. Reabertura exige justificativa.

## Regras e limites de escopo

| Serviço | Condição | Preço inicial |
|---|---|---|
| 200014094 | Impressas Sim, Retida Não, causa vazia | R$ 1,38 |
| 200014096 | Impressas Não, Retida Não, causa vazia | R$ 1,28 |
| 200014095 | Retida Não e causa preenchida | R$ 1,37 |
| 200014102 | Soma de Quantidade comunicados impressos | R$ 0,50 |
| 200014103 | Contagem de CO1 Atual preenchido | R$ 0,50 |

As categorias de leitura são mutuamente exclusivas. Adicionais podem coexistir com a leitura e são aplicados também em faturas retidas. Registros sem data e releituras são incluídos no mês escolhido, conforme confirmação do usuário. Datas presentes fora do mês escolhido são pendências que exigem exclusão justificada ou importação no mês correto. Espaços isolados são tratados como vazio para classificação; o valor original permanece arquivado.

CO1 Atual preenchido é contado inclusive quando descreve vistoria, conforme confirmação; isso cobra apenas apontamento operacional, nunca o serviço de vistoria. Feriado, grandes consumidores, entrega de fatura, ligação inativa e serviços de vistoria não fazem parte desta versão. Tipos de mercado não alteram a regra confirmada.

Não são inventados dados, preenchidas datas ou renomeadas as colunas originais. A data de emissão do relatório não substitui a referência escolhida. Ausência de funcionário ou ATC aparece como Não informado. Fórmulas em campos de cálculo, quantidades inválidas e Sim/Não não reconhecidos produzem pendências e não faturam até a resolução. São usados centavos inteiros para evitar erros de soma monetária.

Linhas exatamente iguais são ignoradas dentro do mesmo mês, mesmo em arquivos diferentes. Mesmo arquivo/aba não pode ser reimportado no mesmo mês. Registros distintos com fornecimento + data + tarefa repetidos permanecem visíveis e bloqueiam o fechamento até decisão justificada; não são removidos por suposição. Se a chave não estiver disponível, apenas a duplicidade integral pode ser verificada. O escopo de deduplicação é mensal: importar sem data em outro mês requer conferência humana.

Preços padrão valem para meses novos; a opção explícita de aplicar ao mês aberto atualiza esse mês. Meses fechados mantêm seus preços. Esta primeira versão administra a medição e os dados básicos do contrato; não emite nota fiscal, não se conecta aos sistemas Sabesp e não inclui gestão de folha ou contabilidade.

## Persistência e backup

O banco SQLite e os originais ficam em `data/`, fora do controle de versão. Pare o aplicativo e copie **toda** essa pasta para backup. Restaurar essa pasta restaura os meses e os originais. Para outro local, defina `APP_DATA_DIR` antes de iniciar. A versão é para operação local, sem login ou controle por usuário; não exponha o servidor na Internet. O pacote do código não contém dados pessoais ou a planilha de trabalho.

## Excluir e restaurar importações

Em Importar planilhas → Arquivos importados e originais, cada aba importada tem identificação, data UTC, mês, quantidade de registros, faturamento correspondente e situação. Excluir importação abre a confirmação do arquivo/aba, mês, quantidade e impacto financeiro com os preços do mês. Informe justificativa e marque a confirmação explícita. Os registros deixam de faturar; o arquivo original e o histórico permanecem intactos. Restaurar importação usa a mesma confirmação e preserva exclusões individuais de registros anteriores.

A operação afeta exclusivamente a importação selecionada, no mês selecionado. Arquivos com várias abas são geridos por importação/aba, sem exclusão das demais abas. Meses fechados exigem reabertura. Todas as tabelas, filtros, gráficos e rankings são recalculados; relatórios gerados anteriormente devem ser gerados novamente (downloads antigos não são alterados). Produtividade agora também permite agrupar por Grupo, disponível nos relatórios Excel e PDF.

Para substituir um arquivo, exclua a importação antiga e importe o XLSX corrigido. Linhas idênticas de importações ativas continuam sendo ignoradas. O mesmo arquivo/aba já cadastrado deve ser restaurado, em vez de reimportado. A restauração é integral e bloqueada se alguma linha já estiver em outra importação ativa: exclua a substituta antes de restaurar. Linhas distintas com a mesma chave operacional continuam exigindo conferência antes do fechamento. Nenhum dado original é corrigido automaticamente.

A atualização migra automaticamente o banco para versão 2 no primeiro início. **Antes da migração, cria e verifica um backup SQLite em data/backups/antes-migracao-v2-*.sqlite3. Se o backup falhar, a migração não prossegue.** A migração, exclusão e restauração são transacionais. O histórico registra data/hora UTC, arquivo, aba, mês, quantidades, impacto em centavos e justificativa. Mantenha também seu backup manual da pasta data completa, com os originais.

## Filtros de data

Painel inicial, Fechamento mensal e Produtividade oferecem **Mês completo**, **Dia específico** e **Intervalo personalizado**. Escolha primeiro o mês de referência na lateral. O intervalo é dentro desse mês e inclui as datas inicial e final. O filtro usa a coluna Data da Leitura Atual com o mapeamento confirmado na importação, inclusive para bases já existentes; não precisa reimportar arquivos.

Indicadores, categorias, gráficos e rankings usam apenas registros não excluídos, sem erros e com data válida dentro do período. Registros com erros e excluídos continuam disponíveis na conferência do período. Duplicidades são identificadas no mês inteiro, mesmo quando um dos registros não está no período mostrado. Pendências mensais continuam bloqueando o fechamento.

Os registros sem data válida não são atribuídos a um dia nem entram nos indicadores filtrados, inclusive no modo Mês completo. Permanecem no histórico e no **acumulado mensal**, que aparece separado e preserva a regra original de inclusão dos registros sem data. A conferência mensal completa fica disponível em um expansor. Por isso, o acumulado mensal pode ser diferente do total do período. Na planilha fornecida há 46 registros sem data e 19.622 com data 10/10/2026; o acumulado continua R$ 30.454,12.

Confirmar fechamento sempre fecha o mês inteiro, sem excluir registros devido ao filtro. Relatórios Excel/PDF continuam mensais. Metas permanecem mensais: o percentual na produtividade compara o realizado no período com a meta mensal, sem inventar rateio diário.

## Atualizar o sistema instalado

1. Pare o Streamlit com Ctrl+C. Faça uma cópia de segurança de toda a pasta `data/` (ou do local definido em APP_DATA_DIR).
2. Extraia o ZIP atualizado em uma pasta temporária. Copie os arquivos de código e a pasta `tests/` para a instalação existente, substituindo os arquivos de código correspondentes. Inclua o novo `periods.py`. **Não substitua, remova ou recrie a pasta data, a pasta originais ou o arquivo contrato.sqlite3.** Não apague arquivos locais ou a `.venv`.
3. As dependências não mudaram. No PowerShell, dentro da pasta instalada, execute:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_periods.py -v
.\.venv\Scripts\python.exe -m streamlit run app.py
```

No Linux/macOS use `.venv/bin/python`. No primeiro início desta versão, o banco é migrado automaticamente após backup SQLite verificado em data/backups. Não é necessário reimportar planilhas. Meses fechados, histórico, preços, metas e originais existentes são reutilizados.

Para executar todos os testes: `python -m unittest discover -s tests -v` usando o Python da `.venv`. Os testes unitários usam fixtures isoladas, que nunca entram no sistema. Os testes de interface usam uma cópia temporária da base real de outubro/2026 e confirmam que banco e originais não mudam; sem essa base, são explicitamente ignorados. Para validar os cálculos originais com o XLSX fornecido, use validar_planilha.py como descrito abaixo.

## Validar com a planilha fornecida

```bash
.venv/bin/python validar_planilha.py /caminho/XLSConsumptionAnalysis-261013103155920-1.xlsx
```

No Windows, use `.\.venv\Scripts\python.exe` no lugar de `.venv/bin/python`. O verificador usa exclusivamente a planilha fornecida, compara as quantidades de cada categoria com a conferência independente e exercita persistência, deduplicação, exclusão/reinclusão, fechamento, preços, Excel e PDF. Outros arquivos não são tratados como a mesma base de referência.

## Ambiente de desenvolvimento na nuvem

Use o checkout existente em `/workspace/TESTE`; cada tarefa já está isolada e não precisa de worktree. Dependências permanecem em `.venv`; processos devem ser iniciados novamente em novas tarefas. O servidor é iniciado com `.venv/bin/python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501`. Valide a saúde local e as telas com Streamlit AppTest. Não há credenciais adicionais nem serviços externos necessários para os cálculos.
