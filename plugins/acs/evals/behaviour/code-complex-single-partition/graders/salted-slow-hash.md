---
type: regex
target: { source: file, path: src/shop/auth.py }
pattern: 'pbkdf2_hmac|scrypt'
---

AC-1 and the plan's second risk: a salted, deliberately slow derivation. A
plain `sha256(key)` -- the approach the plan rejects -- fails here.
