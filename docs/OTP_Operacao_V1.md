# Portically Processos — operação OTP V1

Aplicação v1.3.1 · Atualização 21 · V21. Esta documentação complementa o
README do PR #1, sem depender dele nem modificá-lo. Substitui a limitação de
OTP em memória da V20. O envio continua pelo Resend.

## Configuração e implantação

Preservar `AUTHORIZED_EMAIL`, `SESSION_SECRET`, `RESEND_API_KEY`,
`RESEND_FROM_EMAIL`, `DATABASE_URL`, `DATA_ENCRYPTION_KEY` e `DATA_HMAC_KEY`.
Adicionar **`OTP_HMAC_KEY`**, segredo aleatório independente com pelo menos
32 bytes. Gerar localmente com `python -c 'import secrets;
print(secrets.token_urlsafe(48))'` e cadastrá-lo no gerenciador de segredos;
nunca colocar o valor no Git, em tickets ou logs. `SESSION_SECRET` também
deve ter ao menos 32 bytes. Todos os workers devem receber os mesmos valores
de configuração e acessar o mesmo PostgreSQL primário.

1. Fazer backup do PostgreSQL e testar a branch em ambiente separado.
2. Configurar `OTP_HMAC_KEY` antes de iniciar a nova versão.
3. Implantar juntos `app.py`, `otp_auth.py` e `otp_schema.sql` junto das
   dependências de `requirements.txt`. O arquivo SQL é necessário em runtime.
4. Na inicialização, a migração aditiva e idempotente cria
   `auth_otp_challenges`, `auth_rate_events` e `auth_events` e seus índices.
   Um advisory lock serializa essa criação entre workers; o esquema do Radar
   também é inicializado em uma transação serializada. Não há alteração de
   registros processuais existentes. A conta do banco precisa criar tabelas e
   índices; se sua política separar migração e runtime, execute previamente
   a migração com a conta adequada e revise as permissões do startup existente.
5. Testar o fluxo completo pelo domínio HTTPS: pedir código, conferir o e-mail,
   entrar no mesmo navegador e tentar reutilizar o código.
6. Reiniciar a aplicação entre pedido e validação para verificar continuidade.

A inicialização falha quando banco/segredos obrigatórios estão indisponíveis.
As rotas de autenticação retornam 503 em falha de armazenamento e jamais
recorrem à memória. O `/health` existente continua sendo uma verificação
limitada do Radar: não certifica disponibilidade do OTP nem do Resend.

## Uso e limites

| Controle | Política |
| --- | --- |
| Validade | 10 minutos desde a reserva, pelo relógio PostgreSQL; o instante de vencimento já é inválido |
| Tentativas por código | Até 5, contando entradas incorretas ou malformadas; uso correto consome o código |
| Pedidos por e-mail autorizado | Até 5 em qualquer janela de 15 minutos, com intervalo de 60 segundos |
| Pedidos por IP | Até 30 em qualquer janela de 60 segundos, incluindo e-mails não autorizados |
| Validações por navegador | Até 10 em qualquer janela de 15 minutos, mesmo após pedir outro código |
| Validações por IP | Até 30 em qualquer janela de 5 minutos |
| Bloqueios | Temporários, com HTTP 429 e `Retry-After`; recusas não prolongam a janela |

O navegador recebe um identificador aleatório em cookie `HttpOnly`, `Secure`,
`SameSite=Strict`, com prazo de 24 horas. Cada desafio é vinculado a esse
identificador. O código deve ser digitado no navegador que fez o pedido;
abrir o e-mail em outro dispositivo é permitido. Uma resposta de pedido
recusado não substitui esse cookie nem invalida códigos ativos.

Reenvio confirmado invalida o código anterior **desse navegador**. Pedidos em
outro navegador não anulam o código legítimo. Falhas de validação não criam
bloqueio global do e-mail autorizado: quem conhece seu e-mail não consegue
esgotar as tentativas do seu código sem também possuir o identificador e o
cookie do desafio. Os limites de envio por conta e IP ainda podem causar uma
espera temporária em caso de abuso ou rede compartilhada; não há bloqueio
permanente automático. Proteção volumétrica deve existir também no proxy.

Os cookies de sessão preservam `HttpOnly`, `Secure` e `SameSite=Strict` e a
validade de oito horas. Somente `AUTHORIZED_EMAIL` recebe código e obtém
sessão. A assinatura e a restrição de e-mail são conferidas nas páginas
protegidas. Origins diferentes do site são recusados nas rotas OTP.

## Resend, falhas e concorrência

O banco recebe somente HMAC-SHA256 com segredo, domínio separado e vínculo ao
UUID do desafio e ao identificador pseudônimo do usuário. Um hash simples de
seis dígitos seria insuficiente contra busca exaustiva. Os códigos existem em
texto claro somente durante geração e envio ao Resend, não em tabelas ou logs.
Não ativar logging de payloads HTTP do provedor.

A reserva e o consumo dos limites são confirmados **antes** do envio. O envio
ocorre fora da transação, evitando manter locks durante chamadas externas.
Somente resposta do Resend com `id` ativa o código. Exceções, resposta sem ID,
envio atrasado ou entrega superada por pedido mais recente não ativam o código.
O texto da exceção do provedor não é registrado, pois pode conter o e-mail e
o código. Uma falha mantém o código anterior ativo, se ainda válido, e mantém
o pedido contabilizado para impedir tentativas de envio ilimitadas.

Se o processo cair após enviar mas antes de confirmar no banco, o código pode
chegar ao e-mail e continuar inválido. Esse intervalo não pode ser resolvido
atomicamente entre PostgreSQL e um provedor externo sem outra arquitetura de
entrega. Após 60 segundos, novo pedido pode recuperar o fluxo, respeitando os
demais limites. Não existe promessa de entrega exatamente uma vez.

Validações concorrentes adquirem locks de taxa e de navegador e bloqueiam a
linha do desafio. Verificação, atualização das tentativas, consumo e auditoria
ocorrem na mesma transação: apenas um worker pode obter sucesso. Falha de
auditoria reverte o consumo e impede emissão de sessão. Se a aplicação cair
após consumir o código e antes de responder com a sessão, será necessário
solicitar outro; o código consumido permanece inutilizável.

O OTP funciona com múltiplos workers. **Ainda manter um worker como padrão
operacional do aplicativo inteiro**: o checklist `VALIDATION` segue em memória
e não está no escopo desta correção. Não confundir persistência de OTP com
persistência de todas as funcionalidades.

O IP vem de `request.client`, não de leitura direta de cabeçalhos fornecidos
pelo usuário. Atrás de proxy, configurar `--proxy-headers` e
`--forwarded-allow-ips` somente para IPs confiáveis do proxy. Não confiar em
`*` com acesso direto à aplicação: um cliente poderia falsificar IP e esquema.
O proxy deve conservar host e HTTPS para que a conferência de Origin funcione.
Usar TLS também na conexão PostgreSQL conforme o ambiente e manter o relógio
do servidor sincronizado.

## Auditoria, retenção e manutenção

`auth_events` registra reserva, entrega confirmada/falha/atraso, recusas,
limites, expiração, falhas de validação e sucesso com horário, HMAC do usuário,
HMAC do IP e UUID opcional. Não registra e-mail/IP em claro, cookie, código,
segredos ou resposta do Resend. Esses HMACs são pseudônimos, não tornam os
eventos isentos de cuidados de privacidade. Restringir acesso ao banco e backups.

Consultar contagens por evento e horário, sem expor identificadores:

```sql
SELECT event, count(*) FROM auth_events
WHERE created_at >= clock_timestamp() - interval '24 hours'
GROUP BY event ORDER BY event;
```

Definir retenção de auditoria conforme sua necessidade antes de automatizar
exclusões. Eventos de taxa com mais de um dia e desafios vencidos há mais de
um dia podem ser removidos periodicamente; isso preserva todas as janelas de
controle. Executar fora do pico, em lotes se o volume crescer, com backup e
VACUUM/autovacuum adequados:

```sql
DELETE FROM auth_rate_events
WHERE occurred_at < clock_timestamp() - interval '1 day';
DELETE FROM auth_otp_challenges
WHERE expires_at < clock_timestamp() - interval '1 day';
```

Não apagar contadores recentes para liberar usuários indiscriminadamente.
Trocar `OTP_HMAC_KEY` exige uma janela coordenada: parar todos os workers,
invalidar desafios ativos/pendentes e remover eventos de taxa antigos ligados
à chave anterior; configurar a nova chave em todos e reiniciar. A troca
interrompe códigos pendentes e reinicia a correlação/limites. A chave de sessão
é independente: não trocá-la apenas para resolver problema de envio.

Rollback: parar workers, voltar ao commit anterior e preservar as novas
tabelas para investigação. Não rodar versões antiga e nova ao mesmo tempo.
A V20 não valida desafios novos e volta a usar OTP em memória; usuários terão
de pedir outro código. Voltar a um único worker. As tabelas adicionais não
exigem exclusão para o rollback.

## Testes

```sh
python -m pip install -r requirements-test.txt
# Configurar TEST_DATABASE_URL em banco PostgreSQL descartável, nunca produção.
python -m pytest -q
```

Cada teste cria um esquema temporário e o remove. A conta de testes deve poder
criar/excluir esquemas. A suíte falha se a URL não estiver configurada, evitando
uma execução que pareça bem-sucedida sem testar PostgreSQL. O workflow
`.github/workflows/otp-tests.yml` fornece PostgreSQL 16 dedicado.

Inclui expiração e limite exato, reutilização, reenvios, tentativas persistentes,
falhas e respostas inválidas do Resend, entrega atrasada, queda com reserva
pendente, novo processo Python, consumo concorrente em dois processos, pedidos
concorrentes, auditoria transacional, indisponibilidade do banco, restrição ao
usuário, isolamento entre navegadores e cookies de sessão. O Resend é simulado;
a entrega real deve ser conferida no ambiente de homologação.
