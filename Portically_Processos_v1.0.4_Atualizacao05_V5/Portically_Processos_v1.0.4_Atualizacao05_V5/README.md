# PORTICALLY PROCESSOS — v1.0.4 · Atualização 05 · V5

Continuação da base existente do módulo **PORTICALLY PROCESSOS**, sem recriação do projeto.

## Mantido como regra obrigatória

- Módulo interno do **PORTICALLY HUB**.
- Processo piloto isolado: **0800534-37.2025.8.20.5001**.
- Nenhum Processo 02 deve ser sincronizado antes do fechamento do piloto.
- Nenhum dado processual é exposto antes da autenticação.
- Número CNJ exige correspondência exata; não há associação aproximada.
- Somente fontes oficiais podem alimentar a sincronização processual.
- CAPTCHA, validação humana, conteúdo restrito ou autenticação legítima nunca devem ser contornados.
- Documento oficial deverá manter origem, identificador, data/hora, data de captura e hash de integridade quando incorporado.
- Histórico e auditoria não devem ser apagados por atualizações.

## O que foi implementado nesta atualização

### Autenticação
- Geração criptograficamente segura de OTP de 6 dígitos.
- OTP de uso único, com expiração, limite de tentativas e cooldown de nova solicitação.
- Envio por SMTP configurável.
- Modo `console` exclusivamente para desenvolvimento; bloqueado em produção.
- Sessão assinada com HMAC e cookie `HttpOnly`, `SameSite=Strict` e `Secure` configurável.
- Endpoints de sessão e logout.
- Registro de tentativas e eventos de autenticação em log JSONL de auditoria.

### Área autenticada
- Nova rota `/processos`.
- Processo piloto fixado como único processo nesta etapa.
- Abas: Resumo, Movimentações, Documentos, Fontes Oficiais, Relacionados, Sincronização e Auditoria.
- Estados explícitos sem simulação de sincronização:
  - `EM_VALIDACAO`
  - `AGUARDANDO_VALIDACAO_HUMANA`
  - `AGUARDANDO_DOCUMENTOS_OFICIAIS`
  - relacionados `NAO_VALIDADO`
- Nenhum andamento, documento ou vínculo relacionado é inventado antes da coleta oficial verificável.

## Variáveis de ambiente

Copie `backend/.env.example` para `backend/.env` e configure:

- `AUTHORIZED_EMAIL`
- `SESSION_SECRET`
- `OTP_PROVIDER=smtp`
- parâmetros `SMTP_*`
- `SESSION_COOKIE_SECURE=true` em produção com HTTPS

Para desenvolvimento local sem SMTP, use `OTP_PROVIDER=console` e `SESSION_COOKIE_SECURE=false`. O código aparecerá apenas no terminal do backend.

## Próxima etapa técnica

Conectar o adaptador de sincronização oficial do processo piloto, mantendo três resultados possíveis por fonte:

1. **Automático** — fonte acessível e identidade CNJ validada 100%.
2. **Aguardando validação humana** — CAPTCHA, confirmação legítima ou outra ação humana permitida.
3. **Acesso restrito** — conteúdo exige autenticação/permissão legítima.

Somente após essa camada deve ocorrer a incorporação do inventário documental e cálculo de hash SHA-256.
