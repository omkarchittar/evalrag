"""Protect saved experiment inputs and completed observations against mutation."""

from alembic import op

revision = "0002_experiment_immutability"
down_revision = "29dc53d016e7"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE FUNCTION protect_experiment_inputs() RETURNS trigger AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'experiments are append-only';
      END IF;
      IF OLD.status IN ('completed', 'failed') OR
         (to_jsonb(NEW) - ARRAY['status','metrics','started_at','completed_at','error_code'])
         IS DISTINCT FROM
         (to_jsonb(OLD) - ARRAY['status','metrics','started_at','completed_at','error_code']) THEN
        RAISE EXCEPTION 'experiment inputs and completed experiments are immutable';
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql
    """)
    op.execute("""CREATE TRIGGER immutable_experiment BEFORE UPDATE OR DELETE ON evaluation_runs
                  FOR EACH ROW EXECUTE FUNCTION protect_experiment_inputs()""")
    op.execute("""
    CREATE FUNCTION reject_observation_mutation() RETURNS trigger AS $$
    BEGIN
      RAISE EXCEPTION 'observations are append-only';
    END;
    $$ LANGUAGE plpgsql
    """)
    for table in ["evaluation_results", "query_traces"]:
        op.execute(f"""CREATE TRIGGER immutable_observation BEFORE UPDATE OR DELETE ON {table}
                       FOR EACH ROW EXECUTE FUNCTION reject_observation_mutation()""")


def downgrade():
    for table in ["evaluation_results", "query_traces"]:
        op.execute(f"DROP TRIGGER immutable_observation ON {table}")
    op.execute("DROP FUNCTION reject_observation_mutation()")
    op.execute("DROP TRIGGER immutable_experiment ON evaluation_runs")
    op.execute("DROP FUNCTION protect_experiment_inputs()")
