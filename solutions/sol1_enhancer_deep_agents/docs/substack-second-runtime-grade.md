# Grade: *The Second Runtime*, round 3

Graded against `docs/substack-second-runtime-criteria.md` after the editorial review that benchmarked this article against *Python Owns the Loop*.

**Result: pass.** Two code defects the review predicted were real, and both are fixed with tests.

## The two technical findings, verified

The review claimed the doer's write tool did not enforce the property the article asserted. Both parts were true, and one was worse than described.

| Claim | Verified | Evidence |
| --- | --- | --- |
| The doer can write any file under `tickets/**`, including the real ticket | Yes | `write("tickets/T001.md", ...)` returned `wrote tickets/T001.md` and overwrote the ticket the judge grades, going around the proper-subset gate |
| Path validation ran in the wrong order | Yes, and it escaped the directory | `WriteScope` globs a string and does not resolve `..`, so `tickets/../app/models.py` matched `tickets/**` as text, passed the check, and landed in `app/models.py` |

Both are fixed in `roles.py`:

1. `scoped_write_tool` canonicalizes with `_inside` first, derives the canonical relative path, and scope-checks that. The confirmation message now names the canonical path so a normalization cannot hide.
2. A `CURRENT_ALLOW` context variable carries the turn's scope. `enhancer.draft` grants exactly the candidate path, and `adapter.DeepAgentsBackend.run` holds that scope open around the one graph invocation. A turn may shrink a role's scope, never widen it.

Three regression tests added, plus one existing test tightened. The traversal test was confirmed to fail without the fix. Suite: **218 passed, 1 skipped in 0.44s**.

## Editorial items, all applied

| Item | Applied |
| --- | --- |
| Title too abstract | `The Second Runtime: What Survives When You Port an Agent Loop`, with the reviewer's subtitle |
| Thesis at ~936 words | Thesis pull quote at **190 words**, the mechanism at 291 |
| Part 1 review too long | Cut to one figure, one paragraph on the three roles, one on the proper-subset gate, and two links |
| Ten listings | **Six.** The three fences merged into one listing. The adapter moved to prose plus a Sources pointer |
| Operational section ~1,000 words | Cut to prerequisites, setup, validation, one live poll, and an outcome table. Reset, teardown, and recovery point at `HOW_TO_RUN.md` |
| No paywall point | `<!-- PAYWALL -->` marker after listing 2, with the transition line the reviewer suggested |
| Wide comparison table | Split into three narrow two-column tables |
| Repeated restatements | Removed. Length **8,276 to 5,138 words**, a 38% cut |
| Environment not pinned | Version table: `deepagents` 0.7.10, `langchain` 1.3.18, Python 3.14.6, model `anthropic:claude-sonnet-5`, lab commit `821992f`, tested 31 August 2026 |
| "The entire difference between the two ports" | Now "the entire difference between the two copies of `roleplan.py`" |
| "ready is a fact" overstated | Reframed as a deterministic decision over an independently produced observation, with four bullets naming where determinism starts and stops |
| Unit tests conflated with runtime evidence | Three explicit layers. The article states plainly that `fake_langchain` means no Deep Agents is running when the 218 tests pass |
| `LGTM` presented as authorization | New subsection separating syntax from authorization, naming five identity policies |
| "The loop from part 1 did not move" | Removed. Replaced with the reviewer's framing: four loop policies survived, one exit policy changed deliberately, and the change is the finding |
| Structure | Rebuilt on the reviewer's eight-section outline |
| Opening | Adapted from the reviewer's draft, with the banned openers removed |

## Style gates

Em dashes 0. Banned sentence openers 0. Identifier-led sentences 0. First-person "we" 0. Listing 3 verified line for line against `roles.py`.

## Open before publishing

1. Render the cover at `docs/substack-images/cover.jpg`.
2. Add the layer-two integration test against `deepagents` 0.7.10, which the article now names as the missing layer.
3. Capture a live poll transcript. The article carries the three no-model outputs only.
4. Re-push the gist. The published version is round 2 and predates every change above.
