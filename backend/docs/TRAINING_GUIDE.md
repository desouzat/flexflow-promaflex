# Guia de Treinamento e Demonstração Operacional — FlexFlow

Este documento descreve o passo a passo operacional para demonstração técnica das principais funcionalidades do sistema FlexFlow durante o treinamento de go-live.

---

## 1. Login no Sistema

### Usuários de Teste Disponíveis:
* **Administrador (Thiago):**
  - **E-mail:** `test@example.com`
  - **Senha:** `password123`
  - **Permissões:** Acesso total a todas as colunas, gestão de usuários e tela de configurações globais.
* **Operador (Fábio):**
  - **E-mail:** `fabio_promaflex@grupovelletri.com.br`
  - **Senha:** `Proma@2026`
  - **Permissões:** Visualização restrita do Kanban (Margens e Custos mascarados como `***`), sem acesso a usuários ou configurações.

---

## 2. Fluxo 1: Caminho Feliz (Happy Path)

### Passo 1: Mesa de Conferência (Staging)
1. Acesse o menu **Import POs**. A ingestão via **Integração S3 (Automática)** já estará carregando pedidos de forma contínua no bucket S3. Em caso de instabilidade de rede externa, use o upload manual de planilha Excel como fallback de emergência.
2. Na Mesa de Conferência, selecione a **Unidade de Negócio** ('Indústria', 'Construção Civil' ou 'Varejo') e o **Tipo de Embalagem** para o pedido.
3. Clique em **Checado** para cada item do PO.
4. Clique em **Confirmar Pedido**.

### Passo 2: Roteamento e PCP
1. Como o pedido importado está com crédito liberado, o sistema o direciona automaticamente para a coluna **PCP** (status `APPROVED`).
2. Acesse a coluna PCP e clique no pedido.
3. Se os custos do SKU forem nulos ou não estiverem cadastrados, a margem mostrará a badge cinza `PENDENTE PCP`.
4. Vá até a página **Gerenciar Custos** (ou use a associação de **Vínculo de SKU / Nome do Produto (SKU)** no modal do pedido) e preencha o custo de matéria-prima e rendimento para o SKU.
5. O motor de margem dinâmico recalcula instantaneamente a saúde financeira do PO. Mova o pedido para a coluna de **Produção**.

### Passo 3: Produção e Expedição
1. Na coluna **Produção/Embalagem**, registre a quantidade real produzida. O SLA corre continuamente (não para em caso de falta de insumos). Mova o pedido para **Expedição**.
2. Na coluna **Faturamento/Expedição**, preencha o **Número da NF-e** (refere-se ao número sequencial da nota fiscal e não à chave de 44 dígitos).
3. Faça upload do **PDF da Nota Fiscal** e da **Foto da Carga** (canhoto assinado + carga).
4. Mova o pedido para a coluna final de **Concluídos** para encerrar o ciclo de SLA.

---

## 3. Fluxo 2: Bloqueio de Crédito (Financial Gate)

1. Importe um pedido cujo cliente exceda o limite operacional do ERP (status de crédito configurado como `BLOQUEADO`).
2. Confirme o pedido na Mesa de Conferência.
3. O sistema bloqueia o pedido automaticamente, direcionando-o diretamente para a coluna **Financeiro** com o status `ANALISE_CREDITO` e uma badge vermelha de **CRÉDITO REPROVADO**.
4. O usuário comercial pode acessar o modal do pedido e clicar em **Solicitar Liberação**, preenchendo uma justificativa de crédito técnica.
5. Um aprovador do departamento financeiro visualiza o pedido na coluna, analisa a justificativa e aprova a liberação de crédito.
6. O pedido é liberado do bloqueio e prossegue imediatamente para a coluna **PCP** (`APPROVED`).

---

## 4. Fluxo 3: Partição de Pedido por PCP e Alocação de Frete

1. Em caso de falta de matéria-prima ou limitações de maquinário, o PCP pode dividir o pedido.
2. No modal do pedido na coluna PCP, clique em **Sugerir Partição**, defina a nova data de entrega prevista para o lote atrasado (C2) e as quantidades divididas.
3. O pedido entra em status `WAITING_COMMERCIAL_PARTITION` (badge roxa de partição pendente).
4. O comercial acessa o Kanban e aprova a partição.
5. O pedido original (Pai) é arquivado automaticamente. O sistema cria dois novos pedidos filhos (C1 e C2) em status `SHIPPING` na coluna **Faturamento/Expedição** (Fase A - Frete).
6. O operador logístico preenche o valor do frete rateado para os pedidos C1 e C2.
7. Assim que o frete é alocado com sucesso, os pedidos filhos retornam automaticamente para a coluna **PCP** (`APPROVED`) para início do planejamento de fabricação independente.
