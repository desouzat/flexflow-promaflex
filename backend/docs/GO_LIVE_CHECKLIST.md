# Check-list de Implantação e Go-Live — FlexFlow

Este checklist serve como um guia técnico para a configuração do ambiente de produção e deploy do sistema FlexFlow.

---

## 1. Variáveis de Ambiente (.env)

O arquivo `.env` deve ser colocado na raiz da pasta `backend/` e preenchido com as seguintes chaves reais:

| Variável | Descrição | Exemplo / Padrão |
| :--- | :--- | :--- |
| `DATABASE_URL` | String de conexão com o banco de dados PostgreSQL (GCP Cloud SQL via Proxy). | `postgresql://user:pass@127.0.0.1:5433/dbname` |
| `SECURITY_PEPPER` | Valor fixo de 32 bytes (hexadecimal) para salgar os hashes de senhas e dados. | `4d87c5ab5cb30f0a1e1c4440ca08e305` |
| `SECRET_KEY` | Chave criptográfica para assinatura de tokens JWT. | `your-secret-key-here-change-in-production` |
| `ALGORITHM` | Algoritmo de hash para o JWT. | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Tempo de expiração do token de sessão do usuário. | `1440` (24 horas) |
| `S3_ENDPOINT` | Endpoint da nuvem privada S3 (MSP Clouds / AWS S3). | `https://s3-dc3-002.mspclouds.com` |
| `S3_ACCESS_KEY` | Chave de acesso S3. | `1SRU41YJEJSVFO83HD7E` |
| `S3_SECRET_KEY` | Chave secreta de acesso S3. | `wXViYtZDPSP3A4tgiIMFXRk...` |
| `S3_BUCKET_NAME` | Nome do bucket configurado para ingestão de arquivos. | `flexflow` |
| `SUPPORT_EMAIL_DESTINATION` | E-mail padrão de fallback para chamados de suporte. | `suporte@flexflow.com.br` |
| `UPLOAD_DIR` | Diretório interno onde anexos temporários e persistentes serão gravados. | `backend/uploads` |

> [!CAUTION]
> **Segurança:** Nunca comite o arquivo `.env` ou chaves privadas no controle de versão (Git). Use gerenciadores de segredos das nuvens (ex: GCP Secret Manager) se aplicável.

---

## 2. Passos de Deploy (Infraestrutura)

### 2.1. Banco de Dados (GCP Cloud SQL)
1. **Cloud SQL Proxy:** Certifique-se de iniciar o proxy do GCP Cloud SQL apontando para a porta `5433` (e não a `5411` ou a padrão `5432`, reservada para instâncias locais).
   ```powershell
   ./cloud-sql-proxy.exe --port 5433 <INSTANCE_CONNECTION_NAME>
   ```
2. **Migrations:** Execute as migrações automáticas de banco no startup (lifespan FastAPI) para garantir que as tabelas (`tenants`, `users`, `purchase_orders`, `order_items`, `client_preferences`, `SupportTickets` e `GlobalConfig`) sejam criadas.

### 2.2. Ingestão Automatizada de Arquivos (Background Worker)
1. Certifique-se de que o bucket S3 `flexflow` está ativo e acessível com as credenciais providas.
2. O worker de background em `backend/services/background_worker.py` iniciará automaticamente com o app e verificará continuamente o diretório do bucket para realizar o parser de pedidos.

### 2.3. Frontend (Hardening e Compilação)
1. O arquivo `.npmrc` deve estar presente na pasta `frontend/` bloqueando scripts e forçando versões exatas:
   ```text
   ignore-scripts=true
   save-exact=true
   ```
2. Instalar dependências de produção sem scripts não-verificados e compilar:
   ```powershell
   npm install --ignore-scripts
   npm run build
   ```
3. A pasta `dist/` gerada deve ser servida através do Nginx, Cloud CDN, ou equivalente.
