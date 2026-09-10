# Critérios de aceite

Rastreabilidade dos 42 critérios da especificação. Os nomes abaixo apontam para testes automatizados em `backend/tests`, salvo quando indicado.

| AC | Evidência principal | Resultado |
| --- | --- | --- |
| 01 | `test_ac01_ac02_ac31_reference_balance_boundary_and_history` | aprovado |
| 02 | mesmo teste de saldo de referência | aprovado |
| 03 | `test_ac01_ac02_ac03_ac31_balances_and_transfer_analytics` | aprovado |
| 04 | `test_ac04_installment_remainder_is_exact_and_consecutive` | aprovado |
| 05 | `test_ac05_six_installments_cross_year_without_bank_entry` | aprovado |
| 06 | `test_invoice_payment_is_idempotent_and_divergent_replay_conflicts` | aprovado |
| 07 | `test_stale_payment_preview_recalculates_and_applies_nothing` | aprovado |
| 08 | `test_ac08_only_remaining_old_installments_become_obligations` | aprovado |
| 09 | `test_ac09_opening_replacement_preserves_current_invoice_contribution` | aprovado |
| 10 | `test_days_28_29_30_31_and_ac10_recurrence` | aprovado |
| 11 | `test_ac10_ac11_ac32_recurrence_generation_confirmation_and_versioning` | aprovado |
| 12 | `test_ac12_budget_exceeded` | aprovado |
| 13 | `test_ac13_absent_and_zero_budget_are_distinct` | aprovado |
| 14 | `test_ac14_projected_budget_risk` e `test_ac14_budget_uses_planned_only_as_additional` | aprovado |
| 15 | `test_ac15_refund_after_paid_invoice_preserves_it_and_hits_future_competence` | aprovado |
| 16 | `test_ac16_refund_and_cancellation_cannot_abate_same_value` | aprovado |
| 17 | `test_ac17_credit_carry_is_created_and_consumed_once` | aprovado |
| 18 | `test_ac18_projection_deduplicates_invoice_obligation` | aprovado |
| 19 | `test_ac19_partial_coverage_suppresses_reliable_comparison` | aprovado |
| 20 | `test_ac20_settled_installment_category_snapshot_is_immutable` | aprovado |
| 21 | `test_transfer_rolls_back_if_second_leg_fails` e teste de reversão | aprovado |
| 22 | `test_finbackup_round_trip_and_manifest_privacy` | aprovado |
| 23 | testes de backup corrompido/incompatível e rollback pós-substituição | aprovado |
| 24 | `scripts/test_packaged.ps1` com PATH sem runtime externo | aprovado |
| 25 | suíte `test_security.py`: bootstrap, cookie, CSRF, Host e Origin | aprovado |
| 26 | teste de idempotência persistente após reinício | aprovado |
| 27 | smoke do executável: pasta de dados estável e banco fora do pacote | aprovado |
| 28 | `test_ac28_purchase_on_closing_and_next_day` | aprovado |
| 29 | teste de calendário de fechamento/vencimento | aprovado |
| 30 | `test_ac30_and_ac36_archiving_and_card_terms_preserve_existing_obligations` | aprovado |
| 31 | testes de histórico e cenário integrado | aprovado |
| 32 | teste de versionamento de recorrência | aprovado |
| 33 | previews de reembolso e cancelamento de parcela | aprovado |
| 34 | `test_ac34_planned_purchase_is_replaced_by_exactly_one_real_purchase` | aprovado |
| 35 | `test_ac35_payment_plan_replaces_account_and_date_without_duplicate` | aprovado |
| 36 | arquivamento preservando obrigações e avisos de dependência | aprovado |
| 37 | pagamento exato idempotente e sem dupla contagem | aprovado |
| 38 | GET não mutável, API inexistente 404 e origem única | aprovado |
| 39 | conflito de revisão de compra e preview obsoleto | aprovado |
| 40 | preview e confirmação explícita de restauração | aprovado |
| 41 | valores monetários inseguros rejeitados na API e no banco | aprovado |
| 42 | exceção mensal de recorrência e confirmação de ocorrência | aprovado |

Além dos testes unitários e de integração, `backend/app/maintenance/self_test.py` repete os fluxos críticos usando somente os componentes embutidos no executável.
