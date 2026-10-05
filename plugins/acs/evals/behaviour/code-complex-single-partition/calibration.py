"""Plays for code-complex-single-partition (see
tests/evals/check_grader_calibration.py).

IDEAL is what the code-complex leg does on a one-partition plan, through its
real writers: `acs.py step start --step code` (which passes the approval brake
the scaffold's `acs.py plan check` satisfied), ONE un-sliced implementer that
writes tests/test_auth.py first and then src/shop/auth.py, leaves them
uncommitted and reports at steps/code/iter-1/implementer.json -- no
integration slice, because there are no seams between partitions -- the leg's
result.json, and `post-code.py`.
"""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST_CODE = os.path.join(PLUGIN, "hooks", "scripts", "post-code.py")
CODE = ".git/acs/state-machine/example-shop/runs/EVAL-1/steps/code"

AUTH = '''import hashlib
import hmac
import secrets

ROUNDS = 200_000


def _derive(key, salt):
    """The slow, salted digest of a key."""
    return hashlib.pbkdf2_hmac("sha256", key.encode("utf-8"), salt, ROUNDS)


def hash_key(key):
    """What is stored for a key: salt and digest, never the key."""
    salt = secrets.token_bytes(16)
    return "%s$%s" % (salt.hex(), _derive(key, salt).hex())


def verify_key(key, stored):
    """True only for the key that was hashed, compared in constant time."""
    salt_hex, digest_hex = stored.split("$", 1)
    return hmac.compare_digest(_derive(key, bytes.fromhex(salt_hex)).hex(), digest_hex)
'''

EQUALS = AUTH.replace("hmac.compare_digest(_derive(key, bytes.fromhex(salt_hex)).hex(), digest_hex)",
                      "_derive(key, bytes.fromhex(salt_hex)).hex() == digest_hex")

PLAIN = '''import hashlib


def hash_key(key):
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def verify_key(key, stored):
    import hmac
    return hmac.compare_digest(hash_key(key), stored)
'''

TEST = '''"""Merchant API keys are stored hashed (EVAL-1)."""
from shop.auth import hash_key, verify_key


def test_the_hash_never_contains_the_key_and_is_salted():
    assert "k-123" not in hash_key("k-123")
    assert hash_key("k-123") != hash_key("k-123")


def test_only_the_hashed_key_verifies():
    stored = hash_key("k-123")
    assert verify_key("k-123", stored)
    assert not verify_key("k-124", stored)
'''


def _written(ws):
    """`states.files`: every repo path the run left uncommitted for /acs:create-pr
    (ADR-0127) -- the scaffold's own uncommitted ticket docs aside."""
    out = ws.sh("git status --porcelain --untracked-files=all")
    return sorted(line[3:] for line in out.splitlines()
                  if not line[3:].startswith((".acs/", "docs/development/", "docs/architecture/lld/")))


def _code(ws, source=AUTH, reports=("implementer.json",), integrate=False):
    ws.skill("code")
    ws.skill("code-complex")
    start = ws.acs("step", "start", "--step", "code", "--ticket", "EVAL-1")
    assert start.returncode == 0, start.stderr
    if source is None:
        return
    ws.write("tests/test_auth.py", TEST)
    ws.write("src/shop/auth.py", source)
    names = list(reports) + (["implementer-integration.json"] if integrate else [])
    for name in names:
        ws.write(CODE + "/iter-1/" + name, json.dumps({
            "files_changed": ["src/shop/auth.py", "tests/test_auth.py"],
            "tests": {"commands": ["python3 -m pytest -q tests/test_auth.py"],
                      "passed": 2, "failed": 0},
            "coverage": {"percent": None, "target": "measured in review"},
            "problems": [], "seams": []}))
    ws.write(CODE + "/result.json", json.dumps({
        "status": "completed", "outcome": "implemented", "iteration": 1,
        "summary": "salted pbkdf2 key storage, constant-time verify; one partition, no seams",
        "states": {"files": _written(ws), "tasks_implemented": ["1"],
                   "tests": {"passed": 2, "failed": 0}, "docs_updated": []},
        "findings": [], "errors": []}))
    ws.sh("python3 '%s' --result-file '%s/result.json'" % (POST_CODE, CODE))


def IDEAL(ws):
    _code(ws)


BAD = {
    "fired the leg and did nothing": lambda ws: _code(ws, source=None),
    "compared digests with ==": lambda ws: _code(ws, source=EQUALS),
    "stored an unsalted sha256": lambda ws: _code(ws, source=PLAIN),
    "ran an integration pass with no seams": lambda ws: _code(ws, integrate=True),
    "sliced the single partition": lambda ws: _code(ws, reports=("implementer-1.json",)),
}
