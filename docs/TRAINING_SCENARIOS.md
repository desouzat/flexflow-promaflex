# FlexFlow - Guia de Treinamento Operacional

Este documento contém os fluxos de treinamento e cenários operacionais oficiais para capacitação das equipes comercial, PCP, logística e diretoria no sistema FlexFlow.

---

## Cenário 1: Importação Padrão (Fluxo Feliz)
**Objetivo:** Importar uma planilha de pedidos sem pendências, validar dados na Mesa de Conferência, preencher a Unidade de Negócio e confirmar o pedido no Kanban.

### Passo a Passo:
1. **Upload do Arquivo:** Acesse a página **Importar Pedido**, arraste ou selecione a planilha de pedidos padrão (layout ONET de 22 campos).
2. **Mapeamento de Colunas:** Verifique o mapeamento das colunas. As colunas obrigatórias são automaticamente identificadas pelo sistema.
3. **Mesa de Conferência (Staging Area):**
   - Visualize os pedidos importados na tela.
   - O sistema irá buscar a preferência de **Unidade de Negócio** do cliente no histórico (`client_preferences`). Se for a primeira vez do cliente, o motor de classificação por Regex irá preencher o valor padrão automaticamente (ex: nomes com "LTDA" ou "S/A" podem ser direcionados a *Indústria* ou *Varejo*).
   - O usuário revisará se a **Unidade de Negócio** sugerida está correta. Caso contrário, selecione manualmente no dropdown: `Indústria`, `Construção Civil`, `Varejo` ou `Outros`.
   - Selecione obrigatoriamente o **Tipo de Embalagem** no dropdown (ex: *Palete*, *Caixa de Papelão*, *Fardo Plástico*).
   - Marque a checkbox **Checado** de todos os itens do pedido.
4. **Validação de Margem:** O sistema exibe o extrato de margem em tempo real. Se o custo do SKU estiver cadastrado, a margem será calculada usando a Fórmula do Celso: `CM = (VP - Impostos 22.25% - Comissão - Frete) / Custos`.
5. **Garantia de Confirmação:** O botão **Confirmar Pedido** só será habilitado se todos os itens estiverem checados, sem erros de integridade financeira e se todos os pedidos possuírem um Tipo de Embalagem e uma Unidade de Negócio selecionados.
6. **Confirmação:** Clique em **Confirmar Pedido**. O pedido é persistido no banco e entra na coluna **Comercial** do Kanban. O vínculo de preferência do cliente é salvo em banco para futuras importações do mesmo cliente.

---

## Cenário 2: Exceção de Crédito (Bloqueio Financeiro)
**Objetivo:** Simular a importação de um pedido cujos itens possuem status `BLOQUEADO` ou justificativa financeira no faturamento, ativando a regra de desvio para análise de crédito e a liberação por usuário Master.

### Passo a Passo:
1. **Importação:** Importe uma planilha contendo itens com a coluna de bloqueio preenchida como `BLOQUEADO` ou com justificativa financeira.
2. **Mesa de Conferência:** O sistema detectará o bloqueio e exibirá um alerta vermelho na Mesa de Conferência.
3. **Bypass de Troca/Devolução (Opcional):** Se o pedido for do tipo reposição ou garantia, o usuário pode marcar a opção **Troca/Devolução**. Isso ativa o bypass e altera o status para `CRÉDITO PRÉ-APROVADO (TROCA)`.
4. **Confirmação e Roteamento:** Ao confirmar o pedido, ele será enviado automaticamente para a coluna **Financeiro** no status **ANALISE_CREDITO**.
5. **Aprovação Financeira:**
   - Um usuário operador comum visualizará o pedido travado.
   - Um usuário **Master** ou **Admin** poderá abrir os detalhes do pedido no Kanban e clicar no botão **Aprovar Crédito**, inserindo uma justificativa.
   - Após a liberação manual, o pedido é liberado para a próxima etapa produtiva (PCP/Produção).

---

## Cenário 3: Exceção Logística (Partição de Pedidos)
**Objetivo:** Realizar a quebra (split) de um pedido em lotes parciais pelo PCP, recalculando fretes e organizando a expedição.

### Passo a Passo:
1. **Entrada no PCP:** Um pedido aprovado comercialmente entra na coluna **PCP**.
2. **Sugestão de Partição:** O PCP identifica que parte da carga não pode ser produzida imediatamente ou precisa de datas de entrega distintas.
3. **Interface de Partição:**
   - Clique no pedido e acesse a ferramenta de **Partição**.
   - Defina as quantidades para o Lote A e Lote B.
   - Selecione a estratégia de frete (ex: *Frete Proporcional*, *Atribuir tudo ao Lote A*, ou *Redefinir Manualmente*).
4. **Processamento:**
   - O pedido original (Pai) é arquivado sob o status `ARCHIVED_PARTITIONED`.
   - Dois novos pedidos filhos são criados (`Filho A` e `Filho B`), herdando os históricos e mantendo o vínculo com o ID original.
   - Suas margens são recalculadas dinamicamente com base nas frações de custo e frete definidas.
5. **Confirmação:** Os pedidos filhos seguem fluxos de produção e expedição independentes.

---

## Cenário 4: Ingestão Incremental de Custos (Tabela do Celso)
**Objetivo:** Fazer upload de uma nova planilha de custos de matéria-prima, recalculando margens e limpando badges de pendência no Kanban de forma automática.

### Passo a Passo:
1. **Status Inicial:** No Kanban, se houver SKUs sem custos industriais cadastrados, os pedidos exibirão uma badge cinza escrito `PENDENTE PCP` e a margem será omitida.
2. **Upload de Custos:**
   - Acesse **Gerenciar Custos** (exclusivo para perfil MASTER).
   - Clique em **Importar Planilha**.
   - Selecione a planilha de custos configurada sob o layout estrito do Celso:
     - Coluna A: `Material` (SKU e nome do material).
     - Coluna B: `Rendimento` (kg/m²).
     - Coluna D: `CUSTO KG` (R$/kg).
3. **Cálculo de Custo M2:** O endpoint calcula o custo por metro quadrado dividindo exatamente: `Custo M2 = CUSTO KG / RENDIMENTO`.
4. **Gatilho de Limpeza (Cleanup Trigger):**
   - O banco de dados realiza o upsert dos valores (inserindo novos ou atualizando existentes).
   - O sistema dispara uma revalidação global imediata de todos os pedidos no Kanban que possuem os SKUs atualizados.
   - Os pedidos que estavam com a badge `PENDENTE PCP` devido a esses SKUs têm suas margens recalculadas e as badges removidas automaticamente.
