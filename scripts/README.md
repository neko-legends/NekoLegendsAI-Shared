# scripts/

Developer tooling for maintaining the Neko Legends suite. Not shipped in any
app bundle — these are repo-maintenance tools.

## neko_suite_doctor.py

Cross-repo invariant checker. Assumes all suite repos are checked out as siblings
under one folder (e.g. `D:\forPublic\`); it locates that root relative to its own
path.

Checks two things that are easy to break by hand:

1. **Vendored module drift.** `neko_store.rs` is copied (vendored) into each app.
   This hashes every app's copy against the canonical `rust/neko_store.rs` and
   flags any that diverged — printing the exact `cp` command to fix it.
2. **Agent API port collisions.** Parses `default_agent_api_entries()` in
   `NekoLegendsControlCenter/src-tauri/src/main.rs` (the authoritative list) and
   fails on any duplicate port.

```bash
python scripts/neko_suite_doctor.py                  # check; exit 1 on any problem
python scripts/neko_suite_doctor.py --quiet          # only print problems (CI)
python scripts/neko_suite_doctor.py --write-registry # regenerate AGENT_API_PORTS.md
```

Exit code 0 = all invariants hold; non-zero = at least one problem. Run it before
tagging a release, or after adding/renaming an app or changing an agent port.

### Why these checks exist

Both invariants have already caused near-misses:

- A canonical fix to `neko_store.rs` once had to be back-ported to three app
  copies by hand — nothing warned that they'd drifted.
- The hand-maintained port doc was stale (missing two apps), and following its
  "next free port" advice would have shipped a collision. The doctor parses the
  Rust source instead, so the code is the single source of truth and
  `--write-registry` keeps the human-readable doc in lockstep.
