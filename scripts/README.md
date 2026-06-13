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
python scripts/neko_suite_doctor.py --quiet          # only print problems (CI / hook)
python scripts/neko_suite_doctor.py --fix            # re-vendor canonical into drifted apps
python scripts/neko_suite_doctor.py --write-registry # regenerate AGENT_API_PORTS.md
```

Exit code 0 = all invariants hold; non-zero = at least one problem. Run it before
tagging a release, or after adding/renaming an app or changing an agent port.

## install-hooks.sh

Installs a **pre-commit hook** into each sibling app repo that runs
`neko_suite_doctor.py --quiet` and **blocks the commit** if a vendored module
drifted or two apps share a port. Git hooks aren't shared by clone, so run this
once per machine:

```bash
bash scripts/install-hooks.sh            # install into every sibling repo
bash scripts/install-hooks.sh MyApp      # install into named repos only
```

The hook degrades gracefully: if `NekoLegendsAI-Shared` isn't checked out as a
sibling (e.g. someone cloned just one app), it skips rather than blocks. To bypass
once: `git commit --no-verify`.

## Defense in depth

These layers stack so the vendoring convention is hard to break by accident:

1. **In-file banner** at the top of each vendored module ("DO NOT EDIT HERE").
2. **Per-repo `AGENTS.md`** steering AI coding agents away from editing copies.
3. **Pre-commit hook** that blocks drifted/colliding commits (detection).
4. **`--fix`** that re-vendors canonical into every app (one-command correction).

### Why these checks exist

Both invariants have already caused near-misses:

- A canonical fix to `neko_store.rs` once had to be back-ported to three app
  copies by hand — nothing warned that they'd drifted.
- The hand-maintained port doc was stale (missing two apps), and following its
  "next free port" advice would have shipped a collision. The doctor parses the
  Rust source instead, so the code is the single source of truth and
  `--write-registry` keeps the human-readable doc in lockstep.
