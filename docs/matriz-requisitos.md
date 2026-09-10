# Matriz de requisitos

Fonte de verdade: `Especificacao_MVP_Financas_Local.md` v1.1.

| Requisito | Implementação | Interface | Evidência | Status |
| --- | --- | --- | --- | --- |
| Fundação local, APP_ID, SQLite e Alembic | launcher/storage | onboarding e shell | foundation/schema | concluído |
| Sessão local e proteção HTTP | security/middleware | transparente | security, AC-25/38 | concluído |
| Contas, saldos e histórico | accounts/cash | Contas/Movimentações | AC-01/02/31 | concluído |
| Transferências e estorno | transfers | Contas | AC-03/21 | concluído |
| Cartões, compras, parcelas e faturas | cards/purchases/invoices | Cartões | AC-04/05/08/09/28/29/30 | concluído |
| Pagamento, ajustes, estornos e créditos | settlement/refunds | Cartões | AC-06/07/15/16/17/20/33/37 | concluído |
| Planejamento e recorrências | planning/recurrence | Planejamento | AC-10/11/18/32/34/35/42 | concluído |
| Orçamento, painel e cobertura | analytics/budgets | Visão geral/Orçamentos | AC-12/13/14/19 | concluído |
| Idempotência, revisão e arquivamento | API/domain/storage | todas | AC-26/36/39/41 | concluído |
| Backup e restauração recuperável | maintenance | Configurações e dados | AC-22/23/40 | concluído |
| Executável Windows offline | packaging | aplicação completa | AC-24/27 | concluído |

Todos os 42 critérios possuem implementação e evidência em `docs/criterios-aceite.md`.
