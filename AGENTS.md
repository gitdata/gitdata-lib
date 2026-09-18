# gitdata-lib

- Default branch is `master`. Do not rebase; merge the target branch.
- Secrets persist in the local `.gitdata` sqlite file via EntityStore (`entities`/`attributes`). Do not run `sqlite3_setup.sql` on an existing repo (it drops tables).
- CLI: `gitdata secrets` (`list`/`ls`, `get`, `set`/`add`, `delete`/`rm`, `status`, `resolve`, `clear`, `keygen`). Key from `--key`, `--key-file`, `GITDATA_ENCRYPTION_KEY`, or `/run/secrets/gitdata_encryption_key`. Never store the key in `.gitdata`.
- `status` prints names only. `resolve` hard-fails with missing names unless `--prompt`. `clear` requires `--force`.
- Share handoff: a shared `.gitdata` without the key fails closed. Recipients re-set values under the same names with their own key.
- Connections resolve secrets via `Secrets.resolve` / `resolve_secrets`. Hard-fail on missing names (`MissingSecrets`); no library prompts.
