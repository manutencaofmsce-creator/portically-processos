# Dados processuais protegidos — V1

Aplicação v1.3.2 · Atualização 22 · V22. PR independente baseado em main.

## Achados em 09/10/2026

O repositório é público. Autenticação das páginas não protege o Git.
Há identificadores processuais, tribunais e identificação de partes em
`app.py`, tanto em main quanto no PR #2. Há também cópias no README,
rota de processos e bytecode do pacote V5 arquivado. A busca encontrou
identificadores em todas as 21 revisões de app.py alcançáveis pelos refs
obtidos no clone (incluindo branches). Esse levantamento não identifica
forks, caches, downloads externos, refs removidos ou acesso anterior.
Não foi confirmado se são processos reais, exemplos ou divulgação autorizada.
Este documento deliberadamente não reproduz os identificadores ou nomes.

## Separação implementada

O caso principal, relacionado, título e fragmentos de apresentação que
continham nomes e fatos do caso são um único bundle cifrado com Fernet
no PostgreSQL, em `protected_case_bundles`. Os fragmentos preservam as
abas da V20 sem executar código recuperado do banco. São HTML confiável
importado pelo operador; não devem receber edição por usuários nem fontes
externas. Campos estruturados e título são escapados na saída HTML.
A chave `DATA_ENCRYPTION_KEY` é a mesma chave Fernet já usada no Radar;
fica no gerenciador de segredos, fora do Git e separada do banco/backups.

A leitura ocorre somente após validar a sessão nas telas que precisam do
caso. O contexto é isolado por requisição, também entre threads. Não há
fallback público, exemplo automático, log de payload ou conteúdo no health.
Ausência do registro, chave errada e indisponibilidade retornam 503 genérico
com no-store. Login, autenticação e Radar permanecem com seus fluxos atuais.
O OTP em memória da main é preservado: sua correção é o PR #2 separado.
O checklist de validação continua em memória, conforme V20; esta alteração
não reivindica persistência nem suporte integral a múltiplos workers.

A V5 é arquivo descontinuado: a rota de exemplo foi retirada (410), o README
não lista casos e bytecode foi removido da nova árvore. Originais continuam
no histórico. Nenhuma tabela existente é alterada ou apagada na importação.

## Importação antes da implantação

1. Fazer backup cifrado do banco e validar sua restauração em ambiente isolado.
2. Utilizar checkout deste PR somente em ambiente administrativo protegido.
   Configurar `DATABASE_URL` e `DATA_ENCRYPTION_KEY` pelo gerenciador de segredos.
   Banco privado/TLS, credencial de menor privilégio e acesso restrito aos backups
   devem ser configurados no provedor; o PR não altera infraestrutura.
3. Recuperar a versão V20 de app.py do commit base `9d87d8d` para arquivo
   temporário de acesso restrito, fora do Git. Não copiar para tickets ou PRs.
   Exemplo em terminal administrativo: `umask 077`, criar `private/` e usar
   `git show 9d87d8d:app.py > private/legacy.py`. Essa pasta está ignorada.
4. Revisar privadamente a legitimidade dos registros e sua necessidade para a
   aplicação. Executar `python scripts/import_case_V1.py private/legacy.py
   --confirm-authorized-import`. O script analisa AST sem executar o arquivo;
   a confirmação declara autorização para a importação privada, não divulgação.
5. A importação cria somente a tabela nova, cifra todo o bundle e insere
   o slot `primary` em uma transação com trava. Recusa qualquer sobrescrita
   de registro existente. Erros não imprimem dados. Repetição não altera o caso.
6. Validar, com sessão autorizada, título, dois processos e as oito abas,
   comparando com a fonte privada; validar também usuário sem sessão e falha
   do banco. Só então implantar a nova versão. Remover o temporário protegido.

Não implantar antes da importação: as telas do caso ficarão indisponíveis.
A extração dos fragmentos é específica da estrutura V20/V21 e validada contra
as chaves exigidas pela nova apresentação. Futuras mudanças nesse esquema
exigem migração revisada. Não há editor de casos ou importação web neste PR.
Para rollback, conservar tabela/chave e backups. Voltar ao código antigo
restaura seu uso de dados públicos embutidos; evitar esse rollback sem avaliar
privacidade. Não apagar a tabela nova como parte de um rollback.

## Histórico e ações pendentes

Remover dados da árvore atual não remove versões anteriores. main, PR #2,
diffs dos PRs e commits antigos continuarão expondo conteúdo até medidas
adicionais. A branch do PR #2 não foi modificada; após integrar os dois PRs,
resolver a atualização do middleware/versão e repetir ambos os conjuntos
de testes. Este PR não deve ser tratado como remediação completa do histórico.

Antes de tornar o repositório privado ou reescrever histórico: decidir quem
precisa acessar, confirmar natureza/autorização dos dados e inventariar forks,
branches, tags, PRs e consumidores de SHAs. Planejar backup restrito, manutenção,
reclonagem, sincronização do PR #2 e limpeza de refs/caches com suporte do GitHub
quando necessário. Obter autorização explícita para essas ações definitivas.
Não houve force-push, exclusão de branch, alteração de visibilidade ou produção.
Reescrita não garante remoção de cópias já obtidas por terceiros.

## Testes

`python -m pytest -q tests/test_case_privacy_V1.py` verifica árvore pública
(inclusive arquivos binários), constantes, autenticação antes de leitura,
escapamento, todas as abas, falha fechada, extração estática e cifra.
Todos os registros usados em testes são inventados, com IDs `TEST-MAIN` e
`TEST-RELATED`; nenhum número CNJ real ou sintético válido é necessário.
Com `TEST_DATABASE_URL` em PostgreSQL isolado, o teste adicional verifica
importação/roundtrip, recusa de sobrescrita e adulteração do ciphertext.
O workflow executa esse teste com PostgreSQL 16 e não acessa produção.
