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

## Validar com a planilha fornecida

```bash
.venv/bin/python validar_planilha.py /caminho/XLSConsumptionAnalysis-261013103155920-1.xlsx
```

No Windows, use `.\.venv\Scripts\python.exe` no lugar de `.venv/bin/python`. O verificador usa exclusivamente a planilha fornecida, compara as quantidades de cada categoria com a conferência independente e exercita persistência, deduplicação, exclusão/reinclusão, fechamento, preços, Excel e PDF. Outros arquivos não são tratados como a mesma base de referência.

## Ambiente de desenvolvimento na nuvem

Use o checkout existente em `/workspace/TESTE`; cada tarefa já está isolada e não precisa de worktree. Dependências permanecem em `.venv`; processos devem ser iniciados novamente em novas tarefas. O servidor é iniciado com `.venv/bin/python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501`. Valide a saúde local e as telas com Streamlit AppTest. Não há credenciais adicionais nem serviços externos necessários para os cálculos.
