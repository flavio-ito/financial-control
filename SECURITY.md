# Política de segurança

## Versões suportadas

Durante a fase de protótipo, somente a versão mais recente publicada recebe correções de segurança. Versões anteriores devem ser atualizadas, preservando o diretório de dados e mantendo um backup `.finbackup` recente.

| Versão | Suporte |
| --- | --- |
| Release mais recente | Sim |
| Releases anteriores | Não |

## Relatar uma vulnerabilidade

Prefira **Security → Advisories → New draft security advisory** no repositório. Esse canal mantém descrição, evidências e discussão privadas até que exista uma correção.

Se o recurso não estiver disponível, abra uma issue contendo somente um resumo sem detalhes exploráveis e solicite um canal privado. Não publique tokens, bancos, backups, logs, caminhos pessoais, dados financeiros reais ou instruções completas de exploração.

Inclua, quando possível:

- versão afetada e versão do Windows;
- componente ou fluxo afetado;
- impacto esperado;
- passos mínimos de reprodução com dados fictícios;
- evidências sanitizadas;
- indicação de perda, exposição ou corrupção de dados.

O recebimento será confirmado assim que possível. A prioridade será definida pelo impacto sobre confidencialidade, integridade dos dados, execução local e recuperação. A divulgação pública deve ocorrer somente após a disponibilização de uma correção.

## Modelo de segurança atual

- O servidor vincula somente `127.0.0.1` em porta dinâmica.
- A API e a SPA usam a mesma origem; CORS não é habilitado.
- O bootstrap usa token aleatório de uso único no fragmento da URL.
- A sessão usa cookie `HttpOnly` e `SameSite=Strict`.
- Mutações exigem sessão, origem válida e token CSRF.
- Sessões e tokens permanecem apenas em memória e são revogados ao encerrar.
- O acesso é limitado a hosts `127.0.0.1` e `localhost`.
- O banco usa foreign keys, timeout de concorrência e serialização local de mutações.
- Backups incluem manifesto e SHA-256 do banco; restaurações são validadas antes da substituição.
- O aplicativo cria backup preventivo antes de migrações e restaurações.

## Limites conhecidos

- O banco SQLite e os arquivos `.finbackup` não são criptografados pelo aplicativo.
- Quem obtiver acesso à conta Windows ou aos arquivos do usuário poderá ler os dados.
- O executável ainda pode não possuir assinatura de código, podendo gerar alertas do Windows SmartScreen.
- O aplicativo não fornece autenticação para múltiplos usuários nem proteção contra um administrador local comprometido.
- A segurança depende também de atualizações do Windows, proteção da conta, criptografia de disco e backups externos.

## Dados que nunca devem entrar no Git

- `.env` e variantes contendo configuração privada;
- `database.sqlite3` e arquivos auxiliares do SQLite;
- backups `.finbackup`;
- `runtime.json` e arquivos de lock;
- logs de execução ou erro com dados reais;
- chaves, tokens, cookies e credenciais;
- documentos ou capturas contendo informações financeiras reais.

Se um segredo for enviado ao Git, removê-lo em um commit posterior não é suficiente: revogue ou substitua imediatamente a credencial e depois trate a remoção do histórico.

## Recomendações para usuários

- Mantenha o Windows e o aplicativo atualizados.
- Use senha forte na conta Windows e bloqueio automático da sessão.
- Habilite BitLocker ou criptografia equivalente quando disponível.
- Guarde backups em local protegido e teste periodicamente a restauração.
- Verifique o SHA-256 publicado antes de distribuir ou instalar o ZIP.
- Não execute cópias obtidas fora da página oficial de Releases.
