"""Normalizers for ibis/xorq backend connections."""
from __future__ import annotations

from hasher.core import fqn


def normalize_backend(con):
    match con.name:
        case "snowflake":
            return ("backend.snowflake", con.con._host)
        case "postgres":
            params = con.con.info.get_parameters()
            return ("backend.postgres", params.get("host"), con.con.info.port, params.get("dbname"))
        case "pandas":
            return ("backend.pandas", id(con.dictionary))
        case "datafusion" | "duckdb" | "xorq" | "gizmosql":
            return ("backend.local", con.name, con._profile.con_name, con._profile.kwargs_tuple)
        case "trino":
            return ("backend.trino", con.con.host)
        case "bigquery":
            return ("backend.bigquery", con.project_id, con.dataset_id)
        case "pyiceberg":
            p = con.catalog_params
            return ("backend.pyiceberg", con.catalog.name, p["type"], p["uri"], p["warehouse"])
        case "sqlite":
            return ("backend.sqlite", id(con.con) if con.is_in_memory() else con.uri)
        case name:
            raise ValueError(f"no normalization rule for backend {name!r}")


def _build_rules():
    try:
        from xorq.vendor import ibis
        return ((fqn(ibis.backends.BaseBackend), normalize_backend),)
    except ImportError:
        return ()


RULES: tuple = _build_rules()
