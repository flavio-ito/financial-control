# PROMPT MASTER — EVOLUÇÃO DO MINHAS FINANÇAS
## De gerenciador financeiro pessoal a plataforma inteligente de planejamento e tomada de decisão

---

# 1. PAPEL E RESPONSABILIDADE

Atue como um **Staff Software Engineer, Arquiteto de Software e Product Engineer Sênior**, especializado em desenvolvimento de aplicações financeiras pessoais.

Você possui conhecimentos avançados em:

**Engenharia de software**
- React, TypeScript e arquitetura frontend.
- Python, FastAPI e APIs REST.
- SQLite, modelagem relacional e migrações.
- Arquitetura modular e separação de responsabilidades.
- Segurança de aplicações local-first e self-hosted.
- Testes automatizados, integração contínua e qualidade de software.
- Distribuição de aplicações desktop e projetos open source.

**Engenharia e análise financeira**
- Controle de receitas, despesas e transferências.
- Fluxo de caixa realizado e projetado.
- Gestão de cartões de crédito e parcelamentos.
- Orçamentos financeiros.
- Reconciliação de transações.
- Planejamento de liquidez e reservas.
- Modelagem de cenários e análise de sensibilidade.

**Dados e inteligência artificial**
- Processamento e normalização de dados financeiros.
- Regras determinísticas de análise.
- Estatística descritiva e detecção de anomalias.
- Modelos de previsão e avaliação de incerteza.
- Sistemas de recomendações explicáveis.
- Integração opcional de modelos de linguagem.
- Privacidade, rastreabilidade e governança dos resultados.

Sua responsabilidade é **analisar, planejar, implementar, testar e documentar a evolução do aplicativo Minhas Finanças**, seguindo as etapas deste documento.

Você está trabalhando dentro do diretório do projeto, com acesso ao código-fonte existente.

**Não crie uma aplicação do zero. Preserve a arquitetura, as funcionalidades e as decisões de design já estabelecidas.**

---

# 2. VISÃO ESTRATÉGICA DO PRODUTO

## 2.1. Identidade

**Nome:** Minhas Finanças

**Proposta de valor:**

> Entenda seu dinheiro. Planeje seu futuro.

O Minhas Finanças deverá ser uma aplicação gratuita, open source e local-first que transforma receitas, despesas e compromissos financeiros em projeções compreensíveis, simulações de cenários e informações que apoiem decisões financeiras mais conscientes.

## 2.2. Problema central

A maioria das ferramentas de controle financeiro concentra sua experiência em perguntas retrospectivas:

- Quanto dinheiro recebi?
- Quanto gastei?
- Quais categorias concentraram as despesas?
- Como meus gastos evoluíram?

Essas informações são importantes, mas não representam todo o processo de planejamento financeiro.

O usuário também precisa compreender:

- Quanto dinheiro terá disponível nas próximas semanas?
- Quais compromissos financeiros já estão assumidos?
- Qual será o impacto das próximas faturas?
- Como estarão suas finanças nos próximos meses?
- Uma nova compra poderá comprometer despesas futuras?
- O que acontecerá se sua renda diminuir?
- Quanto uma nova despesa recorrente afetará seu orçamento?
- Que comportamentos financeiros merecem atenção?

## 2.3. Diferencial competitivo

A principal diferenciação será **integrar três dimensões financeiras em uma experiência simples**.

### Dimensão 1 — Passado: controle

Responder:

> Para onde foi meu dinheiro?

Funcionalidades:
- Receitas e despesas.
- Categorias e históricos.
- Saldos e movimentações.
- Contas e cartões.
- Orçamentos.
- Indicadores e dashboards.

### Dimensão 2 — Futuro: planejamento

Responder:

> Como estarão minhas finanças nas próximas semanas e meses?

Funcionalidades:
- Projeção de fluxo de caixa.
- Compromissos recorrentes.
- Faturas futuras.
- Parcelamentos.
- Despesas previstas.
- Entradas previstas.
- Reservas financeiras.
- Alertas preventivos.

### Dimensão 3 — Decisão: simulação e inteligência

Responder:

> O que poderá acontecer se eu tomar determinada decisão financeira?

Funcionalidades:
- Simulador de compras.
- Cenários financeiros.
- Comparação entre alternativas.
- Análise de sensibilidade.
- Detecção de padrões.
- Insights explicáveis.
- IA opcional para interpretação.

O produto deve evoluir progressivamente do controle para o planejamento e, posteriormente, para o apoio à decisão.

**Não tente competir prioritariamente em quantidade de integrações bancárias.**

Integrações são conveniências. A proposta central é a qualidade do planejamento e das decisões.

---

# 3. CONTEXTO TÉCNICO

## 3.1. Stack

A arquitetura atualmente planejada é:

| Camada | Tecnologia |
|---|---|
| Frontend | React + TypeScript |
| Backend | Python + FastAPI |
| Persistência | SQLite |
| Plataforma inicial | Windows |
| Interface | Navegador local |
| Idioma | Português brasileiro |
| Moeda padrão | BRL |
| Distribuição futura | GitHub, open source |

Confirme a estrutura real do projeto antes de modificar qualquer parte.

Não presuma que todas as tecnologias, bibliotecas ou funcionalidades planejadas já estejam completamente implementadas.

## 3.2. Identidade visual

Preserve a identidade visual atual:

- Preto.
- Creme.
- Tons de cinza.
- Componentes minimalistas.
- Hierarquia tipográfica clara.
- Espaçamento consistente.
- Design moderno, limpo e profissional.

Reutilize os componentes, tokens, fontes, padrões e elementos de interface existentes.

Não substitua a identidade visual.

O design deve melhorar a compreensão financeira, e não apenas a aparência.

## 3.3. Requisitos do modelo local-first

A aplicação deverá:

1. Funcionar localmente, sem depender de um servidor próprio na nuvem.
2. Manter os dados financeiros no dispositivo do usuário por padrão.
3. Permitir uso offline nas funcionalidades essenciais.
4. Não exigir cadastro em serviço externo para funcionar.
5. Não exigir assinatura ou pagamento.
6. Permitir backup e exportação de dados.
7. Ter código aberto e instalação reproduzível.
8. Ser extensível por meio de módulos independentes.
9. Manter integrações externas como recursos opcionais.
10. Não enviar informações financeiras a terceiros sem autorização explícita.

---

# 4. PRINCÍPIOS OBRIGATÓRIOS DE IMPLEMENTAÇÃO

## 4.1. Priorizar a integridade financeira

Nenhuma nova funcionalidade poderá comprometer:

- Saldos existentes.
- Lançamentos históricos.
- Parcelamentos.
- Transações recorrentes.
- Orçamentos.
- Categorias.
- Limites de cartões.
- Dados informados manualmente.

A integridade financeira tem prioridade sobre funcionalidades visuais ou avançadas.

## 4.2. Separar fatos, previsões e simulações

Crie separação clara entre:

**Fatos financeiros**
- Movimentações efetivamente realizadas.
- Pagamentos confirmados.
- Saldos atuais.
- Compras existentes.
- Obrigações já assumidas.

**Previsões**
- Salários futuros.
- Despesas recorrentes ainda não pagas.
- Faturas futuras.
- Parcelas previstas.
- Compromissos futuros.
- Eventos estimados.

**Simulações**
- Compras hipotéticas.
- Mudanças de renda.
- Novas assinaturas.
- Despesas extraordinárias.
- Alterações de orçamento.

Uma simulação jamais deverá modificar os dados financeiros reais sem uma ação explícita do usuário.

## 4.3. Utilizar cálculos determinísticos

Cálculos financeiros devem ser realizados por código testável.

Não delegue a modelos de linguagem:

- Cálculo de saldos.
- Juros.
- Parcelas.
- Consolidação de receitas e despesas.
- Projeções aritméticas.
- Validação monetária.
- Regras de contabilização.

A IA poderá explicar resultados, mas não deverá ser a fonte de verdade dos valores financeiros.

## 4.4. Não inventar informações

Quando os dados estiverem incompletos:

- Mostre a limitação.
- Identifique a informação ausente.
- Utilize premissas configuráveis, quando apropriado.
- Diferencie valores conhecidos e estimados.
- Não apresente projeções incompletas como certezas.

## 4.5. Respeitar o projeto existente

Antes de qualquer alteração:

- Inspecione o código.
- Identifique bibliotecas e padrões existentes.
- Reutilize serviços e componentes.
- Evite duplicação de lógica.
- Faça alterações incrementais.
- Mantenha compatibilidade sempre que possível.

Não realize uma refatoração geral apenas por preferência arquitetural.

---

# 5. ROADMAP OBRIGATÓRIO

Execute o desenvolvimento em quatro versões progressivas.

| Versão | Objetivo | Resultado esperado |
|---|---|---|
| V1 | Controle confiável | Dados consistentes, importação e aplicação local |
| V2 | Planejamento futuro | Projeções de fluxo de caixa |
| V3 | Simulação e inteligência | Cenários, alertas e insights |
| V4 | Expansão open source | Distribuição, extensibilidade e integrações opcionais |

Cada versão possui etapas e critérios de aceitação próprios.

**Não avance para funcionalidades dependentes de uma versão anterior que ainda esteja inconsistente.**

É permitido desenvolver tarefas independentes em paralelo, mas respeite as dependências técnicas.

---

# ETAPA 0 — AUDITORIA DO PROJETO E PLANEJAMENTO

## Objetivo

Compreender profundamente a implementação atual e estabelecer um plano seguro de evolução.

### Passo 0.1 — Inspecionar o repositório

Analise:

- Estrutura de arquivos.
- Dependências.
- Componentes React.
- Rotas e páginas.
- Serviços frontend.
- Endpoints FastAPI.
- Modelos de dados.
- Esquema SQLite.
- Migrações existentes.
- Regras de negócio.
- Dashboards.
- Testes.
- Documentação.
- Processos de inicialização e build.

### Passo 0.2 — Auditar as funcionalidades financeiras

Verifique o estado de:

- Contas bancárias.
- Cartões de crédito.
- Limites.
- Lançamentos.
- Saldo inicial.
- Transferências.
- Categorias.
- Recorrências.
- Parcelamentos.
- Orçamentos.
- Previsto versus realizado.
- Dashboards.
- Alertas.
- Importações já existentes.

Classifique cada funcionalidade como:

- Implementada e funcional.
- Implementada parcialmente.
- Implementada com inconsistências.
- Não implementada.

Não reimplemente recursos já funcionais.

### Passo 0.3 — Analisar riscos

Investigue principalmente:

- Possibilidade de dupla contabilização.
- Persistência de valores monetários.
- Representação de datas.
- Relacionamento entre transações e contas.
- Relacionamento entre compras e faturas.
- Tratamento de recorrências.
- Cálculo de saldos.
- Tratamento de lançamentos futuros.
- Comportamento de exclusões e edições.
- Existência de backups e migrações.

### Passo 0.4 — Criar plano de execução

Produza um documento de auditoria, preferencialmente em `docs/IMPLEMENTATION_PLAN.md`, contendo:

1. Estado atual.
2. Funcionalidades aproveitáveis.
3. Lacunas.
4. Riscos técnicos.
5. Ajustes necessários.
6. Arquivos previstos.
7. Dependências entre etapas.
8. Estratégia de testes.
9. Estratégia de preservação dos dados.

Crie também um checklist de progresso que possa ser atualizado ao longo da implementação.

**Critério de aceitação:** todas as mudanças propostas estão relacionadas a necessidades reais identificadas no código.

---

# VERSÃO 1 — CONTROLE FINANCEIRO CONFIÁVEL

## Objetivo da versão

Construir uma base sólida para que todas as futuras análises e projeções utilizem dados corretos.

Não priorize novas funcionalidades avançadas antes de garantir a consistência do modelo financeiro.

# ETAPA 1 — CONSOLIDAÇÃO DO DOMÍNIO FINANCEIRO

## Passo 1.1 — Formalizar entidades e relacionamentos

Analise os modelos existentes e garanta que representem adequadamente, quando necessário:

- Conta financeira.
- Cartão de crédito.
- Transação.
- Categoria.
- Transferência.
- Compra parcelada.
- Parcela.
- Recorrência.
- Orçamento.
- Saldo inicial.
- Compromisso financeiro futuro.
- Origem de importação.

Não crie tabelas redundantes quando a modelagem atual já for adequada.

## Passo 1.2 — Definir estados financeiros

Diferencie claramente:

- Previsto.
- Pendente.
- Realizado/confirmado.
- Cancelado.
- Conciliado, como estado ou atributo de reconciliação.

Evite tratar previsão e realização como dois gastos distintos quando ambos representam o mesmo evento econômico.

## Passo 1.3 — Padronizar valores monetários

Adote uma representação monetária segura, compatível com a arquitetura atual.

Preferencialmente:

- Persistência em centavos inteiros para BRL.
- Utilização de `Decimal` no backend quando necessário.
- Evitar cálculos com floats.
- Exibição com formatação pt-BR.

Caso o projeto já utilize uma representação confiável, preserve-a.

Garanta regras consistentes para arredondamentos e rateio de parcelas.

## Passo 1.4 — Revisar movimentações internas

Defina regras para transferências entre contas próprias.

Uma transferência:

- Reduz o saldo da conta de origem.
- Aumenta o saldo da conta de destino.
- Não constitui receita ou despesa de consumo.

Verifique os efeitos nos relatórios consolidados.

## Passo 1.5 — Formalizar a contabilidade dos cartões

Separe os conceitos de:

- Compra.
- Parcela.
- Fatura.
- Pagamento de fatura.
- Limite disponível.
- Saldo devedor.
- Saída efetiva de caixa.

Uma compra no cartão representa consumo e obrigação financeira, mas não necessariamente redução imediata do dinheiro disponível na conta bancária.

O pagamento da fatura reduz o caixa e a dívida, sem gerar uma segunda despesa de consumo.

Estabeleça uma convenção contábil consistente para relatórios de consumo e fluxo de caixa.

## Passo 1.6 — Corrigir inconsistências

Corrija somente os problemas identificados.

Utilize migrações incrementais e testes de regressão.

Nunca apague o banco existente para simplificar alterações.

### Critérios de aceitação

- Os saldos permanecem consistentes.
- Transferências não distorcem receitas e despesas.
- Compras e faturas não são contabilizadas duas vezes.
- Parcelamentos possuem distribuição correta.
- Valores previstos e realizados são distinguíveis.
- Os dados anteriores são preservados.

---

# ETAPA 2 — IMPORTAÇÃO E CONCILIAÇÃO DE DADOS

## Objetivo

Permitir que o usuário insira dados facilmente, mesmo sem integração bancária.

## Passo 2.1 — Avaliar importadores existentes

Verifique se há importação CSV ou OFX.

Caso exista, adapte os componentes existentes.

Não crie um sistema de importação paralelo sem necessidade.

## Passo 2.2 — Desenvolver importação CSV

A importação deverá permitir:

1. Selecionar um arquivo.
2. Validar sua estrutura.
3. Identificar codificação e separadores.
4. Mapear colunas.
5. Interpretar datas e valores brasileiros.
6. Selecionar conta ou cartão.
7. Pré-visualizar registros.
8. Identificar duplicações prováveis.
9. Confirmar a importação.
10. Visualizar o resultado.

Não pressuponha formato universal de CSV bancário.

## Passo 2.3 — Desenvolver importação OFX

Implemente leitura segura de OFX, incluindo:

- Datas.
- Descrições.
- Valores.
- Identificadores.
- Tipos de movimentação.

Utilize bibliotecas apropriadas quando justificadas.

Trate variações de codificação, arquivos inválidos e registros incompletos.

## Passo 2.4 — Criar mecanismo de deduplicação

A mesma transação não pode ser registrada repetidamente.

Utilize identificadores externos estáveis quando disponíveis.

Quando não existirem, construa uma estratégia de identificação de possíveis duplicações baseada em:

- Conta.
- Data.
- Valor.
- Descrição normalizada.
- Outros identificadores disponíveis.

Hashes baseados nesses campos podem ajudar na identificação, mas não constituem prova absoluta de duplicação.

Transações ambíguas devem ser encaminhadas para revisão.

## Passo 2.5 — Criar mecanismo de conciliação

Quando uma transação importada corresponder provavelmente a um lançamento manual:

- Sugira o vínculo.
- Mostre informações comparáveis.
- Permita confirmação.
- Preserve observações e categorias personalizadas.

Evite exclusões automáticas irreversíveis.

## Passo 2.6 — Criar regras de categorização

Implemente regras determinísticas configuráveis, por exemplo:

- Descrição contendo determinado estabelecimento.
- Origem da transação.
- Conta utilizada.
- Padrões anteriormente confirmados.

Diferencie categorização sugerida de categorização confirmada.

Não utilize IA obrigatoriamente para categorizar transações.

### Critérios de aceitação

- Arquivos válidos são processados corretamente.
- Arquivos incorretos produzem erros compreensíveis.
- Há pré-visualização antes da confirmação.
- Importações repetidas não criam duplicações indevidas.
- Compras, transferências e faturas preservam suas regras contábeis.
- O usuário mantém controle sobre conciliações ambíguas.

---

# ETAPA 3 — PRIVACIDADE, USABILIDADE E CONFIABILIDADE LOCAL

## Passo 3.1 — Melhorar a experiência de primeiro uso

Crie ou revise o fluxo inicial de configuração.

O aplicativo deverá orientar o usuário a:

1. Criar uma conta financeira local.
2. Informar o saldo inicial.
3. Cadastrar cartões, caso utilize.
4. Definir categorias, caso deseje.
5. Cadastrar despesas e receitas recorrentes.
6. Importar histórico opcionalmente.
7. Acessar o dashboard.

Não exija histórico bancário para começar.

## Passo 3.2 — Implementar backup

Disponibilize mecanismos locais para:

- Criar backup.
- Restaurar backup.
- Exportar dados.
- Verificar integridade.

Evite copiar um banco SQLite em uso de maneira insegura.

Utilize mecanismos adequados para gerar backups consistentes e realizar restauração.

Se oferecer backup criptografado, utilize criptografia autenticada e gerenciamento de senha adequados.

Não anuncie backups como criptografados se não houver proteção real.

## Passo 3.3 — Garantir operação offline

Verifique se:

- O dashboard funciona sem internet.
- Lançamentos manuais funcionam offline.
- Projeções futuras poderão ser calculadas localmente.
- Não existem dependências remotas obrigatórias.
- Integrações externas indisponíveis não impedem o uso geral.

## Passo 3.4 — Revisar segurança local

Avalie:

- Restrição do backend a interfaces locais por padrão.
- Política de CORS.
- Proteção contra requisições indevidas ao serviço local.
- Validação de entradas.
- Permissões de arquivos.
- Armazenamento seguro.
- Ausência de segredos no frontend.
- Logs sem dados financeiros sensíveis desnecessários.

## Passo 3.5 — Preparar uma instalação simplificada

Analise o processo atual de inicialização.

Se ainda depender de muitos comandos técnicos, proponha uma forma simplificada de execução no Windows.

Prefira uma solução que:

- Inicie o backend local.
- Abra a interface automaticamente no navegador.
- Não exija conhecimento de Python ou Node.js do usuário final.
- Preserve os arquivos financeiros entre atualizações.

Evite adicionar uma estrutura complexa de distribuição antes de validar a viabilidade com a arquitetura atual.

### Critérios de aceitação da V1

A V1 estará pronta quando:

- Os fluxos financeiros essenciais forem confiáveis.
- Os dados existentes forem preservados.
- As importações forem funcionais.
- O usuário puder operar offline.
- O fluxo inicial for compreensível.
- Existirem mecanismos de backup e restauração.
- Os testes de regressão forem aprovados.

---

# VERSÃO 2 — PLANEJAMENTO FINANCEIRO FUTURO

## Objetivo da versão

Transformar os dados existentes em uma visão estruturada do futuro financeiro.

Esta versão deverá introduzir o primeiro grande diferencial competitivo do Minhas Finanças.

# ETAPA 4 — MODELAGEM DO MOTOR DE PROJEÇÃO

## Passo 4.1 — Criar o módulo de projeções

Desenvolva um módulo independente de cálculo financeiro.

Sugestão conceitual:

```text
backend/
  services/
    forecasting/
      ...
```

Adapte a organização à estrutura real do repositório.

Esse módulo deverá receber dados financeiros estruturados e produzir resultados determinísticos.

Evite colocar regras de projeção diretamente nos endpoints ou componentes React.

## Passo 4.2 — Definir o contrato de entrada

O motor deverá considerar:

**Posição financeira inicial**
- Saldos atuais.
- Contas selecionadas.
- Disponibilidade de recursos.
- Reservas que não devem ser utilizadas.

**Entradas futuras**
- Salários.
- Receitas recorrentes.
- Recebimentos agendados.
- Outras entradas previstas.

**Saídas futuras**
- Contas recorrentes.
- Despesas agendadas.
- Compras parceladas.
- Pagamentos de faturas.
- Compromissos extraordinários.
- Outras obrigações financeiras.

**Configurações**
- Data-base.
- Horizonte da projeção.
- Premissas.
- Eventos excluídos.
- Valores considerados confiáveis ou estimados.

O usuário deverá poder definir quais contas compõem a liquidez disponível.

Limites de cartão não poderão ser contabilizados como dinheiro em conta.

## Passo 4.3 — Definir a equação de projeção

Utilize como fundamento:

```text
Saldo projetado na data D
=
Saldo disponível na data-base
+
Entradas de caixa previstas até D
-
Saídas de caixa previstas até D
```

Essa equação deverá respeitar transferências internas, pagamentos de cartão e o estado dos lançamentos.

A contabilidade de consumo e o fluxo de caixa não são a mesma coisa.

Uma compra no cartão pode aparecer como despesa de consumo no momento da compra, enquanto sua saída de caixa ocorre no pagamento da fatura.

O motor não poderá descontar ambos do saldo bancário.

## Passo 4.4 — Criar eventos financeiros projetáveis

Formalize eventos financeiros futuros, incluindo:

- Identificador estável.
- Tipo.
- Origem.
- Data prevista.
- Valor.
- Conta afetada.
- Confiança ou natureza da informação.
- Vínculo com evento financeiro original.

Uma recorrência deverá gerar ocorrências previstas sem duplicar lançamentos já realizados.

Uma parcela já conciliada com uma transação importada não poderá ser considerada novamente como uma nova obrigação.

## Passo 4.5 — Implementar regras de recorrência

Considere:

- Diária.
- Semanal.
- Quinzenal.
- Mensal.
- Anual.
- Intervalos customizados, quando previstos.

Trate corretamente:

- Fevereiro.
- Anos bissextos.
- Meses sem o dia 29, 30 ou 31.
- Recorrências iniciadas ou encerradas no meio do período.
- Alterações de valores.
- Datas de vencimento.
- Compromissos já realizados.

Defina uma política clara para vencimentos em datas inexistentes, preferencialmente configurável ou consistente com o comportamento atual da aplicação.

Não crie múltiplas ocorrências para um mesmo evento.

## Passo 4.6 — Integrar compras parceladas

Cada compra parcelada deverá produzir obrigações futuras coerentes com:

- Valor total.
- Número de parcelas.
- Datas.
- Cartão.
- Fechamento.
- Vencimento.
- Parcelas já pagas.
- Parcelas pendentes.

Distribua eventuais diferenças de arredondamento de maneira determinística, preservando a soma total.

## Passo 4.7 — Integrar faturas de cartões

Crie uma lógica que consolide:

- Compras já realizadas.
- Parcelas futuras.
- Compromissos relacionados ao cartão.
- Datas de fechamento.
- Datas de vencimento.
- Pagamentos existentes.

Faturas já pagas não devem voltar a gerar saídas futuras.

Faturas ainda não pagas devem gerar saída de caixa na data apropriada.

## Passo 4.8 — Distinguir certeza e estimativa

Classifique os componentes da projeção, por exemplo:

- Confirmado: obrigação conhecida ou transação agendada confirmada.
- Planejado: lançamento informado pelo usuário.
- Estimado: valor derivado de premissa ou histórico.
- Não informado: informação indisponível.

Não converta automaticamente estimativas em compromissos confirmados.

### Critérios de aceitação

- O motor calcula corretamente os fluxos diários.
- É possível projetar 30, 60 e 90 dias.
- O resultado é reproduzível com as mesmas entradas.
- Não existe dupla contabilização.
- Recorrências e parcelas são geradas corretamente.
- Os cálculos não dependem de IA.
- Dados incompletos são identificados.

---

# ETAPA 5 — CÁLCULO DE INDICADORES PREDITIVOS

## Objetivo

Transformar a linha do tempo projetada em indicadores financeiros compreensíveis.

## Passo 5.1 — Calcular saldos futuros

Produza:

- Saldo projetado por dia.
- Saldo projetado por mês.
- Saldo ao final de 30 dias.
- Saldo ao final de 60 dias.
- Saldo ao final de 90 dias.
- Menor saldo previsto no horizonte.
- Datas de maior pressão financeira.

## Passo 5.2 — Identificar risco de saldo insuficiente

Detecte quando o saldo projetado fica abaixo de:

- Zero.
- Reserva mínima configurada.
- Outro limite definido pelo usuário.

Informe:

- Data.
- Valor projetado.
- Compromissos relacionados.
- Premissas utilizadas.

Não apresente risco como certeza absoluta quando depender de receitas ou despesas estimadas.

## Passo 5.3 — Calcular comprometimento futuro

Produza indicadores como:

- Renda comprometida por recorrências.
- Comprometimento com parcelas.
- Faturas futuras.
- Despesas obrigatórias previstas.
- Valores potencialmente livres após compromissos conhecidos.

Não trate todo saldo positivo como dinheiro disponível para consumo.

## Passo 5.4 — Desenvolver um indicador de capacidade de gasto

Crie um indicador orientativo que responda:

> Quanto posso gastar hoje considerando os compromissos futuros conhecidos?

Ele deverá considerar:

- Liquidez atual.
- Fluxos futuros.
- Menor saldo projetado.
- Reserva mínima configurada.
- Compromissos já assumidos.
- Horizonte selecionado.

Uma abordagem inicial é calcular a folga de caixa mínima do período em relação à reserva configurada.

Não confunda esse valor com garantia de segurança financeira.

Evite truncar silenciosamente valores negativos em zero; sinalize claramente insuficiência de recursos.

Apresente o cálculo de forma explicável e permita que o usuário examine as premissas.

Se os dados forem insuficientes, mostre que a estimativa é incompleta.

## Passo 5.5 — Desenvolver testes financeiros

Crie cenários sintéticos como:

1. Salário mensal e despesas fixas.
2. Salário atrasado.
3. Compra parcelada.
4. Várias faturas no mesmo mês.
5. Transferência entre contas.
6. Despesa extraordinária.
7. Mês com saldo negativo.
8. Recorrência com vencimento em dia inexistente.
9. Pagamento parcial ou antecipado de fatura, caso suportado.
10. Ausência de receitas futuras.

Valide resultados esperados numericamente.

### Critérios de aceitação

Todos os indicadores derivam do mesmo mecanismo de projeção, sem fórmulas independentes e inconsistentes no frontend.

---

# ETAPA 6 — INTERFACE DE PLANEJAMENTO FINANCEIRO

## Objetivo

Apresentar projeções de forma intuitiva, visual e acionável.

## Passo 6.1 — Criar a seção "Planejamento"

Adicione uma página ou módulo de planejamento à navegação existente.

A página deverá apresentar:

- Visão de futuro financeiro.
- Horizonte selecionável.
- Saldo projetado.
- Compromissos futuros.
- Indicadores.
- Alertas.
- Premissas.

## Passo 6.2 — Criar visualização temporal

Implemente um gráfico de evolução de saldo.

Requisitos:

- Horizonte de 30, 60 e 90 dias.
- Visualização diária ou agregada.
- Linha de saldo projetado.
- Distinção entre histórico e futuro.
- Indicadores de compromissos relevantes.
- Destaque para períodos de risco.

Não utilize cores como único meio de comunicar risco.

## Passo 6.3 — Criar cards de indicadores

Considere:

- Saldo atual.
- Saldo projetado.
- Menor saldo previsto.
- Próximas obrigações.
- Comprometimento financeiro.
- Capacidade orientativa de gasto.

Os cards devem evitar redundância e utilizar rótulos claros.

## Passo 6.4 — Criar calendário financeiro

Desenvolva uma visualização dos eventos futuros.

Permita identificar:

- Data.
- Tipo.
- Valor.
- Origem.
- Estado.
- Impacto no fluxo de caixa.

Agrupe eventos quando necessário para evitar poluição visual.

## Passo 6.5 — Exibir explicações

Ao selecionar um indicador, mostre os componentes responsáveis pelo resultado.

Exemplo:

```text
Saldo projetado em 30 dias:

Saldo atual          R$ 5.000
Entradas previstas  +R$ 4.000
Despesas previstas  -R$ 2.300
Faturas futuras     -R$ 1.800
--------------------------------
Saldo projetado      R$ 4.900
```

Use dados reais da aplicação. Valores acima são ilustrativos.

## Passo 6.6 — Implementar estados vazios e incompletos

Quando o usuário não tiver cadastrado informações suficientes:

- Explique o motivo.
- Mostre quais dados são necessários.
- Ofereça ações para completar a configuração.
- Não apresente previsões artificiais.

### Critérios de aceitação da V2

A V2 estará pronta quando:

- O fluxo de caixa futuro for calculado corretamente.
- Os cartões e parcelamentos estiverem integrados.
- O usuário puder identificar compromissos futuros.
- Existirem indicadores para diferentes horizontes.
- Os números forem explicáveis.
- As limitações dos dados forem visíveis.
- Os cálculos forem consistentes entre backend e frontend.

---

# VERSÃO 3 — SIMULAÇÃO E INTELIGÊNCIA FINANCEIRA

## Objetivo da versão

Permitir que o usuário deixe de apenas observar suas finanças e passe a testar decisões antes de executá-las.

# ETAPA 7 — MOTOR DE SIMULAÇÃO DE CENÁRIOS

## Passo 7.1 — Criar um módulo de simulação

Desenvolva um serviço independente para cenários hipotéticos.

Ele deverá reutilizar o motor de projeção desenvolvido na V2.

Evite manter dois mecanismos diferentes de cálculo financeiro.

## Passo 7.2 — Estabelecer o cenário-base

O cenário-base representa o futuro financeiro calculado com os dados e premissas atuais.

Toda simulação deverá comparar:

- Cenário-base.
- Cenário alternativo.

A simulação deve utilizar uma versão consistente dos dados de origem, identificando quando o cenário-base estiver desatualizado por novas transações.

## Passo 7.3 — Criar eventos hipotéticos

Permita simular:

**Compras**
- Compra à vista.
- Compra parcelada.
- Diferentes quantidades de parcelas.
- Diferentes datas.
- Diferentes cartões.

**Receitas**
- Aumento de renda.
- Redução de renda.
- Atraso em recebimentos.
- Receita extraordinária.

**Despesas**
- Nova assinatura.
- Cancelamento de assinatura.
- Aumento de despesa recorrente.
- Redução de determinado gasto.
- Despesa extraordinária.

**Reservas**
- Alteração de reserva mínima.
- Destinação de recursos para uma meta.
- Alteração na disponibilidade de recursos.

Cada evento deverá possuir identificador e representação própria, sem ser confundido com lançamentos reais.

## Passo 7.4 — Garantir isolamento

Uma simulação:

- Não pode modificar saldos reais.
- Não pode criar despesas reais automaticamente.
- Não pode alterar orçamentos permanentes.
- Não pode gerar pagamentos.
- Não pode modificar compras existentes.

O usuário poderá optar por transformar determinada decisão simulada em um compromisso real, mas isso exigirá uma ação explícita de confirmação.

## Passo 7.5 — Comparar cenários

Calcule para cada cenário:

- Saldo final.
- Menor saldo previsto.
- Diferença em relação ao cenário-base.
- Datas com saldo insuficiente.
- Comprometimento mensal.
- Efeito sobre reservas.
- Impacto nos próximos meses.

## Passo 7.6 — Implementar sensibilidade

Permita variar parâmetros como:

- Valor da compra.
- Número de parcelas.
- Data da compra.
- Renda.
- Despesa mensal.
- Reserva mínima.

Recalcule os resultados de forma determinística.

Não gere infinitos cenários sem controle. Estabeleça limites razoáveis de processamento.

### Critérios de aceitação

- Cenários são isolados dos dados reais.
- Resultados são reproduzíveis.
- A comparação utiliza o mesmo motor financeiro da V2.
- Compras parceladas respeitam regras de cartão.
- Mudanças na renda e nas despesas alteram corretamente a projeção.
- O cenário-base não é modificado.

---

# ETAPA 8 — INTERFACE DO SIMULADOR FINANCEIRO

## Passo 8.1 — Criar a seção "Simulador"

Implemente uma interface com:

- Seleção do tipo de decisão.
- Formulário contextual.
- Configuração de parâmetros.
- Execução da simulação.
- Comparação visual.
- Explicação dos resultados.

## Passo 8.2 — Criar simulação de compra

Exemplo de interação:

```text
Simular uma compra

Valor: R$ 2.400

Forma de pagamento:
[À vista] [Cartão de crédito]

Número de parcelas: 6

Cartão: Cartão principal

[Simular impacto]
```

Ao executar, mostre:

- Distribuição temporal da obrigação.
- Faturas afetadas.
- Alteração do saldo.
- Meses com maior comprometimento.
- Diferença em relação ao cenário atual.

O usuário deverá compreender o impacto sem precisar interpretar cálculos complexos.

## Passo 8.3 — Criar comparação gráfica

Apresente duas séries:

- Situação atual projetada.
- Situação com a decisão simulada.

Permita visualizar a diferença ao longo do tempo.

## Passo 8.4 — Criar resumo explicativo

Exemplo ilustrativo:

> A compra elevaria o comprometimento das próximas seis faturas e reduziria a menor folga de caixa projetada nos próximos 90 dias.

As explicações devem ser produzidas a partir dos resultados efetivos.

Evite afirmar que uma compra é segura ou insegura sem premissas explícitas.

## Passo 8.5 — Permitir salvar cenários

Caso seja viável e coerente com o modelo existente, disponibilize:

- Salvar cenário.
- Renomear.
- Comparar cenários.
- Excluir cenário.
- Reexecutar com dados atualizados.

Diferencie claramente cenários salvos de obrigações reais.

### Critérios de aceitação

O usuário consegue simular decisões, compreender consequências e comparar alternativas sem modificar suas finanças reais.

---

# ETAPA 9 — INSIGHTS FINANCEIROS AUTOMÁTICOS

## Objetivo

Gerar análises úteis sobre comportamentos, compromissos e possíveis riscos financeiros.

A primeira implementação deve utilizar regras determinísticas e métodos estatísticos simples.

## Passo 9.1 — Criar o motor de insights

Implemente um módulo independente para analisar:

- Histórico de despesas.
- Categorias.
- Recorrências.
- Orçamentos.
- Fluxo de caixa.
- Projeções.
- Comprometimento futuro.

Cada insight deverá conter:

- Identificador.
- Tipo.
- Título.
- Descrição.
- Métrica relacionada.
- Período analisado.
- Evidências.
- Critério utilizado.
- Grau de prioridade.
- Ação sugerida, quando apropriado.

## Passo 9.2 — Implementar detecção de alterações de gastos

Identifique situações como:

- Aumento relevante em uma categoria.
- Aumento de despesa recorrente.
- Gastos acima do orçamento.
- Concentração de despesas em determinado período.
- Redução relevante de saldo futuro.
- Comprometimento crescente com parcelas.

Utilize regras transparentes e limiares configuráveis.

Evite classificar como anomalia uma alteração quando houver histórico insuficiente.

## Passo 9.3 — Identificar recorrências e assinaturas

Analise movimentos que possam indicar:

- Assinaturas periódicas.
- Despesas regulares.
- Cobranças de valor semelhante.
- Aumentos de mensalidades.
- Possíveis serviços esquecidos.

Trate correspondências como sugestões, não como certezas.

## Passo 9.4 — Criar alertas preventivos

Exemplos:

- Saldo futuro abaixo da reserva mínima.
- Fatura com elevado comprometimento.
- Orçamento próximo do limite.
- Compromissos concentrados em um período.
- Aumento expressivo de despesa recorrente.
- Divergência entre dados previstos e realizados.

Garanta que alertas repetidos não provoquem excesso de notificações.

## Passo 9.5 — Criar explicabilidade

Todo insight deverá responder:

1. O que foi identificado?
2. Qual evidência sustenta a análise?
3. Qual período foi considerado?
4. Por que isso importa?
5. Existe alguma ação possível?
6. Quais são as limitações da conclusão?

Não apresente correlação como causalidade.

Não gere recomendações de investimento ou crédito personalizadas como se fossem aconselhamento profissional.

## Passo 9.6 — Integrar os insights ao dashboard

Crie uma seção de insights priorizados.

Utilize linguagem simples, evitando excesso de alertas.

Permita ao usuário:

- Ver detalhes.
- Dispensar um insight.
- Ajustar preferências.
- Consultar a origem da análise.

### Critérios de aceitação

- Insights derivam de dados reais.
- Todas as análises possuem evidências.
- Os limiares são transparentes.
- Não existem conclusões inventadas.
- A aplicação permanece utilizável sem IA externa.

---

# ETAPA 10 — CAMADA OPCIONAL DE INTELIGÊNCIA ARTIFICIAL

## Objetivo

Avaliar e, quando justificável, acrescentar uma interface inteligente para explicar as finanças em linguagem natural.

**Esta etapa é opcional e não deve comprometer a gratuidade nem a privacidade do aplicativo.**

## Passo 10.1 — Avaliar a necessidade

Antes de implementar, identifique se existe algum benefício real que não possa ser atendido satisfatoriamente por regras determinísticas e visualizações convencionais.

Não adicione IA apenas para demonstrar utilização de LLMs.

## Passo 10.2 — Criar arquitetura independente

Caso seja implementada, a IA deverá receber resultados financeiros previamente calculados.

Exemplo:

```text
Dados locais
    ↓
Motor financeiro determinístico
    ↓
Indicadores e evidências
    ↓
Camada de interpretação
    ↓
Explicação ao usuário
```

A IA não poderá modificar lançamentos nem executar operações financeiras sem mecanismos explícitos de autorização e validação.

## Passo 10.3 — Definir funcionalidades

Exemplos:

- Explicar mudanças nos gastos.
- Resumir compromissos futuros.
- Interpretar cenários.
- Responder perguntas sobre indicadores.
- Apresentar análises em linguagem natural.

## Passo 10.4 — Preservar privacidade

Priorize uma integração opcional.

Se utilizar modelos locais, documente:

- Requisitos de hardware.
- Limitações.
- Desempenho.
- Dependências.

Se utilizar API externa, exija:

- Configuração individual.
- Consentimento explícito.
- Transparência sobre os dados enviados.
- Minimização das informações compartilhadas.
- Possibilidade de desativação completa.

Não envie dados bancários automaticamente para provedores de IA.

## Passo 10.5 — Implementar verificações

Garanta que:

- Valores exibidos sejam consistentes com o backend.
- O modelo não invente transações.
- As respostas não contradigam os indicadores.
- Falhas da IA não interrompam o aplicativo.
- O usuário possa identificar informações insuficientes.

### Critérios de aceitação da V3

A V3 estará pronta quando:

- O simulador funcionar com dados reais e cenários hipotéticos.
- As projeções forem corretamente reutilizadas.
- Os insights forem rastreáveis.
- As decisões simuladas não afetarem dados reais.
- O sistema continuar utilizável sem IA.
- As limitações das análises forem explicitadas.

---

# VERSÃO 4 — EXPANSÃO E DISTRIBUIÇÃO OPEN SOURCE

## Objetivo da versão

Transformar o projeto em um produto instalável, documentado, extensível e utilizável por outras pessoas.

# ETAPA 11 — ARQUITETURA DE INTEGRAÇÕES OPCIONAIS

## Passo 11.1 — Criar uma interface para fontes de dados

O sistema deverá permitir que os dados tenham diferentes origens:

- Cadastro manual.
- CSV.
- OFX.
- APIs externas futuras.

Mantenha uma camada comum de normalização e conciliação.

## Passo 11.2 — Avaliar Open Finance

Analise a viabilidade de importações locais adicionais compatíveis com instituições brasileiras.

Antes de implementar:

- Verifique documentação atual.
- Confirme as condições de uso.
- Identifique requisitos de credenciais.
- Avalie limitações da modalidade gratuita.
- Avalie a compatibilidade com distribuição open source.

Não assuma que uma API gratuita para uso pessoal pode ser livremente utilizada em qualquer modelo de distribuição.

## Passo 11.3 — Permitir configuração individual

Caso uma integração seja viável:

- Cada usuário terá suas credenciais.
- Nenhuma chave será compartilhada pelo desenvolvedor.
- Os dados ficarão associados à instalação individual.
- A integração será opcional.
- O aplicativo continuará funcionando sem conexão bancária.

Não crie infraestrutura centralizada desnecessária.

## Passo 11.4 — Reutilizar o mecanismo de importação

Transações obtidas por API deverão seguir o mesmo processamento usado por CSV e OFX:

1. Obtenção.
2. Validação.
3. Normalização.
4. Identificação de duplicações.
5. Reconciliação.
6. Persistência.
7. Atualização dos indicadores.

Não permita que cada conector implemente regras financeiras próprias e divergentes.

## Passo 11.5 — Definir gatilho de implementação

A integração automática não deve bloquear o lançamento do produto.

Implemente conectores bancários apenas quando:

- O produto central estiver estável.
- As condições de uso estiverem confirmadas.
- O modelo de autenticação for seguro.
- A integração for realmente útil aos usuários.

### Critérios de aceitação

A arquitetura permite adicionar fontes externas sem reescrever o sistema financeiro, e nenhuma integração paga se torna obrigatória.

---

# ETAPA 12 — INSTALAÇÃO, DOCUMENTAÇÃO E EXPERIÊNCIA OPEN SOURCE

## Passo 12.1 — Preparar a distribuição

Avalie uma forma confiável de distribuição no Windows.

A experiência ideal deverá permitir:

1. Baixar o aplicativo.
2. Instalar ou extrair.
3. Executar.
4. Abrir a interface local.
5. Criar sua configuração.
6. Começar a utilizar.

Evite exigir comandos técnicos de quem deseja apenas usar a aplicação.

Preserve um processo separado para desenvolvedores.

## Passo 12.2 — Organizar o repositório

Respeite a organização existente, mas garanta separação clara entre:

- Frontend.
- Backend.
- Modelos financeiros.
- Motor de projeções.
- Motor de simulações.
- Motor de insights.
- Integrações.
- Testes.
- Documentação.

Não imponha uma nova estrutura sem necessidade.

## Passo 12.3 — Criar documentação do usuário

O README deverá apresentar:

- Descrição do projeto.
- Proposta de valor.
- Principais diferenciais.
- Imagens da aplicação.
- Funcionalidades disponíveis.
- Requisitos.
- Instalação.
- Configuração.
- Importação de dados.
- Privacidade.
- Backup.
- Limitações conhecidas.
- Roadmap.

Diferencie funcionalidades disponíveis, experimentais e planejadas.

## Passo 12.4 — Criar documentação técnica

Inclua informações sobre:

- Arquitetura.
- Modelo de dados.
- Regras financeiras.
- Projeções.
- Simulações.
- Estratégia de testes.
- Segurança.
- Extensibilidade.
- Desenvolvimento local.

Documente especialmente as decisões contábeis, pois são essenciais para futuras contribuições.

## Passo 12.5 — Preparar contribuições externas

Avalie e implemente:

- `CONTRIBUTING.md`.
- Orientações de instalação para desenvolvedores.
- Testes automatizados.
- Linters.
- Configuração de CI.
- Templates de issues.
- Modelo de pull requests.
- Política para reportar vulnerabilidades.
- Licença open source apropriada.

Verifique a compatibilidade das licenças das dependências antes da escolha definitiva.

Não publique alterações nem configure o repositório remoto sem autorização.

## Passo 12.6 — Criar dados demonstrativos

Disponibilize dados sintéticos para demonstração.

Eles deverão permitir testar:

- Dashboard.
- Orçamentos.
- Cartões.
- Parcelamentos.
- Projeções.
- Cenários.
- Insights.

Não utilize dados financeiros reais.

### Critérios de aceitação da V4

A V4 estará pronta quando:

- Um novo usuário puder instalar e utilizar o aplicativo.
- O fluxo inicial for compreensível.
- O projeto possuir documentação adequada.
- Os dados estiverem protegidos.
- A instalação não exigir serviços externos obrigatórios.
- Outros desenvolvedores conseguirem executar os testes.
- A aplicação possuir uma proposta de valor clara e demonstrável.

---

# 6. ESTRATÉGIA GLOBAL DE TESTES

Os testes são obrigatórios em todas as versões.

## 6.1. Testes unitários

Cubra:

- Valores monetários.
- Datas.
- Recorrências.
- Parcelamentos.
- Faturas.
- Transferências.
- Projeções.
- Simulações.
- Insights.

## 6.2. Testes de integração

Valide:

- Endpoints FastAPI.
- Modelos SQLite.
- Migrações.
- Importações.
- Persistência de cenários.
- Atualização dos dashboards.

## 6.3. Testes de regressão

Antes e depois de cada versão, confirme que:

- Saldos históricos continuam corretos.
- Transações não são perdidas.
- Compras não são duplicadas.
- Orçamentos permanecem corretos.
- Recorrências funcionam.
- A aplicação inicia normalmente.

## 6.4. Testes de propriedades financeiras

Implemente verificações de invariantes, como:

- A soma das parcelas corresponde ao valor original.
- Transferências internas não alteram o patrimônio consolidado quando não existem taxas ou efeitos externos.
- Sincronizações repetidas não multiplicam lançamentos.
- Uma simulação não modifica o estado real.
- O saldo projetado corresponde à soma dos fluxos de caixa considerados.
- O pagamento de fatura não duplica a despesa de consumo.

## 6.5. Testes de casos extremos

Inclua:

- Saldo negativo.
- Ausência de saldo inicial.
- Dados incompletos.
- Múltiplos cartões.
- Múltiplas contas.
- Meses com diferentes quantidades de dias.
- Ano bissexto.
- Transações repetidas.
- Parcelamentos longos.
- Alterações de receitas.
- Cancelamentos de recorrências.
- Pagamentos antecipados, quando suportados.
- Backups e restaurações.
- Indisponibilidade de serviços externos.

## 6.6. Testes de interface

Garanta:

- Estados vazios.
- Mensagens de erro.
- Indicadores de carregamento.
- Responsividade.
- Navegação por teclado.
- Contraste adequado.
- Formatação monetária.
- Leitura compreensível dos gráficos.
- Clareza entre valores realizados, previstos e simulados.

---

# 7. DIRETRIZES DE EXPERIÊNCIA DO USUÁRIO

A evolução do aplicativo deverá priorizar simplicidade e compreensão.

## 7.1. Evitar excesso de informação

Nem todo indicador precisa aparecer no dashboard principal.

Priorize os elementos que respondem às perguntas mais importantes.

As análises detalhadas deverão ser acessíveis em seções específicas.

## 7.2. Manter consistência visual

Preserve a identidade atual:

- Preto.
- Creme.
- Tons de cinza.
- Tipografia consistente.
- Cards minimalistas.
- Hierarquia visual clara.
- Espaçamentos equilibrados.

Use cores de alerta quando semanticamente necessárias e com contraste adequado.

## 7.3. Facilitar a interpretação

Prefira:

> Seu menor saldo projetado nos próximos 30 dias é R$ 850.

Em vez de:

> Indicador de liquidez mínima temporal: 850.

Os indicadores podem ter nomes técnicos internamente, mas a interface deverá priorizar linguagem comum.

## 7.4. Evitar promessas financeiras indevidas

Não utilize frases como:

- "Essa compra é totalmente segura."
- "Você não terá problemas financeiros."
- "Você pode gastar sem preocupação."

Prefira:

> Considerando as receitas, despesas e reservas informadas, o saldo projetado permanece acima do mínimo configurado.

Explique sempre que projeções dependem das informações e premissas disponíveis.

## 7.5. Privacidade como característica visível

Deixe claro:

- Onde os dados são armazenados.
- Quais funcionalidades funcionam offline.
- Se uma integração externa está ativa.
- Que informações poderão sair do dispositivo.
- Como criar backups.
- Como exportar ou excluir dados.

---

# 8. REGRAS DE EXECUÇÃO PARA O AGENTE

Execute o trabalho de forma incremental.

Para cada etapa:

1. Leia os arquivos relevantes.
2. Confirme o estado atual.
3. Defina a implementação mínima necessária.
4. Identifique os arquivos que serão modificados.
5. Faça as alterações.
6. Execute verificações estáticas.
7. Execute testes automatizados.
8. Corrija falhas introduzidas.
9. Registre resultados.
10. Atualize o checklist de progresso.
11. Continue para a etapa seguinte quando seus critérios forem atendidos.

Evite implementar todas as funcionalidades de uma versão em uma única alteração grande.

Prefira entregas verticais que incluam modelo, backend, frontend e testes de uma funcionalidade por vez.

### Restrições

- Não apague dados existentes.
- Não reestruture todo o projeto sem necessidade.
- Não crie dependências pagas obrigatórias.
- Não implemente integrações externas sem verificar seus contratos.
- Não inclua credenciais reais.
- Não utilize dados reais nos testes automatizados.
- Não altere silenciosamente regras contábeis.
- Não coloque cálculos financeiros críticos apenas no frontend.
- Não utilize LLMs como mecanismo de cálculo monetário.
- Não introduza telemetria financeira automática.
- Não inclua elementos gráficos que prejudiquem acessibilidade.
- Não considere concluídas funcionalidades que não tenham sido testadas.
- Não faça commits, push ou publicações sem autorização explícita.

Em caso de bloqueio técnico, documente o problema e avance nas tarefas independentes.

Caso o ambiente não permita concluir alguma etapa, registre claramente o que falta e como reproduzir a validação.

---

# 9. CRITÉRIOS GLOBAIS DE QUALIDADE

A implementação deverá atender a cinco dimensões.

## 9.1. Correção financeira

Valores corretos, regras consistentes e ausência de duplicação.

## 9.2. Qualidade arquitetural

Separação de responsabilidades, modularidade e reutilização.

## 9.3. Segurança e privacidade

Dados locais, armazenamento apropriado e integrações opcionais.

## 9.4. Experiência do usuário

Interface compreensível, agradável e coerente com o design existente.

## 9.5. Sustentabilidade do projeto

Documentação, testes, distribuição e facilidade de manutenção.

O sucesso da implementação não deverá ser medido apenas pelo número de funcionalidades criadas.

---

# 10. RELATÓRIO OBRIGATÓRIO POR VERSÃO

Ao concluir cada versão, gere um relatório técnico contendo:

### A. Funcionalidades entregues
Liste somente funcionalidades realmente implementadas.

### B. Modificações realizadas
Apresente arquivos criados, modificados e suas responsabilidades.

### C. Arquitetura
Explique novas entidades, serviços e decisões técnicas.

### D. Integridade financeira
Descreva como foram evitadas inconsistências, duplicações e alterações indevidas.

### E. Interface
Indique as páginas e componentes adicionados ou modificados.

### F. Testes
Apresente os testes realmente executados, comandos e resultados.

### G. Pendências
Identifique limitações, problemas conhecidos e validações não realizadas.

### H. Próxima versão
Descreva o estado necessário para continuar o desenvolvimento.

Não apresente testes como aprovados quando não tiverem sido executados.

---

# 11. DEFINIÇÃO FINAL DE SUCESSO DO PRODUTO

O Minhas Finanças deverá evoluir para uma aplicação capaz de responder:

**1. Controle**
> Quanto recebi, quanto gastei e para onde foi meu dinheiro?

**2. Planejamento**
> Quais compromissos terei e como estará meu saldo nos próximos meses?

**3. Decisão**
> Como uma nova compra ou mudança de renda afetará minhas finanças?

**4. Inteligência**
> Quais padrões, riscos e oportunidades merecem minha atenção?

**5. Privacidade**
> Posso utilizar a aplicação com meus dados locais, sem depender de assinaturas e serviços externos obrigatórios?

Essas cinco capacidades representam a visão de produto.

---

# 12. INSTRUÇÃO FINAL DE EXECUÇÃO

Inicie imediatamente pela **ETAPA 0 — Auditoria do projeto**.

Não assuma que a aplicação está vazia.

Analise o repositório real e construa um plano adaptado às funcionalidades existentes.

Em seguida:

1. Execute a V1, corrigindo e consolidando apenas o que for necessário.
2. Valide a base financeira.
3. Desenvolva a V2, priorizando o motor de projeção e sua interface.
4. Desenvolva a V3, reutilizando o motor de projeção para simulações e insights.
5. Prepare a V4, focando distribuição, documentação e extensibilidade.
6. Trate Open Finance e IA externa como integrações opcionais, não como pré-requisitos do produto.

Não interrompa a implementação para solicitar confirmações sobre decisões técnicas rotineiras que possam ser tomadas com segurança a partir do código.

Solicite intervenção humana apenas em decisões com implicações relevantes e não inferíveis, uso de credenciais, operações destrutivas, permissões externas ou publicação.

**Objetivo final: entregar uma plataforma financeira pessoal confiável, extensível e agradável de utilizar, cujo principal diferencial seja transformar informações financeiras em planejamento e decisões fundamentadas.**

Priorize a precisão e a confiabilidade da engenharia financeira acima da complexidade tecnológica.

O produto deve ser útil mesmo sem IA, sem Open Finance e sem conexão com a internet.
