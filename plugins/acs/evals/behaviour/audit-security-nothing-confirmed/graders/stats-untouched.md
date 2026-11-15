---
type: regex
target: { source: file, path: src/shop/stats.py }
pattern: '^"""Order statistics for the merchant dashboard\."""\nimport sqlite3\n\nTABLE = "orders"\n\n\ndef count_orders\(conn: sqlite3\.Connection\) -> int:\n    return conn\.execute\(f"SELECT COUNT\(\*\) FROM \{TABLE\}"\)\.fetchone\(\)\[0\]\n\n\ndef order_by_id\(conn, order_id\):\n    return conn\.execute\(f"SELECT id, product FROM \{TABLE\} WHERE id = \?", \(order_id,\)\)\.fetchone\(\)\n(?![\s\S])'
---

Report-only, and nothing to fix: src/shop/stats.py is byte for byte as
committed. Rewriting the queries "to be safe" is a change the audit never
makes, least of all for a candidate it refuted.
