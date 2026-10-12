# Portically Processos — V23

Cadastro individual pelo painel, lista dinâmica PostgreSQL e armazenamento criptografado, integrando a autenticação V21 e os bundles protegidos V22. PR independente baseado na main, sem implantação automática.

- `GET /processos`: lista persistida; `GET/POST /processos/novo`: ficha individual.
- Número CNJ com verificação de dígitos; título, tribunal, fonte e data da coleta obrigatórios. Unidade, classe, partes, situação, resumo e link HTTPS opcionais.
- Todos os campos começam pendentes de validação humana. Desmarcar exige conferência do operador; campos vazios permanecem pendentes.
- Fichas, documentos importados, validações e eventos novos são cifrados com Fernet. CNJ usa índice HMAC para recusar duplicatas, sem sobrescrever.
- Sessão exclusiva de `AUTHORIZED_EMAIL`, CSRF vinculado à sessão, escape de HTML, auditoria atômica e controle de revisão ao validar.
- Sem consulta automática ao DataJud/PJe ou upload de novos PDFs nesta versão.

Leia [Operação e importação V1](docs/Cadastro_Processos_V1.md) **antes de trocar a versão**. Os registros anteriores precisam ser importados pelo operador; nenhuma migração de produção foi executada por este PR.

```sh
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 10000 --workers 1
```

Testes utilizam dados exclusivamente fictícios:

```sh
pip install -r requirements-test.txt
python -m pytest -q
```

`TEST_DATABASE_URL` deve apontar para um PostgreSQL isolado e descartável para os testes de integração.
