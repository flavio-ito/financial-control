# Registro de testes

Data da validação mais recente: 2026-09-10. Nenhuma etapa foi promovida com teste obrigatório falhando.

| Etapa | Evidência executada | Resultado |
| --- | --- | --- |
| 1 — Fundação local | inicialização, persistência, sessão, CSRF, Host/Origin e fallback SPA | concluída |
| 2 — Modelo e persistência | migrações, 22 tabelas, FKs, constraints, rollbacks atômicos | concluída |
| 3 — Domínio financeiro | saldos, transferências, compras, parcelas, faturas, pagamentos, estornos e créditos | concluída |
| 4 — Planejamento | recorrências, compras planejadas, planos de pagamento e projeções | concluída |
| 5 — Orçamento e análise | orçamento ausente/zero, risco projetado, cobertura e cenário integrado | concluída |
| 6 — Interface completa | formulários, centavos, datas civis, onboarding e navegação | concluída |
| 7 — Backup e recuperação | round-trip, manifesto, corrupção, incompatibilidade e rollback | concluída |
| 8 — Empacotamento | executável sem runtime externo, autoteste HTTP, instância única e ZIP | concluída |

## Suítes finais

- Backend: `65 passed` no pipeline final.
- Backend validado também no Python 3.12.10.
- Frontend: `14 passed` em 3 arquivos.
- TypeScript estrito: aprovado sem erros.
- Dependências JavaScript: `npm audit` sem vulnerabilidades após atualização.
- Desempenho: paginação indexada em base sintética de 50 mil movimentos em `0,012493 s` para a consulta medida (teste completo, incluindo preparação, `1,45 s`).
- Cenário integrado: saldos A = R$ 41,00, B = R$ 9,00 e consolidado = R$ 50,00; receita = R$ 20,00, despesa = R$ 5,00, resultado = R$ 15,00 e compromissos = R$ 4,00, sem dupla contagem.
- Autoteste do executável: fluxo HTTP completo de bootstrap, compra, fechamento, pagamento, backup, mutação, restauração e verificações SQLite aprovado.
- Smoke empacotado: health check, fallback SPA, API 404, banco fora do pacote e bloqueio da segunda instância aprovados com `PATH` sem Python ou Node.
- ZIP final: checksum SHA-256 no arquivo companheiro `.zip.sha256`; nenhum banco, backup, log, `.env` ou `runtime.json` embarcado.

Os testes de aceitação estão mapeados em `docs/criterios-aceite.md`. A inspeção interativa por navegador automatizado não estava disponível no ambiente; os fluxos foram validados por testes de componentes, API e pelo autoteste executado dentro do binário final.
