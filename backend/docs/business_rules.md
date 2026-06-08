# Regras de Negócio - Engenharia de Margem (Fórmula Celso) e Governança FlexFlow

Este documento descreve as especificações e fórmulas do **Motor de Margem Dinâmica** (ou "Fórmula Celso"), o **Gate Financeiro Refinado** e as regras de governança das etapas do fluxo de trabalho no FlexFlow.

---

## 1. O Motor de Margem Dinâmica (Fórmula Celso)

A Margem de Contribuição ($CM$) de cada item de pedido de compra (ou consolidada no PO) é calculada dinamicamente com base nas receitas, tributos, despesas financeiras diretas e custos industriais.

### 1.1. Fórmula Geral da Margem de Contribuição ($CM$)

$$CM = \frac{VP - Taxes - Commission - Freight}{Costs}$$

Onde:
* **$VP$**: Valor Presente descontado (ajustado de acordo com o prazo de pagamento).
* **$Taxes$**: Impostos incidentes (alíquota fixa de $22,25\%$).
* **$Commission$**: Comissão de vendas em reais.
* **$Freight$**: Custos logísticos/frete atribuídos ao item.
* **$Costs$**: Custo industrial total (matéria-prima, mão de obra, insumos de energia/gás).

---

## 2. Parâmetros e Cálculos Detalhados

Para manter a **Integridade Matemática**, todos os cálculos internos usam precisão de **pelo menos 4 casas decimais** ($10^{-4}$), sendo arredondados para **2 casas decimais** apenas na camada de exibição da interface do usuário (UI).

### 2.1. Ajuste do Valor Presente ($VP$)
O Valor Bruto ($Gross$) é ajustado ao Valor Presente considerando uma taxa de desconto pro-rata de **$2,5\%$ ao mês** ($0,08333\%$ ao dia) baseada na média de dias da Condição de Pagamento ($Days$).

$$\text{Fator } VP = 1 + \left(0,025 \times \frac{Days}{30}\right)$$

$$VP = \frac{Gross}{\text{Fator } VP}$$

#### Conversão de Condições de Pagamento ($Days$):
* **À vista / Imediato / Cash / 0 dias**: $0$ dias ($VP = Gross$).
* **N dias simples** (ex: *"30 dias"*): $Days = 30$.
* **Múltiplas parcelas** (ex: *"30/60/90 dias"*): Média aritmética das parcelas:
  $$Days = \frac{30 + 60 + 90}{3} = 60 \text{ dias}$$

### 2.2. Impostos ($Taxes$)
A alíquota fiscal fixa é de **$22,25\%$**, calculada diretamente sobre o Valor Presente ($VP$):

$$Taxes = VP \times 0,2225$$

### 2.3. Comissão ($Commission$)
A comissão é calculada aplicando a alíquota definida ($CommissionRate$, ex: $2,5\%$) sobre o Valor Presente ($VP$):

$$Commission = VP \times \frac{CommissionRate}{100}$$

### 2.4. Custos Industriais e Segurança Nula (Null Safety)
* Se o custo industrial ($Costs$) for zero ($0$), indefinido ou nulo, o cálculo não deve prosseguir para evitar erro de **Divisão por Zero** (NaN / Infinity).
* Nesses casos, o cálculo é interrompido com segurança e o status é definido como **`PENDENTE_PCP`** (representado na UI por uma badge cinza com o texto `PENDENTE PCP`).

---

## 3. Matriz de Classificação de Margem (Badges)

Dependendo do resultado percentual final ($CM \times 100$), o FlexFlow classifica visualmente a saúde financeira do PO com as seguintes faixas:

| Faixa de Margem | Cor da Badge | Classificação Visual | Significado |
| :--- | :--- | :--- | :--- |
| $\ge 30,00\%$ | **Verde** | Excelente | Pedido altamente lucrativo, aprovado comercialmente. |
| $19,00\%$ a $29,99\%$ | **Amarelo** | Atenção | Margem dentro da média aceitável. |
| $10,00\%$ a $18,99\%$ | **Laranja** | Crítico | Margem baixa, requer atenção da gerência comercial. |
| $< 10,00\%$ ou Negativa | **Vermelho** | Prejuízo / Bloqueio | Margem inviável, passível de bloqueio automático. |
| Custo zero ou indefinido | **Cinza** | Pendente PCP | Aguardando PCP cadastrar os custos de matéria-prima. |

---

## 4. O Gate Financeiro Refinado

### 4.1. Autonomia Comercial (Twin Buttons)
Para itens marcados com o status de crédito `BLOQUEADO` na mesa de conferência:
1. **Manter Bloqueio**: Permite que o analista confira os dados do item sem liberar o bloqueio. O pedido prossegue para os próximos fluxos mas mantém sua flag restritiva de segurança.
2. **Solicitar Liberação**: Abre um modal de justificativa para o financeiro. A transição altera o status de macro para `ANALISE_CREDITO` e anexa a justificativa para análise.

### 4.2. Bypass de Trocas e Reposições
* Quando a flag **`is_replacement` (Troca/Reposição)** é ativada pelo comercial:
  - O Gate Financeiro de crédito é ignorado por padrão.
  - A interface exibe a badge azul/ciano: **`CRÉDITO PRÉ-APROVADO (TROCA)`**.
  - O fluxo de liberação financeira é dispensado, pois a reposição é tratada como crédito de relacionamento pré-aprovado.
  - O prazo de SLA do pedido é reduzido automaticamente em **$50\%$**.

---

## 5. Regras Oficiais do Fluxo de Trabalho (Go-Live)

### 5.1. Mesa de Conferência (Staging)
* **Unidade de Negócio:** A seleção da 'Unidade de Negócio' ('Indústria', 'Construção Civil' ou 'Varejo') é estritamente obrigatória na Mesa de Conferência antes de confirmar o pedido. Esta escolha alimenta a inteligência de memória do cliente (preenchimento automático no próximo import) e os indicadores de performance do Dashboard.
* **Validação Fotográfica e NFe:** Esta etapa não exige fotos ou NF-e, cuja obrigatoriedade se restringe ao fechamento do pedido na etapa de Expedição.

### 5.2. Comercial
* **Ingestão via S3:** O canal primário e contínuo de importação de pedidos é a **Integração S3 (Automática)**. A planilha Excel é mantida estritamente como um fallback/contingência de emergência caso haja indisponibilidade do S3.
* **Flag Primeiro Pedido:** A antiga flag "Primeira Ordem" foi renomeada para **"Primeiro Pedido"** para melhor representar o início do relacionamento do cliente com a fábrica, recebendo prioridade de auditoria.

### 5.3. Produção/Embalagem
* **SLA de Produção:** O cronômetro de SLA é de execução contínua. **O SLA não para durante a espera de insumos (Transparência Total)**, garantindo a visualização precisa e sem desvios dos gargalos industriais.

### 5.4. PCP (Planejamento e Controle de Produção)
* **Vínculo de SKU / Nome Amigável:** O mapeamento técnico entre SKUs similares e códigos legados é denominado **Vínculo de SKU / Nome Amigável** (substituindo o termo Alias), facilitando a reutilização de custos de matéria-prima e rendimentos técnicos.

### 5.5. Faturamento/Expedição
* **Número da NF-e:** O preenchimento do campo "Número da NF-e" refere-se exclusivamente ao **número sequencial da nota fiscal (Invoice Number)**, e não à chave de acesso XML de 44 dígitos da nota.

### 5.6. Financeiro
* **Escopo:** O departamento financeiro atua no Kanban de forma **exclusiva para análise e liberação de bloqueios de crédito**, eliminando a responsabilidade de 'Auditoria de NF'.

### 5.7. Concluídos (Completed)
* **Repositório Histórico:** Esta coluna serve como **repositório histórico para consulta de pedidos finalizados e auditoria de Timeline**, encerrando o monitoramento ativo de SLA.
