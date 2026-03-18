# FlexFlow - Stress & Journey Test Integrado

## 📋 Visão Geral

Script de teste integrado que simula uma jornada completa do sistema FlexFlow, incluindo cenários de erro proposital para validar a robustez do sistema antes do Kickoff.

## 🎯 Objetivos

1. **Validar Robustez**: Testar o sistema sob condições adversas
2. **Rastreabilidade**: Capturar todos os payloads (sucesso e erro)
3. **Jornada Completa**: Simular fluxo real de ponta a ponta
4. **Blindagem**: Identificar pontos fracos antes do Kickoff

## 📊 Massa de Dados

### Tenant
- **1 Tenant**: PromaFlex Stress Test
- **ID**: `tenant-stress-test-001`

### Usuários (5 com diferentes roles/permissões)

| # | Nome | Email | Role | Permissões Principais |
|---|------|-------|------|----------------------|
| 1 | Admin User | admin@promaflex.com | admin | Todas as permissões |
| 2 | Comercial Manager | comercial@promaflex.com | comercial_manager | Criar PO, Aprovar Comercial |
| 3 | PCP Manager | pcp@promaflex.com | pcp_manager | Aprovar/Rejeitar PCP |
| 4 | Production Manager | producao@promaflex.com | producao_manager | Aprovar Produção |
| 5 | Shipping Manager | expedicao@promaflex.com | expedicao_manager | Expedição, Faturamento, Despacho |

### Purchase Order
- **1 PO** com **10 Itens**:
  - **6 Itens Normais**: SKU-NORMAL-001 a SKU-NORMAL-006
  - **4 Itens Personalizados**: SKU-CUSTOM-001 a SKU-CUSTOM-004 (requerem anexos)

## 🔥 Cenários de Erro Proposital

### Cenário 1: Login com Credenciais Inválidas ❌
**Objetivo**: Validar autenticação e tratamento de erros

**Testes**:
- Email inválido + senha errada
- Email válido + senha errada
- Campos vazios
- Email mal formatado

**Resultado Esperado**: Todos devem falhar com status 401

---

### Cenário 2: Login Válido para Todos os Usuários ✅
**Objetivo**: Obter tokens JWT para os 5 usuários

**Resultado Esperado**: 
- Status 200 para todos
- Tokens JWT armazenados
- Permissões corretas no token

---

### Cenário 3: Upload de Planilha com Dados Corrompidos ❌
**Objetivo**: Validar validação de dados no import

**Dados Corrompidos**:
- Quantidade com valor string ("INVALID_NUMBER")
- Preço negativo (-100)
- Custo com texto ("corrupted")

**Resultado Esperado**: Falha com status 400 e mensagens de validação

---

### Cenário 4: Upload de Planilha Válida ✅
**Objetivo**: Criar PO com 10 itens via import

**Resultado Esperado**:
- Status 200
- PO criado com ID
- 10 itens importados corretamente
- Margens calculadas

---

### Cenário 5: Mover Item Personalizado no PCP sem Anexo ❌
**Objetivo**: Validar regra crítica do PCP

**Regra**: Itens personalizados (`is_personalized = true`) DEVEM ter anexos antes de aprovar PCP → PRODUCAO

**Resultado Esperado**: 
- Falha com status 400
- Mensagem: "Personalized items require attachments"

---

### Cenário 6: Aprovar PCP com Anexo ✅
**Objetivo**: Transição válida PCP → PRODUCAO

**Pré-requisito**: Anexos adicionados para itens personalizados

**Resultado Esperado**:
- Status 200
- PO movido para PRODUCAO
- Audit trail registrado

---

### Cenário 7: Tentar Despacho sem NF e Carga Prontas ❌
**Objetivo**: Validar paralelismo de estados

**Regra**: DESPACHO só pode ocorrer quando AMBOS os estados paralelos estão completos:
- EXPEDICAO_PENDENTE ✅
- FATURAMENTO_PENDENTE ✅

**Teste**: Tentar mover para DESPACHO com apenas um estado completo

**Resultado Esperado**:
- Falha com status 400
- Mensagem: "Both parallel states must be completed"

---

### Cenário 8: Jornada Completa de Sucesso ✅
**Objetivo**: Completar fluxo de ponta a ponta

**Fluxo**:
1. COMERCIAL → PCP (aprovado)
2. PCP → PRODUCAO (com anexos)
3. PRODUCAO → EXPEDICAO_PENDENTE + FATURAMENTO_PENDENTE (paralelo)
4. Completar EXPEDICAO_PENDENTE ✅
5. Completar FATURAMENTO_PENDENTE ✅
6. DESPACHO (ambos completos)
7. CONCLUIDO (finalizado)

**Resultado Esperado**: PO em estado CONCLUIDO

---

## 📦 Rastreabilidade de Payloads

Cada requisição captura:

```json
{
  "timestamp": "2026-03-18T15:30:00.000Z",
  "scenario": "Nome do Cenário",
  "action": "Descrição da Ação",
  "method": "POST",
  "url": "http://localhost:8000/api/auth/login",
  "request_data": { "email": "...", "password": "..." },
  "response_status": 200,
  "response_data": { "access_token": "...", "token_type": "bearer" },
  "error": null,
  "success": true
}
```

## 🚀 Como Executar

### Pré-requisitos

1. **Instalar dependências**:
```bash
pip install requests pandas openpyxl colorama
```

2. **Servidor rodando**:
```bash
cd backend
uvicorn main:app --reload
```

3. **Verificar saúde do servidor**:
```bash
curl http://localhost:8000/health
```

### Executar o Teste

```bash
# A partir do diretório raiz do projeto
python -m backend.tests.stress_test_journey
```

### ⚠️ IMPORTANTE: NÃO EXECUTE AINDA!

Este script está preparado mas **NÃO deve ser executado** até que:
1. O servidor esteja completamente configurado
2. O banco de dados esteja inicializado
3. Todos os endpoints estejam implementados
4. A aprovação para execução seja dada

## 📊 Relatório Gerado

Após a execução, o teste gera:

### Console Output
- Logs coloridos em tempo real
- Status de cada requisição
- Resumo final com métricas

### Arquivo JSON (`stress_test_report.json`)
```json
{
  "start_time": "2026-03-18T15:30:00.000Z",
  "end_time": "2026-03-18T15:32:30.000Z",
  "total_requests": 45,
  "successful_requests": 38,
  "failed_requests": 7,
  "scenarios": [...],
  "errors": [...],
  "payloads": [...]
}
```

## 📈 Métricas Esperadas

| Métrica | Valor Esperado |
|---------|----------------|
| Total de Requisições | ~40-50 |
| Taxa de Sucesso | ~80-85% |
| Falhas Esperadas | ~7-10 (erros propositais) |
| Duração | ~30-60 segundos |
| Payloads Capturados | Todos (100%) |

## 🔍 Validações Críticas

### ✅ Devem Passar
- Login com credenciais válidas
- Upload de planilha válida
- Transições de estado válidas
- Jornada completa

### ❌ Devem Falhar (Propositalmente)
- Login com credenciais inválidas
- Upload de dados corrompidos
- PCP sem anexo para item personalizado
- Despacho sem estados paralelos completos

## 🛡️ Blindagem do Sistema

Este teste valida:

1. **Autenticação**: Rejeita credenciais inválidas
2. **Validação de Dados**: Detecta dados corrompidos
3. **Regras de Negócio**: Aplica regras críticas (anexos, paralelismo)
4. **State Machine**: Transições válidas apenas
5. **Multi-tenancy**: Isolamento de dados
6. **Audit Trail**: Rastreabilidade completa

## 📝 Notas para o Kickoff

- ✅ Script pronto e documentado
- ✅ Massa de dados realista
- ✅ Cenários de erro cobertos
- ✅ Rastreabilidade implementada
- ⏸️ Aguardando aprovação para execução

## 🔧 Troubleshooting

### Erro: "Cannot connect to server"
**Solução**: Inicie o servidor com `uvicorn backend.main:app --reload`

### Erro: "Token not available"
**Solução**: Verifique se o login foi bem-sucedido no Cenário 2

### Erro: "PO ID not available"
**Solução**: Verifique se o upload foi bem-sucedido no Cenário 4

## 📞 Contato

Para dúvidas sobre o teste, consulte a documentação do projeto ou o time de desenvolvimento.

---

**Status**: ✅ Pronto para Kickoff (Aguardando Execução)
**Última Atualização**: 2026-03-18
