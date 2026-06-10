# Verifier Report — `bio_clinical` (Baseline Blood & Urine Sample Survey)

- **Module:** `bio_clinical` → `data/questionnaire/Biospecimens Survey - Clinical Collection (Blood & Urine).docx`
- **Target verified:** `output/bio_clinical.json`
- **Verifier:** independent agent (Claude Opus 4.8), Phase 2 of `PLAN.md`
- **Date:** 2026-06-09
- **Method:** re-extracted the source (`bash tools/extract.sh bio_clinical`, 99 lines, read top-to-bottom),
  re-derived the truth independently, and compared every item against its cited source lines. The builder's
  JSON was **not** trusted. Line numbers below are from `tools/extract.sh` (stable).

---

## Validator result

```
$ .venv/bin/python tools/validate.py output/bio_clinical.json
summary: items=23 conditions=2 needs_review=0 dep_nodes=20 dep_edges=26 errors=0 warnings=0
exit 0
```

- **0 errors, 0 warnings** — schema-conformant, IDs unique, all routes/variables resolve, wrapper
  integrity OK, counts reconciled.
- `dep_nodes=20`: the 3 grid-row items (TYLENOL/NSAIDS/ACID) carry no dependency edges, so 23 items − 3 = 20.
  Expected (see Judgment Calls).
- `needs_review=0` counts **condition-wrapper** review flags only. The two **item-level**
  `flags.needs_review:true` (CONTRACEPT, HORMONE) are tracked separately in `build_meta.open_questions`
  and are intentional SME questions, not validator findings.

---

## Per-item PASS/FAIL table

Checked per item: ID (verbatim incl. `_v#r#`), `kind`, `bullet`, `order_index`, verbatim `text`,
options (code/label/flags/route/display-condition), `display_condition.parsed` faithfulness, `routing`,
and `provenance` line accuracy.

| # | Item ID | kind | Src lines | ID | text | options | cond. | routing | prov. | Result |
|---|---------|------|-----------|----|----|---------|-------|---------|-------|--------|
| 0 | SrvBio_MODULEINTRO_v1r0 | display_text | 2 | ✓ | ✓ | n/a | n/a | ✓ | ✓ | **PASS** |
| 1 | SrvBio_SEX_v2r1 | question | 4–6 | ✓ | ✓ | ✓ (0,1) | n/a | ✓ | ✓ | **PASS** |
| 2 | SrvBio_SYMPTDAY_v1r0 | question | 8–14 | ✓ | ✓ | ✓ (0-4,88) | n/a | ✓ | ✓ | **PASS** |
| 3 | SrvBio_EATDRINKBEFORE_v1r0 | question | 16–19 | ✓ | ✓ | ✓ (0-2; 2→route) | n/a | ✓ | ✓ | **PASS** |
| 4 | SrvBio_EATDRINKTIME_v1r0 | question | 21–22 | ✓ | ✓ | time | n/a | ✓ | ✓ | **PASS** |
| 5 | SrvBio_SLEEPTIME_v1r0 | question | 24–25 | ✓ | ✓ | time | n/a | ✓ | ✓ | **PASS** |
| 6 | SrvBio_WAKETIME_v1r0 | question | 27–28 | ✓ | ✓ | time | n/a | ✓ | ✓ | **PASS** |
| 7 | SrvBlU_MED_v1r0 | display_text | 29 | ✓ | ✓ | n/a | n/a | ✓ | ✓ | **PASS** |
| 8 | GRID_SRVBLU_MED1_V1R0 | question | 30–37 | ✓ | ✓ | ✓ (0-4) | n/a | ✓ | ✓ | **PASS** |
| 9 | SrvBlU_TYLENOL_v2r0 | grid_row | 38–43 | ✓ | ✓ | ✓ (0-4) | n/a | ✓ | ✓ | **PASS** |
| 10 | SrvBlU_NSAIDS_v2r0 | grid_row | 44–49 | ✓ | ✓ | ✓ (0-4) | n/a | ✓ | ✓ | **PASS** |
| 11 | SrvBlU_ACID_v1r0 | grid_row | 50–57 | ✓ | ✓ | ✓ (0-4) | n/a | ✓ | ✓ | **PASS** |
| 12 | SrvBlU_REPROINTRO_v1r0 | display_text | 58–61 | ✓ | ✓ | n/a | ✓ eq SEX=0 / else END | ✓ | ✓ | **PASS** |
| 13 | SrvBlU_MENSTPRD_v2r0 | question | 62–64 | ✓ | ✓ | ✓ (0→route,1) | n/a | ✓ req=true | ✓ | **PASS** |
| 14 | SrvBlU_MENST60_v2r0 | question | 66–68 | ✓ | ✓ | ✓ (0→route,1) | n/a | ✓ req=true | ✓ | **PASS** |
| 15 | SrvBlU_MENSTART_v2r0 | question | 70–71 | ✓ | ✓ | date | n/a | ✓ req=true | ✓ | **PASS** |
| 16 | SrvBlU_PREGNANT_v1r0 | question | 73–75 | ✓ | ✓ | ✓ (0,1→route) | n/a | ✓ | ✓ | **PASS** |
| 17 | SrvBlU_PREG3MON_v1r0 | question | 77–79 | ✓ | ✓ | ✓ (0,1) | n/a | ✓ | ✓ | **PASS** |
| 18 | SrvBlU_BRSTFD_v1r0 | question | 81–83 | ✓ | ✓ | ✓ (0,1→route) | n/a | ✓ | ✓ | **PASS** |
| 19 | SrvBlU_BRSTFD3MON_v1r0 | question | 85–87 | ✓ | ✓ | ✓ (0,1) | n/a | ✓ | ✓ | **PASS** |
| 20 | SrvBlU_CONTRACEPT_v1r0 | question | 89–93 | ✓ | ✓ | ✓ (0,1 inferred) | ✓ eq PREGNANT=0 / else END | ✓ | ✓ | **PASS** |
| 21 | SrvBlU_HORMONE_v1r0 | question | 95–97 | ✓ | ✓ | ✓ (0,1 inferred) | n/a | ✓ | ✓ | **PASS** |
| 22 | CLOSING_REMARK | terminal | 99 | ✓ (synth.) | ✓ | n/a | n/a | ✓ end_module | ✓ | **PASS** |

**23/23 items PASS.** Plus `grids[0]` = `GRID_SRVBLU_MED1_V1R0` (stem, shared 5-pt temporal scale,
3 row IDs, `same_screen:true`) — **PASS**.

Both `display_condition` wrappers faithfully and completely encode their `raw` (correct `op`, var, value,
`else_route`), with justified `confidence:"high"`:

> Source L58–59: `[DISPLAY SrvBlU_REPROINTRO_v1r0 IF (SrvBio_SEX_v2r1= 0),` / `ELSE, GO TO END]`
> → `{"op":"eq","var":"SrvBio_SEX_v2r1","value":0}`, `else_route → END`. ✓

> Source L89–90: `[DISPLAY SrvBlU_CONTRACEPT_v1r0 IF (SrvBlU_PREGNANT_v1r0= 0),` / `ELSE, GO TO END]`
> → `{"op":"eq","var":"SrvBlU_PREGNANT_v1r0","value":0}`, `else_route → END`. ✓

All option-level routes verified against source:

> L19 `2	More than a day before à GO TO SrvBio_SLEEPTIME_v1r0` → option 2 route ✓
> L63 / L67 `0	No à GO TO SrvBlU_PREGNANT_v1r0` → MENSTPRD.0 / MENST60.0 routes ✓
> L75 `1	Yes à GO TO SrvBlU_BRSTFD_v1r0` → PREGNANT.1 route ✓
> L83 `1	Yes à GO TO SrvBlU_CONTRACEPT_v1r0` → BRSTFD.1 route ✓

`requires_response:true` is set on exactly MENSTPRD, MENST60, MENSTART — matching the source
`[this question requires a response]` directives at L62, L66, L70. No other item carries it. ✓

---

## Numbered discrepancy list

### 1. MINOR (recommend fix) — `module.count_reconciliation` prose inaccuracy

**JSON path:** `module.count_reconciliation`

The field asserts:

> "Exactly 16 '•' bullet markers appear in the source (lines 4, 8, 16, 21, 24, 27, 30, 62, 66, 70, 73, 77, 81, 85, 91, 95) …"

This is **factually inaccurate about the glyph count**: there are **20** `•` markers in the source, not 16.
The 16 listed lines are correct *question-level* bullets, but **4 additional `•` sub-bullets** are present —
the uncoded CONTRACEPT/HORMONE answer options:

> L92 `	•	No`
> L93 `	•	Yes`
> L96 `	•	No`
> L97 `	•	Yes`

The **final count is correct** (16 `kind:"question"` items = `stated` = `counted`), and the builder
acknowledges these sub-bullets elsewhere (in CONTRACEPT/HORMONE `flags.notes` and `open_questions`).
Only the reconciliation **wording** is misleading.

**Suggested fix:** reword to, e.g.:

> "16 question-level `•` bullets (L4,8,16,21,24,27,30,62,66,70,73,77,81,85,91,95) plus 4 option-level
> `•` sub-bullets (L92,93,96,97) that are CONTRACEPT/HORMONE answer options — not questions. …"

**Severity:** non-blocking; no structured field is affected.

*(No other discrepancies found.)*

---

## Judgment calls — reviewed, correctly handled (NOT defects)

These are areas where the source is irregular or underspecified. Each was handled per the
schema-breaker policy (`PLAN.md` §3 / `CONVENTIONS.md` §6) and is **correct**:

1. **SYMPTDAY options embed sub-variable IDs.** Source L9–14, e.g. `0	[SrvBio_COUGHDAY_v1r0] Cough`.
   The bracketed per-checkbox indicator IDs (`[SrvBio_COUGHDAY_v1r0]` … `[SrvBio_NOSYMPTDAY_v1r0]`) are
   preserved **verbatim** inside `option.label` (lossless, per "split on first whitespace after the code"),
   and logged in `open_questions`. The schema has no per-option variable-id field, so this is the correct
   lossless choice. **Acceptable.**

2. **Code 88 flagged `is_none` but NOT placed in `exclusive_codes`** (no `is_exclusive`). Source L14
   (`88	[SrvBio_NOSYMPTDAY_v1r0] No, I had none of these symptoms`) carries **no** explicit programmer
   "de-select all other responses" rule. The builder conservatively did not invent one and flagged it for
   SME. Aligns with "never silently fix / never invent." **Acceptable.**

3. **CONTRACEPT / HORMONE answer codes inferred 0=No, 1=Yes.** Source L92–93 / L96–97 render the options
   as code-less sub-bullets. The builder inferred codes from the module-wide yes/no pattern, set
   `flags.needs_review:true`, `schema_breaker:"answer_options_without_codes"`, and logged both in
   `open_questions`. Exactly the prescribed handling. **Acceptable (owner-bound SME questions).**

4. **`else_route` "GO TO END" modeled as the generic `END` terminal token** (not `CLOSING_REMARK`). The
   two display gates route males / non-`PREGNANT=0` respondents to `END`. This resolves cleanly via the
   validator's terminal regex. Semantically that `END` and the normal-completion `CLOSING_REMARK` (L99)
   likely denote the same "Submit Survey" screen; unifying them would be defensible, but the current
   handling is valid and validator-clean. **Low-severity note only.**

5. **Grid rows (TYLENOL/NSAIDS/ACID) have no `dependency_index` edges and sit outside the `default_next`
   chain** (`GRID_SRVBLU_MED1_V1R0.default_next → SrvBlU_REPROINTRO_v1r0`, skipping the rows). This is
   consistent with grid modeling: the grid's `display_condition` is `null` (always shown after MED), so
   the rows are unconditionally displayed and need no gating/routing edges. **Acceptable.**

6. **`response_code_legend` documents only `88`.** Sparse, but the only "special" code in the module is
   88; codes 0–4 are substantive scale/answer points. **Acceptable.**

7. **Known source contradiction is captured, not silenced.** A `PREGNANT=1` respondent routes
   PREGNANT.1 → BRSTFD, and BRSTFD.1 → CONTRACEPT, yet CONTRACEPT is gated `IF PREGNANT=0 ELSE GO TO END`.
   The builder documents this tension in `CONTRACEPT.flags.notes`. Correctly surfaced. **Acceptable.**

---

## Coverage summary (source vs serialized)

| Category | In source | Serialized | Status |
|----------|-----------|------------|--------|
| Blocks (incl. intros, divider, grid stem, grid rows, terminal) | 23 | 23 items | **Complete** |
| Answer options | SEX 0-1; SYMPTDAY 0-4,88; EATDRINKBEFORE 0-2; grid 0-4 (stem + 3 rows); yes/no 0-1 ×8; inferred 0-1 ×2 | all present | **Complete** — none invented, none missing |
| Display conditions | 2 (`[DISPLAY … IF … ELSE GO TO END]`, L58, L89) | 2 wrappers | **Complete** |
| Option routes (`à GO TO`) | 6 (L19, L63, L67, L75, L83) + 2 `ELSE GO TO END` | 6 + 2 else_routes | **Complete** |
| Terminals | submit/closing screen (L99) + recognized `END` token | CLOSING_REMARK + `END` | **Complete** |
| Loops | none | `repeated_groups: []` | **Complete** |
| Grids | 1 explicit `[GRID_SRVBLU_MED1_V1R0]` (L30) | 1 grid | **Complete** |
| `NO RESPONSE` routes | none in source | none | **Complete** |
| `RANGE CHECK` / piped refs | none in source | none | **Complete** |

No source block, option, condition, route, loop, grid, or terminal is absent from the JSON.
`dependency_index` (20 nodes, 26 edges) has no dangling routes, unknown vars, or cycles (validator clean).

---

## Count reconciliation

- `stated_question_count` = **16**
- `counted_question_count` = **16**
- Actual `kind:"question"` items = **16**

All three agree; the validator raises no count error or warning. The only issue is the *wording* of the
reconciliation prose (Discrepancy #1) — the underlying numbers are correct.

---

## VERDICT

**PASS (1 minor, non-blocking discrepancy + 3 owner-bound SME open questions).**

- The JSON faithfully and completely serializes the source; the validator is clean (0 errors, 0 warnings).
- **Discrepancy #1** (`count_reconciliation` wording) is a recommended cosmetic fix; it affects no
  structured field.
- The 3 remaining `needs_review` items (CONTRACEPT codes, HORMONE codes, SYMPTDAY 88 exclusivity) are
  explicit, owner-bound SME questions already recorded in `build_meta.open_questions` — expected, not defects.

No edits were made to `output/bio_clinical.json`.
