# Guia do usuário

O aplicativo abre no navegador, mas servidor e dados permanecem locais. Fechar a aba não encerra o processo; use **Encerrar aplicativo** em **Configurações e dados**.

## Primeiro acesso

O onboarding funciona como um assistente de configuração e exige ao menos uma conta. Informe saldo e data de referência com cuidado: o saldo representa o início daquela data, antes dos movimentos registrados. Receitas e despesas efetivadas na mesma data são aplicadas imediatamente. Em seguida, o assistente permite cadastrar cartões, categorias, recorrências e orçamentos. Essas etapas são opcionais, aceitam vários itens e podem ser puladas para configuração posterior pelo menu. O progresso fica salvo.

## Uso diário

- **Visão geral** reúne saldos, receitas, despesas, resultado, compromissos e cobertura do período.
- **Movimentações** cadastra receitas/despesas, filtra o histórico e permite corrigir, cancelar ou estornar preservando auditoria.
- **Contas** administra contas, transferências com prévia e correção do saldo de referência.
- **Cartões** cria compras parceladas, fecha/reabre e paga faturas, lança compras antigas, reembolsos, cancelamentos e termos futuros do cartão.
- **Planejamento** contém compromissos manuais, recorrências e planos de pagamento. Ocorrências projetadas nunca são efetivadas automaticamente.
- **Orçamentos** distingue limite ausente de limite igual a zero e mostra risco projetado.
- **Categorias** permite renomear e arquivar sem apagar o histórico.

Compras no cartão entram nas despesas na competência de vencimento da parcela. Pagar a fatura movimenta a conta, mas não cria uma segunda despesa. Transferências não são receita nem despesa. Ações sensíveis exibem prévia e exigem confirmação; uma prévia desatualizada é recusada e recalculada.

## Backup e recuperação

Backups automáticos ficam na pasta de dados e os 30 diários mais recentes são mantidos. Exporte periodicamente um `.finbackup` para outro dispositivo. Na restauração, confira a prévia e confirme somente o arquivo esperado. O aplicativo valida hash, schema, integridade e chaves estrangeiras e mantém uma cópia recuperável do banco atual.

O arquivo SQLite e os backups não possuem criptografia própria. Use senha na conta Windows e, quando necessário, criptografia de disco. Veja [migração e recuperação](migracao-recuperacao.md).
