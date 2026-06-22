# SOP: Code Deploy -- schools-pwa (api_deploy.sh -> PR -> merge)

**Status:** BINDING. This is the standard flow for every change to `main` in the
schools-pwa repo.

**Why this method:** `git fetch` / `git pull` / `git push` HANG PERMANENTLY on this
network (pack-data transfer stalls; confirmed unfixable, 21 Jun 2026 -- not a config
issue, not a credentials issue, the transport itself never completes). All git
*transport* is therefore banned. We deploy over the GitHub REST API (plain HTTPS,
~0.4s) and read files over the raw CDN. No local git clone push/pull is used.

**Scope note:** this SOP covers schools-pwa only. Unlike inspections-pwa, schools-pwa
currently has **no invariants CI gate** and **no live invariant runner**
(`check_invariants_live.py`). Steps that reference those in the inspections SOP do
**not** apply here. Do not copy them in. If/when schools-pwa gains a CI gate or a
diagnostics runner, update this SOP to add the corresponding wait-for-green and
verify steps.

---

## NEVER do these (they hang this network -- no exceptions)

- `git push`  /  `git push -u origin <branch>`
- `git pull`  /  `git fetch`  /  `git clone`
- any command that moves pack data to/from GitHub over git transport

If a future thread or reader proposes any of the above: STOP. It will hang. Use
`api_deploy.sh` for writes and `raw.githubusercontent.com` for reads instead.

---

## The flow (every deploy, no exceptions)

### 1. On Mac terminal -- read the current file (so the patch matches live)
Read the *currently deployed* file over the raw CDN before patching, so any
assert-guarded patch matches byte-for-byte:

```
curl -s https://raw.githubusercontent.com/JohanBenade/schools-pwa/main/<repo_path> -o ~/Downloads/<file>
```

### 2. On Mac terminal -- run the patch script Claude provides
Claude supplies an assert-guarded Python find/replace script (it aborts before
writing if the target text is not found verbatim). Run it against the file you
just downloaded:

```
python3 ~/Downloads/patch_<name>.py ~/Downloads/<file>
```

Expect a clear success line. If you see `AssertionError` or any `EDIT ... FAILED`
line: STOP, paste it back to Claude. The live file changed since it was read; do
not proceed.

(For a brand-new file with no patch step, skip steps 1-2 and deploy the file
directly in step 3.)

### 3. On Mac terminal -- deploy via api_deploy.sh
One command commits the file to a NEW branch and opens a PR:

```
bash ~/dev/schools-pwa/api_deploy.sh <owner/repo> <local_file> <repo_path> <branch> "<commit msg>"
```

Example:
```
bash ~/dev/schools-pwa/api_deploy.sh JohanBenade/schools-pwa ~/Downloads/app.py app/app.py fix/short-name "fix(scope): short description"
```

The script prints progress and ends with a PR URL like:
`https://github.com/JohanBenade/schools-pwa/pull/NN`
Paste that URL back to Claude.

Notes on the script:
- It works regardless of which directory you run it from (all targets are passed
  as arguments). The `~/dev/schools-pwa/` path is only the location of the script
  file itself. (schools-pwa lives at `~/dev/schools-pwa`, NOT `~/Documents/GitHub`.)
- It reads the PAT from `~/.gh_deploy_token` (chmod 600, expires ~21 Sep 2026,
  scoped to both repos).
- It always creates a branch + PR; it never writes to `main` directly.

### 4. In browser -- merge
- Open the PR URL.
- schools-pwa currently has **no required CI check**, so the PR is mergeable
  immediately -- there is nothing to wait for.
- **Merge pull request** -> **Confirm merge**.
- The deploy target picks up `main` after merge.

There is no local-sync / branch-delete step. Nothing lives in a local git clone
that is pushed/pulled, so there is nothing to prune on the Mac. Merged branches
can be deleted in the browser if desired (cosmetic only).

### 5. Verify the deploy
schools-pwa has no automated invariant runner. Verify the change took effect by
the means appropriate to the change (e.g. load the affected page/route and
confirm the expected behaviour).

> TODO (fill in when known): document schools-pwa's exact deploy target/host and
> a concrete post-deploy smoke check. Until then, verify manually and do not
> assume the deploy is correct just because the merge succeeded.

---

## Reading files without deploying

To inspect any committed file without a deploy, fetch it over the raw CDN:

```
curl -s https://raw.githubusercontent.com/JohanBenade/schools-pwa/main/<path>
```

Unauthenticated raw reads share a CDN rate limit; if a read returns empty or a
rate-limit response, wait and retry.

---

## Commit message convention

`type(scope): description`. Types: `fix`, `feat`, `refactor`, `chore`, `docs`.
One logical change per commit.

---

## Rollback

Each merged PR has a one-click **Revert** button in the browser, which opens a
revert PR through the same flow. That is the safe rollback path. Do not attempt a
git-transport revert from the Mac (it will hang).

---

*Created 22 Jun 2026. Mirrors the inspections-pwa deploy method (api_deploy.sh +
raw-CDN) but scoped to schools-pwa: no invariants CI gate, no live runner. The
deploy script `api_deploy.sh` was committed to this repo the same day.*
