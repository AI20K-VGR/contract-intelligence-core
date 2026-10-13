# P4 implementation record

- Added a centralized exact-boolean consent reader. Only dossier metadata `ai2_content_sharing_consent is True` grants content-sharing consent; absent, null, strings, and other malformed values deny it.
- Both Backend query routes now send consent as a separate top-level signed payload field. Server-controlled `policy_flags` remain independent, and caller body models do not accept overrides.
- Enabled the Backend query egress and vector caps by default to match the requested full AI2 runtime defaults. Explicit operator false remains a narrowing cap.
- Canonical processing retains its existing consent field and budget/vector configuration independently. Added regression coverage that changing consent does not change budget or vector config.
- TDD evidence: new route tests failed first due to missing consent field and default false setting; after implementation they passed. Updated the existing search-router expectation to assert default cap true while missing dossier consent stays false.
- Verification: full Backend unit suite 595 passed; focused consent/query/router suite 96 passed; integration set 24 passed with the opt-out rollback race on PostgreSQL; architecture suite 4 passed; Ruff check passed.
- Existing warnings: 29 unit warnings, mostly pre-existing deprecations/incorrect asyncio marks; 2 integration deprecation warnings. PostgreSQL test used a disposable local pgvector/pg16 container.
