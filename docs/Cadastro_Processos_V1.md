# Cadastro seguro de processos — Operação V1

## Integração

V23 consolida a autenticação transacional do PR #2/V21 e os bundles cifrados do PR #3/V22 com a main de referência. Não aplicar os três PRs cegamente: este PR já inclui os módulos/migrações de ambos. Revisar o diff e repetir os testes antes de integrar; os PRs anteriores não foram alterados.

Configure `AUTHORIZED_EMAIL`, `SESSION_SECRET` e `OTP_HMAC_KEY` (32+ bytes independentes), `RESEND_API_KEY`, `RESEND_FROM_EMAIL`, `DATABASE_URL`, `DATA_ENCRYPTION_KEY` (Fernet) e `DATA_HMAC_KEY` (32+ bytes). Todos os workers devem compartilhar os segredos. Preserve as chaves existentes: trocá-las sem migração impede a leitura/identificação dos registros. A chave HMAC de OTP deve ser independente das demais.

## Importar antes de implantar

1. Faça backup restaurável do PostgreSQL e guarde a fonte anterior da main em diretório privado, fora do Git público. Recupere-a por `git show <commit-anterior>:app.py > /caminho/privado/app_anterior.py`. Não registre esse arquivo em commits ou logs.
2. Com o mesmo banco e chave da aplicação, execute:

   ```sh
   python scripts/import_registry_V1.py /caminho/privado/app_anterior.py --confirm-authorized-import
   ```

3. O importador usa AST, sem executar a fonte. Reutiliza o bundle V22 se existir; caso contrário importa o bundle anterior. Importa principal, relacionado, todos os `process_records`, seus `process_documents`, `process_validations` e auditoria relacionada. Se a nova ficha ainda não está no banco, lê `NEW_CASE` da fonte privada. A importação de conteúdo é uma transação, serializada, idempotente e sem sobrescrita de fichas cadastradas. Reexecução ignora fichas já importadas; não incorpora alterações posteriores no legado.
4. Confira pelo painel cada ficha, PDFs/links/hash, notas e validações. Metadados antigos sem fonte temporal ou confirmação registrada permanecem pendentes. O checklist do caso principal antes mantido em memória não pode ser recuperado após reinício: o importador só recebe o estado na fonte privada, sem inventar confirmações. Capture eventual estado operacional antes da troca.
5. Só então implante a branch aprovada. O startup cria tabelas aditivas, sem seeds e sem alterações nas tabelas antigas. Revise permissões PostgreSQL: credencial da aplicação restrita ao banco necessário, tráfego TLS conforme o provedor e backups protegidos.

## Preservação e limites

As tabelas `process_records`, `process_documents`, `process_validations`, `audit_log`, `protected_case_bundles` e as tabelas OTP continuam intactas. A nova migração adiciona `encrypted_process_registry` e `encrypted_process_events`. Cada registro importado retém os dados originais e snapshots documentais/validações/histórico cifrados. O aplicativo usa o registro novo; a apresentação do bundle anterior continua disponível nas abas originais, com validação e histórico novos no registro.

A inclusão e a auditoria compartilham uma transação: falha de auditoria desfaz a inclusão. Validações mantêm histórico, usam bloqueio da linha e recusam revisões antigas. Duplicatas nunca substituem documentos ou validações. Fonte informada não significa consulta/validação automática. Não há cálculo de prazo ou conclusão judicial automática.

Os dados antigos em texto claro no banco e no histórico público do Git permanecem existentes. Esta migração aditiva não elimina cópias anteriores; sua remediação exige trabalho separado. Documentos binários externos não são movidos ou removidos: seus metadados e referências são preservados.

Rollback de código não deve apagar tabelas novas. A versão antiga não exibirá processos novos; preservar o banco e backups. Não reimplantar a versão antiga com seus seeds de sobrescrita sem avaliação.
