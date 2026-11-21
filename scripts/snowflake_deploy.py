#!/usr/bin/env python3
"""
Snowflake CD Deployment Script
-------------------------------
Deploys the dbt project(s) to Snowflake using native Git integration
and Snowflake's dbt Projects execution environment.

This script is designed to be run from GitHub Actions CD pipeline.
It is idempotent and safe to re-run.

Required environment variables (set via GitHub Secrets):
  SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD,
  SNOWFLAKE_ROLE, SNOWFLAKE_WAREHOUSE, SNOWFLAKE_DATABASE,
  GITHUB_REPO_URL
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

# ── Mask secrets in GitHub Actions logs ──────────────────────────────
MASKED_KEYS = ["SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD"]
for key in MASKED_KEYS:
    val = os.environ.get(key, "")
    if val:
        print(f"::add-mask::{val}")


def get_env(name: str, required: bool = True) -> str:
    """Get environment variable, failing if required and missing."""
    val = os.environ.get(name, "").strip()
    if required and not val:
        print(f"::error::Missing required environment variable: {name}")
        sys.exit(1)
    return val


# ── Try loading .env for local runs ──────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Configuration ────────────────────────────────────────────────────
ACCOUNT = get_env("SNOWFLAKE_ACCOUNT")
USER = get_env("SNOWFLAKE_USER")
PASSWORD = get_env("SNOWFLAKE_PASSWORD")
ROLE = get_env("SNOWFLAKE_ROLE", required=False) or "ACCOUNTADMIN"
WAREHOUSE = get_env("SNOWFLAKE_WAREHOUSE", required=False) or "COMPUTE_WH"
DATABASE = get_env("SNOWFLAKE_DATABASE", required=False) or "ECOM_DB"
GITHUB_REPO_URL = get_env("GITHUB_REPO_URL", required=False) or "https://github.com/SonjeVilas/dbt-project-factory.git"

# Snowflake object names
SCHEMA = get_env("SNOWFLAKE_SCHEMA", required=False) or "RAW"
API_INTEGRATION = os.environ.get("SNOWFLAKE_API_INTEGRATION", "GITHUB_API_INTEGRATION")
GIT_REPO_NAME = os.environ.get("SNOWFLAKE_GIT_REPO", "DBT_PROJECT_FACTORY_REPO")
FQ_GIT_REPO = f"{DATABASE}.{SCHEMA}.{GIT_REPO_NAME}"


def get_projects_to_deploy() -> list[tuple[str, str]]:
    """Determine which dbt project(s) to deploy: returns [(rel_path, snowflake_project_name)]."""
    # 1. CLI argument takes highest precedence
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        path = sys.argv[1].replace("\\", "/").rstrip("/")
        name = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("DBT_PROJECT_NAME", "")
        if not name:
            base = os.path.basename(path)
            name = "RETAIL_DBT_PROJECT" if base == "retail_dbt_v1" else f"{base.upper()}_PROJECT"
        return [(path, name)]

    # 2. Explicit DBT_PROJECT_PATH environment variable
    env_path = os.environ.get("DBT_PROJECT_PATH", "").strip().replace("\\", "/").rstrip("/")
    if env_path and env_path.lower() != "all":
        name = os.environ.get("DBT_PROJECT_NAME", "")
        if not name:
            base = os.path.basename(env_path)
            name = "RETAIL_DBT_PROJECT" if base == "retail_dbt_v1" else f"{base.upper()}_PROJECT"
        return [(env_path, name)]

    # 3. Auto-discover all generated projects in generated_projects/
    discovered = []
    base_dir = "generated_projects"
    if os.path.isdir(base_dir):
        for item in sorted(os.listdir(base_dir)):
            full_path = os.path.join(base_dir, item)
            if os.path.isdir(full_path) and os.path.exists(os.path.join(full_path, "dbt_project.yml")):
                rel_path = f"generated_projects/{item}"
                name = "RETAIL_DBT_PROJECT" if item == "retail_dbt_v1" else f"{item.upper()}_PROJECT"
                discovered.append((rel_path, name))

    if not discovered:
        return [("generated_projects/retail_dbt_v1", "RETAIL_DBT_PROJECT")]
    return discovered


def connect():
    """Establish Snowflake connection."""
    import snowflake.connector

    print("🔌 Connecting to Snowflake...")
    conn = snowflake.connector.connect(
        account=ACCOUNT,
        user=USER,
        password=PASSWORD,
        role=ROLE,
        warehouse=WAREHOUSE,
        database=DATABASE,
        schema=SCHEMA,
    )
    print("✅ Connected to Snowflake")
    return conn


def execute_sql(cursor, sql: str, description: str = "") -> list:
    """Execute SQL and return results with logging."""
    label = description or sql[:60]
    print(f"\n{'─' * 60}")
    print(f"📌 {label}")
    print(f"{'─' * 60}")

    try:
        cursor.execute(sql)
        results = cursor.fetchall()
        print(f"✅ Success – {cursor.rowcount} row(s)")
        return results
    except Exception as e:
        print(f"❌ Failed: {e}")
        raise


def step_summary(title: str, body: str):
    """Append to GitHub Actions step summary."""
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a") as f:
            f.write(f"## {title}\n{body}\n\n")


def main():
    results_log = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "started",
        "steps": [],
    }
    conn = None

    try:
        projects = get_projects_to_deploy()
        print(f"📦 Projects targeted for deployment ({len(projects)}):")
        for p_path, p_name in projects:
            print(f"   • {p_name} -> {p_path}")

        conn = connect()
        cur = conn.cursor()

        # ── Step 1: Use correct context ──────────────────────────────
        execute_sql(cur, f"USE ROLE {ROLE}", "Set role")
        execute_sql(cur, f"USE WAREHOUSE {WAREHOUSE}", "Set warehouse")
        execute_sql(cur, f"USE DATABASE {DATABASE}", "Set database")
        execute_sql(cur, f"USE SCHEMA {SCHEMA}", "Set schema")
        results_log["steps"].append({"step": "set_context", "status": "success"})

        # ── Step 2: Create Git Repository (idempotent) ───────────────
        create_repo_sql = f"""
        CREATE GIT REPOSITORY IF NOT EXISTS {FQ_GIT_REPO}
            API_INTEGRATION = {API_INTEGRATION}
            ORIGIN = '{GITHUB_REPO_URL}'
        """
        execute_sql(cur, create_repo_sql, "Create Git Repository (idempotent)")
        results_log["steps"].append({"step": "create_git_repo", "status": "success"})

        # ── Step 3: Fetch latest from GitHub ─────────────────────────
        fetch_sql = f"ALTER GIT REPOSITORY {FQ_GIT_REPO} FETCH"
        execute_sql(cur, fetch_sql, "Fetch latest code from GitHub")
        results_log["steps"].append({"step": "git_fetch", "status": "success"})

        # ── Step 4: Verify branch exists ─────────────────────────────
        branches = execute_sql(
            cur,
            f"SHOW GIT BRANCHES IN GIT REPOSITORY {FQ_GIT_REPO}",
            "List branches in Git repository",
        )
        branch_names = [row[0] if len(row) > 0 else str(row) for row in branches]
        print(f"📂 Available branches: {branch_names}")

        # ── Step 5 & 6: Deploy and build each project ─────────────────
        for rel_path, proj_name in projects:
            fq_dbt_project = f"{DATABASE}.{SCHEMA}.{proj_name}"
            stage_path = f"@{FQ_GIT_REPO}/branches/main/{rel_path}"

            create_project_sql = f"""
            CREATE OR REPLACE DBT PROJECT {fq_dbt_project}
                FROM '{stage_path}'
            """
            execute_sql(cur, create_project_sql, f"Create/Replace dbt Project ({proj_name})")
            results_log["steps"].append({"step": f"create_{proj_name}", "status": "success"})

            print(f"\n🚀 Executing dbt build for {proj_name} (this may take several minutes)...")
            execute_sql(
                cur,
                f"EXECUTE DBT PROJECT {fq_dbt_project} ARGS = 'build'",
                f"Execute dbt build ({proj_name})",
            )
            results_log["steps"].append({"step": f"build_{proj_name}", "status": "success"})

        # ── Step 7: Check execution results ──────────────────────────
        time.sleep(5)
        history_sql = f"""
        SELECT QUERY_ID, QUERY_TEXT, EXECUTION_STATUS, ERROR_MESSAGE,
               TOTAL_ELAPSED_TIME, START_TIME
        FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY(
            RESULT_LIMIT => 20
        ))
        WHERE QUERY_TEXT ILIKE '%DBT%'
        ORDER BY START_TIME DESC
        LIMIT 10
        """
        try:
            history = execute_sql(cur, history_sql, "Query execution history")
            for row in history[:5]:
                print(f"  Query: {row[0]} | Status: {row[2]} | Time: {row[4]}ms")
                if row[3]:
                    print(f"  ⚠️  Error: {row[3]}")
        except Exception as e:
            print(f"⚠️  Could not fetch query history: {e}")

        # ── Success ─────────────────────────────────────────────────
        results_log["status"] = "success"
        print("\n" + "═" * 60)
        print("🎉 DEPLOYMENT SUCCESSFUL!")
        print("═" * 60)

        step_summary(
            "🚀 Snowflake Deployment",
            f"✅ **Deployment successful** at `{datetime.now(timezone.utc).isoformat()}`\n\n"
            f"| Step | Status |\n|------|--------|\n"
            + "\n".join(
                f"| {s['step']} | ✅ {s['status']} |"
                for s in results_log["steps"]
            ),
        )

    except Exception as e:
        results_log["status"] = "failed"
        results_log["error"] = str(e)
        print(f"\n💥 DEPLOYMENT FAILED: {e}")

        step_summary(
            "🚀 Snowflake Deployment",
            f"❌ **Deployment failed** at `{datetime.now(timezone.utc).isoformat()}`\n\n"
            f"**Error:** `{e}`\n\n"
            f"| Step | Status |\n|------|--------|\n"
            + "\n".join(
                f"| {s['step']} | ✅ {s['status']} |"
                for s in results_log["steps"]
            ),
        )
        sys.exit(1)

    finally:
        with open("deploy_results.json", "w") as f:
            json.dump(results_log, f, indent=2, default=str)
        print(f"\n📄 Results saved to deploy_results.json")

        if conn:
            conn.close()
            print("🔌 Snowflake connection closed")


if __name__ == "__main__":
    main()
