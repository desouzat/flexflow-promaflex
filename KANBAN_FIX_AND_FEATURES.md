# FlexFlow - Correção Kanban e Novas Funcionalidades

## 📋 Resumo das Alterações

Este documento descreve todas as correções e novas funcionalidades implementadas no sistema FlexFlow.

---

## 🔧 1. Correção da Tela Branca do Kanban

### Problema
O sistema logava com sucesso (200 OK), mas a tela do Kanban ficava branca devido a falta de tratamento de erros.

### Solução Implementada

#### 1.1 ErrorBoundary Component
**Arquivo:** `frontend/src/components/ErrorBoundary.jsx`
- Componente React para capturar erros em toda a árvore de componentes
- Exibe mensagem amigável em PT-BR quando ocorre erro
- Mostra detalhes técnicos em modo expandível
- Botão para recarregar a página

#### 1.2 Proteções no KanbanPage
**Arquivo:** `frontend/src/pages/KanbanPage.jsx`
- Adicionado ErrorBoundary envolvendo todo o conteúdo
- Verificação de null/undefined em `boardData.columns`
- Verificação de array em `filterPOs()`
- Proteção contra `po.po_number` e `po.client_name` undefined
- Botão "Carregar Dados" quando não há dados disponíveis

### Verificação de Status
✅ Backend retorna status corretos: `DRAFT`, `SUBMITTED`, `APPROVED`, `IN_PROGRESS`, `COMPLETED`
✅ Frontend mapeia para PT-BR: `Pendente`, `PCP`, `Produção`, `Expedição`, `Concluído`
✅ Sincronização verificada em [`backend/routers/kanban.py`](backend/routers/kanban.py:30-40)

---

## 💰 2. Módulo de Custos (MASTER Only)

### 2.1 Modelo de Dados
**Arquivo:** [`backend/models.py`](backend/models.py:425-505)

Nova tabela `material_costs`:
```python
- id: UUID (PK)
- tenant_id: UUID (FK)
- sku: VARCHAR(100)
- nome: VARCHAR(255)
- custo_mp_kg: NUMERIC(10,2) - Custo de matéria-prima por kg
- rendimento: NUMERIC(10,4) - Rendimento em kg por unidade
- indice_impostos: NUMERIC(5,2) - Índice de impostos (padrão 22.25%)
- created_at, updated_at: TIMESTAMP
- updated_by: UUID (FK para users)
```

**Constraints:**
- `custo_mp_kg >= 0`
- `rendimento > 0`
- `indice_impostos >= 0 AND <= 100`
- UNIQUE (tenant_id, sku)

### 2.2 API de Custos
**Arquivo:** [`backend/routers/costs.py`](backend/routers/costs.py)

**Endpoints (Todos requerem role MASTER):**

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/api/costs/materials` | Listar todos os custos |
| GET | `/api/costs/materials/{sku}` | Obter custo por SKU |
| POST | `/api/costs/materials` | Criar novo custo |
| PUT | `/api/costs/materials/{sku}` | Atualizar custo |
| DELETE | `/api/costs/materials/{sku}` | Deletar custo |
| GET | `/api/costs/settings` | Configurações globais |

**Schemas:** [`backend/schemas/cost_schema.py`](backend/schemas/cost_schema.py)

### 2.3 Segurança
- Dependency `require_master_role()` valida role MASTER
- Retorna HTTP 403 se usuário não for MASTER
- Isolamento por tenant_id automático

---

## 🚀 3. Motor de Override (Salto de Etapa)

### 3.1 Funcionalidade
Permite que usuários **LEADER** e **MASTER** pulem etapas do workflow com justificativa.

### 3.2 Implementação

#### Schema Atualizado
**Arquivo:** [`backend/schemas/kanban_schema.py`](backend/schemas/kanban_schema.py:54-77)

```python
class MoveStatusRequest(BaseModel):
    po_id: str
    to_status: str
    reason: Optional[str]
    metadata: Optional[dict]
    skip_validation: bool = False  # NOVO
    justificativa_lider: Optional[str]  # NOVO (obrigatório se skip_validation=True)
```

**Validação:**
- Se `skip_validation=True`, `justificativa_lider` é obrigatória
- Justificativa deve ter mínimo 10 caracteres

#### Lógica no Router
**Arquivo:** [`backend/routers/kanban.py`](backend/routers/kanban.py:290-433)

**Fluxo:**
1. Verifica se transição é válida
2. Se inválida E `skip_validation=True`:
   - Verifica se usuário é LEADER ou MASTER
   - Valida justificativa
   - Permite a transição
   - Marca como exceção
3. Cria registro de auditoria com `is_exception=True`

### 3.3 Auditoria de Exceções
**Arquivo:** [`backend/models.py`](backend/models.py:333-365)

Campos adicionados ao `AuditLog`:
```python
- is_exception: BOOLEAN (default=False)
- justification: TEXT (justificativa do líder)
```

**Dados gravados:**
- Hash blockchain mantido
- `is_exception=True`
- Justificativa completa
- Metadados: po_id, po_number, user_role, reason

---

## 🔧 4. Campo Extra Metadata (JSONB)

### 4.1 Modelo OrderItem
**Arquivo:** [`backend/models.py`](backend/models.py:267-279)

Adicionado campo:
```python
extra_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
```

### 4.2 Uso
- Armazena campos customizados dos workshops
- Flexível para adicionar novos campos sem migração
- Formato JSON permite estruturas complexas

**Exemplo:**
```json
{
  "workshop_custom_field_1": "valor",
  "workshop_custom_field_2": 123,
  "nested_data": {
    "key": "value"
  }
}
```

---

## 🗄️ 5. Migração do Banco de Dados

### 5.1 Script de Migração
**Arquivo:** [`backend/migrations/add_costs_and_metadata.py`](backend/migrations/add_costs_and_metadata.py)

**Execução:**
```bash
# Aplicar migração
python backend/migrations/add_costs_and_metadata.py

# Reverter migração
python backend/migrations/add_costs_and_metadata.py rollback
```

**Alterações:**
1. ✅ Adiciona `extra_metadata` JSONB em `order_items`
2. ✅ Adiciona `is_exception` BOOLEAN em `audit_logs`
3. ✅ Adiciona `justification` TEXT em `audit_logs`
4. ✅ Cria índice em `audit_logs.is_exception`
5. ✅ Cria tabela `material_costs` completa
6. ✅ Cria índices em `material_costs`
7. ✅ Adiciona comentários nas colunas

---

## 🌐 6. Integração com Main App

### 6.1 Routers Registrados
**Arquivo:** [`backend/main.py`](backend/main.py:13-170)

```python
from backend.routers import auth, import_router, kanban, dashboard, costs

app.include_router(costs.router)  # NOVO
```

### 6.2 Endpoints Documentados
Adicionado em `/api` e `/`:
```json
"costs": {
  "list_materials": "GET /api/costs/materials",
  "get_material": "GET /api/costs/materials/{sku}",
  "create_material": "POST /api/costs/materials",
  "update_material": "PUT /api/costs/materials/{sku}",
  "delete_material": "DELETE /api/costs/materials/{sku}",
  "settings": "GET /api/costs/settings"
}
```

---

## 📝 7. Idioma PT-BR

### Verificação Completa
✅ Todas as mensagens de erro em PT-BR
✅ Labels de status em PT-BR
✅ Mensagens de validação em PT-BR
✅ Comentários de código em PT-BR
✅ Documentação em PT-BR

**Exemplos:**
- "Pedido não encontrado" (não "Order not found")
- "Transição inválida" (não "Invalid transition")
- "Apenas usuários MASTER podem gerenciar custos"
- "Justificativa é obrigatória para salto de etapa"

---

## 🧪 8. Como Testar

### 8.1 Testar Correção do Kanban
```bash
# 1. Executar migração
python backend/migrations/add_costs_and_metadata.py

# 2. Iniciar backend
cd backend
python main.py

# 3. Iniciar frontend
cd frontend
npm run dev

# 4. Login e acessar Kanban
# Verificar que não há tela branca
# Verificar que colunas aparecem corretamente
```

### 8.2 Testar Módulo de Custos
```bash
# Fazer login como MASTER
POST /api/auth/login
{
  "email": "master@example.com",
  "password": "senha"
}

# Criar material
POST /api/costs/materials
{
  "sku": "MAT-001",
  "nome": "Material Teste",
  "custo_mp_kg": 15.50,
  "rendimento": 0.5,
  "indice_impostos": 22.25
}

# Listar materiais
GET /api/costs/materials

# Tentar com usuário não-MASTER (deve retornar 403)
```

### 8.3 Testar Salto de Etapa
```bash
# Login como LEADER ou MASTER
POST /api/auth/login

# Tentar salto de etapa
POST /api/kanban/move-status
{
  "po_id": "uuid-do-pedido",
  "to_status": "Concluído",  # Pulando etapas
  "skip_validation": true,
  "justificativa_lider": "Cliente VIP solicitou urgência devido a prazo crítico de produção"
}

# Verificar audit_logs
SELECT * FROM audit_logs WHERE is_exception = true;
```

---

## 📊 9. Arquivos Modificados/Criados

### Novos Arquivos
- ✅ `frontend/src/components/ErrorBoundary.jsx`
- ✅ `backend/schemas/cost_schema.py`
- ✅ `backend/routers/costs.py`
- ✅ `backend/migrations/add_costs_and_metadata.py`
- ✅ `KANBAN_FIX_AND_FEATURES.md` (este arquivo)

### Arquivos Modificados
- ✅ `frontend/src/pages/KanbanPage.jsx` - ErrorBoundary e null checks
- ✅ `backend/models.py` - MaterialCost, extra_metadata, is_exception
- ✅ `backend/schemas/kanban_schema.py` - skip_validation, justificativa
- ✅ `backend/routers/kanban.py` - Lógica de salto de etapa
- ✅ `backend/main.py` - Registro do router costs
- ✅ `backend/routers/__init__.py` - Export costs

---

## ✅ 10. Checklist de Implementação

- [x] Fix Kanban white screen - ErrorBoundary e null checks
- [x] Verificar sincronização de status backend/frontend
- [x] Criar tabela material_costs no models
- [x] Criar router de custos (MASTER only)
- [x] Adicionar campo extra_metadata JSONB ao OrderItem
- [x] Implementar lógica de salto de etapa com justificativa
- [x] Atualizar AuditLog com is_exception flag
- [x] Garantir todas as labels em PT-BR
- [x] Criar script de migração do banco
- [x] Registrar router costs no main.py
- [x] Documentar todas as alterações

---

## 🚀 11. Próximos Passos

### Para Executar
1. **Executar migração do banco de dados:**
   ```bash
   python backend/migrations/add_costs_and_metadata.py
   ```

2. **Reiniciar o backend:**
   ```bash
   cd backend
   python main.py
   ```

3. **Testar funcionalidades:**
   - Acessar Kanban e verificar que não há tela branca
   - Testar criação de custos (como MASTER)
   - Testar salto de etapa (como LEADER/MASTER)

### Para Desenvolvimento Futuro
- [ ] Criar tela frontend para gerenciar custos
- [ ] Criar tela frontend para visualizar audit logs de exceções
- [ ] Implementar cálculo automático de margem usando material_costs
- [ ] Adicionar relatório de exceções para auditoria
- [ ] Implementar notificações quando há salto de etapa

---

## 📞 Suporte

Para dúvidas ou problemas:
1. Verificar logs do backend
2. Verificar console do navegador (F12)
3. Consultar documentação da API em `/docs`
4. Verificar este documento

---

**Data:** 2026-04-15
**Versão:** 1.0.0
**Status:** ✅ Implementação Completa - Aguardando Aprovação para Salvar
