#!/usr/bin/env python3
"""
Sync production PostgreSQL data to local PostgreSQL.

Requires:
- SSH access to production server
- Local PostgreSQL running (docker compose -f docker-compose.dev.yml up -d)

Usage:
    python scripts/sync_from_production.py
"""

import subprocess
import sys
import os

# Production server details (from DEPLOYMENT.md)
PROD_HOST = "178.156.211.75"
PROD_USER = "austin"
PROD_COMPOSE_PATH = "/opt/apps/mouse_domination"
PROD_DB_USER = "mouse"
PROD_DB_NAME = "mouse_domination"

# Local database (must match docker-compose.dev.yml)
LOCAL_CONTAINER = "mouse_domination_dev_db"
LOCAL_DB_USER = "mouse"
LOCAL_DB_NAME = "mouse_domination"

# Path to this repo's docker-compose.dev.yml
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(SCRIPT_DIR)
LOCAL_COMPOSE_FILE = os.path.join(REPO_DIR, "docker-compose.dev.yml")


def docker_psql(sql, capture=False):
    """Run psql command via local Docker container."""
    cmd = [
        "docker", "exec", "-i", LOCAL_CONTAINER,
        "psql", "-U", LOCAL_DB_USER, "-d", LOCAL_DB_NAME, "-c", sql
    ]
    if capture:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result
    else:
        return subprocess.run(cmd)


def check_local_postgres():
    """Verify local PostgreSQL is running."""
    result = subprocess.run(
        ["docker", "ps", "--filter", f"name={LOCAL_CONTAINER}", "--format", "{{.Status}}"],
        capture_output=True,
        text=True
    )
    if "healthy" not in result.stdout.lower() and "up" not in result.stdout.lower():
        print(f"Error: Local PostgreSQL container '{LOCAL_CONTAINER}' not running.")
        print(f"Start it with: docker compose -f docker-compose.dev.yml up -d")
        sys.exit(1)

    # Test connection
    result = docker_psql("SELECT 1", capture=True)
    if result.returncode != 0:
        print("Error: Cannot connect to local PostgreSQL.")
        print(f"Error details: {result.stderr}")
        sys.exit(1)


def check_ssh_access():
    """Verify SSH access to production."""
    result = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=5", f"{PROD_USER}@{PROD_HOST}", "echo ok"],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"Error: Cannot SSH to {PROD_USER}@{PROD_HOST}")
        print("Check your SSH key is loaded: ssh-add -l")
        sys.exit(1)


def sync_data():
    """
    Sync data from production to local.

    Uses pg_dump --data-only to export just the data (not schema),
    then imports to local database.
    """
    print(f"Syncing from {PROD_HOST} to local PostgreSQL...")

    # Clear existing data first (disable triggers to handle foreign keys)
    print("Clearing local data...")
    clear_sql = """
    DO $$
    DECLARE
        r RECORD;
    BEGIN
        FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename != 'alembic_version') LOOP
            EXECUTE 'TRUNCATE TABLE ' || quote_ident(r.tablename) || ' CASCADE';
        END LOOP;
    END $$;
    """
    result = docker_psql(clear_sql, capture=True)
    if result.returncode != 0:
        print(f"Warning: Could not clear local data: {result.stderr}")

    # Build the command pipeline:
    # 1. SSH to production, run pg_dump
    # 2. Pipe to local docker exec psql
    dump_cmd = (
        f"docker compose -f {PROD_COMPOSE_PATH}/docker-compose.yml "
        f"exec -T db pg_dump -U {PROD_DB_USER} -d {PROD_DB_NAME} "
        f"--data-only --disable-triggers"
    )

    ssh_cmd = f"ssh {PROD_USER}@{PROD_HOST} '{dump_cmd}'"
    local_cmd = f"docker exec -i {LOCAL_CONTAINER} psql -U {LOCAL_DB_USER} -d {LOCAL_DB_NAME}"

    full_cmd = f"{ssh_cmd} | {local_cmd}"

    print(f"Running: ssh ... pg_dump | docker exec ... psql")

    # Import production data
    print("Importing production data...")
    result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error during sync: {result.stderr}")
        sys.exit(1)

    print("Sync complete!")

    # Show row counts
    print("\nRow counts:")
    count_sql = """
    SELECT relname as table, n_live_tup as rows
    FROM pg_stat_user_tables
    ORDER BY relname;
    """
    docker_psql(count_sql)


def main():
    print("Production → Local PostgreSQL Sync")
    print("=" * 40)

    print("\n1. Checking local PostgreSQL...")
    check_local_postgres()
    print("   ✓ Local PostgreSQL is running")

    print("\n2. Checking SSH access...")
    check_ssh_access()
    print(f"   ✓ SSH to {PROD_HOST} works")

    print("\n3. Syncing data...")
    sync_data()

    print("\nDone! Your local database now matches production.")


if __name__ == "__main__":
    main()
