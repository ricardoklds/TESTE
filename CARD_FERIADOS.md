# Ajuste pontual do card de feriados — Windows

## O que mudou

Somente o **Painel inicial** recebeu este ajuste. Os três indicadores financeiros continuam na mesma ordem: total, leituras/adicionais normais e adicional de feriados. No terceiro card, abaixo do valor em destaque, aparece “Quantidade: … leituras”, em fonte menor. A quantidade vem do mesmo agregado de eventos cobrados que forma o valor, e não da quantidade de feriados cadastrados no calendário.

O próprio card contém a ação discreta **“Exportar leituras em feriados”**. Ela prepara o arquivo apenas ao clicar, com indicação de processamento; depois surge **“Baixar leituras em feriados”** no mesmo card. O download usa o arquivo já preparado e não dispara sua geração novamente. Se não houver eventos, aparece uma mensagem amigável e a ação fica desabilitada.

No Painel, foram removidos o indicador específico de registros sem data e seu aviso amarelo. A legenda com a quantidade também foi retirada desse painel, ficando apenas uma observação genérica sobre preservação e auditoria. Os números continuam no banco, nas conferências e nos relatórios técnicos/gerenciais existentes. As outras páginas mantêm seus indicadores e avisos anteriores. Os demais erros continuam sendo sinalizados normalmente; não há ocultação de problemas financeiros ou de integridade.

Não houve reformulação completa da tela, mudança de filtros ou alteração das regras de competência. Mês completo continua acumulado; dia e intervalo continuam recortes por data. Nenhum registro foi descartado, corrigido, reimportado ou recebeu uma data inventada.

## Conteúdo e consistência do Excel

O arquivo contém somente os IDs efetivamente cobrados na seleção, usando a mesma consulta de elegibilidade/deduplicação e os mesmos registros congelados de meses fechados. Os vencedores de duplicidades são definidos globalmente antes dos filtros gerenciais; filtrar outro funcionário não elege outra execução.

As abas “Leituras” trazem competência, IDs do registro/importação, arquivo/aba/linha de origem, data original e data de elegibilidade, Cidade/ATC original, município/UF utilizados na apuração quando identificados, grupo e funcionário originais, fornecimento, execução, código 200014097, quantidade e valores. Campos ausentes ficam vazios, sem adivinhação. Identificadores textuais com zeros à esquerda continuam textuais. Cada evento faturado é uma linha; eventos distintos do mesmo fornecimento não são colapsados em um único fornecimento.

“Resumo” registra quantidade, preço unitário, total, competência, período, filtros e revisão. “Por cidade e grupo” agrupa os eventos e seus valores. Todos os valores monetários são derivados de quantidades inteiras e do preço vigente do adicional. A gravação em reais no Excel ocorre somente na apresentação.

A exportação verifica a revisão do banco, a consistência de quantidade/valor do card e a igualdade da quantidade detalhada. Em caso de divergência ou mudança de revisão, o arquivo não é oferecido como se estivesse correto. A interface pede atualização. Uma importação legítima ou mudança de filtros/período invalida o download visível da seleção antiga.

O texto original vem dos registros arquivados no banco; não há releitura ou modificação dos Excel originais. Acesso SQLite é somente leitura, em uma transação consistente. O processamento lê os IDs cobrados e busca os originais por chave primária, em lotes de até 500; não faz uma junção do calendário para cada registro do mês. O Excel usa escrita incremental e divisão de abas quando necessário. Não são criadas cópias do banco ou arquivos permanentes de exportação em `data`. Os XML temporários internos do openpyxl são limpos também quando ocorre um erro na preparação.

## Atualização mínima no Windows

1. Feche o aplicativo e faça o backup habitual com ele fechado.
2. Extraia o ZIP na **pasta principal do sistema**, mesclando os arquivos. Substitua somente **`app.py` e `managerial_ui.py`**. Acrescente **`holiday_card_export.py`** na mesma pasta. `CARD_FERIADOS.md` é apenas documentação.
3. Preserve integralmente `data`, `.venv`, originais, backups e relatórios já salvos. Nenhum deles está no ZIP. Não é necessário reinstalar Python, dependências, reimportar arquivos ou migrar o banco.
4. Reinicie pelo iniciador habitual ou pelo terminal da pasta do sistema:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Esta atualização parte da versão anterior do painel gerencial (`2b65528`), com `managerial.py` e demais módulos já instalados. `cached_queries.py`, `managerial.py`, os seis critérios, preços, calendário, importações de setembro/outubro e relatórios oficiais permanecem inalterados. Outubro continua a referência inicial em andamento.

## Conferir setembro na instalação real

Escolha setembro/2026, **Mês completo** e “Todos — limpar filtros gerenciais”. As referências fornecidas após a conciliação são total de R$ 596.906,23, adicional de 19.951 leituras e R$ 20.948,55. Elas não são constantes do novo código. Clique em exportar e confira “Resumo”: sua quantidade e total devem coincidir com o card. Repita com filtros de cidade/ATC, grupo, funcionário e período.

Se o script de conferência da atualização anterior estiver instalado, ele continua disponível, sem alteração e sem reler Excel:

```powershell
.\.venv\Scripts\python.exe validar_gerencial.py --data data --reference .\validacao-setembro-2026\calculo_independente.json --output .\conferencia-card-setembro.json
```

Use um arquivo de saída novo. A referência é lida como comparação; nenhuma quantidade é imposta ao cálculo. A base real de setembro e seus 20 Excel não estão neste ambiente Codex, portanto esses valores **não foram verificados novamente aqui contra a base real**. A consistência do card/exportação foi testada em fixtures isoladas e a exportação confere sua quantidade contra o card a cada solicitação.

## Testes e desempenho medidos

A suíte completa terminou com **90 testes aprovados em 46,991 s**, incluindo regressões dos seis serviços. Os quatro testes específicos também passaram após a verificação adicional de preservação dos arquivos da fixture. Foram conferidos: filtros combinados e períodos, IDs faturados sem repetição, múltiplos eventos no mesmo fornecimento, identificadores textuais, meses fechados, exclusão/restauração, seleção vazia, revisão antiga, discrepância entre card/detalhe, limpeza de temporários e ausência de consulta detalhada na abertura do painel.

Na mesma fixture sintética com **500.000 registros**, antes/depois em processos separados, medindo execução da interface no servidor com Streamlit AppTest:

| Operação | Antes | Depois |
| --- | ---: | ---: |
| Primeira carga da competência | 5,02 s | 5,02 s |
| Mediana de três cargas com cache | 0,0645 s | 0,0650 s |
| Consultas de originais para exportação ao abrir o painel | 0 | 0 |

O novo Excel foi preparado **somente após clicar**, em **3,64 s**, incluindo atualização da interface, para 23.809 eventos sintéticos. O arquivo teve aproximadamente 1,8 MB e 23.809 IDs únicos; quantidade e valor coincidiram com o card. Houve 48 buscas de originais por lote indexado, em vez de carregar os 500.000 registros na memória. Reexibir o painel reutilizou o arquivo, sem novas consultas detalhadas. O banco sintético permaneceu byte a byte idêntico.

São uma amostra inicial e três amostras cacheadas por versão; os tempos não representam o navegador, rede ou uma promessa para o computador Windows. Não se deve interpretar diferenças pequenas dessas amostras como ganho de velocidade. O objetivo deste ajuste foi não acrescentar trabalho de exportação ao carregamento: a quantidade usa o agregado já disponível, e os detalhes ficam sob demanda. Evidências e logs estão em `measurements/card-feriados`.

Não foi implementado o módulo de Vistorias.
