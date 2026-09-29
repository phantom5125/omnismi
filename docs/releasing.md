# Publishing a release

1. Update the version in `pyproject.toml` and `src/omnismi/__init__.py`, the
   changelog, and version-specific installation examples. Run the regression,
   documentation, build and clean-wheel checks described in
   [Contributing](https://github.com/phantom5125/omnismi/blob/main/CONTRIBUTING.md).
2. Merge the reviewed release changes into `main` after CI passes.
3. Tag that commit as `release-VERSION`. Build the wheel and source distribution
   from the tag, then compute a `SHA256SUMS` file containing their two filenames
   and SHA-256 hashes.
4. Create a GitHub Release with release notes and attach the wheel, source
   distribution and `SHA256SUMS` **before publishing the release**.
5. The `Publish to PyPI` workflow verifies those exact assets, checks the tag and
   package version, runs installed-wheel and quickstart checks, and uploads the
   same files to PyPI. Verify a clean installation from PyPI after it succeeds.

## One-time PyPI authentication

The workflow supports [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/adding-a-publisher/).
In the existing `omnismi` project's publishing settings, configure:

| Field | Value |
|---|---|
| Owner | `phantom5125` |
| Repository | `omnismi` |
| Workflow filename | `publish.yml` |
| Environment | `pypi` |

Alternatively, store an `omnismi`-scoped PyPI API token in the GitHub repository
or `pypi` environment secret named `PYPI_API_TOKEN`. Do not commit or put the token
in an issue or release note.

If authentication needs configuration after a GitHub Release is published,
rerun the failed publishing job. The workflow also supports manual dispatch
with the existing release tag. Published package files are immutable; do not
replace a released file or reuse a version for different contents.
