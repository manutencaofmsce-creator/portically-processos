# Portically Processos — piloto DataJud V1

## Resultado e escopo

Piloto administrativo executável, manual e opt-in, sem novas rotas públicas. Recupera capas/metadados e movimentações para um único número CNJ exato por execução. Permite TJRN, TJCE, TRT7, TRT21 e TRF1; não consulta por nomes/CPF/CNPJ, não busca relacionados automaticamente e não baixa documentos. Guarda snapshots independentes de cada consulta no PostgreSQL, cifrados com Fernet; índices usam HMAC por processo. Fonte oficial, início/fim UTC, resultado e histórico ficam persistentes. Um resultado vazio não significa inexistência do processo ou ausência de movimentações. DataJud não assegura completude ou atualização em tempo real.

Não houve implantação, uso de dados do usuário, mudança de main ou confirmação de PDFs. A disponibilização destes snapshots nas telas é uma etapa posterior à integração V21/V22. A autenticação existente continua intacta; acesso ao piloto depende das credenciais administrativas do banco/ambiente. Nunca exponha o CLI pela web. Não representa integração PJe homologada nem monitoramento agendado.

## Pesquisa oficial em 11/10/2026 UTC (10/10 em Fortaleza)

| Fonte | Dados e acesso | Decisão |
|---|---|---|
| API Pública DataJud | Capas e movimentos; proteção de dados das partes e processos sigilosos; cabeçalho `Authorization: APIKey` com chave pública rotativa do CNJ | Primeira integração viável |
| API DataJud para tribunais | Interface distinta com credenciais institucionais, inclusive dados restritos | Fora do piloto |
| PJe/MNI | Interoperabilidade SOAP/WSDL, versão/serviço e operações dependem do tribunal; documentos apenas quando o serviço, usuário e processo permitem | Sem conector até confirmar documentação e autorização local |
| SEEU/MNI | Documentação oficial exemplifica `consultarProcesso`, identificação/senha de órgão jurídico externo, movimentos e inclusão de documentos sujeitos a sigilo | Evidência de acesso condicionado, não contrato universal de TJRN/TRT7 |

Referências consultadas (somente oficiais):
- https://datajud-wiki.cnj.jus.br/api-publica/ — alcance público.
- https://datajud-wiki.cnj.jus.br/api-publica/acesso/ — autenticação/chave rotativa.
- https://datajud-wiki.cnj.jus.br/api-publica/endpoints/ — aliases oficiais.
- https://datajud-wiki.cnj.jus.br/api-publica/glossario/ — campos e número sem formatação.
- https://datajud-wiki.cnj.jus.br/api-publica/exemplos/exemplo1/ — POST e consulta por número.
- https://datajud-wiki.cnj.jus.br/api-publica/termo-uso/ — condições de uso.
- https://www.cnj.jus.br/integracao-para-os-tribunais/ — homologação/autorização e MNI.
- https://docs.pje.jus.br/servicos-negociais/servico-pje-legacy/notas-da-versao/ — operações MNI do PJe.
- https://docs.seeu.pje.jus.br/docs/documentacao-tecnica/manual_intercomunicacao_service/ — contrato SEEU, distinto de outros tribunais.

As páginas diretas da Wiki/CNJ retornaram HTTP 403 neste ambiente. Os trechos oficiais foram recuperados pelo índice de pesquisa; não equivale a validar o serviço em produção. Revisar páginas e termo integral no ambiente do operador antes de executar. O termo publicado restringe a finalidade a uso legal, não comercial e autorizado e não garante atualidade. O piloto atende uso pessoal; eventual exploração comercial do Hub exige verificar autorização aplicável antes de ativá-lo.

Para PJe: obter do tribunal o endpoint oficial, versão/WSDL, ambiente de homologação, modalidade de autenticação e habilitação do usuário/órgão, escopo permitido e requisitos de rede. Não presumir que login de navegador ou certificado concede acesso MNI. Não contornar CAPTCHA/OTP, reutilizar credenciais alheias ou fazer scraping. Só catalogar documento disponível após resposta oficial autorizada com identificação, origem, captura e integridade do conteúdo.

## Operação

Instalar `requirements.txt`. Configurar no ambiente privado (não no Git nem na linha de comando): `DATABASE_URL`, `DATA_ENCRYPTION_KEY` (Fernet válida), `DATA_HMAC_KEY` (mínimo 32 caracteres), `DATAJUD_API_KEY` (chave vigente da Wiki), `DATAJUD_COURT` (`tjrn`, `tjce`, `trt7`, `trt21`, `trf1`) e `DATAJUD_PROCESS_NUMBER` (CNJ válido). Não há número real ou chave fixados no código. Confirmar o direito de consulta e o termo do CNJ.

```sh
python datajud_sync_V1.py --authorized-personal-use
python datajud_sync_V1.py --authorized-personal-use --history
python -m pytest -q tests/test_datajud_sync_V1.py
```

O sinalizador declara confirmação pelo operador; não concede permissão. A tabela `judicial_sync_runs_v1` é criada aditivamente. Conceder acesso apenas ao operador/backend autorizado; chaves e banco nunca devem ser públicos. A criação de tabela necessita permissão DDL inicial. O CLI retorna apenas ID da execução, estado e quantidade de registros; histórico não imprime número ou conteúdo processual. Para examinar snapshots, operador autorizado pode decifrar `encrypted_payload` com a chave do ambiente; não exportar em logs públicos. Manter backup das chaves; rotacioná-las requer migração dos ciphertexts/HMACs.

Uma consulta por processo a cada 60 segundos no mínimo, serializada no PostgreSQL. Timeout de rede 20 s, sem retries automáticos, sem redirecionamentos, tamanho de resposta limitado a 4 MiB. Valida dígito CNJ, tribunal e identidade exata em todos os hits. Guarda todas as instâncias retornadas; mais de 100 hits, timeout de origem, shards falhos ou total inexato são `partial_response`, sem incorporar dados parciais. Duplicatas idênticas de movimentos dentro do snapshot são eliminadas; snapshots históricos nunca são sobrescritos. Não infere que cada movimento represente documento disponível.

Resultados: `success`, `not_found`, `access_denied`, `rate_limited`, `network_error`, `http_error`, `invalid_response`, `partial_response`, `identity_mismatch`, `restricted_data`, `response_too_large`, `configuration_error`, `unexpected_error`. Erros nunca guardam corpo HTTP/chaves. Início é gravado antes da rede; se banco falhar, nenhuma consulta é feita. Se o processo cair ou a finalização falhar, a linha permanece `started` para revisão administrativa; nunca marca sucesso sem persistência. Falhas de configuração/início podem impedir criar histórico; CLI retorna erro genérico e código diferente de zero. Ausência de chave resulta em tentativa `configuration_error`, sem chamada HTTP.

## Coordenação V21/V22

Base: main `9d87d8d0c5f8c14b9e4d46e7ed354e7a6521f04b`. PR #2 (OTP persistente V21) e #3 (dados cifrados V22) estavam abertos. Apenas arquivos novos; não altera `app.py`, `case_store.py`, `otp_auth.py`, requirements ou workflow existente. Não importa constantes com dados embutidos na main nem extrai bundle V22. Não promove snapshots a conteúdo validado. Aplicar após/rebasear sobre ambos e executar conjuntos de regressão antes de conectar às telas. Main ainda possui exposição descrita no PR #3; este piloto não remedia histórico público.

## Validação

Testes usam exclusivamente identificadores sintéticos gerados e respostas fictícias, sem rede. CI usa PostgreSQL 16 isolado para histórico, cifra, cooldown e falhas. Local: 25 testes passaram; 1 integração PostgreSQL inicialmente ignorada por falta de servidor. Compilação e `git diff --check` obrigatórios. A tentativa ao serviço real usa somente o exemplo público da documentação CNJ, nunca um processo do usuário; registrar abaixo o resultado efetivamente observado, sem afirmar sincronização produtiva.

Consulta de conectividade oficial: o exemplo público do CNJ retornou HTTP 200 e 1 registro. Nenhum conteúdo processual foi impresso ou salvo no repositório. Não valida produção nem o processo pessoal do usuário.
O mesmo exemplo foi consultado pelo adaptador V1, com validação CNJ/tribunal: sucesso, 1 registro, 43 movimentações e 0 documentos baixados. O resultado permaneceu em memória e foi descartado após contagem; a persistência é validada separadamente com dados sintéticos.
