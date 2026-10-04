# Portically Processos

Documentação operacional da **v1.3.0 · Atualização 20 · V20**, conferida com `app.py` e `requirements.txt` no commit `9d87d8d0c5f8c14b9e4d46e7ed354e7a6521f04b`.

Aplicação FastAPI com acesso restrito por e-mail e código OTP enviado pelo **Resend**. O Radar persiste seus cadastros em **PostgreSQL**, com criptografia de campos e identificação de duplicidades por HMAC.

O pacote arquivado da V5 é histórico: suas instruções SMTP não se aplicam à V20. Execute os arquivos atuais da raiz. Não publique credenciais, códigos OTP, dumps, documentos ou dados processuais em commits, issues ou logs compartilhados.

## Instalação

Pré-requisitos: Git, Python 3.10 ou superior (use uma versão compatível e validada no seu ambiente), PostgreSQL acessível e conta Resend com remetente autorizado. Acesso autenticado requer HTTPS.

```bash
git clone https://github.com/manutencaofmsce-creator/portically-processos.git
cd portically-processos
git checkout 9d87d8d0c5f8c14b9e4d46e7ed354e7a6521f04b
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

No Windows/PowerShell, ative com `.venv\Scripts\Activate.ps1`. O checkout acima fixa a referência V20 e fica em HEAD destacada; para atualizar, selecione depois o commit aprovado conforme o procedimento abaixo.

## Variáveis obrigatórias

Configure todas as variáveis no ambiente do processo ou no gerenciador de segredos da hospedagem, antes de iniciar. O código lê o ambiente ao importar `app.py` e não carrega arquivos `.env` automaticamente.

| Variável | Finalidade e formato |
| --- | --- |
| `AUTHORIZED_EMAIL` | Único e-mail autorizado a solicitar acesso. O código remove espaços externos e converte para minúsculas. |
| `SESSION_SECRET` | Segredo aleatório para assinar sessões e hashes dos OTPs. Use valor forte, exclusivo e estável. |
| `RESEND_API_KEY` | Chave Resend com permissão de envio. |
| `RESEND_FROM_EMAIL` | Endereço remetente autorizado pelo Resend, em domínio verificado. Configure explicitamente, mesmo havendo um padrão no código. |
| `DATABASE_URL` | URI PostgreSQL aceita pelo psycopg, com usuário, senha, host, porta e banco; configure TLS conforme o provedor. |
| `DATA_ENCRYPTION_KEY` | Chave Fernet: 32 bytes aleatórios codificados em Base64 URL-safe. Não use uma senha comum. |
| `DATA_HMAC_KEY` | Segredo aleatório independente, usado no HMAC-SHA256 dos documentos normalizados para detectar duplicidades. |

Modelo de preenchimento **somente com placeholders** (não é uma configuração executável):

```text
AUTHORIZED_EMAIL=<EMAIL_AUTORIZADO>
SESSION_SECRET=<SEGREDO_ALEATORIO_DA_SESSAO>
RESEND_API_KEY=<CHAVE_RESEND>
RESEND_FROM_EMAIL=<REMETENTE_VERIFICADO>
DATABASE_URL=postgresql://<USUARIO>:<SENHA>@<HOST>:<PORTA>/<BANCO>?sslmode=require
DATA_ENCRYPTION_KEY=<CHAVE_FERNET_BASE64_URLSAFE>
DATA_HMAC_KEY=<SEGREDO_HMAC_INDEPENDENTE>
```

Gere os segredos localmente, após instalar as dependências, e transfira a saída diretamente para o gerenciador de segredos:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

As saídas correspondem, respectivamente, a `SESSION_SECRET`, `DATA_ENCRYPTION_KEY` e `DATA_HMAC_KEY`. Execute em terminal privado e não compartilhe a saída. Guarde cópias protegidas das chaves, separadas dos backups do banco.

A V20 não valida todas as variáveis de forma centralizada na inicialização. Um processo iniciado ou uma página de login aberta não comprovam configuração completa.

## Inicialização

Na raiz do repositório, com ambiente virtual ativo e variáveis configuradas:

```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --workers 1
```

Em hospedagem como Render:

- Build: `pip install -r requirements.txt`
- Start: `uvicorn app:app --host 0.0.0.0 --port "$PORT" --workers 1`
- Caminho de saúde: `/health`
- Uma instância e um worker, pois os OTPs ficam na memória do processo.
- HTTPS no endereço público; mantenha PostgreSQL e segredos configurados no ambiente do serviço.

Abra `/` para solicitar o código. O cookie de sessão usa `HttpOnly`, `Secure` e `SameSite=strict`; para validar o login localmente, use um proxy HTTPS confiável. HTTP local serve para verificar saúde e página inicial, mas não deve ser usado para comprovar a sessão autenticada.

## Saúde do serviço

```bash
curl --fail --silent --show-error http://127.0.0.1:8000/health
```

Resposta esperada de um ambiente V20 pronto, com Radar vazio:

```json
{
  "status": "ok",
  "service": "portically-processos",
  "version": "1.3.0",
  "update": "Atualização 20 · V20",
  "database": "connected",
  "radar_items": 0
}
```

`radar_items` varia conforme os cadastros. Confira **também** `database`:

| Estado | Significado / ação |
| --- | --- |
| `connected` | Conexão e tabela `public.radar_items` encontradas. |
| `not-linked` | Falta `DATABASE_URL`, `DATA_ENCRYPTION_KEY` ou `DATA_HMAC_KEY`. |
| `table-missing` | Banco acessível, mas tabela do Radar ausente; confira inicialização, permissões e schema. |
| `connection-error` | Falha de conexão ou consulta; confira rede, TLS, credenciais e logs privados. |

O endpoint retorna HTTP 200 e `status: "ok"` mesmo quando o banco está indisponível. Uma checagem somente de HTTP não é uma checagem de prontidão. A contagem pode ser `null` se não estiver disponível. O endpoint não testa envio Resend, validade da chave Fernet, descriptografia nem a tabela de auditoria.

## OTP e Resend

1. `POST /solicitar-codigo` aceita somente o e-mail configurado em `AUTHORIZED_EMAIL`.
2. Um código de seis dígitos é enviado via SDK Resend; não há configuração SMTP na V20.
3. O código expira em 10 minutos, tem limite de cinco tentativas e é removido após validação correta. Solicitar outro substitui o anterior.
4. `POST /validar-codigo` cria uma sessão assinada com duração de oito horas. `POST /sair` remove o cookie.

Verifique o domínio/remetente no painel Resend, os registros DNS exigidos e as permissões da chave. Restrições de contas de teste também podem limitar destinatários. Em falhas de envio, confira os eventos no Resend e `ERRO_ENVIO_OTP` nos logs privados; um erro HTTP 403 exige conferir autorização, remetente e restrições da conta.

`OTP_STORE` é local ao processo: reinícios/deploys apagam códigos pendentes e múltiplos workers ou instâncias podem receber a validação sem conhecer o código. Solicite novo OTP após reiniciar. Não existe registro persistente completo de tentativas de autenticação nesta versão.

## PostgreSQL e persistência

Na inicialização, `init_db()` cria `radar_items` e `audit_log` se necessário e adiciona, de forma idempotente, as colunas de contato criptografado/mascarado. A conta do banco precisa de permissão para criar/alterar essas tabelas e executar SELECT, INSERT e DELETE, incluindo a sequência de auditoria.

- Se faltar banco ou uma das chaves de dados, a criação de tabelas é ignorada e o Radar fica indisponível.
- Se as variáveis estiverem presentes, mas a conexão ou DDL falhar, a inicialização pode falhar.
- As operações usam autocommit; o cadastro/exclusão e sua auditoria são operações separadas. Uma falha de auditoria pode ocorrer após a alteração já ter sido persistida. Confira o estado antes de repetir.
- `doc_hash` tem restrição UNIQUE; um documento repetido pode gerar erro de gravação.
- `audit_log` registra criação e exclusão do Radar. Não representa auditoria completa de todo o sistema.
- O checklist `VALIDATION` fica em memória e é perdido ao reiniciar. Dados processuais exibidos também estão definidos no código; nem todo conteúdo da aplicação está no PostgreSQL.

O Radar grava alvos e preferências com status de integração pendente. A V20 não implementa agendamento automático de buscas oficiais nem entrega automática de alertas por e-mail/WhatsApp. A frequência escolhida é uma preferência armazenada.

## Criptografia e recuperação

Fernet criptografa CPF/CNPJ e, quando habilitados, e-mail e WhatsApp dos alertas. O HMAC-SHA256 identifica o documento normalizado sem armazená-lo em claro para comparação. Nomes, máscaras, preferências, status e metadados continuam em claro; a criptografia de campos não substitui controle de acesso, TLS e proteção dos backups.

Preserve `DATA_ENCRYPTION_KEY` e `DATA_HMAC_KEY` em atualizações e rollback:

- Perder/trocar a chave Fernet impede recuperar os campos previamente criptografados.
- Trocar a chave HMAC altera as impressões digitais e compromete a detecção de duplicidades entre registros antigos e novos.
- A V20 não oferece rotação automática ou migração de chaves. Rotação exige procedimento específico de recriptografia e recálculo dos hashes, com backup e validação.
- Trocar `SESSION_SECRET` invalida sessões existentes e OTPs derivados do segredo anterior.

## Atualização

1. Registre o commit em produção, a versão, o estado de `/health` e as versões efetivas das dependências. Algumas dependências têm limites mínimos, não versões fixas.
2. Faça backup PostgreSQL e confirme recuperação em ambiente isolado. Preserve também a configuração e as chaves em armazenamento protegido.
3. Revise a diferença entre commits, mudanças de schema, variáveis e compatibilidade de dados. Não use o pacote V5 como configuração atual.
4. Valide o commit candidato em ambiente isolado, sem enviar OTPs reais ou usar dados processuais de produção em testes.
5. Selecione o commit aprovado e instale suas dependências:
   ```bash
   git fetch origin
   git checkout <COMMIT_APROVADO>
   python -m pip install -r requirements.txt
   ```
6. Reinicie/reimplante com as mesmas chaves de dados. Espere perda de OTPs pendentes e do checklist em memória.
7. Confira versão/atualização, `database: connected`, contagem esperada e, por usuário autorizado, login OTP e operações do Radar com dados de teste próprios e protegidos. Verifique persistência após reinício e auditoria. Não registre os valores dos testes no repositório.

Alterar apenas este README não muda `APP_VERSION` nem `UPDATE_LABEL`.

## Rollback

1. Pause novas gravações e registre a falha, o commit atual e o último commit estável. Faça backup do estado atual antes de qualquer restauração.
2. Verifique se o código anterior é compatível com o schema/dados atuais. Reverter código não reverte o banco.
3. Reimplante o commit estável com suas dependências compatíveis e a configuração preservada:
   ```bash
   git checkout <COMMIT_ESTAVEL>
   python -m pip install -r requirements.txt
   ```
   Em hospedagem, selecione esse commit no fluxo de deploy/rollback. Não force o histórico da branch compartilhada.
4. Mantenha as chaves Fernet/HMAC correspondentes aos dados. Se houve mudança incompatível, prepare recuperação em banco isolado e valide antes de substituir produção. Restaurar um backup pode perder gravações posteriores; a decisão deve ser explícita.
5. Reinicie o serviço, solicite novo OTP e repita as verificações de saúde, acesso e persistência. Só retome gravações após confirmar a recuperação.

Não faça rollback automático para a V5: ela usa configuração histórica diferente e não deve ser presumida compatível com a V20.

---
Revisão do documento: **V1**.
