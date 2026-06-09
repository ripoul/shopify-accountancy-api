import os
from unittest.mock import patch

from django.test import TestCase

from config.settings import database_config


class DatabaseConfigTest(TestCase):
    def test_sqlite_when_no_database_url(self):
        env = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
        with patch.dict(os.environ, env, clear=True):
            config = database_config()
        self.assertEqual(config["ENGINE"], "django.db.backends.sqlite3")

    def test_postgres_config_from_database_url(self):
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost:5432/mydb"}):
            config = database_config()
        self.assertEqual(config["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(config["NAME"], "mydb")
        self.assertEqual(config["USER"], "user")
        self.assertEqual(config["PASSWORD"], "pass")
        self.assertEqual(config["HOST"], "localhost")
        self.assertEqual(config["PORT"], "5432")

    def test_postgres_scheme_also_accepted(self):
        with patch.dict(os.environ, {"DATABASE_URL": "postgres://user:pass@db.example.com:5432/appdb"}):
            config = database_config()
        self.assertEqual(config["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(config["NAME"], "appdb")

    def test_invalid_scheme_raises_value_error(self):
        with patch.dict(os.environ, {"DATABASE_URL": "mysql://user:pass@localhost:3306/mydb"}):
            with self.assertRaises(ValueError):
                database_config()

    def test_postgres_host_override_from_query_string(self):
        with patch.dict(
            os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost:5432/mydb?host=/var/run/postgresql"}
        ):
            config = database_config()
        self.assertEqual(config["HOST"], "/var/run/postgresql")
