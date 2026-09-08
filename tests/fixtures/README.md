# Fixture corpus

Real SEC filings, committed, so that every test and benchmark runs offline and
against the same bytes. `make check` verifies the hashes and never contacts the
SEC.

## What is here

| Directory | Contents |
|---|---|
| `filings/<form>/<accession>.<ext>` | 18 real primary documents, 2 per form type |
| `malformed/` | 5 documents derived from the above by deterministic corruption |
| `manifest.json` | path, SHA-256, size and provenance for all 23 |
| `tools/` | the selection list and the script that rebuilds both |

Form types covered: `8-K`, `10-Q`, `10-K`, `6-K`, Forms `3`/`4`/`5`,
`SCHEDULE 13D`, `SCHEDULE 13G`. Total 4.5 MB.

The corpus is deliberately small. Filings were chosen as the smallest real
documents of each form type, so the repository stays cheap to clone. The two
10-Ks are 1.6 MB and 1.9 MB because no 10-K is smaller than that — they are the
smallest found across three sampled filing days.

**This is not B5's benchmark corpus.** B5 needs 25 8-Ks, 25 10-Qs, 25 10-Ks and
10 malformed documents at realistic sizes, which is a different order of
magnitude and needs its own storage decision before it lands in git.

## Malformed fixtures

Each is generated from a named real filing by a documented, deterministic
transform, so its hash is stable across rebuilds. The parser (B4) must recover
from all five without panicking and must report a non-zero
`malformed_nodes_skipped`.

| Fixture | Corruption |
|---|---|
| `truncated-mid-tag.htm` | 8-K cut at 60% of its bytes, ending inside an open tag |
| `unclosed-tags.htm` | 8-K with every closing `div` and the trailing `body`/`html` removed |
| `invalid-utf8.xml` | Form 4 with bytes `0xFF 0xFE` injected at its midpoint |
| `broken-xml-nesting.xml` | Form 4 whose root element closes immediately, orphaning its children |
| `empty.txt` | Zero-byte document |

## Rebuilding

The corpus is committed; you only need this when adding or replacing fixtures.

```sh
DISCO_SEC_USER_AGENT="Your Name your.email@example.com" make fixtures
```

To add a filing, add an entry to `tools/selection.json` and re-run. The script
rate-limits itself to 5 requests per second and identifies itself to the SEC, as
[EDGAR access guidance](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)
requires.

To rebuild the derived fixtures and manifest without touching the network:

```sh
uv run python tests/fixtures/tools/build_corpus.py --manifest-only
```

`retrieved_at` is preserved for files already in the manifest, so a rebuild does
not churn provenance for fixtures that did not change.

## Manifest format

`scripts/verify_fixture_hashes.py` reads only `path` and `sha256`; the remaining
keys are provenance for humans and for B5's report.

```json
{
  "files": [
    {
      "path": "filings/8-k/0001320461-25-000012.htm",
      "sha256": "3de40c5b...",
      "bytes": 33303,
      "kind": "primary_document",
      "form_type": "8-K",
      "cik": "0001320461",
      "accession_number": "0001320461-25-000012",
      "company": "Cooper-Standard Holdings Inc.",
      "filed": "2025-02-14",
      "source_uri": "https://www.sec.gov/Archives/edgar/data/1320461/...",
      "retrieved_at": "2026-09-05T05:47:12Z"
    }
  ]
}
```

Derived fixtures carry `kind: "derived"` with `derived_from` and `description`
instead of the EDGAR provenance fields.
