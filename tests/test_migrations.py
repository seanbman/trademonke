from app.telemetry.migrations import migration_files


def test_migrations_are_ordered_and_append_only_named():
    names = [path.name for path in migration_files()]
    assert names == sorted(names)
    assert names == [
        "0001_initial.sql",
        "0002_setup_current_state.sql",
        "0003_service_heartbeats.sql",
        "0004_research_provenance.sql",
        "0005_research_workstation.sql",
    ]
