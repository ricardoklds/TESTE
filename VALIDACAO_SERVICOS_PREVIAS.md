# Validação: tabela de preços e prévias gerenciais

Referência anterior: `5ba82eb`. Ambiente de testes, sem modificar produção ou Excel original. Nenhum preço/classificação cadastrado é substituído ao instalar. Menu, Geolocalização, glosa simulada e funcionalidades operacionais preservados; alterações novas limitadas ao editor de serviços e ao Fechamento Geral.

**153 testes aprovados em 46,343 segundos.** Os 13 testes novos cobrem a tabela, inclusão, preço específico e classificação (também nos testes anteriores), confirmação de desativação, histórico/vigência, rollback de lote, dez serviços, Vistorias/Geolocalização separados, subtotal informativo sem dupla contagem, PDF/Excel, simulação sem gravação, geração somente sob demanda e invalidação de arquivos após mudança real nos dados. Abertura da tabela é testada com o classificador financeiro bloqueado e hashes dos bancos preservados.

**Diferenças financeiras antes/depois: R$0,00** para Leituras, Vistorias, Geolocalização e bruto, antes e após o lançamento sintético de Geolocalização. As seis quantidades de Leituras coincidiram. O relatório e a simulação preservaram os hashes dos bancos. Os valores auditados de setembro não foram usados como constantes ou resultados de destino. Não houve uma nova auditoria real dos 20 Excel nesta etapa.

## Desempenho

500.000 Leituras e 100.000 Vistorias sintéticas, versões executadas sequencialmente em bases temporárias separadas. Tempos em segundos. AppTest mede servidor, não navegador/rede ou importação Excel desse volume.

| Operação | Antes | Depois |
|---|---:|---:|
| Leituras em cache (mediana de 3) | 0.021 | 0.021 |
| Primeira entrada em Vistorias | 1.674 | 1.573 |
| Primeira abertura de Fechamento Geral | 2.034 | 2.201 |
| Fechamento sem cache (mediana de 3) | 2.090 | 2.012 |
| Fechamento em cache (mediana de 3) | 0.010 | 0.009 |
| Simulação (mediana de 4) | 0.009 | 0.011 |
| Abrir Geolocalização | 0.007 | 0.007 |
| Salvar Geolocalização | 0.012 | 0.010 |

Exportações completas de prévia não existiam antes. Nesta execução: PDF 0.011s, Excel 0.011s e geração de ambos pela tela 0.081s. A soma dos dez serviços coincidiu com o bruto. O subtotal Vistorias + Geolocalização foi conferido separadamente e não entra novamente na soma.

A primeira abertura variou de 2,034s para 2,201s nessa amostra; as medianas sem cache e em cache não apresentaram regressão relevante. Não é garantia universal de tempo em outro computador. Arquivos brutos e todos os tempos estão em measurements/price-reports. Quantidade de registros não aumenta o trabalho de exportação: os geradores recebem apenas as linhas agregadas de serviços, sem reabrir banco ou Excel.

## Alterações e instalação

Quatro arquivos existentes de aplicação foram ajustados: contract_finance.py (detalhe do agregado existente), contract_ui.py (composição e botão de prévia), inspection_billing.py (proposta atômica de preços em lote e tarifa na descrição de geolocalização ainda não lançada), inspection_module_ui.py (substituição do formulário de preços pela tabela e confirmação de desativação). Três auxiliares novos: inspection_price_editor.py, contract_presentation.py e contract_reports.py. Não houve modificação do menu, importadores ou motores de regras de Leituras, feriados, OS e escopo.

Sem migração ou dependência nova para executar o aplicativo. requirements-dev.txt acrescenta pypdf apenas para testar o conteúdo do PDF, sem uso em produção. No Windows: parar, fazer backup completo de data e do código atual, atualizar código preservando data/.venv/.streamlit/backups, iniciar com `.venv\Scripts\python.exe -m streamlit run app.py`. Não reimportar planilhas nem reinstalar Python. Guia: SERVICOS_PREVIAS_GERENCIAIS.md.
