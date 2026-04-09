"""
End-to-End API Test Script
--------------------------
Tests the full lifecycle:
  Auth → Projects → Upload SQL → Poll Status → Suggestions → Finalize → Download

Run from project root:
    python scripts/e2e_test.py

Requirements: pip install requests
"""

import sys
import time
import uuid
import requests

# ── Config ───────────────────────────────────────────────────────────────────
BASE_URL = "http://localhost:8000/api/v1"
TEST_EMAIL = f"e2e_{uuid.uuid4().hex[:6]}@test.com"
TEST_PASSWORD = "TestPass123!"
TEST_PROJECT_NAME = "E2E Test Project"
SQL_FILE_PATH = "test.sql"  # small test SQL file in project root

# Polling config
MAX_POLL_ATTEMPTS = 30   # 30 × 5s = 150s max wait
POLL_INTERVAL_SECONDS = 5

# ── Helpers ──────────────────────────────────────────────────────────────────
PASS = "\033[92m✅ PASS\033[0m"
FAIL = "\033[91m❌ FAIL\033[0m"
INFO = "\033[94mℹ️ \033[0m"

failed = 0

def check(label: str, condition: bool, detail: str = ""):
    global failed
    if condition:
        print(f"  {PASS}  {label}")
    else:
        print(f"  {FAIL}  {label}" + (f" — {detail}" if detail else ""))
        failed += 1

def section(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")

# ── Phase 5.0: Health Check ───────────────────────────────────────────────────
section("Phase 5.0 — Health Check")
try:
    r = requests.get("http://localhost:8000/health", timeout=5)
    check("GET /health → 200 OK", r.status_code == 200)
    check("Response has status=ok", r.json().get("status") == "ok")
except Exception as e:
    print(f"  {FAIL}  Cannot reach API: {e}")
    sys.exit(1)

# ── Phase 5.1: Register ───────────────────────────────────────────────────────
section("Phase 5.1 — Auth: Register")
r = requests.post(f"{BASE_URL}/auth/register", json={
    "email": TEST_EMAIL,
    "password": TEST_PASSWORD,
    "full_name": "E2E Tester"
})
check("POST /register → 201", r.status_code == 201, r.text[:200])
check("Response has 'id' field", "id" in r.json())
check("Response has 'email' field", r.json().get("email") == TEST_EMAIL)

# ── Phase 5.2: Login ─────────────────────────────────────────────────────────
section("Phase 5.2 — Auth: Login")
r = requests.post(f"{BASE_URL}/auth/login", data={
    "username": TEST_EMAIL,
    "password": TEST_PASSWORD,
})
check("POST /login → 200", r.status_code == 200, r.text[:200])
token = r.json().get("access_token", "")
check("Response has access_token", bool(token))
check("token_type is bearer", r.json().get("token_type") == "bearer")

HEADERS = {"Authorization": f"Bearer {token}"}

# ── Phase 5.3: Get Me ─────────────────────────────────────────────────────────
section("Phase 5.3 — Auth: GET /me")
r = requests.get(f"{BASE_URL}/auth/me", headers=HEADERS)
check("GET /me → 200", r.status_code == 200, r.text[:200])
check("Email matches", r.json().get("email") == TEST_EMAIL)

# ── Phase 5.4: Create Project ─────────────────────────────────────────────────
section("Phase 5.4 — Projects: Create")
r = requests.post(f"{BASE_URL}/projects/", headers=HEADERS, json={
    "name": TEST_PROJECT_NAME,
    "description": "Automated E2E test project"
})
check("POST /projects → 201", r.status_code == 201, r.text[:200])
project_id = r.json().get("id", "")
check("Response has 'id'", bool(project_id))
check("Name matches", r.json().get("name") == TEST_PROJECT_NAME)

# ── Phase 5.5: List Projects ──────────────────────────────────────────────────
section("Phase 5.5 — Projects: List")
r = requests.get(f"{BASE_URL}/projects/", headers=HEADERS)
check("GET /projects → 200", r.status_code == 200)
check("Returns a list", isinstance(r.json(), list))
check("Project appears in list",
    any(p["id"] == project_id for p in r.json()), "project not found in list")
check("job_count field exists", "job_count" in r.json()[0])

# ── Phase 5.6: Get Project Detail ────────────────────────────────────────────
section("Phase 5.6 — Projects: Get Detail")
r = requests.get(f"{BASE_URL}/projects/{project_id}", headers=HEADERS)
check("GET /projects/{id} → 200", r.status_code == 200, r.text[:200])
check("ID matches", r.json().get("id") == project_id)

# ── Phase 5.7: Upload SQL File → Queue Job ────────────────────────────────────
section("Phase 5.7 — Jobs: Upload SQL File")
try:
    with open(SQL_FILE_PATH, "rb") as f:
        r = requests.post(
            f"{BASE_URL}/jobs/upload",
            headers=HEADERS,
            files={"file": (SQL_FILE_PATH, f, "application/sql")},
            data={"project_id": project_id, "app_context": "READ_HEAVY"},
        )
    check("POST /jobs/upload → 202", r.status_code == 202, r.text[:300])
    job_id = r.json().get("job_id", "")
    check("Response has job_id", bool(job_id))
    check("Status is QUEUED", r.json().get("status") in ("QUEUED", "PROCESSING"))
except FileNotFoundError:
    print(f"  ⚠️  SKIP — {SQL_FILE_PATH} not found, using inline SQL")
    # Create a tiny inline test SQL file
    with open(SQL_FILE_PATH, "w") as f_tmp:
        f_tmp.write(
            "CREATE TABLE users (id SERIAL PRIMARY KEY, email VARCHAR(255) UNIQUE NOT NULL, created_at TIMESTAMP DEFAULT NOW());\n"
            "CREATE TABLE posts (id SERIAL PRIMARY KEY, user_id INT REFERENCES users(id), title VARCHAR(255) NOT NULL, body TEXT);\n"
        )
    with open(SQL_FILE_PATH, "rb") as f:
        r = requests.post(
            f"{BASE_URL}/jobs/upload",
            headers=HEADERS,
            files={"file": (SQL_FILE_PATH, f, "application/sql")},
            data={"project_id": project_id, "app_context": "READ_HEAVY"},
        )
    check("POST /jobs/upload → 202 (with inline SQL)", r.status_code == 202, r.text[:300])
    job_id = r.json().get("job_id", "")
    check("Response has job_id", bool(job_id))

# ── Phase 5.8: Poll Until COMPLETED ──────────────────────────────────────────
section("Phase 5.8 — Jobs: Poll Status until COMPLETED")
print(f"  {INFO} Polling job {job_id} (max {MAX_POLL_ATTEMPTS * POLL_INTERVAL_SECONDS}s)...")
final_status = None
for attempt in range(MAX_POLL_ATTEMPTS):
    r = requests.get(f"{BASE_URL}/jobs/{job_id}/status", headers=HEADERS)
    if r.status_code != 200:
        print(f"  ⚠️  Poll attempt {attempt+1}: HTTP {r.status_code}")
        break
    current_status = r.json().get("status")
    print(f"  [{attempt+1:02d}/{MAX_POLL_ATTEMPTS}] Status: {current_status}")
    if current_status in ("COMPLETED", "FAILED"):
        final_status = current_status
        break
    time.sleep(POLL_INTERVAL_SECONDS)

check("Job reached COMPLETED", final_status == "COMPLETED",
      f"Final status was: {final_status}")

# ── Phase 5.9: Get Suggestions ────────────────────────────────────────────────
section("Phase 5.9 — Jobs: Get Suggestions")
r = requests.get(f"{BASE_URL}/jobs/{job_id}/suggestions", headers=HEADERS)
check("GET /suggestions → 200", r.status_code == 200, r.text[:200])
suggestions = r.json()
check("Returns a list", isinstance(suggestions, list))
check("At least 1 suggestion", len(suggestions) > 0, f"Got {len(suggestions)} suggestions")
if suggestions:
    s = suggestions[0]
    check("Suggestion has 'issue'", "issue" in s)
    check("Suggestion has 'sql_patch'", "sql_patch" in s)
    check("Suggestion has 'risk_level'", s.get("risk_level") in ("LOW", "MEDIUM", "HIGH"))
    check("Suggestion has 'confidence' (0-1)", 0.0 <= s.get("confidence", -1) <= 1.0)
    print(f"\n  {INFO} Sample suggestion: [{s.get('risk_level')}] {s.get('issue', '')[:80]}")

# ── Phase 5.9b: ERD Schema ────────────────────────────────────────────────────
section("Phase 5.9b — Jobs: GET /schema (ERD Parser)")
r = requests.get(f"{BASE_URL}/jobs/{job_id}/schema", headers=HEADERS)
check("GET /schema → 200", r.status_code == 200, r.text[:200])
if r.status_code == 200:
    schema = r.json()
    check("Response has 'job_id'", "job_id" in schema)
    check("Response has 'tables' list", isinstance(schema.get("tables"), list))
    check("Response has 'table_count'", isinstance(schema.get("table_count"), int))
    check("Response has 'relationship_count'", isinstance(schema.get("relationship_count"), int))
    check("table_count > 0", schema.get("table_count", 0) > 0,
          f"Got {schema.get('table_count')} tables")

    if schema["tables"]:
        first_table = schema["tables"][0]
        check("Table has 'name'", "name" in first_table)
        check("Table has 'columns' list", isinstance(first_table.get("columns"), list))
        check("Table has 'foreign_keys' list", isinstance(first_table.get("foreign_keys"), list))

        if first_table["columns"]:
            col = first_table["columns"][0]
            check("Column has 'name'", "name" in col)
            check("Column has 'type'", "type" in col)
            check("Column has 'is_primary_key' bool", isinstance(col.get("is_primary_key"), bool))
            check("Column has 'is_foreign_key' bool", isinstance(col.get("is_foreign_key"), bool))
            check("Column has 'is_nullable' bool", isinstance(col.get("is_nullable"), bool))

    # Print a friendly summary of extracted schema
    print(f"\n  {INFO} Extracted ERD schema:")
    print(f"       Tables  : {schema['table_count']}")
    print(f"       FK rels : {schema['relationship_count']}")
    for tbl in schema["tables"]:
        pks = [c["name"] for c in tbl["columns"] if c["is_primary_key"]]
        fks = [f"{fk['column']} → {fk['references_table']}" for fk in tbl["foreign_keys"]]
        print(f"       [{tbl['name']}] cols={len(tbl['columns'])} PKs={pks} FKs={fks}")
    if schema.get("errors"):
        print(f"  ⚠️  Parse warnings: {schema['errors']}")

# ── Phase 5.10: Finalize ──────────────────────────────────────────────────────
section("Phase 5.10 — Jobs: Finalize (Trigger Sandbox)")
r = requests.post(f"{BASE_URL}/jobs/{job_id}/finalize", headers=HEADERS)
check("POST /finalize → 200", r.status_code == 200, r.text[:200])
check("Response has 'message'", "message" in r.json())

# ── Phase 5.11: Poll Until FINALIZED ─────────────────────────────────────────
section("Phase 5.11 — Jobs: Poll Status until FINALIZED")
print(f"  {INFO} Polling finalization (max {MAX_POLL_ATTEMPTS * POLL_INTERVAL_SECONDS}s)...")
final_status = None
for attempt in range(MAX_POLL_ATTEMPTS):
    r = requests.get(f"{BASE_URL}/jobs/{job_id}/status", headers=HEADERS)
    current_status = r.json().get("status")
    print(f"  [{attempt+1:02d}/{MAX_POLL_ATTEMPTS}] Status: {current_status}")
    if current_status in ("FINALIZED", "FAILED"):
        final_status = current_status
        break
    time.sleep(POLL_INTERVAL_SECONDS)

check("Job reached FINALIZED", final_status == "FINALIZED",
      f"Final status was: {final_status}")

# ── Phase 5.12: Download ──────────────────────────────────────────────────────
section("Phase 5.12 — Jobs: Download Optimized SQL")
if final_status == "FINALIZED":
    r = requests.get(f"{BASE_URL}/jobs/{job_id}/download", headers=HEADERS)
    check("GET /download → 200", r.status_code == 200, r.text[:200])
    download_url = r.json().get("download_url", "")
    check("Response has download_url", bool(download_url))
    check("URL contains minio/localhost", "localhost" in download_url or "minio" in download_url,
          download_url[:100])
    print(f"\n  {INFO} Download URL: {download_url[:80]}...")
else:
    print(f"  ⚠️  SKIP — Job not FINALIZED, sandbox may have failed")

# ── Phase 5.Error: Auth Guardrails ───────────────────────────────────────────
section("Phase 5.E — Error Cases & Security Guardrails")

# Wrong password
r = requests.post(f"{BASE_URL}/auth/login", data={"username": TEST_EMAIL, "password": "WRONG"})
check("Login with wrong password → 400", r.status_code == 400)

# Upload non-SQL file
r = requests.post(
    f"{BASE_URL}/jobs/upload",
    headers=HEADERS,
    files={"file": ("hack.txt", b"not sql", "text/plain")},
    data={"project_id": project_id, "app_context": "READ_HEAVY"},
)
check("Upload non-.sql file → 400", r.status_code == 400, r.text[:100])

# Access another user's project with fake ID
fake_id = str(uuid.uuid4())
r = requests.get(f"{BASE_URL}/projects/{fake_id}", headers=HEADERS)
check("GET nonexistent project → 404", r.status_code == 404)

# ── Summary ───────────────────────────────────────────────────────────────────
section("SUMMARY")
if failed == 0:
    print(f"  \033[92m🎉 ALL TESTS PASSED!\033[0m")
else:
    print(f"  \033[91m⚠️  {failed} test(s) FAILED. Check logs above.\033[0m")
    sys.exit(1)
