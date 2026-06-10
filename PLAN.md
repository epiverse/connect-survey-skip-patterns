# Plan: Machine-Readable Serialization of the Connect Survey Questionnaire & Skip Logic

## Context

The **Connect for Cancer Prevention Study** survey instrument is documented across **11 Word
(`.docx`) files** (one per module/survey) totaling **~1,350 questions**. Each file is a
*survey-programming specification*: it states each question, its answer codes, and the **skip /
branching logic** that governs which questions a participant sees. The logic is complex and
**human-authored** (irregular, occasionally malformed).

We are serializing these documents into **machine-readable JSON** — one file per module — whose
core is a set of **parsed expression trees** describing the conditional/skip logic, wrapped in rich
metadata (verbatim text, answer domains, routing, loops, grids, validation, provenance).

**Why:** two named downstream use cases (and "many other anticipated" ones):
1. **Toy data simulation** — generate random respondents with *structurally missing* (but otherwise
   complete) data, to exercise data-platform infrastructure. Requires, per question, an *evaluable*
   display predicate over other variables + answer domains + survey traversal order.
2. **Bayesian-network structure (pgmpy)** — initialize a BN's structure from the structural-missingness
   dependency graph. Requires a **DAG** of variable dependencies + discrete node state-spaces.

**Intended outcome:** A faithful, auditable, schema-validated JSON serialization per module, plus a
shared schema, conventions doc, a validator, and a cross-module variable registry. **Accuracy is
non-negotiable; no hallucinations.** The work will be executed by independent Claude Code agents —
**one *builder* + one *verifier* per module** — and this document is their complete, self-contained
brief.

### Decisions already made (by the project owner)
- **Repeated/parallel blocks** → represent as **template + enumerated instances**.
- **Ambiguous/malformed source logic** → builder records a **best-guess parsed tree WITH a confidence
  level, the verbatim raw text, a `needs_review` flag, and an interpretation note**. Nothing is
  silently "fixed."
- **Validation machinery** → a formal **JSON Schema** + a **Python validator script** + a **semantic
  verifier agent** per module.
- **Scope** → the **per-module JSON is the sole deliverable** (with a derived dependency/edge index
  baked in). The pgmpy BN and the data simulator are **downstream projects, out of scope here**.

---

## 1. Source data & how it is documented

| # | module_id | Title | File (under `data/questionnaire/`) | Stated Qs | Naming |
|---|-----------|-------|-------------------------------------|-----------|--------|
| 1 | `baseline_m1` | Background & Overall Health | `Baseline Survey - Module 1.docx` | 293 | short |
| 2 | `baseline_m2` | Medications, Reproductive Health, Exercise, Sleep | `Baseline Survey - Module 2.docx` | 194 | short |
| 3 | `baseline_m3` | Smoking, Alcohol, Sun Exposure | `Baseline Survey - Module 3.docx` | 220 | short |
| 4 | `baseline_m4` | Where You Live and Work | `Baseline Survey - Module 4.docx` | 322 | short (indexed) |
| 5 | `bio_mouthwash` | At-Home Mouthwash Sample | `Biospecimens Survey - At Home Mouthwash.docx` | 31 | `SrvMtW_…_v#r#` |
| 6 | `bio_covid19` | COVID-19 | `Biospecimens Survey - COVID19.docx` | 41 | `SrvCov_…_v#r#` |
| 7 | `bio_clinical` | Baseline Blood & Urine Sample | `Biospecimens Survey - Clinical Collection (Blood & Urine).docx` | 16 | `SrvBio_`/`SrvBlU_` |
| 8 | `bio_menstrual` | Menstrual Cycle | `Biospecimens Survey - Menstrual Cycle.docx` | 2 | `SrvBlU_…_v#r#` |
| 9 | `bio_research_appt` | Blood, Urine & Mouthwash (Research Appt) | `Biospecimens Survey - Research Appointment (Blood, Urine, Mouthwash).docx` | 47 | `SrvBio_`/`SrvBlU_`/`SrvMtW_` |
| 10 | `screening` | Cancer Screening History | `Cancer Screening History.docx` | 141 | `SrvScr_…_v#r#` |
| 11 | `qol` | Quality of Life | `Quality of Life.docx` | 40 | `SrvQoL_…_v1r0` |

### Extraction (read-only, faithful, reproducible)
`pandoc` is **not** installed; `python-docx` is **not** installed. Use macOS **`textutil`**, which
faithfully preserves question IDs, tab-separated answer codes, routing arrows, and bracketed
directives:

```bash
textutil -convert txt -stdout "data/questionnaire/<FILE>.docx"
```

**For provenance, always pipe through `cat -n`** so every claim cites a stable line number:
```bash
textutil -convert txt -stdout "data/questionnaire/<FILE>.docx" | cat -n
```
The `.docx` files are read-only inputs and do not change, so line numbers are **stable within and
across agent runs**. **Both builder and verifier must cite line numbers from this exact command.**
(Phase 0 will wrap this as `tools/extract.sh <module_id>` for consistency.)

### Document structure (consistent across files)
- **Title line**: e.g., `Module 1: Background and Overall Health`.
- **Section headers**: e.g., `Background Information [SECTION 1]`, or intro blocks `[INTROMH] … [SECTION 2]`.
- **Blocks** start with a bracketed ID: `[MARITAL]`, `[SrvScr_ANALSCREEN2_v1r0]`.
  - **Askable questions** are preceded by a bullet **`•`** (renders as `•` / `\t•\t`).
  - **Display-only** blocks (intros, summaries, end-messages) have an ID but **no bullet**.
- **Answer options**: lines of the form `<code>\t<label>`, where `<code>` ∈ {0..N, 44, 55, 77, 88, 99}.
  Options may carry an **inline route** (`… à GO TO X`) and/or an **inline display condition**
  (`… [DISPLAY IF SEX2= 5]`) and/or a free-text affordance (`[text box]`).
- **Question-level NO RESPONSE routing**: a line `NO RESPONSE à GO TO <target>`.
- **Bracketed directives** carry the programming logic: `[DISPLAY … IF …]`, `[RANGE CHECK …]`,
  `[REPEAT …]`, `[NOTE … PROGRAMMERS …]`, `[insert …]`, `[GRID_… ]`, `[EXIT AND CLEAR CACHE]`, etc.

---

## 2. Skip-logic taxonomy (confirmed across all 11 modules)

Every construct below was observed with line-referenced evidence. The JSON schema (§5) has a home
for each.

1. **Option-level routing/skip** (~2,014 `GO TO` across the corpus). An answer option routes the
   participant: `99 Prefer not to answer à GO TO LANG`. Targets include another block ID, a section
   name (`GO TO ALCOHOL SECTION`), `GO TO END`, `GO TO END MESSAGE n`, `EXIT AND CLEAR CACHE`.
2. **Question-level NO RESPONSE routing**: `NO RESPONSE à GO TO <target>` — fires when the item is
   skipped entirely (a **distinct** state from coded missing values 55/77/88/99).
3. **Block-level conditional display** — `[DISPLAY IF <expr>]`, `[DISPLAY <var(s)> IF <expr>]`,
   `[DISPLAY <var> IF <expr> ELSE, GO TO <target>]`, `[DISPLAY IF <expr>. OTHERWISE à GO TO <target>]`,
   `[IF <expr>, GO TO <t1>. ELSE GO TO <t2>]`. The boolean grammar (irregular) includes:
   - equality `VAR = 0`; value-list (implicit OR) `VAR = 1, 2, 3, OR 77`;
   - ranges `VAR = 0-6` and range+code `0-6, 55`;
   - `AND` / `OR` / `NOT`, and the compound token **`AND/OR`**;
   - parenthesized & **nested** groups; note `[...]` is *also* used for grouping in M3/M4;
   - **multi-select membership**: `0 SELECTED AT RACEETH`, `0, 1, AND/OR 2 WAS SELECTED IN CHOLHTN`,
     `at least one of the [COV6 = 1]`;
   - comparisons with system vars: `age ≥ 40` (Unicode `≥`);
   - **answered / null** tests: `X HAS A RESPONSE`, `X IS NULL`, `RESPONSE ENTERED AT X`;
   - **composite sub-field** refs: `HOMEADD1_1_SRC: CITY, STATE, ZIP, OR COUNTRY = NR` (colon) and
     `HOMEADD1_1_SRC STREET NUMBER = NR` (space);
   - **domain predicates**: `ADDRESS ENTERED IN <list>` / `NO ADDRESS ENTERED IN <list>`;
   - **meta-predicate**: `<Q> DISPLAYED TO RESPONDENT`.
4. **Option-level conditional display** — an individual option shown only if a condition holds:
   `10 Vasectomy [DISPLAY IF SEX2= 0 AND 1]`, `0 Uterine Fibroids [DISPLAY ONLY IF SEX2= 5]`.
5. **Loops / iteration** — four sub-types:
   - **(a) repeat-N-times**: `[REPEAT PREG5–PREG11 AS MANY TIMES AS THE #PREGNANCIES REPORTED IN PREG4]`
     with index piping `[insert number in loop]`, ordinal fills `first/2nd/3rd`, and per-iteration
     rules (`[IF PREG1=1, DO NOT DISPLAY PREG5 FOR THE MOST RECENT PREGNANCY, GO TO PREGSUMMARY]`).
     COVID has explicit `SET LOOP ITERATION TO 1` and a vaccination-shot loop.
   - **(b) per-selected-option**: `[THIS QUESTION IS TO BE DISPLAYED FOR EACH RESPONSE OPTION SELECTED
     AT PAINREL1]` (+ `[MED]` piping per option). Family-cancer detail (SIBCANC2/MOMCANC2/…) expands
     per selected cancer type.
   - **(c) per-entity over prior entries**: `[DISPLAY HOMEWTR1–HOMEWTR3 FOR EACH ADDRESS PROVIDED IN
     HOMEADD1–HOMEADD3]`; family-member loops repeat a block per sibling/child up to a count, with
     `[insert sibling nickname]` piping.
   - **(d) parallel copy-paste blocks** (structurally repeated, *not* a runtime loop): M3 substances
     (CIG/ECIG/CIGAR/CHEW/HOOKAH/PIPE), marijuana routes, alcohol types; M4 address slots
     (HOMEADD1..11), work slots. Each instance has distinct IDs.
6. **Grids / matrix questions**:
   - **Explicit**: COVID `[GRID_SRVCOV_COV19A_V1R0]` (row item IDs + shared response scale);
     Clinical `[GRID_SRVBLU_MED1_V1R0]` (medication rows × temporal scale).
   - **Implicit**: QoL — 10 PROMIS-style domains, each = intro + 4–5 item IDs sharing a response
     scale, grouped by `[NOTE: DISPLAY … ON SAME SCREEN]`, **no GRID id**. Scales sometimes **reverse-
     ordered** (4→0) and some use `44 = Never`.
   - **Computed-row grids**: M3 lifetime substance grids (CIGLIFEA–H …) whose rows are age ranges
     with bounds computed from prior answers.
7. **Piping / display dependencies** (not skips, but data dependencies — relevant to the BN):
   `[insert <var>]`, conditional fills `[IF X=1, fill "smoked"]`, arithmetic
   `[insert number calculated from CURRENT YEAR – 20]`, fallback
   `[FILL RESPONSE FROM X. IF NO TEXT…, FILL "another type of cancer"]`, and **cross-survey** piping
   `[insert SrvBlU_MENSTART_v2r0]`.
8. **Validation / range checks**: `[RANGE CHECK: min=, max=]` — constants; system vars (`age`, `yob`,
   `Current Year`); **conditional/dependent** (`min= CIG2 IF CIG2 HAS A RESPONSE, or min=0 if NULL`);
   **relative dates** (`min=(Today date – 60 days)`); **prior-response-dependent**
   (`max= COV13 response or 180 if null`); **version-specific** (`min=0 (min=1 IN VERSIONS 1.0–1.4)`).
   Plus required-response notes.
9. **Programmer notes**: `[PROGRAMMING NOTE …]`, `[NOTE TO/FOR PROGRAMMERS …]` — some are purely
   advisory; **some carry logic** (e.g., "IF 88 IS SELECTED, DE-SELECT ALL OTHER RESPONSES";
   iteration scope; adaptive field presentation). Capture verbatim; extract logic where present.
10. **Terminal nodes**: `GO TO END`, `END OF MODULE`, `END MESSAGE n` (often **conditionally gated**
    by a `[DISPLAY IF …]`), `[EXIT AND CLEAR CACHE]`.

### Response-code conventions (recurring — but **verify per question**, do not assume)
| Code | Typical meaning | Notes |
|------|-----------------|-------|
| `0..N` | substantive answers | ordinal or nominal |
| `44` | "Never" (context-specific) | "never had period", "never on a regular basis", QoL "Never" |
| `55` | "None of these / Other" | usually `+ please describe [text box]` |
| `77` | "Don't know" | |
| `88` | "None of the above / I have not had any of these" | multi-select-exclusive; often routes onward; screening "de-select all others" rule |
| `99` | "Prefer not to answer" | |
| `NR` / `NO RESPONSE` | item skipped — **distinct structural-missing state** | has own routing; in M4 also tracked at sub-field level |

QoL codes are **scale points**, sometimes reverse-ordered, sometimes including `44=Never`; scoring
direction varies per domain/item. **Always capture options verbatim; codes are the source of truth.**

---

## 3. Catalog of known schema-breakers (handle, never silently fix)

These are real source irregularities. Policy (per owner decision): **record best-guess `parsed` +
`confidence` + verbatim `raw` + `needs_review: true` + `interpretation_note`.** All are aggregated
into the module's `build_meta.open_questions` and the Phase-3 SME review list.

| Module | Line(s) | Issue | Guidance |
|--------|---------|-------|----------|
| `baseline_m1` | 1177 | `(SEX= 1) AND ((age ≥ 40)]` unbalanced parens | infer `and[eq SEX 1, gte age 40]`, low conf |
| `baseline_m1` | 751 | `(SEX2=0 AND 1)` literal "AND 1" | best guess `in SEX2 [0,1]`, low conf, note |
| `baseline_m1` | 1983 | `MULT2 AND SIBCANC2 DISPLAYED TO RESPONDENT` | `and[<MULT2 truthy>, displayed SIBCANC2]`; flag `MULT2` bare-var |
| `baseline_m2` | 3, 71 | unbalanced parens; mixed `or`/`OR` | infer grouping, low conf |
| `baseline_m2` | 362 | imperative prose `DO NOT DISPLAY … FOR THE MOST RECENT PREGNANCY` | store as `per_iteration_rule`, raw + parsed-if-possible |
| `baseline_m3` | 339 | missing closing `]` (CIGAR conditional) | infer close, low conf |
| `baseline_m3` | 896, 1370 | missing `=` (`SMMAR3_SRC 44`) | infer `eq …_SRC 44`, low conf |
| `baseline_m3` | 81, 120… | nested AND/OR + implicit list `[CIG4= 2,1,OR 0]` | parse to `in`, document precedence assumption |
| `baseline_m4` | 2704 | unclosed `[` in pandemic-work condition | infer close, low conf |
| `baseline_m4` | 3047 | mismatched `(`…`]` | normalize grouping, low conf, note |
| `baseline_m4` | 2759 | ungrouped `A AND B OR C` | assume AND binds tighter → `(A∧B)∨C`, note assumption |
| `baseline_m4` | 17 vs 27 | inconsistent sub-field notation (colon vs space) | both → `subfield_*` ops |
| `baseline_m4` | 27 | cross-slot ref (`HOMEADD3_1` depends on `HOMEADD2_2`) | capture as-is, flag possible doc error |
| `bio_menstrual` | 12 vs 22 | **version drift**: question `SrvBlU_MENS2_v2r0` referenced as `…_v1r0` | resolve to defined ID, record `resolved_from`, flag |
| `bio_menstrual` | 15 | relative-date range `(Today – 60 days)` | structured relative-date range, `needs_review` |
| `bio_research_appt` | 19 | typo `à TO` (missing `GO`) | treat as route arrow, note typo |
| `screening` | 33–40 | option-level `[DISPLAY IF …]` inside options | option-level `display_condition` |
| `screening` | 355, 1047 | programmer note: "IF 88 → de-select all" | capture as multi-select exclusivity rule |
| `bio_covid19` | 100, 112… | range `max = COV13 response or 180 if null` | dependent range, structured + raw |

**Question-count discrepancies (expected, not failures):** bullet counts differ from the stated
totals (e.g., builder agents counted **294** vs. stated 293 for M1, and **353** vs. stated 322 for
M4). Stated totals likely count *distinct data variables* and exclude display-only blocks / composite
`_SRC` sub-fields / copy-paste follow-up forms. Record **both** `stated_question_count` and
`counted_question_count`, explain the delta in `count_reconciliation`, and flag large gaps for review.

---

## 4. External / system variables (cross-cutting)

Some conditions/pipes reference variables **not defined in the module**. Capture them as leaves with
`var_kind: "system" | "external"` and (for external) `source_module`. Seed registry:

- **System** (platform-provided, derived from enrollment/runtime): `age`, `yob` (year of birth),
  `Current Year`, `Today date`, `participant name`.
- **External / cross-survey**: `SrvBlU_MENSTART_v2r0` (defined in `bio_clinical`, piped by
  `bio_menstrual`). The composed surveys (`bio_research_appt`, `bio_clinical`) reuse `SrvBio_`/
  `SrvBlU_`/`SrvMtW_` blocks; treat each block by its own ID and let the Phase-3 registry resolve
  shared IDs across files.

---

## 5. Target JSON serialization — schema

### 5.1 Repository layout & artifacts
```
data/questionnaire/*.docx              # read-only inputs (exist)
schema/connect_survey.schema.json      # JSON Schema (Draft 2020-12) for a module file  [Phase 0]
docs/CONVENTIONS.md                    # taxonomy + grammar + code legend + breaker catalog  [Phase 0]
tools/extract.sh                       # wraps `textutil … | cat -n` per module_id           [Phase 0]
tools/validate.py                      # structural + referential validator                  [Phase 0]
registry/variable_index.json           # cross-module variable registry (built in Phase 3)
output/<module_id>.json                # the serialization (one per module)        [Phase 1]
output/<module_id>.verify.md           # verifier report (one per module)          [Phase 2]
output/_integration_report.md          # cross-module reconciliation               [Phase 3]
```
One JSON file per module. All files validate against the single shared schema.

### 5.2 Module-level object
```json
{
  "schema_version": "1.0.0",
  "module": {
    "id": "baseline_m1",
    "title": "Module 1: Background and Overall Health",
    "survey_family": "baseline",
    "source_file": "data/questionnaire/Baseline Survey - Module 1.docx",
    "naming_convention": "short_uppercase",      // or "srv_versioned"
    "id_prefixes": [],                            // e.g. ["SrvScr_"] or ["SrvBio_","SrvBlU_","SrvMtW_"]
    "stated_question_count": 293,
    "counted_question_count": 294,
    "count_reconciliation": "294 bullet-marked questions; stated 293. Delta +1 = [explain]. [REVIEW]",
    "response_code_legend": { "55": "…", "77": "Don't know", "88": "…", "99": "Prefer not to answer",
                               "NR": "No response (item skipped); structural missing" },
    "sections": [ { "id": "SECTION1", "title": "Background Information", "order": 1,
                     "item_id_first": "MARITAL", "item_id_last": "LANG" } ],
    "external_variables": [ { "name": "age", "var_kind": "system", "description": "current age" } ]
  },
  "items": [ /* §5.3 — ordered by survey appearance */ ],
  "repeated_groups": [ /* §5.5 */ ],
  "grids": [ /* §5.6 */ ],
  "dependency_index": { /* §5.9 — DERIVED by tools/validate.py, not hand-authored */ },
  "build_meta": {
    "built_by": "agent",
    "extraction_cmd": "textutil -convert txt -stdout '<file>' | cat -n",
    "open_questions": [ { "item_id": "…", "line": 1177, "issue": "…", "confidence": "low" } ]
  }
}
```

### 5.3 Item object
```json
{
  "id": "RACEETH",                       // VERBATIM, including any _v#r# suffix
  "kind": "question",                    // question|display_text|section_header|terminal|loop_control|grid_row
  "section": "SECTION1",
  "order_index": 12,                     // 0-based position in survey order
  "bullet": true,                        // was it marked with •
  "text": "Which of these describes you? Select all that apply…",   // VERBATIM (trim trailing ws)
  "piped_refs": [ { "var": "participant name", "var_kind": "system", "raw": "[insert participant name]" } ],
  "requires_response": false,
  "response": {
    "type": "multi_select",              // single_select|multi_select|integer|decimal|date|time|text|composite|scale
    "select_all": true,                  // "select all that apply"
    "exclusive_codes": [],               // codes that de-select others (e.g. 88) — incl. programmer-note rules
    "options": [
      { "code": "0", "label": "American Indian or Alaska Native", "flags": [], "display_condition": null, "route": null },
      { "code": "55", "label": "None of these: please describe", "flags": ["is_other","has_textbox"], "route": null },
      { "code": "99", "label": "Prefer not to answer", "flags": ["is_refused"],
        "route": { "target": "LANG", "kind": "goto", "raw": "99 … à GO TO LANG" } }
    ],
    "composite_fields": null,            // §5.7
    "range_check": null,                 // §5.8
    "scale": null                        // {"reverse_scored": true|false|"uncertain","note":"…"} for QoL-type items
  },
  "display_condition": null,             // §5.4 wrapper, or null if always shown
  "routing": {
    "default_next": "RACEETH2",          // fall-through in source order (null if terminal)
    "no_response_route": { "target": "LANG", "raw": "NO RESPONSE à GO TO LANG" },
    "terminal": null                     // {"type":"end_module|end_message|exit","id":"1","message":"…","exit_behavior":"clear_cache"}
  },
  "membership": { "repeated_group": null, "grid": null, "iteration_role": null },
  "provenance": { "file": "Baseline Survey - Module 1.docx", "line_start": 31, "line_end": 44,
                   "raw_excerpt": "[RACEETH] Which of these…\\n0\\tAmerican Indian…" },
  "flags": { "needs_review": false, "schema_breaker": null, "notes": [] }
}
```
**Flag vocabulary** (`option.flags` / item): `is_other`, `is_dontknow`, `is_refused`, `is_none`,
`is_never`, `has_textbox`, `is_exclusive`.

### 5.4 Canonical expression-tree grammar (the heart)
Every `display_condition` (block- and option-level) and every parsed `per_iteration_rule` uses this
**wrapper**:
```json
{
  "raw": "[DISPLAY RACEETH2 IF 0 SELECTED AT RACEETH]",     // VERBATIM directive
  "parsed": { /* node, below */ },                           // best-effort canonical tree
  "confidence": "high",                                      // high|medium|low
  "needs_review": false,
  "interpretation_note": null,                               // required (non-null) whenever confidence != high
  "else_route": null                                         // for "… ELSE, GO TO X" / "OTHERWISE à GO TO X"
}
```
**Node types** (recursive):
- Logical: `{"op":"and","args":[…]}` · `{"op":"or","args":[…]}` · `{"op":"not","args":[node]}`
- Comparison: `{"op":"eq|ne|lt|lte|gt|gte","var":"SEX","value":1}` — `value` may be a number or the
  token `"NR"`. Add `"var_kind"` and (composite) `"field"`.
- **Set membership** (single-select equals one of; covers value-lists and ranges):
  `{"op":"in","var":"X","values":[1,2,77],"raw_value_spec":"1, 2, OR 77"}`.
  Ranges are **expanded** with the spec preserved: `0-6,55` →
  `{"op":"in","var":"X","values":[0,1,2,3,4,5,6,55],"raw_value_spec":"0-6, 55"}`.
- **Multi-select membership**: `{"op":"selected","var":"CHOLHTN","values":[0,1,2],"quantifier":"any","raw_value_spec":"0, 1, AND/OR 2"}` (quantifier `any`|`all`). Covers `SELECTED AT` / `WAS SELECTED IN` / `at least one of …`.
- **Answered/null/entered**: `{"op":"answered","var":"X"}` · `{"op":"is_null","var":"X"}` · `{"op":"response_entered","var":"X"}`
- **Composite sub-field**: single → `{"op":"eq","var":"HOMEADD1_1_SRC","field":"CITY","value":"NR"}`;
  quantified-over-fields → `{"op":"subfield_any","var":"HOMEADD1_1_SRC","fields":["CITY","STATE","ZIP","COUNTRY"],"predicate":{"op":"eq","value":"NR"}}` (also `subfield_all`).
- **Domain predicates**: `{"op":"address_entered","vars":["CURWORKPOSTPAN1_SRC","CURWORKPOSTPAN2_SRC","CURWORKPOSTPAN3_SRC"],"quantifier":"any","negated":false}` · `{"op":"displayed","var":"SIBCANC2"}`
- **System/external leaf**: any `var` leaf may carry `"var_kind":"question"|"derived"|"system"|"external"`; external adds `"source_module"`. Derived example: M3 `CIG3_AGE` is the numeric value of `CIG3_SRC` → `"var":"CIG3_AGE","var_kind":"derived","derived_from":"CIG3_SRC"`.
- **Raw escape hatch** (only if even a best guess is impossible): `{"op":"raw","text":"<verbatim>"}` with wrapper `confidence:"low"`, `needs_review:true`. Prefer a structured best-guess over this.

**Worked raw → tree examples** (builders should mirror these):
| Raw directive | `parsed` |
|---|---|
| `[DISPLAY IF MHGROUP1= 0]` | `{"op":"eq","var":"MHGROUP1","value":0}` |
| `[… IF 0 SELECTED AT RACEETH]` | `{"op":"selected","var":"RACEETH","values":[0],"quantifier":"any"}` |
| `[… = 1, 2, 3, 4, OR 77]` | `{"op":"in","var":"X","values":[1,2,3,4,77],"raw_value_spec":"1, 2, 3, 4, OR 77"}` |
| `[… CURWORKPOSTPANT1= 0-6, 55]` | `{"op":"in","var":"CURWORKPOSTPANT1","values":[0,1,2,3,4,5,6,55],"raw_value_spec":"0-6, 55"}` |
| `[… (SEX= 0) AND (age ≥ 40)]` | `{"op":"and","args":[{"op":"eq","var":"SEX","value":0},{"op":"gte","var":"age","var_kind":"system","value":40}]}` |
| `[… 0, 1, AND/OR 2 WAS SELECTED IN CHOLHTN]` | `{"op":"selected","var":"CHOLHTN","values":[0,1,2],"quantifier":"any"}` |
| `[… (HOMEADD1_1_SRC: CITY, STATE, ZIP, OR COUNTRY= NR)]` | `{"op":"subfield_any","var":"HOMEADD1_1_SRC","fields":["CITY","STATE","ZIP","COUNTRY"],"predicate":{"op":"eq","value":"NR"}}` |
| `[… (PREPANDIFF=1) AND (ADDRESS ENTERED IN A,B,OR C)]` | `{"op":"and","args":[{"op":"eq","var":"PREPANDIFF","value":1},{"op":"address_entered","vars":["A","B","C"],"quantifier":"any"}]}` |
| `[… (SEX= 1) AND ((age ≥ 40)]` *(malformed)* | best-guess `and[…]`, `confidence:"low"`, note: "unbalanced parens; inferred one closing paren" |
| `bio_menstrual` L22 ref to `…MENS2_v1r0` while Q is `…_v2r0` | leaf `{"op":"response_entered","var":"SrvBlU_MENS2_v2r0","resolved_from":"SrvBlU_MENS2_v1r0"}`, `needs_review:true` |

### 5.5 Repeated groups (template + instances)
```json
{
  "group_id": "loop_pregnancy",
  "type": "repeat_n",                 // repeat_n | per_selected_option | per_entity | parallel_block
  "label": "Pregnancy history loop",
  "controller": { "count_source": "PREG3", "var_kind": "question",
                   "raw": "[REPEAT PREG5–PREG11 AS MANY TIMES AS THE #PREGNANCIES REPORTED IN PREG4]" },
  "domain_source": null,              // for per_selected_option: the multi-select var; for per_entity: the entry-set var range
  "index_pipe_token": "[insert number in loop]",
  "ordinal_fill": "first/2nd/3rd/…",
  "template_item_ids": ["PREG5","PREG6","PREG7","PREG8","PREG9","PREG10","PREG11"],
  "per_iteration_rules": [ { "raw": "[IF PREG1=1, DO NOT DISPLAY PREG5 FOR THE MOST RECENT PREGNANCY…]",
                              "parsed": null, "confidence": "medium", "needs_review": true,
                              "interpretation_note": "Skip PREG5 on the final iteration when PREG1=1." } ],
  "summary_item": "PREGSUMMARY",
  "instances": null,                  // repeat_n/per_*: dynamic → null. parallel_block: enumerate (below)
  "provenance": { "file": "…", "line_start": 409, "line_end": 413 }
}
```
**Parallel-block** form (M3 substances, M4 address slots) — enumerate instances:
```json
{
  "group_id": "tobacco_substances", "type": "parallel_block",
  "template_item_ids": ["<PREFIX>1","<PREFIX>2","<PREFIX>3_SRC","…","<PREFIX>LIFEA..H"],
  "instances": [
    { "key": "CIG",  "gate": { "raw": "[DISPLAY IF TOBACCO= 0…]", "parsed": {"op":"selected","var":"TOBACCO","values":[0],"quantifier":"any"}, "confidence":"high" },
      "item_ids": ["CIG1","CIG2","CIG3_SRC", "…"] },
    { "key": "ECIG", "gate": { "raw": "[DISPLAY IF TOBACCO= 1…]", "parsed": {"op":"selected","var":"TOBACCO","values":[1],"quantifier":"any"}, "confidence":"high" },
      "item_ids": ["ECIG1","ECIG2","ECIG3_SRC","…"] }
  ]
}
```
Each member item also sets `membership.repeated_group = group_id` and (for parallel blocks)
`membership.iteration_role = "<key>"`.

### 5.6 Grids
```json
{
  "grid_id": "GRID_SRVCOV_COV19A_V1R0",  // explicit if present; else synthesized e.g. "qol_physfnct"
  "explicit_id": true,
  "stem": "Since your COVID-19 diagnosis, have you experienced …?",   // VERBATIM
  "shared_scale": [ { "code": "1", "label": "Yes, I have this now" },
                     { "code": "2", "label": "Yes, in the past but not now" },
                     { "code": "0", "label": "No, never" } ],
  "row_item_ids": ["SrvCov_COV19A1_v1r0","SrvCov_COV19A2_v1r0"],
  "same_screen": true,
  "display_condition": null,             // §5.4 wrapper or null
  "provenance": { "file": "…", "line_start": 151, "line_end": 229 }
}
```
Each grid row is **also** a full item (with `membership.grid = grid_id`). If a row overrides the
shared scale (QoL reverse-scoring), put the row's actual options on the **item** and set
`item.response.scale`. For QoL (no explicit grid IDs), synthesize `grid_id` per domain and record
`explicit_id: false`.

### 5.7 Composite `_SRC` fields
For multi-part fields (M4 addresses; some Srv `_SRC`), set `response.type = "composite"` and:
```json
"composite_fields": [
  { "name": "STREET_NUMBER", "type": "integer", "label": "Street number" },
  { "name": "STREET_NAME", "type": "text" }, { "name": "CITY", "type": "text" },
  { "name": "STATE", "type": "text" }, { "name": "ZIP", "type": "text" }, { "name": "COUNTRY", "type": "text" }
]
```
Sub-fields are addressable in expressions via the `"field"` key (§5.4). **Note:** in M3, `_SRC` is a
*single* age field (not composite) — `response.type = "integer"`; do **not** force composite there.

### 5.8 Validation / range checks
```json
"range_check": {
  "raw": "[RANGE CHECK: min= 0, max= age]",
  "min": { "kind": "const", "value": 0 },
  "max": { "kind": "system_var", "var": "age" },
  "needs_review": false
}
```
Bound `kind` ∈ `const` | `var` | `system_var` | `relative_date` | `conditional`.
- relative: `{"kind":"relative_date","expr":"today - 60d","raw":"(Today date – 60 days)"}`
- conditional: `{"kind":"conditional","cases":[{"when":{"op":"answered","var":"CIG2"},"value":{"kind":"var","var":"CIG2"}}],"default":{"kind":"const","value":0}}`
Set `needs_review:true` for relative/dependent/version-specific checks.

### 5.9 Dependency index (DERIVED — bridge to BN & simulation)
**Generated by `tools/validate.py`**, not hand-authored. For each variable, list parents/children
with edge type, so downstream tools get a ready DAG:
```json
"dependency_index": {
  "RACEETH2": { "parents": [ { "var": "RACEETH", "edge_type": "display" } ], "children": [] },
  "PREG4":    { "parents": [ { "var": "PREG3",   "edge_type": "route"   } ],
                 "children": [ { "var": "PREG5", "edge_type": "display" } ] }
}
```
`edge_type` ∈ `display` (from display_condition vars) | `route` (option/NR routing targets &
sources) | `pipe` (piped_refs) | `loop` (controller/domain sources) | `grid`. The validator must also
**report cycles** (BN needs a DAG; genuine cycles → flag for review, do not auto-break).

---

## 6. Phased execution plan

### Phase 0 — Foundation (run **once**, before any module)
Produce the shared assets so every module is built against the same contract:
1. `schema/connect_survey.schema.json` — encode §5 as JSON Schema (Draft 2020-12). Enumerate node
   `op`s; require the §5.4 wrapper fields; require `provenance` on every item; allow `parsed:null`
   only when `wrapper.op=="raw"` or for prose `per_iteration_rules`.
2. `docs/CONVENTIONS.md` — distill §§2–4 (taxonomy, code legend, grammar, breaker catalog) as the
   builder/verifier quick-reference.
3. `tools/extract.sh <module_id>` — map module_id → file, run `textutil … | cat -n`.
4. `tools/validate.py` — §9 spec (structural + referential checks; **emits** `dependency_index`;
   reports cycles, dangling routes, unknown vars, count deltas).
5. `registry/variable_index.json` — start empty `{}`; populated in Phase 3.
**Validate Phase 0** on the pilot module before scaling.

### Phase 1 — Per-module build (one **builder** agent per module)
Builder reads the `.docx` via `tools/extract.sh`, produces `output/<module_id>.json` strictly to the
schema, citing provenance for **every** item, and self-runs `tools/validate.py` until structurally
clean. Uses the §7 prompt. Records every irregularity in `build_meta.open_questions`.

### Phase 2 — Per-module verify (one **verifier** agent per module)
Independent verifier (must **not** trust the builder's JSON): re-extracts the source, and for **every
item** checks ID, text, options/codes/flags, routes, display conditions (does `parsed` faithfully
encode `raw`?), loops, grids, composite fields, range checks, and provenance line accuracy. Runs
`tools/validate.py`. Writes `output/<module_id>.verify.md` with per-item PASS/FAIL, a discrepancy
list, count reconciliation, and a verdict. Uses the §8 prompt. **Builder fixes; re-verify until the
report is clean** (or remaining items are explicit, owner-bound `needs_review` SME questions).

### Phase 3 — Cross-module integration & reconciliation (once, after all modules pass)
1. Build `registry/variable_index.json`: every variable ID → defining module + item, with aliases for
   version-drift (`resolved_from`) and shared composed-survey blocks.
2. Resolve `external`/cross-survey references (e.g., `SrvBlU_MENSTART_v2r0`) against the registry;
   anything unresolved → `system` or genuinely missing (flag).
3. Run a **global** validation pass; merge all `open_questions` into `output/_integration_report.md`
   as the **SME review queue** (grouped by confidence).
4. Reconcile `counted` vs `stated` question counts corpus-wide; document deltas.

### Module sequencing (pilot-first — de-risk the schema)
1. **Pilot: `bio_menstrual` (2 Qs)** — tiny but exercises external pipe, version drift, relative-date
   range, and conditionally-gated END messages. Shake out schema + tooling here.
2. **`bio_clinical` (16)** + **`qol` (40)** — explicit grid + composite-ish; implicit grids +
   reverse-scored scales. Validates §5.6/§5.7.
3. **`bio_mouthwash` (31)**, **`bio_covid19` (41)** — ELSE-routing, explicit grids, COVID loops.
4. **`bio_research_appt` (47)**, **`screening` (141)** — composed/mixed prefixes; option-level
   display; long value-lists.
5. **Baseline `m2` (194)**, **`m1` (293)**, **`m3` (220)**, **`m4` (322)** — the loop/parallel-block/
   nested-condition heavyweights. Do `m4` **last** (most schema-breakers).

Each module = build → validate → verify → fix → re-verify. Independent modules may run in parallel,
but **after** the pilot has locked the schema.

---

## 7. Builder agent — ready-to-use prompt

> You are serializing **one module** of the Connect study survey into machine-readable JSON.
> **Accuracy is paramount; never hallucinate. Every item must cite source line numbers.**
>
> **Inputs/contract (read first):** `docs/CONVENTIONS.md` (taxonomy, code legend, grammar, known
> schema-breakers) and `schema/connect_survey.schema.json` (the exact output contract). Your output
> MUST validate against that schema.
>
> **Module:** `<module_id>` → `data/questionnaire/<FILE>.docx`. Stated question count: `<N>`.
>
> **Extract (read-only):** `bash tools/extract.sh <module_id>` (= `textutil -convert txt -stdout
> '<FILE>' | cat -n`). Cite these line numbers in every `provenance`. Read the **entire** file
> top-to-bottom before emitting JSON.
>
> **Produce** `output/<module_id>.json` per the schema:
> 1. Module header: ids, naming convention, sections, response-code legend, external variables,
>    `stated_question_count`, `counted_question_count` (count `•` bullets), `count_reconciliation`.
> 2. One ordered `item` per block (questions, display text, section headers, terminals). Capture
>    **verbatim** text; all options with codes, labels, flags, per-option routes & display conditions;
>    `range_check`; `requires_response`; `piped_refs`; full `provenance` with `raw_excerpt`.
> 3. Parse every display condition / option condition / per-iteration rule into the **§5.4 wrapper**:
>    `raw` (verbatim) + `parsed` (canonical tree, §5.4 grammar) + `confidence` + `needs_review` +
>    `interpretation_note` (required when confidence≠high) + `else_route`.
> 4. **Repeated/parallel blocks** → `repeated_groups` as **template + instances** (§5.5); set each
>    member's `membership`.
> 5. **Grids** → `grids` (§5.6); each row is also an item; capture per-row scale overrides
>    (incl. reverse-scoring) on the item.
> 6. **Composite `_SRC`** → `response.type:"composite"` + `composite_fields` (§5.7). (M3 `_SRC` = a
>    single age field, NOT composite.)
> 7. Leave `dependency_index` `{}` (the validator fills it).
>
> **Schema-breaker policy (firm):** for unbalanced/malformed/ambiguous source (see CONVENTIONS
> catalog), record a **best-guess `parsed` + low/medium `confidence` + verbatim `raw` +
> `needs_review:true` + an `interpretation_note` explaining the assumption.** Do **not** silently
> correct the source. Add an entry to `build_meta.open_questions`.
>
> **Environment:** use the project venv — `source .venv/bin/activate`, or call tools via
> `.venv/bin/python` (the validator needs `jsonschema` installed there).
>
> **Self-check before finishing:** run `.venv/bin/python tools/validate.py output/<module_id>.json` and fix
> all structural/referential errors. Confirm every item has provenance; every non-high-confidence
> condition has a note; counts are reconciled. Report a summary: items emitted, conditions parsed,
> `needs_review` count, count delta, and any places you were genuinely unsure (quote them).

## 8. Verifier agent — ready-to-use prompt

> You are the **independent verifier** for `output/<module_id>.json`. **Assume nothing in it is
> correct.** Re-derive the truth from the source and compare. Goal: catch every inaccuracy,
> omission, or mis-parse. Do **not** edit the JSON — produce a report; the builder fixes.
>
> **Read** `docs/CONVENTIONS.md` and `schema/connect_survey.schema.json`. **Re-extract** the source
> yourself: `bash tools/extract.sh <module_id>`. Use the project venv (`source .venv/bin/activate`, or
> call `.venv/bin/python`).
>
> **Run** `.venv/bin/python tools/validate.py output/<module_id>.json` and record results.
>
> **For EVERY item** in the JSON, verify against the source line(s) it cites (and confirm those line
> numbers are correct):
> - ID matches the bracketed token exactly (incl. `_v#r#`); `kind`/`bullet`/`section`/order correct.
> - `text` is verbatim (flag paraphrase/truncation).
> - Options: every code, label, flag, per-option route, and per-option display condition present and
>   correct; none invented, none missing; `exclusive_codes` (e.g. 88 de-select rules) captured.
> - `display_condition.parsed` **faithfully and completely** encodes `raw` (no dropped/added
>   conjuncts; correct op; correct values incl. expanded ranges; `selected` vs `eq` correct;
>   composite/`subfield_*` correct; system/external/derived `var_kind` correct). For every malformed/
>   ambiguous source, confirm `needs_review:true` + a sensible `interpretation_note`.
> - `routing` (default_next, no_response_route, terminal incl. conditional END messages) correct.
> - Loops/parallel blocks: template + instances complete; controllers/domain sources correct.
> - Grids: stem, shared scale, row IDs, per-row overrides correct.
> - `range_check` and `piped_refs` correct.
> **Also** scan the source for any block, option, condition, route, loop, grid, or terminal that is
> **absent** from the JSON (coverage check). Reconcile `counted` vs `stated` counts; investigate
> large deltas. Confirm `dependency_index` has no unexpected dangling routes / unknown vars / cycles.
>
> **Output** `output/<module_id>.verify.md`: per-item PASS/FAIL table; a numbered discrepancy list
> (each with source line + JSON path + what's wrong + suggested fix); a coverage summary
> (blocks/options/conditions in source vs serialized); count reconciliation; the validator result;
> and a final **VERDICT: PASS / FAIL (n issues)**. Quote the source verbatim for every flagged issue.

## 9. Validator tool (`tools/validate.py`) — spec
Python in the project `.venv` (stdlib + `jsonschema`; `graphlib` for cycle detection). CLI:
`.venv/bin/python tools/validate.py output/<module_id>.json [--registry registry/variable_index.json] [--emit-deps]`.
Checks:
1. **Schema** conformance to `schema/connect_survey.schema.json`.
2. **ID uniqueness** within the module; ID format matches `naming_convention`.
3. **Route resolution**: every route `target` resolves to an item ID, a section, or a recognized
   terminal (`END`, `END MESSAGE n`, `EXIT…`); unresolved → error (within-module) or `external` note
   (cross-module, when `--registry` given).
4. **Expression var resolution**: every leaf `var` is a known item ID, a declared `external_variable`,
   or `var_kind ∈ {system,derived}`; else error.
5. **Wrapper integrity**: `confidence≠high` ⇒ non-null `interpretation_note`; `op:"raw"` ⇒
   `needs_review:true`.
6. **Counts**: recompute bullet count; compare to `stated`/`counted`; warn on delta.
7. **Emit `dependency_index`** (display/route/pipe/loop/grid edges) and **detect cycles**; write back
   with `--emit-deps`, and always report cycles/dangling refs.
Exit non-zero on any error; warnings are non-fatal but listed.

---

## 10. Verification / acceptance (how we know it's right)
- **Per module:** `tools/validate.py` exits clean **and** `output/<module_id>.verify.md` says **PASS**
  (remaining open items only the explicit, owner-bound `needs_review` SME questions).
- **Pilot gate:** `bio_menstrual` fully built+verified before scaling; schema/tooling frozen after.
- **Corpus gate (Phase 3):** global validation clean; `_integration_report.md` lists the full SME
  review queue; all cross-survey references resolved or explicitly flagged.
- **Round-trip smoke test (optional, recommended):** a throwaway script that walks one module's items
  in `order_index`, samples answers from `response` domains, and evaluates each `display_condition`
  to mark unshown items missing — confirms the parsed logic is actually *executable* (validates the
  simulation use case without building the simulator). If any condition can't be evaluated, that's a
  parse/grammar gap to fix.
- **Spot audit:** owner reviews a random sample of items per module against the `.docx`.

---

## 11. Per-module appendix (quirks to brief each agent on)
- **`baseline_m1`** — race/ethnicity cascade (RACEETH→RACEETH2..8, each gated by a `selected`);
  family-cancer **repeat-N loops** (siblings via `SIB1`, children via `CHILD1`) with **per-selected-
  option** sub-iteration (SIBCANC2→SIBCANC3A..Y per cancer type); `88`="none"; option-level
  `[DISPLAY ONLY IF SEX2=…]`; breakers L751, L1177, L1983; counted ≈294 vs 293.
- **`baseline_m2`** — section-wide reproductive gate `(SEX=0) OR (SEX2=5,6)`; **pregnancy repeat-N**
  loop (PREG3→PREG5–PREG11) + per-iteration skip prose (L362); **per-selected-option** medication
  iterations (PAINREL/CHOLHTN/HORMED/FERT6) with `[MED]` piping; `44`="never"; breakers L3, L71.
- **`baseline_m3`** — **parallel substance blocks** (CIG/ECIG/CIGAR/CHEW/HOOKAH/PIPE), marijuana
  routes, alcohol types (→ `parallel_block` groups); **computed-row age grids** (CIGLIFEA–H …);
  conditional verb-tense fills; derived `*_AGE` vars; `44`="never on a regular basis"; layered
  conditional RANGE CHECKs; breakers L339, L896/L1370.
- **`baseline_m4`** — **composite `_SRC` addresses** (STREET_NUMBER/NAME/CITY/STATE/ZIP/COUNTRY);
  **per-entity loops** (`FOR EACH ADDRESS PROVIDED IN HOMEADD1–3`); address slots HOMEADD1..11,
  SEASADD1..10 (→ `parallel_block`); the tangled **pre/post-pandemic work** decision tree
  (WORK2019 × WORK2019POSTPAN, SAMEJOBPREPAN, PREPANDIFF…); `subfield_*` + `address_entered`
  predicates; arithmetic pipes; many breakers (L17/27 notation, L2704, L2759, L3047); counted ≈353
  vs 322 — **investigate & document the delta**.
- **`bio_mouthwash`** — `SrvMtW_`; ELSE-routing `[DISPLAY … ELSE, GO TO …]`; conditional END message
  + `[EXIT AND CLEAR CACHE]`; `44`="never".
- **`bio_covid19`** — `SrvCov_` (mixed `_v1r0.._v3r0`); **explicit grids** `[GRID_SRVCOV_…]`;
  **two loops** (COVID instances `SET LOOP ITERATION TO 1`; vaccination shots) with ordinal piping;
  long multi-var OR conditions; dependent/relative range checks (L100…, L476).
- **`bio_clinical`** — mixed `SrvBio_`/`SrvBlU_` (module reuse); **explicit medication grid**
  `[GRID_SRVBLU_MED1_V1R0]` (rows × 5-pt temporal scale); reproductive section gated by sex →
  `ELSE GO TO END`; defines `SrvBlU_MENSTART_v2r0` (consumed by `bio_menstrual`).
- **`bio_menstrual` (PILOT)** — `SrvBlU_`; **external pipe** `[insert SrvBlU_MENSTART_v2r0]`;
  **version drift** (Q `…MENS2_v2r0` referenced as `…_v1r0`); **relative-date** range
  `(Today – 60 days)`; **two conditionally-gated END messages**.
- **`bio_research_appt`** — composed: `SrvBio_`+`SrvBlU_`+`SrvMtW_` (reuses clinical + mouthwash);
  ELSE-routes jump across module boundaries; typo `à TO` (L19, missing `GO`).
- **`screening`** — `SrvScr_`; deep per-cancer screening cascades (oral/colorectal/cervical/breast/
  prostate/anal/endometrial); **option-level `[DISPLAY IF …]` inside option lists** (L33–40);
  long value-lists `=1,2,3,4,OR 77`; `88` de-select-all programmer rule (L355, L1047); `age`/`yob`
  range checks.
- **`qol`** — `SrvQoL_…_v1r0`; **10 implicit grids** (PROMIS domains), each = intro + 4–5 items +
  shared scale, grouped by `[NOTE: DISPLAY … ON SAME SCREEN]`; **no GRID ids → synthesize**;
  scales vary, some **reverse-scored**, some use `44=Never`; **no skip logic** (pure grids — capture
  scale direction per item).

---

### Appendix: extraction & glyph notes
- Routing arrow renders variably: `à`, `-->`, `→`, and the typo `à TO`. Normalize all to a route;
  preserve the original in `raw`.
- Tabs separate `<code>` from `<label>`; counts of tabs/spaces are inconsistent — split on first run
  of whitespace after the leading code token.
- Trailing whitespace is rampant; trim it from captured `text`/`label`, but keep `raw_excerpt` faithful.
- `≥`/`≤` are Unicode; preserve in `raw`, encode as `gte`/`lte` in `parsed`.
