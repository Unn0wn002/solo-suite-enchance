"""Policy check: the database-audit skill's read-only reference must not
contain write-capable SQL inside its ```sql fences. Mutating maintenance
(ANALYZE, PRAGMA optimize, VACUUM, ...) belongs to database-fix only."""
import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(REPO, "plugins", "site-doctor", "skills",
                   "database-audit", "references", "audit-queries.md")
SKILL = os.path.join(REPO, "plugins", "site-doctor", "skills",
                     "database-audit", "SKILL.md")

# Statement-leading keywords that can write. EXPLAIN prefixes are stripped
# first so `EXPLAIN QUERY PLAN SELECT` stays legal.
WRITE_KEYWORDS = re.compile(
    r"^\s*(ANALYZE|VACUUM|REINDEX|INSERT|UPDATE|DELETE|ALTER|CREATE|DROP|"
    r"TRUNCATE|GRANT|REVOKE|MERGE|REPLACE|SET\s|BEGIN|COMMIT|ATTACH|DETACH)\b",
    re.I)
# PRAGMAs: query form `PRAGMA name;` / `PRAGMA name('arg');` is read-only,
# but assignment form or the optimize/wal_checkpoint family writes.
PRAGMA_WRITE = re.compile(r"^\s*PRAGMA\s+(?:\w+\s*=|optimize|wal_checkpoint|"
                          r"shrink_memory|incremental_vacuum)", re.I)


def sql_blocks(text):
    return re.findall(r"```sql\n(.*?)```", text, re.S)


def offending_lines(text):
    bad = []
    for block in sql_blocks(text):
        for raw in block.splitlines():
            line = raw.split("--", 1)[0].strip()      # strip SQL comments
            if not line:
                continue
            line = re.sub(r"^\s*EXPLAIN(\s+QUERY\s+PLAN)?\s+", "", line,
                          flags=re.I)
            if WRITE_KEYWORDS.search(line) or PRAGMA_WRITE.search(line):
                bad.append(raw.strip())
    return bad


class ReadOnlyAuditPolicy(unittest.TestCase):
    def test_audit_reference_has_no_write_sql(self):
        with open(REF, encoding="utf-8") as f:
            text = f.read()
        self.assertEqual(offending_lines(text), [],
                         "write-capable SQL found in read-only audit reference")

    def test_audit_skill_has_no_write_sql(self):
        with open(SKILL, encoding="utf-8") as f:
            text = f.read()
        self.assertEqual(offending_lines(text), [])

    def test_policy_detects_mutations(self):
        """The checker itself must catch the statements it exists to block."""
        sample = "```sql\nANALYZE;\nPRAGMA optimize;\nVACUUM;\n" \
                 "PRAGMA journal_mode = WAL;\nDROP TABLE x;\n```"
        self.assertEqual(len(offending_lines(sample)), 5)

    def test_policy_allows_read_only_forms(self):
        sample = ("```sql\nSELECT 1;\nEXPLAIN QUERY PLAN SELECT * FROM t;\n"
                  "PRAGMA integrity_check;\nPRAGMA foreign_key_check;\n"
                  "PRAGMA journal_mode;\nSHOW GLOBAL STATUS LIKE 'x%';\n"
                  "-- ANALYZE; (comment only)\n```")
        self.assertEqual(offending_lines(sample), [])

    def test_maintenance_moved_to_database_fix(self):
        fix = os.path.join(REPO, "plugins", "site-doctor", "skills",
                           "database-fix", "SKILL.md")
        with open(fix, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("Maintenance statements", text)
        for guard in ("confirmation", "backup", "Rollback"):
            self.assertIn(guard, text)


if __name__ == "__main__":
    unittest.main()
