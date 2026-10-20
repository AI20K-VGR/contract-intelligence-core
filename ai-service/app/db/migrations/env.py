from alembic import context

from app.db.tables import metadata

connection = context.config.attributes["connection"]
context.configure(connection=connection, target_metadata=metadata, version_table_schema="ai2",
                  include_schemas=True, include_name=lambda name, kind, parent: kind != "schema" or name == "ai2")
with context.begin_transaction():
    context.run_migrations()
