CREATE TABLE IF NOT EXISTS signups (
  email TEXT NOT NULL,
  product TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (email, product)
);
