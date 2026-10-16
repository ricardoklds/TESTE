# Referência de localidades

Fonte: https://github.com/kelvins/municipios-brasileiros
Commit fixado: 503e2f70bbf1b4b7ec0b1f68b09086ccc38fe861
Arquivos csv/municipios.csv e csv/estados.csv. Distribuição comunitária de nomes/códigos IBGE, com referência ao Serviço de Dados do IBGE, não um download direto da API oficial. A API https://servicodados.ibge.gov.br/api/v1/localidades/municipios retornou HTTP 403 neste ambiente.

O CSV acessado tem 5.571 IDs únicos, apesar do README upstream citar 5.570. Foram extraídos somente ID, nome e UF; não se criaram correspondências. As 27 UFs são obtidas da tabela de estados do mesmo commit; o prefixo do código IBGE foi conferido contra o código UF. Agudos (3500709/SP) e Araçariguama (3502754/SP) foram verificados nessa referência.

Ausências/renomeações ficam pendentes, sem busca aproximada. Não se afirma que a lista é a relação oficial atual completa.

SHA-256 de municipalities.json: 72e96f8c4044bdba30397231a7695a36c9f4134b984f954d5fd65b22675f1702

Confirmação contratual de 14/10/2026: o usuário identificou ATC BOCAINA como Bocaina/SP.
O código 3506805/SP foi verificado na referência acima; ela também contém Bocaina/PI
(2201804), portanto o nome sem UF não foi desambiguado por suposição. O arquivo
municipal_confirmations.json documenta a confirmação específica da origem ATC, usada
somente em contexto municipal, sem substituir a resolução geral nacional/estadual.
