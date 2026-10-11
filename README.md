# Portically Processos

Aplicação privada em FastAPI para acompanhamento processual, autenticação por OTP e persistência em PostgreSQL.

## Atualização 21 · v1.4.0

- Inclui o processo `0800534-37.2025.8.20.5001` sem substituir o caso já existente.
- Registra somente dados presentes na decisão de 29/09/2026.
- Mantém o status interno separado do andamento oficial do PJe.
- Exibe próximos passos sem calcular vencimento quando a data de ciência não está disponível.
- Cataloga a decisão pelo ID oficial, fonte, link e SHA-256 do PDF recebido.
- Persiste ficha, documento e validação humana em tabelas PostgreSQL aditivas.
- Não publica o PDF judicial no repositório público.

## Banco de dados

Na inicialização, a aplicação mantém as tabelas existentes e cria, apenas se necessário:

- `process_records`
- `process_documents`
- `process_validations`

O cadastro do novo processo é idempotente. O estado de validação humana não é sobrescrito durante uma nova implantação.

## Executar testes

```bash
python -m unittest discover -v
```

## Executar localmente

```bash
uvicorn app:app --reload
```

As variáveis de ambiente usadas em produção continuam sendo `AUTHORIZED_EMAIL`, `SESSION_SECRET`, `RESEND_API_KEY`, `RESEND_FROM_EMAIL`, `DATABASE_URL`, `DATA_ENCRYPTION_KEY` e `DATA_HMAC_KEY`.
