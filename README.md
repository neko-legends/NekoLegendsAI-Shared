# NekoLegendsAI-Shared

Shared **local AI store** convention for the Neko Legends / ForPublic app suite.

This repo is the single source of truth for how every GPU app in the suite finds
(or creates) one shared, **visible** folder — `NekoLegendsAI/` — so that:

- Hugging Face **models download once** (shared `HF_HOME`).
- PyTorch / CUDA wheels are **cached once** (shared pip + uv caches). With `uv`,
  packages are hardlinked into each app's venv on the same volume, so the bytes
  exist once on disk instead of once *per app*.

It is shipped as two small, dependency-light files you **vendor** (copy) into
each app, not a package you depend on. That keeps every app fully standalone.

```
rust/neko_store.rs     # resolver: discovers/creates the store, exports env vars
python/neko_store.py   # worker helper: reads the env vars, uv-aware venv bootstrap
```

## The one rule that shapes everything

> The shared store is a **convention with discovery + fallback**, never a
> dependency. A portable app with nothing else installed still works. The Neko
> Legends Control Center, *if present*, only points at and manages the store — it
> is never required.

## Discovery order (first hit wins)

1. **Per-app override** env var `NEKO_<APP>_STORE` (e.g. `NEKO_ANGLEFORGE_STORE`).
2. **Global** env var `NEKO_AI_HOME`.
3. **Pointer file** `<home>/NekoLegendsAI/store.json` (`{"root": "..."}`).
4. **Default visible folder** `<volume-of-app>/NekoLegendsAI` (e.g. `D:\NekoLegendsAI`).
   The first app to run creates it and drops the pointer file, so the *next* app
   you install finds it automatically — **dedup with no Control Center**.
5. **App-local fallback** — the app's own data dir. Pure portable; works with
   nothing else present.

## Store layout (flat, human-readable, not hidden)

```
NekoLegendsAI/
  store.json           marker / metadata
  models/              HF_HOME — models downloaded once
    huggingface/
  cache/
    pip/               PIP_CACHE_DIR
    uv/                UV_CACHE_DIR
    torch/             TORCH_HOME
  envs/                per-app venvs (shared store)
    <app>/
```

In app-local fallback mode the venv stays at the historical `python-env/` path so
existing installs keep working.

## Same-volume caveat (by design)

`uv` hardlink dedup only works when an app's venv and the shared cache are on the
**same volume**. That's why the default store root is chosen on the *same drive as
the app*. If a user puts an app on `C:` but the store on `D:`, uv silently falls
back to copying — still correct, just not deduped. The Control Center can warn
about this; standalone apps just accept it.

## Vendoring into a Tauri app

**Rust side** (`src-tauri/`):

1. Copy `rust/neko_store.rs` to `src-tauri/src/neko_store.rs`.
2. Add `mod neko_store;` near the top of `lib.rs`.
3. Where you currently derive `env_dir` / `model_dir` from the app data dir:

   ```rust
   let app_data = app_data_dir(app)?;
   let store = neko_store::NekoStore::resolve("angleforge", &app_data);
   let env_dir = store.env_dir.clone();          // replaces app_data.join("python-env")
   let models  = store.models_dir.clone();       // replaces app_data.join("models")
   // ...when spawning the Python worker:
   store.apply_env(&mut command);                // routes HF/pip/uv/torch caches
   ```

   Requires only `serde_json`, which every Neko app already depends on.

**Python side** (worker):

1. Copy `python/neko_store.py` next to your worker module.
2. Replace bespoke venv bootstrap with:

   ```python
   from neko_store import StoreContext
   store = StoreContext.from_env(app_slug="angleforge", env_dir=job_env_dir)
   python = store.ensure_venv("3.11")            # uv-preferred, hardlinked
   store.pip_install(python, ["torch==2.7.1+cu128"],
                     index_url="https://download.pytorch.org/whl/cu128")
   ```

   No third-party imports, so it runs under system Python before any venv exists.

## CUDA note for this suite

The suite standardizes on **cu128**, the only CUDA build that spans both target
GPUs: RTX 5090 (Blackwell, sm_120, needs cu128+) and RTX 3090 (Ampere, sm_86,
works everywhere). Keeping one toolkit is what makes a shared torch cache useful.

## Tests

The Rust module ships unit tests:

```
cd rust && # vendored into any crate, or use the throwaway selftest crate
cargo test
```

## License

MIT.
