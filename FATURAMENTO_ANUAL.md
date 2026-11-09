# Faturamento Anual

Abra **Faturamento Anual** no menu lateral e selecione o ano. A página é independente da competência mensal do menu e não altera nenhuma tela financeira existente.

## Valores e identificação

- Componentes: Leituras (incluindo feriados), três serviços de Vistorias e Geolocalização, separados.
- Bruto: soma dos componentes, sem glosa simulada ou desconto definitivo. Fotografias do Fechamento Geral aprovado são prioritárias e não são recalculadas.
- Meses abertos: reutilizam as consultas de faturamento existentes; a nova página abre conexões somente leitura. Não cria tabelas, não executa migrações e não importa registros.
- **Aprovado** significa Fechamento Geral aprovado. Componentes aprovados com Geral aberto são identificados como tal; os demais meses são provisórios ou incompletos.
- Um componente sem informação fica em branco, não vira zero. Zero informado/confirmado explicitamente continua sendo zero.
- Composição completa significa que há dados de Leituras, projeção de Vistorias pronta/sem pendências e Geolocalização confirmada. Isso não comprova que todos os grupos do mês foram importados. Valores ainda abertos são sempre identificados como provisórios.
- Acumulado disponível inclui os valores conhecidos de meses parciais. Aprovados e provisórios/parciais têm indicadores separados. Melhor/pior mês e média simples usam somente meses de composição completa, podendo incluir provisórios, conforme identificação explícita.

O gráfico permite alternar entre bruto total e cada componente. A linha tracejada dourada representa a meta **do contrato**, inclusive ao visualizar um componente. A linha roxa é sempre a média móvel **do bruto total**. As cores de atingimento referem-se ao bruto mensal; não representam o atingimento da média móvel.

## Metas

A referência inicial é R$ 650.000,00. Abra **Meta mensal gerencial**, informe vigência `AAAA-MM`, valor e clique em **Salvar meta**. Não são necessários documentos ou responsáveis.

O histórico é salvo exclusivamente em `data/gerencial/metas_anuais.json`, separado dos bancos financeiros. Cada gravação acrescenta um evento com ID, data/hora UTC, vigência e valor. Uma alteração vale até a próxima vigência cadastrada; ao revisar a mesma vigência, prevalece o último evento, preservando os anteriores no histórico. Alterar uma meta histórica muda apenas a comparação gerencial, nunca os valores de um fechamento aprovado.

A gravação usa arquivo temporário, fsync e substituição atômica; uma trava impede gravações simultâneas. Em encerramento abrupto durante a gravação, se restar `metas_anuais.lock`, feche todas as instâncias antes de remover **somente essa trava**. Preserve o JSON de histórico.

## Médias móveis

Janelas de 3 (padrão), 6 e 12 competências consecutivas, incluindo a competência analisada. Usa os meses do ano anterior quando necessários. O resultado é arredondado em centavos com Decimal/ROUND_HALF_UP. Ausências ou composição incompleta tornam a média indisponível: não são substituídas por zero nem por meses mais antigos.

Uma janela com competências completas ainda provisórias recebe **Inclui provisórios**; somente janelas totalmente aprovadas recebem **Apenas aprovados**. A média atual corresponde à última competência com informação no ano selecionado, identificada na tela. Não se confunde meta do mês com meta da média.

## Relatórios e desempenho

O botão **Gerar relatórios anuais PDF e Excel** gera os 12 meses, componentes, metas, diferenças, atingimento, médias móveis, situações e indicadores exibidos. Geração somente sob demanda. Download anterior é invalidado quando o ano, a janela, as metas ou os dados financeiros mudam. Não altera os relatórios anteriores do sistema.

A consulta abrange no máximo 23 competências e usa apenas agregados/fotografias. Cache limitado a oito anos consultados e invalidado por mudanças nos arquivos SQLite/WAL. Editar uma meta, trocar componente ou janela não refaz a consulta financeira. Se os arquivos mudarem durante a leitura, a página pede atualização em vez de guardar uma consulta misturada em cache.

Validação: 181 testes aprovados na suíte de regressão. Inclui metas variáveis e histórico, os três tamanhos de janela, transição de anos, zero explícito, ausência/incompletude, bruto sem glosa, preservação de fotografias, conexões somente leitura, exportações e ausência de consultas repetidas nas interações de apresentação.

Benchmark reproduzível: `benchmark_annual.py`, resultados em `measurements/annual-final/results.json`. Em bases temporárias com 400.000 leituras, 100.000 vistorias, um mês aberto e 22 fotografias aprovadas **sintéticas**:

| Operação | Antes | Depois |
| --- | ---: | ---: |
| Fechamento Geral em cache (mediana de 5 execuções) | 0,0223 s | 0,0177 s |
| Anual, primeira consulta | inexistente | 2,4594 s |
| Anual em cache (mediana de 5 execuções) | inexistente | 0,0604 s |
| PDF anual | inexistente | 0,0254 s |
| Excel anual | inexistente | 0,0130 s |

Estado financeiro antes/depois: idêntico; hashes dos bancos de teste: preservados. Não é uma nova auditoria da base real de setembro. Tempos medem o servidor via AppTest, sem navegador/rede. Benchmark executado neste ambiente, com a suíte de testes em paralelo; números variam conforme carga e computador. Não mede vários meses abertos com grandes volumes simultaneamente; nesse cenário, o primeiro acesso pode demorar mais. Não se afirma suporte ilimitado ou latência garantida para qualquer base histórica.

Reproduzir em ambiente de testes (gera somente dados sintéticos temporários; pode consumir espaço considerável):

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests
.venv\Scripts\python.exe benchmark_annual.py --output measurements\annual-nova-medicao
```

## Atualizar no Windows

1. Encerre o Streamlit com Ctrl+C e copie a pasta do sistema como segurança.
2. Atualize juntos `app.py`, `navigation.py`, `annual_billing.py`, `annual_ui.py` e `annual_reports.py` desta branch.
3. Preserve integralmente `data`, `.venv`, configurações, planilhas originais e backups. Não reimporte setembro/outubro e não execute migrações. Não é necessário reinstalar Python ou dependências.
4. Reinicie na pasta do sistema:

```powershell
.venv\Scripts\python.exe -m streamlit run app.py
```

O diretório `data/gerencial` só será criado ao salvar a primeira meta. Inclua-o nas cópias de segurança de `data`. Para voltar à versão anterior, restaure `app.py` e `navigation.py` da cópia; preserve o arquivo de metas para futuras atualizações.

## Arquivos desta atualização

Aplicativo: `app.py`, `navigation.py`, `annual_billing.py`, `annual_ui.py`, `annual_reports.py`.

Validação/entrega: `tests/ui_navigation.py`, `tests/test_annual_billing.py`, `benchmark_annual.py`, `measurements/annual-final/` e este guia. Nenhum arquivo de regras financeiras, importação, preços, prazos, geolocalização ou glosa foi alterado.
