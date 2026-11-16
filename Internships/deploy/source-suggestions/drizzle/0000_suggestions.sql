CREATE TABLE suggestions (
 id TEXT PRIMARY KEY,
 company TEXT NOT NULL,
 url TEXT NOT NULL,
 reason TEXT NOT NULL,
 ip_hash TEXT NOT NULL,
 created_at INTEGER NOT NULL,
 lease TEXT,
 lease_until INTEGER,
 delivered_at INTEGER,
 archived_at INTEGER
);
--> statement-breakpoint
CREATE INDEX suggestions_pending ON suggestions(delivered_at, lease_until);
--> statement-breakpoint
CREATE INDEX suggestions_limits ON suggestions(created_at, ip_hash);
