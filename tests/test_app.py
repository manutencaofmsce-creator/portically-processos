import unittest
from unittest.mock import patch

from starlette.requests import Request

import app


def request(path="/"):
    return Request({
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "client": ("test", 1234),
        "server": ("testserver", 443),
        "root_path": "",
    })


class NewCaseTests(unittest.TestCase):
    def response_text(self, response):
        return response.body.decode("utf-8")

    def test_process_list_includes_new_case(self):
        with patch.object(app, "auth", return_value=True):
            response = app.processos(request("/processos"))

        body = self.response_text(response)
        self.assertIn("0800534-37.2025.8.20.5001", body)
        self.assertIn("7ª Vara Cível da Comarca de Natal", body)

    def test_document_tab_has_official_link_and_hash(self):
        with patch.object(app, "auth", return_value=True):
            response = app.detalhe(
                app.NEW_CASE["cnj"], request(f"/processos/{app.NEW_CASE['cnj']}"), "documentos"
            )

        body = self.response_text(response)
        self.assertIn(app.NEW_CASE["document_id"], body)
        self.assertIn(app.NEW_CASE["document_sha256"], body)
        self.assertIn(app.NEW_CASE["official_url"].replace("&", "&amp;"), body)
        self.assertIn("não foi adicionado ao repositório público", body)

    def test_deadline_is_not_invented(self):
        body = app.new_case_tab_content("prazos")
        self.assertIn("15 dias", body)
        self.assertIn("Termo inicial e vencimento não informados", body)

    def test_validation_requires_all_five_checks(self):
        partial = {"metadata": True, "decision": True}
        complete = {key: True for key in (
            "metadata", "decision", "status", "next_steps", "document_link"
        )}

        self.assertEqual(app.new_case_validation_status(partial)[:2], ("Parcialmente validado", 2))
        self.assertEqual(app.new_case_validation_status(complete)[:2], ("Validado manualmente", 5))

    def test_database_initialization_is_additive_and_idempotent(self):
        statements = []

        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def execute(self, statement, params=None):
                statements.append((" ".join(statement.split()), params))

        class Connection:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def cursor(self):
                return Cursor()

        with patch.object(app, "db_ready", return_value=True), patch.object(
            app, "db_conn", return_value=Connection()
        ):
            app.init_db()

        sql = "\n".join(statement for statement, _ in statements).upper()
        self.assertNotIn("DROP TABLE", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS PROCESS_RECORDS", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS PROCESS_DOCUMENTS", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS PROCESS_VALIDATIONS", sql)
        self.assertIn("ON CONFLICT (PROCESS_CNJ) DO NOTHING", sql)


if __name__ == "__main__":
    unittest.main()
