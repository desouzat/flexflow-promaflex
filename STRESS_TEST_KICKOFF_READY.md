# ✅ FlexFlow - Stress Test Pronto para Kickoff

## 🎯 Status: PRONTO (Aguardando Execução)

O **Stress & Journey Test Integrado** foi criado e está pronto para blindar o sistema antes do Kickoff de amanhã.

---

## 📦 O Que Foi Criado

### 1. Script Principal de Teste
**Arquivo**: [`backend/tests/stress_test_journey.py`](backend/tests/stress_test_journey.py)

**Características**:
- ✅ Massa de dados completa (1 Tenant, 5 Usuários, 1 PO com 10 Itens)
- ✅ 8 cenários de teste (4 de sucesso + 4 de erro proposital)
- ✅ Rastreabilidade total de payloads (request/response)
- ✅ Relatório JSON detalhado
- ✅ Logs coloridos em tempo real
- ✅ ~40-50 requisições HTTP

### 2. Documentação Completa
**Arquivo**: [`backend/tests/STRESS_TEST_README.md`](backend/tests/STRESS_TEST_README.md)

**Conteúdo**:
- Visão geral e objetivos
- Detalhamento da massa de dados
- Descrição de cada cenário
- Instruções de execução
- Métricas esperadas
- Troubleshooting

### 3. Scripts de Execução
- **Windows**: [`backend/tests/run_stress_test.bat`](backend/tests/run_stress_test.bat)
- **Linux/Mac**: [`backend/tests/run_stress_test.sh`](backend/tests/run_stress_test.sh)

### 4. Dependências
**Arquivo**: [`backend/tests/requirements_stress_test.txt`](backend/tests/requirements_stress_test.txt)

**Bibliotecas**:
- `requests` - HTTP requests
- `pandas` - Manipulação de dados
- `openpyxl` - Geração de Excel
- `colorama` - Logs coloridos

---

## 🔥 Cenários de Teste

### ❌ Cenários de Erro Proposital (Devem Falhar)

#### 1. Login com Credenciais Inválidas
- Email inválido + senha errada
- Email válido + senha errada
- Campos vazios
- Email mal formatado

#### 2. Upload de Planilha Corrompida
- Quantidade com string ("INVALID_NUMBER")
- Preço negativo (-100)
- Custo com texto ("corrupted")

#### 3. PCP sem Anexo para Item Personalizado
- Tentar aprovar PCP → PRODUCAO
- Sem anexos para itens `is_personalized = true`
- **Regra Crítica**: Deve bloquear!

#### 4. Despacho sem Estados Paralelos Completos
- Tentar DESPACHO sem EXPEDICAO_PENDENTE completo
- Tentar DESPACHO sem FATURAMENTO_PENDENTE completo
- **Regra Crítica**: Ambos devem estar prontos!

---

### ✅ Cenários de Sucesso (Devem Passar)

#### 5. Login Válido para 5 Usuários
- Admin, Comercial, PCP, Produção, Expedição
- Tokens JWT armazenados
- Permissões corretas

#### 6. Upload de Planilha Válida
- 10 itens (6 normais + 4 personalizados)
- Margens calculadas
- PO criado com sucesso

#### 7. Aprovação PCP com Anexos
- Anexos adicionados para itens personalizados
- Transição PCP → PRODUCAO bem-sucedida
- Audit trail registrado

#### 8. Jornada Completa
- COMERCIAL → PCP → PRODUCAO
- PRODUCAO → EXPEDICAO_PENDENTE + FATURAMENTO_PENDENTE (paralelo)
- Completar ambos os estados paralelos
- DESPACHO → CONCLUIDO

---

## 📊 Massa de Dados Detalhada

### Tenant
```json
{
  "id": "tenant-stress-test-001",
  "name": "PromaFlex Stress Test"
}
```

### 5 Usuários com Roles Diferentes

| # | Role | Email | Permissões Principais |
|---|------|-------|----------------------|
| 1 | admin | admin@promaflex.com | Todas |
| 2 | comercial_manager | comercial@promaflex.com | Criar PO, Aprovar Comercial |
| 3 | pcp_manager | pcp@promaflex.com | Aprovar/Rejeitar PCP |
| 4 | producao_manager | producao@promaflex.com | Aprovar Produção |
| 5 | expedicao_manager | expedicao@promaflex.com | Expedição, Faturamento, Despacho |

### 1 PO com 10 Itens

**6 Itens Normais**:
- SKU-NORMAL-001 a SKU-NORMAL-006
- Quantidade: 15 a 40 unidades
- Preço: R$ 110 a R$ 160
- Custos: MP, MO, Energia, Gás

**4 Itens Personalizados** (Requerem Anexos):
- SKU-CUSTOM-001 a SKU-CUSTOM-004
- Quantidade: 8 a 17 unidades
- Preço: R$ 220 a R$ 280
- `is_personalized = true`

---

## 🎬 Como Executar

### Pré-requisitos

1. **Instalar dependências**:
```bash
pip install -r backend/tests/requirements_stress_test.txt
```

2. **Iniciar o servidor**:
```bash
cd backend
uvicorn main:app --reload
```

3. **Verificar saúde**:
```bash
curl http://localhost:8000/health
```

### Execução

**Windows**:
```cmd
cd backend\tests
run_stress_test.bat
```

**Linux/Mac**:
```bash
cd backend/tests
chmod +x run_stress_test.sh
./run_stress_test.sh
```

**Direto com Python**:
```bash
python -m backend.tests.stress_test_journey
```

---

## 📈 Resultados Esperados

### Métricas
- **Total de Requisições**: ~40-50
- **Taxa de Sucesso**: ~80-85%
- **Falhas Esperadas**: ~7-10 (erros propositais)
- **Duração**: ~30-60 segundos

### Relatório Gerado
**Arquivo**: `backend/tests/stress_test_report.json`

```json
{
  "start_time": "2026-03-18T15:30:00.000Z",
  "end_time": "2026-03-18T15:32:30.000Z",
  "total_requests": 45,
  "successful_requests": 38,
  "failed_requests": 7,
  "scenarios": [...],
  "payloads": [
    {
      "timestamp": "...",
      "scenario": "Invalid Login",
      "action": "Login attempt with invalid@test.com",
      "method": "POST",
      "url": "http://localhost:8000/api/auth/login",
      "request_data": {...},
      "response_status": 401,
      "response_data": {...},
      "error": null,
      "success": true
    }
  ]
}
```

---

## 🛡️ Blindagem do Sistema

Este teste valida:

✅ **Autenticação**: Rejeita credenciais inválidas  
✅ **Validação de Dados**: Detecta dados corrompidos  
✅ **Regras de Negócio**: Aplica regras críticas (anexos, paralelismo)  
✅ **State Machine**: Apenas transições válidas  
✅ **Multi-tenancy**: Isolamento de dados por tenant  
✅ **Audit Trail**: Rastreabilidade completa de ações  

---

## ⚠️ IMPORTANTE: NÃO EXECUTE AINDA!

O script está **PRONTO** mas **NÃO deve ser executado** até:

1. ✅ Servidor completamente configurado
2. ✅ Banco de dados inicializado
3. ✅ Todos os endpoints implementados
4. ✅ Aprovação explícita para execução

---

## 📋 Checklist para o Kickoff

- [x] Script de teste criado
- [x] Massa de dados preparada (1 Tenant, 5 Usuários, 10 Itens)
- [x] Cenários de erro implementados (4 cenários)
- [x] Cenários de sucesso implementados (4 cenários)
- [x] Rastreabilidade de payloads completa
- [x] Documentação detalhada
- [x] Scripts de execução (Windows + Linux/Mac)
- [x] Arquivo de dependências
- [ ] **Execução do teste** (Aguardando aprovação)
- [ ] **Análise dos resultados** (Após execução)

---

## 🎯 Próximos Passos

1. **Revisar** este documento e o script
2. **Validar** que todos os cenários fazem sentido
3. **Aprovar** a execução do teste
4. **Executar** o teste antes do Kickoff
5. **Analisar** os resultados e corrigir problemas encontrados
6. **Apresentar** no Kickoff com confiança!

---

## 📞 Suporte

- **Script Principal**: `backend/tests/stress_test_journey.py`
- **Documentação**: `backend/tests/STRESS_TEST_README.md`
- **Dependências**: `backend/tests/requirements_stress_test.txt`

---

**Status Final**: ✅ **PRONTO PARA KICKOFF**  
**Criado em**: 2026-03-18  
**Aguardando**: Aprovação para execução
