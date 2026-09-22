from sqlalchemy import String
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import FunctionElement


class EmailKey(FunctionElement):
    """Canonical email lookup expression shared by indexes and future auth queries."""

    type = String(320)
    inherit_cache = True


@compiles(EmailKey)
def compile_email_key(element, compiler, **kwargs):
    return f"lower(trim({compiler.process(element.clauses, **kwargs)}))"


@compiles(EmailKey, "postgresql")
def compile_postgresql_email_key(element, compiler, **kwargs):
    # Match PostgreSQL's reflected spelling so autogenerate does not rebuild the index.
    return f"lower(TRIM(BOTH FROM {compiler.process(element.clauses, **kwargs)}))"
