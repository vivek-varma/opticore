# Releasing OptiCore

How to cut a new release. Audience: maintainers.

---

## 0. One-time setup

Before the first release, do these once per repo:

### TestPyPI account + token

1. Register: https://test.pypi.org/account/register/
2. Enable 2FA (required to upload).
3. Create an API token:
   - TestPyPI → Account settings → **API tokens** → **Add API token**
   - Name: `opticore-github-actions`
   - Scope: "Entire account" (narrow to project-specific after the first upload)
   - Copy the token (starts with `pypi-`) — shown **once**.
4. Add the token to GitHub:
   ```bash
   gh secret set TEST_PYPI_API_TOKEN --repo vivek-varma/opticore
   # paste the token when prompted
   ```
5. Create the `testpypi` environment in GitHub:
   - Repo → Settings → Environments → **New environment** → `testpypi`
   - Optional: add a required reviewer for extra safety

### Real PyPI — deferred

See issue #18. Real PyPI uses OIDC trusted publishers, not API tokens. Do the TestPyPI dry-run first.

---

## 1. Pre-flight check

```bash
# Everything in main, tree clean
git checkout main && git pull && git status

# All tests pass locally
./build_and_test.sh                              # C++: 96 tests / 1653 assertions
pip install -e ".[dev]" && pytest tests/python   # Python: 182 tests

# CI is green on main
gh run list --branch main --limit 1
```

If any of these fail, fix first. Do not release broken code.

---

## 2. Bump the version

Semantic versioning (`MAJOR.MINOR.PATCH`):

| Change | Bump |
|---|---|
| Bug fix, internal refactor | PATCH (0.2.0 → 0.2.1) |
| New public function / feature | MINOR (0.2.0 → 0.3.0) |
| Breaking API change | MAJOR (0.2.0 → 1.0.0) |

Edit **three** files in one commit:

1. `pyproject.toml` → `version = "X.Y.Z"`
2. `python/opticore/__init__.py` → `__version__ = "X.Y.Z"`
3. `CHANGELOG.md` → move `[Unreleased]` bullets under a new `## [X.Y.Z] - YYYY-MM-DD` heading

```bash
git add pyproject.toml python/opticore/__init__.py CHANGELOG.md
git commit -m "chore: bump version to vX.Y.Z"
git push origin main
```

Wait for CI to go green on main before tagging.

---

## 3. Dry-run on TestPyPI

**Always do this first.** PyPI uploads are immutable — you can't un-publish a bad wheel.

```bash
# Trigger the release workflow manually with TestPyPI enabled
gh workflow run release.yml --ref main -f publish_to_testpypi=true

# Watch it run (~15 min for full matrix)
gh run watch
```

Once it finishes, verify on TestPyPI:

```bash
# From a clean venv, install from TestPyPI and confirm the wheel works
python -m venv /tmp/opticore-test && source /tmp/opticore-test/bin/activate
pip install --index-url https://test.pypi.org/simple/ \
            --extra-index-url https://pypi.org/simple/ \
            opticore==X.Y.Z
python -c "import opticore as oc; print(oc.price(100,100,0.5,0.05,0.2,'call'))"
deactivate && rm -rf /tmp/opticore-test
```

If the import fails or the number is wrong, **do not proceed to the tag**. Fix, bump to `X.Y.(Z+1)`, retry the dry-run.

---

## 4. Tag and push

```bash
# Signed tag (requires GPG setup). Drop -s if not signing.
git tag -s vX.Y.Z -m "OptiCore vX.Y.Z"
git push origin vX.Y.Z
```

The tag push triggers `.github/workflows/release.yml`:
- Builds 12 wheels (3 OSes × 4 Python versions)
- Builds 1 sdist
- Creates a GitHub Release at `https://github.com/vivek-varma/opticore/releases/tag/vX.Y.Z`
- Attaches all 13 artifacts to the release
- Auto-generates release notes from commit messages since the previous tag

```bash
# Watch the run
gh run watch

# When done, verify the release
gh release view vX.Y.Z
```

---

## 5. Publish to real PyPI

**Currently deferred — see issue #18.** Once that lands, the tag push will also publish to PyPI automatically.

For now, after verifying the GitHub Release artifacts, a maintainer can optionally upload manually:

```bash
# Only if you really need to — issue #18 will automate this
pip install twine
twine upload --repository pypi dist/*
```

---

## 6. Post-release

- Announce on the GitHub Discussions / README
- Update the Documentation site (see issue #11)
- Open a new `[Unreleased]` entry at the top of `CHANGELOG.md`
- If you skipped the real-PyPI step, open an issue linking this tag

---

## Troubleshooting

### Wheel matrix fails on one cell

Inspect the failed job's logs:
```bash
gh run view <run-id> --log-failed
```

Most common causes:
- **Windows**: MSVC can reject code GCC/Clang accept (see ADR-0001 for an example). Use `inline` not `constexpr` with `std::exp`/`std::isnan`.
- **macOS ARM**: Sometimes pandas has wheel-availability lag for new CPython versions. Wait for upstream or pin.
- **manylinux**: A transitive dependency may not have a manylinux2014 wheel. Upgrade the base image to `manylinux_2_28` in `[tool.cibuildwheel.linux]`.

### TestPyPI says "File already exists"

The workflow sets `skip-existing: true`, so this should just be a warning. If you really need to re-upload the same version (you shouldn't — bump the patch version instead), delete the project from TestPyPI and retry.

### "This event loop is already running" during cibuildwheel test step

The wheel tests import `opticore.data.ibkr`, which loads the Jupyter event-loop patcher. Should not fire in cibuildwheel (no Jupyter), but if it does, check that `test-requires` does not include `jupyter` or `ipykernel`.

---

## Design rationale — why these choices

- **cibuildwheel** over hand-rolled CI: battle-tested on thousands of PyPI projects, handles manylinux images + MSVC + macOS universal2 for us.
- **Skip musllinux / Alpine**: Our retail-trader audience runs macOS/Windows/Ubuntu. Alpine is container-niche. Adds ~4 builds for ~0% of users. Revisit if a user opens an issue.
- **Skip 32-bit**: No one does quant work on 32-bit in 2026.
- **manylinux2014 (glibc 2.17)**: Works on every Linux distro from 2014 onward. Upgrading to `manylinux_2_28` would drop RHEL/CentOS 7 support — not worth it for Phase 1.
- **TestPyPI before real PyPI**: PyPI uploads are immutable. One typo in the wheel metadata and you've burned a version number.
- **OIDC trusted publisher for real PyPI** (issue #18): eliminates the risk of a leaked `PYPI_API_TOKEN` — there's no token to leak.
