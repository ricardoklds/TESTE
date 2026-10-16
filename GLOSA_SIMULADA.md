# Simulação ajustável de glosa

Na página Fechamento Geral, ative **Aplicar glosa simulada** e ajuste o slider entre 0,1% e 5%, em passos de 0,1%. Ao ativar, o padrão é 1%. O percentual fica somente na sessão do Streamlit, separado por competência, sem persistência no banco.

A simulação usa o bruto existente (Leituras + Vistorias + Geolocalização). O desconto é arredondado para centavos com Decimal e ROUND_HALF_UP; o líquido é a diferença em centavos. Desligado: desconto zero e líquido igual ao bruto. Nenhum desconto é aplicado por IDG, nem registrado ou aprovado automaticamente.

As prévias gerenciais PDF/Excel já ofereciam glosa simulada: agora recebem o percentual selecionado. Mover o slider invalida a prévia anterior; gere-a novamente pelo botão existente. Serviços, subtotais e valores oficiais continuam iguais. O relatório oficial do contrato não foi alterado.

## Atualização no Windows

1. Encerre o Streamlit (Ctrl+C).
2. Copie sua pasta do sistema como segurança.
3. Atualize juntos `contract_ui.py`, `contract_presentation.py` e `contract_reports.py` desta versão.
4. Preserve `data`, `.venv`, configurações locais, planilhas originais e backups. Não reimporte registros e não execute migrações. Não é necessário reinstalar Python ou dependências.
5. Reinicie na pasta do sistema:

```powershell
.venv\Scripts\python.exe -m streamlit run app.py
```

Rollback: restaure esses três arquivos da cópia anterior; esta atualização não altera o banco.

## Validação

Testes em bases temporárias verificam todos os 50 percentuais, arredondamento em centavos, desativação, padrão de 1%, valores PDF/Excel, invalidação das prévias e igualdade do estado financeiro antes/depois de mover o slider. Também verificam os hashes dos bancos temporários e bloqueiam recálculos financeiros ou aplicação oficial de multa durante a interação. A suíte de regressão cobre os demais módulos. Não foi utilizada a base de produção do computador do usuário; não se afirma uma nova auditoria dos totais reais de setembro.
