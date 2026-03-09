"""Normalizers for ibis/xorq expression types."""
from __future__ import annotations

import itertools
import pathlib
import re
import urllib.error
import urllib.request

import xxhash

from hasher.core import defaulting, fqn
from hasher.rules.backends import normalize_backend


# --- in-memory tables ---

def normalize_inmemorytable(dt):
    return (
        "ibis.InMemoryTable",
        dt.schema.to_pandas(),
        tuple(
            xxhash.xxh128(el.serialize().to_pybytes()).hexdigest()
            for el in dt.to_expr().to_pyarrow_batches()
        ),
    )


def normalize_memory_databasetable(dt):
    return (
        "ibis.MemoryDatabaseTable",
        dt.schema.to_pandas(),
        tuple(
            xxhash.xxh128(el.serialize().to_pybytes()).hexdigest()
            for el in dt.to_expr().to_pyarrow_batches()
        ),
    )


# --- database table: one normalizer per backend ---

def normalize_remote_databasetable(dt):
    return ("ibis.DatabaseTable.remote", dt.name, dt.schema, dt.source, dt.namespace)


def normalize_postgres_databasetable(dt):
    from xorq.common.utils.postgres_utils import get_postgres_n_reltuples
    return (
        "ibis.DatabaseTable.postgres",
        dt.name, dt.schema, dt.source, dt.namespace,
        get_postgres_n_reltuples(dt),
    )


def normalize_snowflake_databasetable(dt):
    from xorq.common.utils.snowflake_utils import get_snowflake_last_modification_time
    return (
        "ibis.DatabaseTable.snowflake",
        dt.name, dt.schema, dt.source, dt.namespace,
        get_snowflake_last_modification_time(dt).tobytes(),
    )


def normalize_bigquery_databasetable(dt):
    query = f"""
    SELECT last_modified_time
    FROM `{dt.namespace.database}.__TABLES__` where table_id = '{dt.name}'
    """
    ((last_modified_time,),) = dt.source.raw_sql(query).to_dataframe()
    return (
        "ibis.DatabaseTable.bigquery",
        dt.name, dt.schema, dt.source, dt.namespace,
        last_modified_time,
    )


def normalize_pyiceberg_databasetable(dt):
    from xorq.common.utils.pyiceberg_utils import get_iceberg_snapshots_ids
    return (
        "ibis.DatabaseTable.pyiceberg",
        dt.name, dt.schema, dt.source, dt.namespace,
        get_iceberg_snapshots_ids(dt),
    )


def normalize_datafusion_databasetable(dt):
    table = dt.source.con.table(dt.name)
    ep_str = str(table.execution_plan())
    if ep_str.startswith(("ParquetExec:", "CsvExec:")) or re.match(
        r"DataSourceExec:.+file_type=(csv|parquet)", ep_str
    ):
        return ("ibis.DatabaseTable.datafusion.file", dt.schema.to_pandas(), ep_str)
    elif ep_str.startswith(("MemoryExec:", "DataSourceExec:")):
        return normalize_memory_databasetable(dt)
    elif "PyRecordBatchProviderExec" in ep_str:
        return ("ibis.DatabaseTable.datafusion.recordbatch", dt.schema.to_pandas(), dt.name)
    elif ep_str.startswith("EmptyExec"):
        raise ValueError("No data to cache")
    else:
        raise ValueError(f"unrecognized DataFusion execution plan: {ep_str!r}")


def normalize_duckdb_file_databasetable(dt):
    import sqlglot as sg
    name = sg.exp.convert(dt.name).sql(dialect=dt.source.name)
    (sql_ddl,) = dt.source.con.sql(
        f"select sql from duckdb_views() where view_name = {name} "
        f"UNION select sql from duckdb_tables() where table_name = {name}"
    ).fetchone()
    return ("ibis.DatabaseTable.duckdb.file", dt.schema.to_pandas(), sql_ddl)


def normalize_duckdb_databasetable(dt):
    import sqlglot as sg
    name = sg.table(dt.name, quoted=dt.source.compiler.quoted).sql(dialect=dt.source.name)
    ((_, plan),) = dt.source.raw_sql(f"EXPLAIN SELECT * FROM {name}").fetchall()
    scan_line = plan.split("\n")[1]
    match re.match(r"\s*│\s*(\w+)\s*│\s*", scan_line).group(1):
        case "ARROW_SCAN" | "PANDAS_SCAN":
            return normalize_memory_databasetable(dt)
        case "READ_PARQUET" | "READ_CSV" | "SEQ_SCAN":
            return normalize_duckdb_file_databasetable(dt)
        case _:
            raise NotImplementedError(scan_line)


def normalize_sqlite_databasetable(dt):
    from xorq.common.utils.sqlite_utils import get_sqlite_stats
    if dt.source.is_in_memory():
        return normalize_memory_databasetable(dt)
    return (
        "ibis.DatabaseTable.sqlite",
        dt.name, dt.schema, dt.source, dt.namespace,
        get_sqlite_stats(dt),
    )


def normalize_xorq_databasetable(dt):
    from xorq.expr.relations import FlightExpr, FlightUDXF
    from xorq.expr import relations as rel

    if isinstance(dt, FlightExpr):
        return ("xorq.FlightExpr", dt.input_expr, _rename_unbound(dt.unbound_expr.op()).to_expr(), dt.make_connection)
    if isinstance(dt, FlightUDXF):
        return ("xorq.FlightUDXF", dt.input_expr, dt.udxf.exchange_f, dt.make_connection)
    native_source = dt.source._sources.get_backend(dt)
    if native_source.name == "xorq":
        return normalize_datafusion_databasetable(dt)
    new_dt = rel.make_native_op(dt)
    return new_dt  # recursively normalized by Hasher


def normalize_databasetable(dt):
    dispatch = {
        "pandas":     normalize_memory_databasetable,
        "datafusion": normalize_datafusion_databasetable,
        "postgres":   normalize_postgres_databasetable,
        "snowflake":  normalize_snowflake_databasetable,
        "xorq":       normalize_xorq_databasetable,
        "duckdb":     normalize_duckdb_databasetable,
        "trino":      normalize_remote_databasetable,
        "gizmosql":   normalize_remote_databasetable,
        "bigquery":   normalize_bigquery_databasetable,
        "pyiceberg":  normalize_pyiceberg_databasetable,
        "sqlite":     normalize_sqlite_databasetable,
    }
    return dispatch[dt.source.name](dt)


# --- other relation types ---

def normalize_remote_table(dt):
    return ("xorq.RemoteTable", dt.schema, dt.remote_expr, dt.source.name)


def normalize_cached_node(node):
    return ("xorq.CachedNode", node.parent, node.cache)


def normalize_read(read):
    read_kwargs = dict(read.read_kwargs)
    try_names = ("path", "paths", "source", "source_list")
    try:
        path = next(v for k in try_names if (v := read_kwargs.get(k)))
    except StopIteration as err:
        raise ValueError("unable to find path in read_kwargs") from err
    if isinstance(path, (list, tuple)) and len(path) == 1:
        path = path[0]
    match path:
        case str() if path.startswith(("http://", "https://")):
            req = urllib.request.Request(path, method="HEAD", headers={"User-Agent": ""})
            resp = urllib.request.urlopen(req)
            headers = resp.info()
            path_token = tuple(
                (k, headers.get(k)) for k in ("Last-Modified", "Content-Length", "Content-Type")
            )
        case str() if path.startswith(("s3", "gs", "gcs")):
            from xorq.expr import api
            meta = api.get_object_metadata(
                path, **{k: v for k, v in read_kwargs.items() if k != "path"}
            )
            path_token = tuple(
                (k, meta.get(k)) for k in ("location", "last_modified", "size", "e_tag", "version")
            )
        case str() | pathlib.Path() if (p := pathlib.Path(path)).exists():
            path_token = read.normalize_method(p)
        case _:
            raise NotImplementedError(f"Don't know how to handle path {path!r}")
    extra = tuple(
        (k, v) for k, v in read.read_kwargs if k in ("mode", "schema", "temporary")
    )
    return ("xorq.Read", read.schema, path_token, extra)


# --- schema / namespace / datatype ---

def normalize_schema(schema):
    return ("ibis.Schema", schema.to_pandas())


def normalize_namespace(ns):
    return ("ibis.Namespace", ns.catalog, ns.database)


def normalize_ibis_datatype(datatype):
    return ("ibis.DataType", datatype.name.lower(), *datatype.args)


# --- UDFs ---

def normalize_input_type(obj):
    return ("ibis.InputType", obj.__class__.__module__, obj.__class__.__name__, obj.name, obj.value)


def normalize_scalar_udf(udf):
    typs = tuple(arg.dtype for arg in udf.args)
    return (
        "ibis.ScalarUDF",
        typs,
        udf.dtype,
        udf.__func__,
        udf.__config__.get("computed_kwargs_expr"),
    )


def normalize_agg_udf(udf):
    (*args, where) = udf.args
    if where is not None:
        raise NotImplementedError
    typs = tuple(arg.dtype for arg in args)
    return ("ibis.AggUDF", typs, udf.dtype, udf.__func__)


# --- expr / op ---

def _rename_unbound(op, prefix="static"):
    """Replace UnboundTable names with sequential stable names."""
    count = itertools.count()

    def rename(node, _, **kwargs):
        from xorq.vendor.ibis.expr.operations.relations import UnboundTable
        if isinstance(node, UnboundTable):
            return node.copy(name=f"{prefix}-{next(count)}")
        return node.__recreate__(kwargs)

    return op.replace(rename)


def _opaque_to_placeholder(node, _, **kwargs):
    """Replace opaque leaf nodes with UnboundTable placeholders for SQL generation."""
    from xorq.expr.relations import CachedNode, FlightExpr, FlightUDXF, HashingTag, Read, RemoteTable
    from xorq.expr import api

    match node:
        case CachedNode():
            name = f"cached-{id(node)}"
        case Read():
            name = f"read-{id(node)}"
        case RemoteTable():
            name = f"remote-{id(node.remote_expr)}"
        case FlightExpr() | FlightUDXF():
            name = f"flight-{id(node)}"
        case HashingTag():
            name = f"tag-{id(node)}"
        case _:
            if kwargs:
                return node.__recreate__(kwargs)
            return node
    return api.table(node.schema, name=name).op()


def normalize_expr(expr):
    from xorq.expr.api import get_compiler, to_sql
    from xorq.expr.relations import CachedNode, Read
    from xorq.vendor.ibis.expr.operations.relations import DatabaseTable, InMemoryTable
    from xorq.vendor.ibis.expr.operations.udf import AggUDF, ScalarUDF

    op = expr.op()
    compiler = get_compiler(expr)
    sql = str(to_sql(op.replace(_opaque_to_placeholder).to_expr().unbind(), compiler=compiler))
    reads = op.find(Read)
    dts = tuple(n for n in op.find(DatabaseTable) if not isinstance(n, (CachedNode, Read)))
    udfs = op.find((AggUDF, ScalarUDF))
    mems = op.find(InMemoryTable)
    return (
        "ibis.Expr",
        sql,
        reads,
        dts,
        udfs,
        tuple(normalize_inmemorytable(m) for m in mems),
    )


@defaulting(ImportError, ())
def _build_rules():
    import xorq.expr.datatypes as dat
    import xorq.expr.relations as rel
    import xorq.vendor.ibis.expr.operations.relations as ir
    from xorq.vendor.ibis.expr.operations.udf import AggUDF, InputType, ScalarUDF
    from xorq.vendor.ibis import expr as ibis_expr

    return (
        (fqn(ibis_expr.types.Expr),   normalize_expr),
        (fqn(ir.DatabaseTable),        normalize_databasetable),
        (fqn(ir.Schema),               normalize_schema),
        (fqn(ir.Namespace),            normalize_namespace),
        (fqn(rel.Read),                normalize_read),
        (fqn(rel.RemoteTable),         normalize_remote_table),
        (fqn(rel.CachedNode),          normalize_cached_node),
        (fqn(dat.DataType),            normalize_ibis_datatype),
        (fqn(InputType),               normalize_input_type),
        (fqn(ScalarUDF),               normalize_scalar_udf),
        (fqn(AggUDF),                  normalize_agg_udf),
    )


RULES: tuple = _build_rules()
