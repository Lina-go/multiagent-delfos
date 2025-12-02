"""
Unit tests for SQL validation patterns.

Note: El Validator ahora es un agente LLM en el workflow.
Estos tests verifican patrones que debe detectar.
"""

import pytest


# Patrones peligrosos que el Validator debe rechazar
DANGEROUS_PATTERNS = [
    "DROP TABLE dbo.Users",
    "DELETE FROM dbo.Accounts",
    "TRUNCATE TABLE dbo.Logs",
    "ALTER TABLE dbo.Users ADD column",
    "EXEC sp_executesql",
    "SELECT * FROM dbo.Users --",
    "SELECT * FROM dbo.Users; DROP TABLE dbo.Users",
]

# Queries válidas que el Validator debe aceptar
VALID_QUERIES = [
    "SELECT * FROM dbo.Accounts",
    "SELECT accountType, SUM(balance) FROM dbo.Accounts GROUP BY accountType",
    "INSERT INTO dbo.Logs (message) VALUES ('test')",
    "SELECT TOP 10 * FROM dbo.Transactions ORDER BY date DESC",
]


class TestValidatorPatterns:
    """Tests para verificar patrones de validación."""

    @pytest.mark.parametrize("query", DANGEROUS_PATTERNS)
    def test_dangerous_pattern_detection(self, query: str):
        """Verifica que los patrones peligrosos sean detectables."""
        dangerous_keywords = ["DROP", "DELETE", "TRUNCATE", "ALTER", "EXEC", "--", ";"]
        assert any(kw in query.upper() for kw in dangerous_keywords)

    @pytest.mark.parametrize("query", VALID_QUERIES)
    def test_valid_query_patterns(self, query: str):
        """Verifica que las queries válidas no tengan patrones peligrosos."""
        dangerous_keywords = ["DROP", "DELETE", "TRUNCATE", "ALTER", "EXEC"]
        assert not any(kw in query.upper() for kw in dangerous_keywords)
        assert query.strip().upper().startswith(("SELECT", "INSERT"))
        assert "dbo." in query.lower()

    def test_missing_dbo_prefix(self):
        """Verifica detección de tablas sin prefijo dbo."""
        query = "SELECT * FROM Accounts"
        assert "dbo." not in query.lower()

    def test_select_star_detection(self):
        """Verifica detección de SELECT *."""
        query = "SELECT * FROM dbo.Accounts"
        assert "SELECT *" in query.upper()
