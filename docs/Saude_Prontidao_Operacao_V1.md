# Saúde e prontidão do Portically Processos — V1

## Ativação obrigatória

Inicializar com `uvicorn health_app_V1:app --host 0.0.0.0 --port "$PORT"` (ou porta local 8000). O novo ponto de entrada reutiliza o aplicativo, middleware e lifecycle existentes, substitui a rota GET `/health` e registra `/live` e `/ready`. O arquivo original `app.py` não é reenviado nem alterado por este PR.

O ponto de entrada antigo `uvicorn app:app` continua com o comportamento anterior. Atualizar o comando de inicialização e o monitor faz parte da implantação; sem isso a correção não está ativada. A infraestrutura de produção não foi modificada.

## Contrato HTTP

| Rota | Finalidade | Resposta |
| --- | --- | --- |
| `/health`, `/live` | Servidor consegue atender requisições | 200, `{"status":"ok"}` |
| `/ready` | Configuração e PostgreSQL prontos para as funcionalidades instaladas | 200, `{"status":"ready"}`; falha: 503, `{"status":"not-ready"}` |

Rotas públicas, sem OTP. Todas recebem `Cache-Control: no-store, max-age=0` do middleware; `/ready` também define esse cabeçalho diretamente. Não retornam versão, endereço do banco, mensagens de exceção, contagens, e-mails ou informações processuais. Os probes não executam migrações, não inserem registros, não leem conteúdo dos processos e não enviam e-mails.

`/health` era um diagnóstico misto: retornava 200 mesmo sem banco, com estado e contagem de registros. Seu contrato agora é exclusivamente de funcionamento do servidor. Consumidores dos antigos campos devem migrar. Um monitor que continue usando `/health` continua verificando apenas o servidor; configure `/ready` explicitamente para disponibilidade funcional.

## Dependências verificadas

Configuração obrigatória: `DATABASE_URL`, `DATA_ENCRYPTION_KEY`, `DATA_HMAC_KEY`, `AUTHORIZED_EMAIL`, `SESSION_SECRET`, `RESEND_API_KEY`, `RESEND_FROM_EMAIL`. Valores vazios são recusados. A chave Fernet deve ser válida, seguindo a normalização de padding já usada no aplicativo.

O probe abre uma conexão nova, executa `SELECT 1` e consultas `SELECT * ... LIMIT 0` nas tabelas do perfil instalado. Isso verifica existência e permissão de leitura sem recuperar registros. Não basta testar apenas `radar_items`.

| Funcionalidade instalada | Tabelas obrigatórias adicionais |
| --- | --- |
| Base V20/V21/V22 | `radar_items`, `audit_log` |
| Ficha adicional da main atual (`NEW_CASE`) | `process_records`, `process_documents`, `process_validations` |
| OTP persistente do PR #2 (`otp_service`) | `auth_otp_challenges`, `auth_rate_events`, `auth_events` |
| Dados cifrados do PR #3 (`CaseStore`) | `protected_case_bundles` |

A detecção usa os componentes carregados no namespace da aplicação, não uma variável de ambiente que possa desativar tabelas obrigatórias. Ao integrar o OTP, `OTP_HMAC_KEY` e `SESSION_SECRET` devem ter pelo menos 32 bytes, conforme o contrato da V21. Componentes novos ou renomeados exigem atualizar explicitamente o probe e os testes.

Conexão: `connect_timeout=3` segundos; cada comando SQL: `statement_timeout=1000` ms. A transação é somente leitura. Opções são definidas pelo probe e substituem opções equivalentes na string de conexão. A conexão fecha após cada probe, incluindo falhas. O timeout da conexão é por endereço/tentativa do libpq, não um limite absoluto da requisição; DNS e múltiplos hosts podem aumentar a duração. Configure um timeout externo compatível e monitore a latência.

É uma verificação de configuração, conexão e estrutura; não certifica envio real do Resend, validade remota da API key, permissão de escrita, integridade/decriptação do bundle importado, conteúdo cadastrado, completude das colunas ou consulta DataJud/PJe. Esses itens permanecem na validação operacional autenticada. O piloto DataJud do PR #4 é administrativo/opt-in e não é dependência para abrir o painel.

## Implantação e diagnóstico

1. Aplicar migrações e configurar segredos das funcionalidades instaladas antes de encaminhar tráfego. Não usar probes para criar tabelas ou importar dados.
2. Verificar `/live`: deve retornar 200 mesmo durante indisponibilidade do PostgreSQL.
3. Verificar `/ready`: deve retornar 200 com configuração e tabelas acessíveis. Derrubar uma conexão de teste ou retirar uma tabela somente em ambiente descartável deve produzir 503.
4. Configurar o balanceador/monitor/plataforma para usar `/ready` como disponibilidade. Em Kubernetes, usar `/live` como liveness e `/ready` como readiness. Uma queda do banco deve retirar prontidão sem provocar reinicializações por liveness.
5. Se a plataforma oferece uma única rota de saúde, avaliar sua política de reinício: selecionar `/ready` pode também disparar reinicializações, além de impedir tráfego. Configurar tolerância e alertas antes de alterar produção.
6. Em 503, investigar privadamente configuração, conectividade, migrações e permissões com a conta da aplicação. Não publicar credenciais, registros ou logs do banco. O probe não imprime exceções.

Não foi confirmado qual rota a infraestrutura de produção utiliza. Este PR não altera configuração externa, não implanta e não modifica main diretamente. Na reversão, manter as tabelas aditivas e ajustar o monitor à versão implantada; a versão anterior não possui `/ready` e seu `/health` não comprova PostgreSQL disponível.

## Integração com os PRs existentes

Base: main `18f68f0`, posterior à base dos PRs #2 e #3 (`9d87d8d`). Os PRs #2 e #3 continuam abertos e já têm conflitos com main. Este PR não integra nem altera suas branches.

Na resolução desses conflitos, preservar o novo ponto de entrada e usar `health_app_V1:app` com o middleware de segurança/privacidade e as inicializações específicas de cada versão. O probe reconhece os componentes V21 e V22 simultaneamente. Não restaurar a antiga rota `/health` nem retirar a detecção de `NEW_CASE` caso a ficha adicional seja mantida. Repetir os testes de OTP, privacidade, ficha adicional e saúde na árvore integrada antes de implantar.

## Testes

```bash
pip install -r requirements.txt httpx
python -m unittest discover -s tests -p 'test_health_V1.py' -v
python -m unittest discover -s tests -v
```

O teste real requer `TEST_HEALTH_DATABASE_URL` apontando exclusivamente para um banco PostgreSQL vazio e descartável. Ele cria/remove tabelas sintéticas, verifica cada ausência e simula bloqueio real com timeout. Não usar banco compartilhado ou de produção. Sem essa variável, a integração é marcada como ignorada. O workflow `health-readiness-v1.yml` executa com PostgreSQL 16 isolado e credenciais exclusivamente sintéticas. Jobs adicionais aplicam somente os novos arquivos aos commits fixos dos PRs V21/V22 e executam a suíte de saúde e as regressões de cada versão. Não representam um merge dos PRs conflitantes.
