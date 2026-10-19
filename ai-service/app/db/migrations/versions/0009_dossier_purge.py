"""Permanent dossier tombstones and database-enforced write fencing.

Writers share the transaction advisory gate; purge takes it exclusively.
Resource-specific locks protect immutable ownership without serializing tenants.
"""

from alembic import op

revision = "0009_dossier_purge"
down_revision = "0008_ai2_processing_trace"
branch_labels = None
depends_on = None

SCOPED = (
    "jobs", "dossier_query_snapshots", "contract_edges", "contract_pair_relations",
    "contract_graph_write_receipts", "ai2_processing_trace_events", "sessions", "durable_runs",
)
CHILDREN = ("session_blobs", "durable_checkpoints", "durable_events", "durable_outbox", "durable_audit")


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS ai2.dossier_tombstones (
            tenant_id text NOT NULL, dossier_id text NOT NULL,
            deleted_ms bigint NOT NULL, status text NOT NULL DEFAULT 'pending',
            evidence_json text NOT NULL DEFAULT '{}',
            PRIMARY KEY (tenant_id, dossier_id)
        );
        CREATE INDEX IF NOT EXISTS idx_ai2_pending_purges ON ai2.dossier_tombstones(deleted_ms)
            WHERE status='pending';
        -- Retain ownership history without content, including after deletion.
        CREATE TABLE IF NOT EXISTS ai2.dossier_resource_refs (
            tenant_id text NOT NULL, dossier_id text NOT NULL,
            resource_kind text NOT NULL, resource_id text NOT NULL,
            snapshot_digest text NOT NULL DEFAULT '',
            PRIMARY KEY (tenant_id, dossier_id, resource_kind, resource_id, snapshot_digest)
        );
        CREATE INDEX IF NOT EXISTS idx_ai2_resource_owner ON ai2.dossier_resource_refs(resource_kind, resource_id);
        CREATE INDEX IF NOT EXISTS idx_ai2_digest_owner ON ai2.dossier_resource_refs(snapshot_digest);

        CREATE FUNCTION ai2.purge_write_lock() RETURNS void LANGUAGE sql AS $$
            SELECT pg_advisory_xact_lock_shared(131, 2)
        $$;
        CREATE FUNCTION ai2.lock_dossier_statement() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN PERFORM ai2.purge_write_lock(); RETURN NULL; END $$;

        CREATE FUNCTION ai2.register_dossier_resource(kind text, row_data jsonb)
        RETURNS void LANGUAGE plpgsql AS $$
        DECLARE t text; d text; rid text; doc jsonb; dg text; ids text[];
        BEGIN
            PERFORM ai2.purge_write_lock();
            doc := row_data;
            IF kind = 'sessions' THEN doc := (row_data->>'payload')::jsonb;
            ELSIF kind = 'durable_runs' THEN doc := (row_data->>'snapshot_json')::jsonb;
            END IF;
            t := COALESCE(row_data->>'tenant_id', doc #>> '{record,tenant_id}',
                          doc #>> '{envelope,auth,tenant_id}');
            d := row_data->>'dossier_id';
            IF kind='sessions' THEN
                -- The canonical record owns the session; imported AI1/demo
                -- provenance may contain IDs from before adaptation.
                d := doc #>> '{record,dossier_id}';
                IF (doc #>> '{envelope,auth,dossier_id}' IS NOT NULL
                    AND doc #>> '{envelope,auth,dossier_id}' <> d)
                   OR (doc #>> '{envelope,auth,tenant_id}' IS NOT NULL
                    AND doc #>> '{envelope,auth,tenant_id}' <> t) THEN
                    RAISE EXCEPTION 'AI2_RESOURCE_OWNER_MISMATCH';
                END IF;
            END IF;
            IF d IS NULL THEN
                SELECT array_agg(DISTINCT v #>> '{}') INTO ids
                FROM jsonb_path_query(doc, '$.**.dossier_id') v
                WHERE jsonb_typeof(v) = 'string' AND v #>> '{}' <> '';
                IF cardinality(ids) > 1 THEN
                    RAISE EXCEPTION 'AI2_AMBIGUOUS_DOSSIER_OWNER';
                END IF;
                d := ids[1];
            END IF;
            -- Generic durable runs with no dossier are not dossier content.
            IF d IS NULL THEN RETURN; END IF;
            IF t IS NULL OR t = '' OR d = '' THEN
                RAISE EXCEPTION 'AI2_DOSSIER_OWNER_REQUIRED';
            END IF;
            IF EXISTS (SELECT 1 FROM ai2.dossier_tombstones WHERE tenant_id=t AND dossier_id=d) THEN
                RAISE EXCEPTION 'AI2_DOSSIER_DELETED' USING ERRCODE='23514';
            END IF;
            rid := COALESCE(row_data->>'session_id', row_data->>'run_id', row_data->>'job_id', d);
            -- Shared erasure gates allow writers to overlap. Serialize only
            -- competing registrations of the same globally identified resource.
            IF kind IN ('sessions','durable_runs','jobs') THEN
                PERFORM pg_advisory_xact_lock(hashtextextended('ai2.owner:' || kind || ':' || rid, 0));
            END IF;
            IF kind IN ('sessions','durable_runs','jobs') AND EXISTS (
                SELECT 1 FROM ai2.dossier_resource_refs r
                WHERE r.resource_kind=kind AND r.resource_id=rid
                  AND (r.tenant_id<>t OR r.dossier_id<>d)) THEN
                RAISE EXCEPTION 'AI2_RESOURCE_OWNER_IMMUTABLE';
            END IF;
            INSERT INTO ai2.dossier_resource_refs VALUES (t,d,kind,rid,'') ON CONFLICT DO NOTHING;
            -- Parse encoded JSON fields too. Only named snapshot pins are refs;
            -- durable_runs.snapshot_digest hashes run state, not vector input.
            IF kind = 'jobs' THEN
                doc := jsonb_build_object('request', (row_data->>'request_json')::jsonb,
                    'wire', (row_data->>'wire_json')::jsonb,
                    'result', (row_data->>'result_json')::jsonb);
            ELSIF kind = 'dossier_query_snapshots' THEN
                doc := jsonb_build_object('snapshot_digest', row_data->>'snapshot_digest',
                                         'payload', (row_data->>'payload')::jsonb);
            ELSIF kind NOT IN ('sessions', 'durable_runs') THEN doc := row_data;
            END IF;
            FOR dg IN
                SELECT DISTINCT regexp_replace(v #>> '{}', '^sha256:', '')
                FROM (
                    SELECT jsonb_path_query(doc, '$.**.source_snapshot_digest') v
                    UNION ALL SELECT jsonb_path_query(doc, '$.**.query_snapshot_digest')
                    UNION ALL SELECT jsonb_path_query(doc, '$.**.snapshot_digest')
                ) pins WHERE jsonb_typeof(v) = 'string'
            LOOP
                IF dg ~ '^[0-9a-f]{64}$' THEN
                    INSERT INTO ai2.dossier_resource_refs VALUES (t,d,kind,rid,dg) ON CONFLICT DO NOTHING;
                END IF;
            END LOOP;
        END $$;

        CREATE FUNCTION ai2.guard_dossier_write() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE data jsonb;
        BEGIN
            PERFORM ai2.purge_write_lock();
            data := to_jsonb(NEW);
            IF TG_OP = 'UPDATE' THEN
                -- The old owner is already registered. Check it without decoding
                -- megabytes of unchanged OCR on every progress/lease update.
                IF EXISTS (
                    SELECT 1 FROM ai2.dossier_resource_refs r JOIN ai2.dossier_tombstones t
                    USING (tenant_id,dossier_id)
                    WHERE r.resource_kind=TG_TABLE_NAME AND r.resource_id=COALESCE(
                        to_jsonb(OLD)->>'session_id',to_jsonb(OLD)->>'run_id',
                        to_jsonb(OLD)->>'job_id',to_jsonb(OLD)->>'dossier_id')
                      AND r.tenant_id=COALESCE(to_jsonb(OLD)->>'tenant_id',r.tenant_id)) THEN
                    RAISE EXCEPTION 'AI2_DOSSIER_DELETED' USING ERRCODE='23514';
                END IF;
                IF TG_TABLE_NAME='jobs' THEN
                    IF data->>'wire_json' IS NOT DISTINCT FROM to_jsonb(OLD)->>'wire_json' THEN
                        data := data || '{"wire_json":"{}"}'::jsonb;
                    END IF;
                    IF data->>'request_json'=to_jsonb(OLD)->>'request_json' THEN
                        data := data || '{"request_json":"{}"}'::jsonb;
                    END IF;
                    IF data->>'result_json' IS NOT DISTINCT FROM to_jsonb(OLD)->>'result_json' THEN
                        data := data || '{"result_json":"{}"}'::jsonb;
                    END IF;
                END IF;
            END IF;
            PERFORM ai2.register_dossier_resource(TG_TABLE_NAME, data);
            RETURN NEW;
        END $$;

        CREATE FUNCTION ai2.register_durable_child(child jsonb) RETURNS void LANGUAGE plpgsql AS $$
        DECLARE parent ai2.durable_runs; doc jsonb;
        BEGIN
            SELECT * INTO parent FROM ai2.durable_runs WHERE run_id=child->>'run_id';
            IF NOT FOUND THEN RAISE EXCEPTION 'AI2_RESOURCE_PARENT_MISSING'; END IF;
            IF child->>'tenant_id' IS NOT NULL AND child->>'tenant_id' <> parent.tenant_id THEN
                RAISE EXCEPTION 'AI2_RESOURCE_OWNER_MISMATCH';
            END IF;
            doc := jsonb_build_object('snapshot',parent.snapshot_json::jsonb,
                'payload',(child->>'payload_json')::jsonb,
                'state',(child->>'state_json')::jsonb,
                'details',(child->>'details_json')::jsonb);
            PERFORM ai2.register_dossier_resource('durable_runs',jsonb_build_object(
                'tenant_id',parent.tenant_id,'run_id',parent.run_id,'snapshot_json',doc::text));
        END $$;

        CREATE FUNCTION ai2.guard_dossier_child_write() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE k text; rid text; owner record;
        BEGIN
            PERFORM ai2.purge_write_lock();
            k := CASE WHEN TG_TABLE_NAME='session_blobs' THEN 'sessions' ELSE 'durable_runs' END;
            rid := COALESCE(to_jsonb(NEW)->>'session_id', to_jsonb(NEW)->>'run_id');
            -- Parent must exist; deleted parent IDs cannot recreate orphan blobs/events.
            IF k='sessions' THEN
                IF NOT EXISTS (SELECT 1 FROM ai2.sessions WHERE session_id=rid) THEN
                    RAISE EXCEPTION 'AI2_RESOURCE_PARENT_MISSING';
                END IF;
            ELSE
                PERFORM ai2.register_durable_child(to_jsonb(NEW));
            END IF;
            FOR owner IN SELECT tenant_id, dossier_id FROM ai2.dossier_resource_refs
                         WHERE resource_kind=k AND resource_id=rid
            LOOP
                IF EXISTS (SELECT 1 FROM ai2.dossier_tombstones
                           WHERE tenant_id=owner.tenant_id AND dossier_id=owner.dossier_id) THEN
                    RAISE EXCEPTION 'AI2_DOSSIER_DELETED' USING ERRCODE='23514';
                END IF;
            END LOOP;
            RETURN NEW;
        END $$;

        CREATE FUNCTION ai2.guard_vector_write() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE t text; d text; dg text;
        BEGIN
            PERFORM ai2.purge_write_lock();
            dg := regexp_replace(NEW.snapshot_digest, '^sha256:', '');
            t := NULLIF(current_setting('ai2.vector_tenant', true), '');
            d := NULLIF(current_setting('ai2.vector_dossier', true), '');
            IF t IS NOT NULL AND d IS NOT NULL THEN
                IF EXISTS (SELECT 1 FROM ai2.dossier_tombstones WHERE tenant_id=t AND dossier_id=d) THEN
                    RAISE EXCEPTION 'AI2_DOSSIER_DELETED' USING ERRCODE='23514';
                END IF;
                INSERT INTO ai2.dossier_resource_refs VALUES
                    (t,d,'vector_segments',dg,dg) ON CONFLICT DO NOTHING;
            ELSIF EXISTS (SELECT 1 FROM ai2.dossier_resource_refs WHERE snapshot_digest=dg)
              AND NOT EXISTS (
                  SELECT 1 FROM ai2.dossier_resource_refs r
                  WHERE r.snapshot_digest=dg AND NOT EXISTS (
                      SELECT 1 FROM ai2.dossier_tombstones x
                      WHERE x.tenant_id=r.tenant_id AND x.dossier_id=r.dossier_id)) THEN
                RAISE EXCEPTION 'AI2_DOSSIER_DELETED' USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END $$;

        -- Keep audit append-only except for explicit erasure of an entire deleted run.
        CREATE OR REPLACE FUNCTION ai2.reject_audit_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
            IF TG_OP='DELETE' AND EXISTS (
                SELECT 1 FROM ai2.dossier_resource_refs r JOIN ai2.dossier_tombstones t
                USING (tenant_id,dossier_id)
                WHERE r.resource_kind='durable_runs' AND r.resource_id=OLD.run_id
                  AND r.tenant_id=OLD.tenant_id) THEN RETURN OLD;
            END IF;
            RAISE EXCEPTION 'durable audit is append-only';
        END $$;
    """)
    for table in SCOPED:
        # Backfill exact structured ownership/digest history before installing guards.
        op.execute(f"SELECT ai2.register_dossier_resource('{table}', to_jsonb(r)) FROM ai2.{table} r")
        op.execute(f"""CREATE TRIGGER dossier_write_fence BEFORE INSERT OR UPDATE ON ai2.{table}
            FOR EACH ROW EXECUTE FUNCTION ai2.guard_dossier_write()""")
    for table in CHILDREN:
        if table != "session_blobs":
            op.execute(f"SELECT ai2.register_durable_child(to_jsonb(r)) FROM ai2.{table} r")
        op.execute(f"""CREATE TRIGGER dossier_child_fence BEFORE INSERT OR UPDATE ON ai2.{table}
            FOR EACH ROW EXECUTE FUNCTION ai2.guard_dossier_child_write()""")
    op.execute("""CREATE TRIGGER dossier_vector_fence BEFORE INSERT OR UPDATE ON ai2.vector_segments
        FOR EACH ROW EXECUTE FUNCTION ai2.guard_vector_write()""")
    # Acquire before row locks, including for UPDATEs that affect zero rows.
    for table in (*SCOPED, *CHILDREN, "vector_segments"):
        op.execute(f"""CREATE TRIGGER dossier_statement_lock BEFORE INSERT OR UPDATE OR DELETE
            ON ai2.{table} FOR EACH STATEMENT EXECUTE FUNCTION ai2.lock_dossier_statement()""")


def downgrade():
    # Old graph migrations remain reversible on databases that have never purged.
    # After erasure, reverting the guards would permit resurrection by an old worker.
    from sqlalchemy import text

    if op.get_bind().execute(text("SELECT 1 FROM ai2.dossier_tombstones LIMIT 1")).scalar():
        raise RuntimeError("Cannot downgrade dossier fencing after a purge")
    for table in (*SCOPED, *CHILDREN, "vector_segments"):
        op.execute(f"DROP TRIGGER dossier_statement_lock ON ai2.{table}")
    for table in SCOPED:
        op.execute(f"DROP TRIGGER dossier_write_fence ON ai2.{table}")
    for table in CHILDREN:
        op.execute(f"DROP TRIGGER dossier_child_fence ON ai2.{table}")
    op.execute("DROP TRIGGER dossier_vector_fence ON ai2.vector_segments")
    for function in ("guard_dossier_write()", "guard_dossier_child_write()", "guard_vector_write()",
                     "register_durable_child(jsonb)", "register_dossier_resource(text,jsonb)",
                     "lock_dossier_statement()", "purge_write_lock()"):
        op.execute(f"DROP FUNCTION ai2.{function}")
    op.execute("""CREATE OR REPLACE FUNCTION ai2.reject_audit_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'durable audit is append-only'; END $$""")
    # Metadata tables intentionally survive: ownership history is not contract content.
