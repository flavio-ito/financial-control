# Migração e recuperação

## Migrações

O inicializador adquire a trava de instância, cria a pasta privada de dados e executa Alembic até `head`. Se já houver banco, cria antes uma cópia `.finbackup`. O schema só é alterado pelas revisões em `backend/migrations/versions`; não há `create_all` em produção.

Após a migração, o aplicativo valida `PRAGMA integrity_check` e `PRAGMA foreign_key_check`. Uma falha impede a inicialização e é registrada em `startup-error.log` na pasta de dados.

## Backup

O `.finbackup` é um ZIP contendo banco SQLite e manifesto com versão, data e SHA-256. Backups diários automáticos mantêm as 30 cópias mais recentes. O arquivo não contém token de sessão, caminho de usuário ou segredo, e não é criptografado.

## Restauração segura

1. Em **Configurações e dados**, selecione o `.finbackup`.
2. Execute a prévia; incompatibilidade, hash, integridade e FKs são verificados sem tocar no banco ativo.
3. Confirme a revisão exibida.
4. O serviço cria uma cópia de segurança do estado atual, promove o banco restaurado atomicamente e reabre as conexões.
5. Se qualquer validação posterior falhar, o banco anterior volta automaticamente.

Para desastre de disco, mantenha ao menos uma exportação em outro dispositivo. Nunca substitua manualmente o banco enquanto o processo estiver aberto.
