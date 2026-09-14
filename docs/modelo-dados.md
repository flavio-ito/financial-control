# Modelo de dados e invariantes

## Convenções globais

- IDs de entidades são UUIDs textuais de 36 caracteres.
- Entidades mutáveis registram `created_at`, `updated_at` e `revision`.
- Instantes técnicos e de auditoria são UTC; datas financeiras são civis.
- Meses usam `YYYY-MM`; datas usam `YYYY-MM-DD`.
- Valores monetários usam inteiros em centavos no intervalo seguro do JavaScript (`±9.007.199.254.740.991`).
- A moeda do MVP é exclusivamente `BRL`.
- Foreign keys usam `RESTRICT`; vínculos não podem ser apagados silenciosamente.
- Entidades com histórico relevante são arquivadas ou mudam de estado, em vez de serem removidas.

## Núcleo cadastral

### `settings`

Configuração única do aplicativo: locale `pt-BR`, moeda `BRL`, timezone, etapa do onboarding e revisão.

### `accounts`

Contas financeiras. O saldo é derivado de um saldo de referência em uma data e dos lançamentos aplicáveis. Uma conta pode ser arquivada, mas vínculos históricos permanecem.

### `cards`

Cartões com limite, dia de fechamento, dia de vencimento e conta padrão opcional. Dias ficam entre 1 e 31; regras de calendário ajustam datas para meses menores.

### `categories`

Categorias de receita (`income`) ou despesa (`expense`). O tipo condiciona seu uso em lançamentos, compras e orçamento. Categorias usadas historicamente são arquivadas.

## Caixa e transferências

### `cash_entries`

Livro de movimentos das contas. Um lançamento possui valor assinado não zero, conta, datas, estado, origem e vínculos opcionais com transferência, pagamento, recorrência, reembolso ou reversão.

Estados:

```text
planned → effective → voided
   └────→ cancelled
```

Principais tipos: receita, despesa, entrada/saída de transferência, pagamento de fatura, reembolso e ajuste de saldo.

### `transfers`

Representa a intenção única de movimentar valor positivo entre contas distintas. Sua efetivação cria efeitos opostos no caixa sem alterar o patrimônio consolidado.

Estados:

```text
planned → effective → reversed
   └────→ cancelled
```

Invariantes:

- origem e destino são diferentes;
- valor é estritamente positivo;
- as duas pernas são criadas na mesma transação;
- transferência interna não é receita nem despesa consolidada.

## Cartões, faturas e pagamentos

### `purchases`

Compra confirmada em um cartão. Armazena total positivo, quantidade de parcelas, categoria, origem e vínculo opcional com planejamento ou recorrência.

Invariantes:

- ao menos uma parcela;
- nenhuma parcela pode receber zero centavos;
- a soma das parcelas é exatamente o total da compra;
- uma compra confirmada pode ser anulada, mas não apagada.

### `installments`

Parcelas de uma compra, cada uma ligada a uma única fatura. O número da parcela é único dentro da compra. A categoria é copiada como snapshot para preservar análise histórica.

Estados: `confirmed`, `cancelled` e `historical_settled`.

### `invoices`

Uma fatura por cartão e mês de referência. A data de fechamento deve ser anterior ao vencimento.

Estados:

```text
open ⇄ closed ⇄ settled
```

A reabertura é explícita. O valor da fatura é derivado de parcelas e ajustes aplicáveis; não é armazenado como saldo independente.

### `invoice_adjustments`

Débitos, créditos, saldos iniciais, reembolsos e carregamento de crédito entre faturas. Valores são assinados e não podem ser zero. Um crédito ativo originado por uma fatura é único.

### `payments`

Pagamento de uma fatura a partir de uma conta. Um pagamento ativo gera um lançamento de caixa vinculado. Há no máximo um pagamento ativo por fatura no MVP.

Estados:

```text
active → reversed
```

A reversão preserva o pagamento original e seus efeitos históricos.

### `invoice_payment_plans`

Planejamento de pagamento de uma fatura por uma conta e data. Há no máximo um plano ativo por fatura. Um plano pode ser cancelado.

### `refunds`

Reembolso originado exclusivamente de uma compra ou lançamento de caixa e destinado exclusivamente a uma fatura ou conta.

Estados:

```text
planned → confirmed
   └────→ cancelled
```

O total reembolsado não pode exceder o valor elegível da origem.

## Planejamento e recorrência

### `planned_card_purchases`

Intenção de compra futura com cartão, valor estimado e mês previsto de fatura. Uma confirmação cria exatamente uma compra e grava o vínculo único.

Estados:

```text
planned → confirmed
   └────→ cancelled
```

### `recurrence_rules`

Regras versionadas para receitas, despesas ou compras recorrentes no cartão. Alterar uma série cria nova versão; não reescreve a regra histórica. Regras de caixa exigem conta, e regras de compra exigem cartão.

### `recurrence_occurrences`

Materialização mensal de uma série. Existe no máximo uma ocorrência não superada por série e mês. Uma ocorrência confirmada liga-se exclusivamente ao lançamento ou compra produzido.

Estados:

```text
planned → confirmed
   ├────→ cancelled
   └────→ superseded
```

Exceções mensais são registradas na ocorrência sem alterar retroativamente as demais.

## Orçamento e análise

### `budget_defaults`

Valor padrão de orçamento de uma categoria a partir de determinado mês. A combinação categoria/mês inicial é única.

### `budgets`

Override explícito de orçamento para uma categoria e mês. Zero é um orçamento válido e difere de orçamento ausente.

### `coverage_intervals`

Declara a completude dos dados de uma conta ou cartão em um intervalo: `complete`, `partial` ou `unknown`. Cada intervalo pertence exclusivamente a uma conta ou cartão e sua data inicial não pode superar a final.

A cobertura contextualiza relatórios; ausência de lançamentos não significa automaticamente ausência de atividade.

## Integridade operacional

### `idempotency_records`

Registra chave, escopo, hash do request e resposta de uma mutação. A combinação chave/escopo é única. Reutilizar a chave com payload diferente gera conflito; reutilizá-la com o mesmo payload retorna o resultado anterior.

### `audit_events`

Histórico append-only de ações sobre entidades, com representação anterior, posterior, motivo e instante UTC. Não deve armazenar tokens ou segredos.

### `backup_runs`

Registro de backups promovidos ou tentativas de manutenção, com destino lógico, status, checksum, versão do aplicativo, revisão Alembic e versão do formato.

## Relações principais

```text
Account ─┬─ CashEntry
         ├─ Transfer (origem/destino)
         ├─ Payment ─ Invoice ─ Card
         └─ CoverageInterval

Card ────┬─ Purchase ─ Installment ─ Invoice
         ├─ PlannedCardPurchase
         ├─ RecurrenceRule/Occurrence
         └─ CoverageInterval

Category ├─ CashEntry
         ├─ Purchase/Installment
         ├─ BudgetDefault
         └─ Budget
```

## Regras para evolução

1. Toda alteração estrutural exige nova migração Alembic e teste partindo da revisão anterior.
2. Uma Release publicada torna suas migrações e backups parte do contrato de compatibilidade.
3. Campos monetários novos devem usar centavos inteiros, constraint de intervalo e moeda explícita quando aplicável.
4. Novos estados exigem atualização conjunta de constraint, máquina de estados, serviços, API, frontend e testes.
5. Novas operações compostas devem falhar por inteiro; nunca promover efeitos parciais.
6. Importações futuras devem ter identificador externo, preview, confirmação, deduplicação e idempotência.
7. Relatórios devem distinguir realizado, previsto, transferências internas e cobertura desconhecida.
8. Exclusão física só é aceitável para dados temporários sem valor histórico; entidades financeiras exigem reversão ou mudança de estado.

Os detalhes normativos permanecem nos modelos e migrações. Este documento explica o contrato conceitual e deve ser atualizado no mesmo pull request que alterá-lo.
