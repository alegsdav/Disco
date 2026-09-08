# Development, in plain English

Last updated: 2026-09-07.

This is the simple companion to [DEVELOPMENT.md](DEVELOPMENT.md). It explains
where we are, what has been checked, and what comes next. The detailed build
order lives in [ROADMAP.md](ROADMAP.md).

## What are we building?

Disco will watch for documents companies send to the SEC, save them, read them,
and send useful research alerts to Discord. Each alert should show the source
and the words that support it.

We are still building the foundations. The full filing-to-Discord system is
not running yet.

## What have we done?

| Work | In simple words | Current state |
|---|---|---|
| A1: tools and automatic checks | Gave the project its toolbox and a way to catch mistakes. | Included in B1's starting point; merged in the locally known history. |
| B1: message rules | Agreed on the shape of the information each part sends to the next part. | Written, tested, and approved by both owners; final GitHub checks and merge remain. |
| B1: practice documents | Saved 18 real SEC documents and 5 deliberately broken ones so we can test without downloading them again. | 23 files checked; all match their recorded fingerprints. |
| A's receiving exercise | Built a separate reader to see whether another part of the project can understand B's messages. | Passed against B1 commit `a10326b`. Reader and review notes are included in the G1 handoff. |

There are four kinds of messages:

1. **FilingDetected:** "We found a company filing."
2. **ParseRequest:** "Here is the saved document. Please read it using this reader version."
3. **ParsedFiling:** "Here is what we found inside, with supporting text and any reading problems."
4. **RankedEvent:** "Here are its scores, and whether it should become an alert."

These rules are called **contracts**. They let A and B build different parts
without guessing what the other person's information will look like.

## What did the receiving exercise prove?

The small reader is [scripts/g1_consumer.py](../scripts/g1_consumer.py).
It reads the shared rule files directly, without using B's Python message models.

- It understood all 13 good example messages and rejected all 14 bad examples.
- It accepted "we don't know the ticker or document name yet."
- It checked that finding the same filing through two sources keeps the same
  filing ID, while each source gets its own delivery key. The second observation
  was made in memory for this check.
- It read the requested reader version and document fingerprint.
- It checked that a quotation's start and end positions match its character
  count, including accented letters and emoji.
- It displayed missing statistics as "not available" and kept actual zero as zero.
- It marked the example with `should_alert: false` as suppressed.

We also made a fresh local copy of B1 and ran the project's checks: **128 Python
tests passed**, all four rule files matched their Python definitions, all 23
document fingerprints matched, and the Rust and infrastructure checks passed.
Rust currently has no tests; its code is still a starting shell.

This proves the examples and current setup work in the checked environment.
It does not prove that live SEC collection, the real document reader, or Discord
delivery works. No alerts were sent and no cloud resources were deployed.
Checking quotation positions also does not yet prove the words match the real
reader's cleaned document text; that needs the future reader and its output.

## What do the two owners need to do now?

We are at **G1**, the "agree on the message rules before building further" checkpoint.

**Person A — the person building the plumbing:**

1. Review the reader and its results in [G1_REVIEW.md](G1_REVIEW.md).
2. Walk through the four messages with B and ask whether anything needed by the
   receiving services is missing or unclear.
3. Explicitly approve the final rules if satisfied. The automated exercise has
   passed; it does not count as A's personal approval.
4. After both approvals, successful GitHub checks, and the merge, record that G1
   is closed in the review file.

**Person B — the person building the filing and data logic:**

1. Walk through the same messages with A and explain the meaning of each field.
2. Fix any agreed problems and update the examples and generated rule files.
   If the rules change, repeat A's receiving exercise against that revision.
3. Explicitly approve the final rules and finalize the B1 review request.

**Together:** make sure the reader and evidence are included in the reviewed
changes, record both approvals, confirm GitHub's automatic checks pass for the
final revision, and merge B1 into `main` (the shared accepted version).
Passing checks on this computer does not replace passing checks on GitHub.

## What comes after G1?

- **A builds A2:** the cloud storage, work queues, permissions, and cost alarms.
  Then **A3:** shared helpers so B can use storage and queues without writing
  cloud setup code everywhere.
- **B can build B4:** the actual document reader, using the saved practice files.
  This can happen while A builds the cloud pieces.
- **B2's live daily filing collection** needs A's infrastructure and helpers to
  reach the next checkpoint, G2. Offline preparation can happen earlier.

## How do we check changes?

The detailed installation instructions are in [DEVELOPMENT.md](DEVELOPMENT.md).
The toolbox uses fixed versions so both people run the same tools:
GNU Make, uv 0.7.18, Rust 1.88.0, and Terraform 1.12.2.

Run the normal project checks with:

```sh
make check
```

Think of this as an inspection: it looks for common code mistakes, mismatched
message rules, failing examples, damaged practice files, and invalid cloud setup.
It may download required software on first use. It does not build the live cloud
system or download the SEC practice documents again.

Run A's separate message-reading exercise with:

```sh
uv run --locked --all-packages python scripts/g1_consumer.py
```

On the Windows computer used for this review, Make was unavailable, so we ran
each of its checks separately. The exact checks are recorded in the G1 review.

Two other commands change files:

- `make contracts` rebuilds the shared rule files from the Python definitions.
  Changes to the rules still need both owners' approval.
- `make fixtures` downloads the selected SEC practice documents again. It needs
  the SEC contact identification described in the fixture instructions.

## Keep this page current

With each code change, update this page in the same review request. Explain:

1. What changed and what it lets the project do now.
2. What was actually checked and whether it passed.
3. What is still missing and who does it next.

Update the date and the current-state sections instead of leaving old claims
that work is still pending after it is done. Use everyday words; put exact
technical details in DEVELOPMENT.md or the relevant review document and link
to them. Keep local checks, owner approvals, GitHub checks, and merged work
separate so readers can tell what is really finished.

This page is maintained by people and coding assistants; it does not update itself.


## Approved handoff

Both owners approved on 2026-09-07. Their approval steps above are complete.
The remaining shared step is successful GitHub checks and merge.
See [NEXT_STEPS.md](NEXT_STEPS.md) for A2 and B2 starting tasks.
A's reader now runs automatically inside make check.
