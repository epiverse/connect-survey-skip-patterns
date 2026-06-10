# Independent Verification — `output/bio_menstrual.json` (Menstrual Cycle module)

**Verifier:** independent agent (Claude Opus 4.8, 1M context)
**Date:** 2026-06-09
**Source re-extracted via:** `bash tools/extract.sh bio_menstrual` (`textutil -convert txt -stdout … | cat -n`; `.docx` is read-only, line numbers stable)
**Contract read:** `docs/CONVENTIONS.md`, `schema/connect_survey.schema.json`
**Method:** Re-derived truth from source independently (assumed nothing in the JSON). All text/option/directive/message/excerpt strings were byte-compared against the freshly extracted source (including dash and curly-quote codepoints and trailing-whitespace handling).

---

## 1. Per-item PASS/FAIL table

| order | id | kind | bullet | text verbatim | options | display_condition | routing | range_check | piped_refs | provenance | overall |
|-------|----|------|--------|---------------|---------|-------------------|---------|-------------|------------|------------|---------|
| 0 | `SrvBlU_MENSINTRO_v2r0` | display_text | false | PASS | n/a | null (none in src) | null (none) | n/a | none | L2–2 PASS | **PASS** |
| 1 | `SrvBlU_MENSINTRO2_v1r0` | display_text | false | PASS | n/a | null (none in src) | null (none) | n/a | `[insert SrvBlU_MENSTART_v2r0]` PASS | L3–5 PASS | **PASS** |
| 2 | `SrvBlU_MENS1_v1r0` | question | true | PASS | 2 opts PASS | null (correct) | opt routes PASS | n/a | none | L6–8 PASS | **PASS** |
| 3 | `SrvBlU_MENS2_v2r0` | question | true | PASS | n/a (date) | `eq MENS1=1` high PASS | `default_next=END_MESSAGE_2` PASS | relative_date min / system_var max, needs_review PASS | none | L10–17 PASS | **PASS** |
| 4 | `END_MESSAGE_1` | terminal | false | PASS | n/a | `eq MENS1=0` high PASS | terminal end_message id=1, clear_cache, condition=null PASS | n/a | none | L19–20 PASS | **PASS** |
| 5 | `END_MESSAGE_2` | terminal | false | PASS | n/a | `response_entered` w/ version-drift PASS | terminal end_message id=2, exit_behavior=null, condition=null PASS | n/a | none | L22–23 PASS | **PASS** |

All 6 items PASS. No BLOCKING issues.

### Field-level evidence (string fidelity, byte-compared)
- **MENSINTRO_v2r0.text** == source L2 body (prefix `[SrvBlU_MENSINTRO_v2r0] ` stripped, trailing NBSP trimmed). EQUAL.
- **MENSINTRO2_v1r0.text** == source L3–5 joined with `\n` (id prefix stripped on L3, trailing NBSP trimmed per line). `[insert SrvBlU_MENSTART_v2r0]` correctly retained inline in `text`. EQUAL.
- **MENS1.text** == source L6 body. EQUAL. Options: code `0`/`1`, labels `No`/`Yes`; `route.raw` == L7/L8 verbatim (`0\tNo --> GO TO END MESSAGE 1` / `1\tYes --> GO TO SrvBlU_MENS2_v2r0`); kinds `terminal`/`goto`. EQUAL.
- **MENS2.text** == source L12 body + `\n` + L13. EQUAL. `requires_response:true` reflects L11 `[PROGRAMMING NOTE: QUESTION REQUIRES RESPONSE]` (§4). `response.type:date` justified by L15 mask `_ _/_ _ /_ _ _ _`.
- **MENS2 range_check.raw** == L15 directive verbatim, incl. EN DASH `–` (U+2013, bytes `e2 80 93`) — matches source dash exactly. `min={kind:relative_date, expr:"today - 60d", raw:"(Today date – 60 days)"}`, `max={kind:system_var, var:"Today date"}`, `needs_review:true`. PASS (§7, conv #7).
- **MENS2.flags.notes[0]** == L16 verbatim (error message, with curly quotes `“…”`). EQUAL.
- **EM1.text** == `END MESSAGE 1: “<msg>”` reconstruction (no `[EXIT AND CLEAR CACHE]`, trailing NBSP trimmed). **EM1 terminal.message** == inner quoted text of L20 verbatim. `exit_behavior:"clear_cache"` ⇐ L20 `[EXIT AND CLEAR CACHE]`. PASS (conv #1).
- **EM2.text** / **EM2 terminal.message** == L23 inner quoted text verbatim, incl. nested curly quotes around `“Submit Survey”`. `exit_behavior:null` (no EXIT directive). PASS.
- **All 6 provenance.raw_excerpt** match their cited source spans verbatim (modulo trailing-NBSP normalization, which CONVENTIONS §1 permits). The question-level forward `--> GO TO END MESSAGE 2` (L17) is preserved verbatim inside MENS2's `raw_excerpt`, satisfying conv #2's "verbatim arrow preserved" intent while the resolved target lives in `default_next`.

---

## 2. Numbered discrepancy list

> No BLOCKING issues found. Two ADVISORY observations and the legitimate owner-bound `needs_review` items (which do not block) are listed.

**D1 — ADVISORY.** Source L11 `[PROGRAMMING NOTE: QUESTION REQUIRES RESPONSE]` (within MENS2 span 10–17).
- JSON path: `items[3].flags.notes` / `items[3].requires_response`.
- What: The note's *logic* is correctly encoded as `requires_response:true` (CONVENTIONS §4 explicitly maps this directive to `requires_response`). However, CONVENTIONS §3.9 ("Programmer notes → keep verbatim in `item.flags.notes`") is not also satisfied for this particular note — its verbatim text is absent from `flags.notes` (only the error-message note and the date-mask note are listed). By contrast, the L16 error-message note *was* captured verbatim, so the treatment is slightly inconsistent.
- Suggested fix (optional): add `"[PROGRAMMING NOTE: QUESTION REQUIRES RESPONSE]"` to `items[3].flags.notes` for verbatim completeness. Not required for correctness — §4 takes precedence for this directive and the logic is faithfully represented.
- Severity: **ADVISORY**.

**D2 — ADVISORY.** Relative-date bound `expr` field, `items[3].response.range_check.min.expr`.
- What: `expr:"today - 60d"` is a synthesized/normalized form; the source phrasing is `Today date – 60 days`. The schema makes `expr` optional and the verbatim string is preserved in `min.raw`, so this is acceptable. Flagging only because `expr` is not verbatim source.
- Suggested fix: none required; optionally align `expr` text closer to source (e.g., `"Today date - 60 days"`). `needs_review:true` already set on the range_check (conv #7), which is the contractually required signal.
- Severity: **ADVISORY**.

**D3 — needs_review (owner-bound SME question; NON-blocking).** END MESSAGE 2 gate version drift. Source L22 `[DISPLAY IF RESPONSE ENTERED AT SrvBlU_MENS2_v1r0]` cites stale `…_v1r0`; the only defined MENS2 item is `…_v2r0` (defined at L8/L12; no `_v1r0` item exists anywhere in source).
- JSON path: `items[5].display_condition`.
- Status: **Correctly handled** per CONVENTIONS §6 and the schema-breaker catalog (bio_menstrual L12-vs-22 entry). Leaf `var:"SrvBlU_MENS2_v2r0"`, `resolved_from:"SrvBlU_MENS2_v1r0"`, `op:"response_entered"`, `confidence:"medium"`, `needs_review:true`, non-empty `interpretation_note`. No item invented. Also mirrored in `build_meta.open_questions`. This is a legitimate SME confirmation item, not a defect.
- Severity: **non-blocking** (acceptable owner-bound `needs_review`).

**D4 — needs_review (owner-bound; NON-blocking).** Relative-date range check `items[3].response.range_check.needs_review:true` and corresponding `build_meta.open_questions` entry. Correctly flagged per conv #7. Non-blocking.

---

## 3. Coverage summary (source vs serialized)

**Source line accounting (1–23 meaningful; 24–26 trailing blank):**

| Source construct | Source location | Serialized as | Status |
|---|---|---|---|
| Title `Menstrual Cycle Survey` | L1 | `module.title` (not an item, per §1) | ✓ |
| ID block `[SrvBlU_MENSINTRO_v2r0]` | L2 | item 0 (display_text) | ✓ |
| ID block `[SrvBlU_MENSINTRO2_v1r0]` | L3–5 | item 1 (display_text) | ✓ |
| pipe `[insert SrvBlU_MENSTART_v2r0]` | L3 | item 1 `piped_refs[0]` (external, src_module bio_clinical) | ✓ |
| `•` question `[SrvBlU_MENS1_v1r0]` | L6 | item 2 (question) | ✓ |
| option `0 No --> END MESSAGE 1` | L7 | item2 opt0 route → `END_MESSAGE_1` (terminal) | ✓ |
| option `1 Yes --> SrvBlU_MENS2_v2r0` | L8 | item2 opt1 route → `SrvBlU_MENS2_v2r0` (goto) | ✓ |
| blank (NBSP) | L9 | — (separator) | ✓ |
| `[DISPLAY IF SrvBlU_MENS1_v1r0= 1]` | L10 | item3 `display_condition` (`eq MENS1=1`) | ✓ |
| `[PROGRAMMING NOTE: QUESTION REQUIRES RESPONSE]` | L11 | item3 `requires_response:true` (§4) | ✓ (see D1) |
| `•` question `[SrvBlU_MENS2_v2r0]` | L12 | item 3 (question) | ✓ |
| sub-instruction (phone/tablet) | L13 | part of item3 `text` (2nd line) | ✓ |
| blank (NBSP) | L14 | — (separator) | ✓ |
| date mask + `[RANGE CHECK …]` | L15 | item3 `response.range_check` + date-mask note | ✓ |
| error message string | L16 | item3 `flags.notes[0]` (verbatim) | ✓ |
| `--> GO TO END MESSAGE 2` | L17 | item3 `routing.default_next = END_MESSAGE_2` (conv #2) | ✓ |
| blank (NBSP) | L18 | — (separator) | ✓ |
| `[DISPLAY IF SrvBlU_MENS1_v1r0= 0]` | L19 | item4 `display_condition` (`eq MENS1=0`) | ✓ |
| `END MESSAGE 1: “…” [EXIT AND CLEAR CACHE]` | L20 | item 4 terminal (id=1, msg, clear_cache) | ✓ |
| blank | L21 | — (separator) | ✓ |
| `[DISPLAY IF RESPONSE ENTERED AT SrvBlU_MENS2_v1r0]` | L22 | item5 `display_condition` (response_entered, version-drift) | ✓ |
| `END MESSAGE 2: “…”` | L23 | item 5 terminal (id=2, msg, no exit) | ✓ |

**Counts (source vs serialized):**

| Construct | In source | Serialized | Match |
|---|---|---|---|
| ID blocks (bracketed item ids) | 4 | 4 items keyed to them | ✓ |
| `•` bullet questions | 2 (L6, L12) | 2 `kind:question` | ✓ |
| display-text intros | 2 | 2 `kind:display_text` | ✓ |
| END MESSAGE terminals | 2 (L20, L23) | 2 `kind:terminal` | ✓ |
| Total items | 6 | 6 | ✓ |
| Answer options | 2 (MENS1) | 2 | ✓ |
| `[DISPLAY IF …]` conditions | 3 (L10, L19, L22) | 3 (validator: `conditions=3`) | ✓ |
| Option-level routes | 2 (L7, L8) | 2 | ✓ |
| Question-level forwards | 1 (L17) | 1 (`default_next`) | ✓ |
| Range checks | 1 (L15) | 1 | ✓ |
| Pipes `[insert …]` | 1 (L3) | 1 `piped_ref` | ✓ |
| `[EXIT AND CLEAR CACHE]` | 1 (L20) | 1 (`exit_behavior:clear_cache`) | ✓ |
| Programming notes | 1 (L11) | encoded as `requires_response` (§4) | ✓ (D1) |

**Invented content:** none. No options, conditions, routes, terminals, pipes, sections, repeated_groups, or grids exist in the JSON that are absent from source. `module.sections:[]`, `repeated_groups:[]`, `grids:[]` are all correctly empty (source has intro blocks, not `[SECTION n]` headers; no loops/grids).

**Omitted content:** none. Every bracketed token, every `Srv…` id token (6 unique), every END MESSAGE reference (4), and every option/route/condition/range/pipe/terminal in source is represented. Only uncovered source lines are L1 (title → `module.title`) and L9/L14/L18/L21/L24–26 (NBSP/blank separators) — correctly excluded.

**Routing integrity:** all route targets and `default_next` resolve to existing item ids — `MENS1.opt0→END_MESSAGE_1`, `MENS1.opt1→SrvBlU_MENS2_v2r0`, `MENS2.default_next→END_MESSAGE_2`. No dangling routes.

**Dependency graph:** validator reports `dep_nodes=6 dep_edges=7`, no cycle warning. Independently re-derived the 7 edges (3 route + 3 display + 1 pipe): `MENS1→EM1` (route+display), `MENS1→MENS2` (route+display), `MENS2→EM2` (route+display), `MENSTART→MENSINTRO2` (pipe). Data-dependency subgraph (display+pipe) is acyclic — confirmed DAG.

**Unknown variables:** none. Both non-item leaves are declared in `module.external_variables`: `SrvBlU_MENSTART_v2r0` (`external`, `source_module:"bio_clinical"`) and `Today date` (`system`). Validator emits only a NOTE for the external pipe, no `unknown variable` error.

---

## 4. Count reconciliation

- `stated_question_count` = **2**
- `counted_question_count` = **2** (the two `•` bullets at L6 and L12)
- Number of `kind:"question"` items = **2** (validator's hard check: `counted_question_count` must equal question-item count → satisfied)
- The two unbulleted MENSINTRO blocks (`display_text`) and the two END MESSAGE blocks (`terminal`) are correctly excluded from the question count.
- The JSON's `count_reconciliation` narrative is accurate and matches the source. **Reconciliation: PASS (2 == 2 == 2).**

---

## 5. Convention-compliance checks (build must follow these)

| Conv | Requirement | Result |
|---|---|---|
| #1 | END MESSAGE = `terminal`, synthesized `END_MESSAGE_<n>`, `response:null`, terminal `{type:end_message, id, message verbatim w/o prefix, exit_behavior=clear_cache iff [EXIT AND CLEAR CACHE], condition:null}` | PASS (both EMs) |
| #2 | route→END MESSAGE targets synthesized id + verbatim arrow in `route.raw`; question-level `--> GO TO END MESSAGE n` → `routing.default_next` | PASS (opt0→EM1 raw kept; L17→`default_next=END_MESSAGE_2`) |
| #3 | END MESSAGE `[DISPLAY IF…]` gate in item `display_condition`, NOT `terminal.condition` (which is null) | PASS (both EMs: `display_condition` set, `terminal.condition:null`) |
| #4 | Directives preceding a `•` question (its `[DISPLAY IF…]`/`[PROGRAMMING NOTE…]`) belong to that question's block (provenance span + display_condition + requires_response) | PASS (L10/L11 → MENS2 span 10–17, `display_condition`, `requires_response:true`) |
| #5 | Validation error strings captured verbatim in `flags.notes` | PASS (L16 error message verbatim in `notes[0]`) |
| #6 | Version drift → leaf var = existing id, `resolved_from` = stale cite, `confidence:medium`, `needs_review:true`, explanatory `interpretation_note`; no invented items | PASS (EM2 gate) |
| #7 | Relative-date bound `{kind:relative_date, expr, raw}`; `Today date` bound `{kind:system_var, var:"Today date"}`; `range_check.needs_review:true` | PASS (MENS2 range_check) |
| §7 | external/system leaves declared in `module.external_variables` | PASS (both declared) |

No convention violations detected.

---

## 6. Validator result (verbatim)

Command: `.venv/bin/python tools/validate.py output/bio_menstrual.json --registry registry/variable_index.json`

```
WARNINGS (2):
  - id-format: 'END_MESSAGE_1' does not match srv_versioned
  - id-format: 'END_MESSAGE_2' does not match srv_versioned
NOTES (1):
  - external variable: SrvBlU_MENSTART_v2r0 (at items[1].piped_refs[0])
summary: items=6 conditions=3 needs_review=1 dep_nodes=6 dep_edges=7 errors=0 warnings=2
```

- **errors=0.** Clean.
- The 2 WARNINGS are expected and correct: synthesized `END_MESSAGE_<n>` ids deliberately do not follow the `srv_versioned` pattern (conv #1 mandates these synthesized ids — there is no bracket id in source). Advisory, non-blocking.
- The 1 NOTE is informational (declared external pipe).
- `needs_review=1` corresponds to the EM2 version-drift gate (the range-check `needs_review:true` is on the `range_check` object, which the validator counts separately/not in this tally; both are intentional per conv #6/#7).

---

## 7. Verdict

No BLOCKING issues. Two ADVISORY observations (D1: programming-note text not also mirrored verbatim in `flags.notes`; D2: `expr` field not verbatim source — both non-blocking, with the contractually-required signals present). The two `needs_review` items (version drift, relative-date range) are legitimate owner-bound SME questions, correctly modeled, and do not block.

**VERDICT: PASS**
