# Validação da versão consolidada de Vistorias

Execução em 16/10/2026 UTC. Código anterior comparado: `568bc75`. Todas as bases foram temporárias/sintéticas. Não houve acesso de escrita à produção, aprovação de fechamento ou aplicação de glosa.

O recálculo independente do Excel original e o SQL concordam em **R$91.383,00**, sem usar a hipótese informada para determinar quantidades. Aprovação: **1.231/R$27.697,50**; Predial: **2.679/R$60.277,50**; Cadastral: **284/R$3.408,00**. Os 4.431 registros ficam preservados: 4.194 cobrados, 12 sem cobrança adicional, 223 fora do contrato, dois explicitamente não faturáveis. Pendências comerciais nessa fonte: zero. Geolocalização não incluída por ausência de quantidade documental confirmada.

O estado anterior reproduzido em banco temporário tinha R$91.113,00 e 247 pendências. O acréscimo de R$270,00 representa 12 cobranças, não 24. Os outros 223 registros passaram para Fora do escopo do contrato. A lista de representantes com OS, linha, execução e município está no guia ESCOPO_CONTRATUAL_VISTORIAS.md e no JSON independente.

Prazo contratual do original: 4.208 ocorrências apuráveis, 3.936 dentro, 272 fora, 93,5361%. Meta de 99% não atingida. Atraso não exclui faturamento. Nenhuma multa foi aplicada; depende de contrato validado e confirmação própria.

## Testes

**132 testes aprovados em 44,894 segundos.** Log integral: measurements/inspection-contract-scope/tests.txt. Incluem 19 testes de escopo, escolha cronológica, desempate, critérios configuráveis, edição com confirmação, vigência, municípios divergentes/desconhecidos, geolocalização, competêcias cruzadas e cobrança aprovada congelada. Migração foi exercitada contra dumps sintéticos produzidos pelo código anterior: backup com integridade, preservação do payload aprovado, origem ausente e rollback em inconsistência. Os testes de Leituras cobrem seis serviços, feriados, filtros, exclusão/restauração e auditoria.

## Desempenho efetivamente medido

500.000 Leituras e 100.000 Vistorias sintéticas. Valores em segundos; três amostras para agregação e painel cacheado de Leituras. Demais linhas são uma medição cada. AppTest mede execução de servidor Streamlit, não navegador/rede nem importação Excel de 500 mil linhas. O conjunto de Vistorias do benchmark tem OS únicas e municípios autorizados; repetições/fora de escopo têm testes separados.

| Operação | Antes | Versão consolidada |
|---|---:|---:|
| Preparar projeção com backup | 1.455 | 2.254 |
| Primeira entrada em Vistorias | 0.580 | 1.662 |
| Painel de Vistorias em cache | 0.042 | 0.043 |
| Abrir página Prazos | 0.044 | 0.070 |
| Retornar a Leituras | 0.018 | 0.019 |
| Agregado operacional de prazo | 0.033 | 0.034 |
| Página financeira na posição 50.000 | 0.383 | 1.474 |
| Excel resumido | 1.140 | 3.133 |
| Agregado financeiro, mediana de 3 | 0.535 | 1.508 |
| Leituras em cache, mediana de 3 | 0.018 | 0.017 |

O custo financeiro sem cache aumentou em relação à regra antiga, pois agora há escopo versionado, escolhas entre competências e proteção de cobranças aprovadas. Não é apresentado como ganho sobre a versão anterior. A primeira implementação desta etapa levou 6,81s para abrir Vistorias; depois de eliminar recálculos SQL e reutilizar agregados, a versão final levou 1,66s. A navegação cacheada ficou próxima da anterior e Leituras permaneceu próxima de 0,02s. Não há garantia desses tempos em outro hardware ou com milhões de Vistorias numa única competência.

Pico de RAM do processo completo: antes 710,71 MiB; depois 712,45 MiB (inclui Streamlit e painel com 500 mil Leituras). Os seis totais sintéticos de Leituras foram comparados com o cálculo de referência e permaneceram idênticos; SHA-256 do banco de Leituras também permaneceu igual. O valor real de setembro R$596.906,23 não foi recalculado sem seus 20 Excel nesta etapa e não é valor fixo no código.

Consultas usam índices, seleção do mês e das OS relacionadas em outros meses, agrupamentos SQL e paginação de 50 linhas. Originais Excel só são lidos na importação/validação solicitada. Configurações e importações invalidam os caches por revisão. O painel financeiro reutiliza o agregado municipal e normaliza municípios dos prazos após agregação, evitando processamento por linha na navegação.

## Atualização e riscos

Consulte o guia ESCOPO_CONTRATUAL_VISTORIAS.md: parar aplicativo, copiar toda data e código atual, atualizar somente código preservando data/.venv/.streamlit/backups, iniciar com `.venv\Scripts\python.exe -m streamlit run app.py`. Migração somente do financeiro de Vistorias, com backup consistente verificado antes da estrutura e transação com rollback. Originais, registros operacionais e aprovações antigas permanecem preservados. Não é necessário instalar versões intermediárias.
