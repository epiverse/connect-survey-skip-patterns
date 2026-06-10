# Connect Survey Serialization — Conventions & Quick Reference

Builder/verifier reference for serializing a Connect questionnaire module into JSON. This condenses
`PLAN.md` §§1–5 and is **aligned to `schema/connect_survey.schema.json`**. The master brief (`PLAN.md`)
has the full narrative; this file is the day-to-day cheat-sheet.

> **Schema status: FROZEN at v1.0.0** (locked by the `bio_menstrual` pilot, 2026-06). The modeling
> conventions below — especially terminal/END MESSAGE handling (§3.10) — were validated by that pilot
> and apply to all 11 modules. Treat the schema as stable; change it only with explicit owner sign-off.

## How to use this with the tooling
1. **Extract** the source (read-only, line-numbered for provenance):
   `bash tools/extract.sh <module_id>` → pipes `textutil -convert txt -stdout "<file>" | cat -n`.
   Cite these line numbers in every `provenance`. (`bash tools/extract.sh --list` shows the 11 ids.)
2. **Build** `output/<module_id>.json` to the schema (see field shapes below).
3. **Validate** continuously: `.venv/bin/python tools/validate.py output/<module_id>.json --registry registry/variable_index.json`.
   Fix all ERRORS; WARNINGS/NOTES are advisory (unless `--strict`). `--emit-deps` fills `dependency_index`.
4. **Verify** independently (second agent) against the source; see `PLAN.md` §8.

`module_id` → file map: `baseline_m1..m4`, `bio_mouthwash`, `bio_covid19`, `bio_clinical`,
`bio_menstrual`, `bio_research_appt`, `screening`, `qol` (see `tools/extract.sh`).

---

## 1. Document structure (what the source looks like)
- **Title line**, then **section headers** (`Background Information [SECTION 1]`, or intro blocks).
- **Blocks** start with a bracketed ID: `[MARITAL]`, `[SrvScr_ANALSCREEN2_v1r0]`.
  - **Askable questions** are preceded by a bullet **`•`** → `item.kind = "question"`, `bullet = true`.
  - **Display-only** blocks (intros/summaries) have an ID, no bullet → `kind = "display_text"`.
- **Answer options**: `<code>\t<label>`; split on the first whitespace run after the code token.
  Trim trailing whitespace from captured `text`/`label`; keep `provenance.raw_excerpt` faithful.
- **Routing arrow** renders variably: `à`, `-->`, `→`, and the typo `à TO` (missing GO). Normalize all
  to a route; keep the original glyph in `route.raw`.
- **Bracketed directives** carry logic: `[DISPLAY … IF …]`, `[RANGE CHECK …]`, `[REPEAT …]`,
  `[THIS QUESTION … FOR EACH RESPONSE OPTION SELECTED AT …]`, `[insert …]`, `[GRID_…]`,
  `[NOTE … PROGRAMMERS …]`, `[END MESSAGE n]`, `[EXIT AND CLEAR CACHE]`.
- **A directive immediately *preceding* a bulleted question** (its `[DISPLAY IF…]` gate,
  `[PROGRAMMING NOTE…]`, etc.) belongs to **that question's block**: fold those lines into the question
  item's `provenance` span, put the gate in its `display_condition`, and a "requires response" note
  into `requires_response` (and verbatim in `flags.notes`, per §3.9).

**Two naming conventions** (`module.naming_convention`): `short_uppercase` (Baseline M1–M4, e.g.
`HOMEADD1_1_SRC`) and `srv_versioned` (`Srv<Code>_NAME_v#r#`). Use `mixed` for composed surveys that
reuse multiple prefixes (`bio_clinical`, `bio_research_appt`).

## 2. Response-code conventions (verify per question — do not assume)
| Code | Typical meaning | Encode `option.flags` |
|------|-----------------|------------------------|
| `0..N` | substantive answers | — |
| `44` | "Never" (context-specific) | `is_never` |
| `55` | "None of these / Other" (often `+ describe [text box]`) | `is_other`, `has_textbox` |
| `77` | "Don't know" | `is_dontknow` |
| `88` | "None of the above / not applicable" (often exclusive; routes onward) | `is_none`, `is_exclusive` |
| `99` | "Prefer not to answer" | `is_refused` |
| `NR` / `NO RESPONSE` | item skipped — **distinct structural-missing state** | (its own `routing.no_response_route`) |

Multi-select "de-select all others if 88 selected" → put such codes in `response.exclusive_codes` and
mark the option `is_exclusive`. QoL scales may be **reverse-ordered** or use `44=Never`; record actual
options verbatim and set `response.scale.reverse_scored` (`true`/`false`/`"uncertain"`).

## 3. Skip-logic taxonomy → where it goes in the JSON
1. **Option-level routing** (`… à GO TO X`) → `option.route` `{target, kind, raw}`.
2. **Question-level NO RESPONSE routing** → `routing.no_response_route`.
3. **Block conditional display** (`[DISPLAY … IF …]`) → `item.display_condition` (a *condition wrapper*, §5).
4. **Option-level conditional display** (`<code> label [DISPLAY IF …]`) → `option.display_condition`.
5. **Loops / iteration** → `repeated_groups[]` (template + instances), members link via `item.membership`.
   Four `type`s: `repeat_n`, `per_selected_option`, `per_entity`, `parallel_block` (copy-paste blocks).
6. **Grids/matrix** → `grids[]`; each row is also an `item` with `membership.grid` set; per-row scale
   overrides live on the row item's `response.scale`.
7. **Piping / display dependencies** (`[insert X]`) → `item.piped_refs[]` (not a skip, but a BN edge).
8. **Validation** (`[RANGE CHECK …]`) → `response.range_check` (structured `min`/`max` + verbatim `raw`).
   A field's **validation error string** (e.g. "Error message if someone clicks NEXT…") has no schema
   field → capture it **verbatim** in the item's `flags.notes`.
9. **Programmer notes** (`[PROGRAMMING NOTE…]`/`[NOTE…]`) → **always** keep the verbatim text in
   `item.flags.notes`, **and additionally** encode any logic into structured fields
   (`requires_response` for "REQUIRES RESPONSE"; `exclusive_codes`+`is_exclusive` for "de-select all
   others"; a `repeated_group` for iteration scope; etc.). Capture both the text and the logic.
10. **Terminal nodes** (`GO TO END`, `END MESSAGE n`, `[EXIT AND CLEAR CACHE]`) — pilot-locked rules:
    - An END MESSAGE / exit block becomes its **own `item`** with `kind:"terminal"`, `response:null`,
      and `routing.terminal = {type` (end_module/end_message/exit)`, id, message` (verbatim, without the
      "END MESSAGE n:" prefix)`, exit_behavior:"clear_cache"` iff `[EXIT AND CLEAR CACHE]`, else `null,
      condition:null}`.
    - Source END MESSAGE blocks carry **no bracket id → synthesize `END_MESSAGE_<n>`** (the `n` from the
      source); an `[EXIT AND CLEAR CACHE]`-only terminal → synthesize a short descriptive id.
    - **Routes to a terminal target the synthesized item id** (`route.target:"END_MESSAGE_1"`,
      `route.kind:"terminal"`) with the verbatim arrow in `route.raw`; a question-level
      `--> GO TO END MESSAGE n` → that item's `routing.default_next = "END_MESSAGE_<n>"`. *Targeting the
      synthesized id (not the bare "END MESSAGE 1" label) is what makes the validator emit the route
      dependency edge.*
    - A terminal's `[DISPLAY IF…]` gate goes in the item's **`display_condition`**, NOT in
      `routing.terminal.condition` (leave that `null`). *`build_dep_index` reads display edges from
      `item`/`option.display_condition` only — a gate hidden in `terminal.condition` would silently drop
      the edge.* Reserve `terminal.condition` for a gate that is genuinely not a `[DISPLAY IF]` directive.

## 4. Canonical expression-tree grammar (the heart)
Every `display_condition`, `option.display_condition`, `grid.display_condition`, `terminal.condition`,
and `repeated_group.per_iteration_rules[]`/`instances[].gate` is a **condition wrapper**:
```json
{ "raw": "<verbatim directive>", "parsed": <expr_node|null>,
  "confidence": "high|medium|low", "needs_review": false,
  "interpretation_note": null, "else_route": null }
```
**Rules (enforced by the validator):** `interpretation_note` is **required** (non-empty) whenever
`confidence != "high"`; `parsed.op == "raw"` **requires** `needs_review == true`.

**Expr nodes** (recursive). `op` ∈:
- logical: `and`/`or` (`args:[…]`), `not` (`args:[one]`)
- comparison: `eq|ne|lt|lte|gt|gte` (`var`, `value`; optional `field`, `var_kind`)
- `in` (single-select value list/range): `var`, `values:[…]`, optional `raw_value_spec`
- `selected` (multi-select membership): `var`, `values:[…]`, `quantifier:"any"|"all"`
- presence: `answered` / `is_null` / `response_entered` / `displayed` (`var`)
- composite sub-field: `subfield_any` / `subfield_all` (`var`, `fields:[…]`, `predicate:{op,value}`)
- `address_entered` (`vars:[…]`, `quantifier`, `negated`)
- `raw` (`text`) — last resort; pair with `needs_review:true`

**Worked raw → `parsed`:**
| Raw | parsed |
|---|---|
| `[DISPLAY IF MHGROUP1= 0]` | `{"op":"eq","var":"MHGROUP1","value":0}` |
| `[… 0 SELECTED AT RACEETH]` | `{"op":"selected","var":"RACEETH","values":[0],"quantifier":"any"}` |
| `[… = 1, 2, 3, 4, OR 77]` | `{"op":"in","var":"X","values":[1,2,3,4,77],"raw_value_spec":"1, 2, 3, 4, OR 77"}` |
| `[… = 0-6, 55]` | `{"op":"in","var":"X","values":[0,1,2,3,4,5,6,55],"raw_value_spec":"0-6, 55"}` |
| `[… (SEX=0) AND (age ≥ 40)]` | `{"op":"and","args":[{"op":"eq","var":"SEX","value":0},{"op":"gte","var":"age","var_kind":"system","value":40}]}` |
| `[… 0, 1, AND/OR 2 WAS SELECTED IN CHOLHTN]` | `{"op":"selected","var":"CHOLHTN","values":[0,1,2],"quantifier":"any"}` |
| `[… (HOMEADD1_1_SRC: CITY, STATE, ZIP, OR COUNTRY= NR)]` | `{"op":"subfield_any","var":"HOMEADD1_1_SRC","fields":["CITY","STATE","ZIP","COUNTRY"],"predicate":{"op":"eq","value":"NR"}}` |
| `[… (PREPANDIFF=1) AND (ADDRESS ENTERED IN A,B,OR C)]` | `{"op":"and","args":[{"op":"eq","var":"PREPANDIFF","value":1},{"op":"address_entered","vars":["A","B","C"],"quantifier":"any"}]}` |
| `[… (SEX=1) AND ((age ≥ 40)]` *(malformed)* | best-guess `and[…]`; `confidence:"low"`, note: "unbalanced parens; inferred one closing paren" |

**Range-check bounds** (`response.range_check.min/max`): `kind` ∈ `const` (`value`), `var` (`var`),
`system_var` (`var`), `relative_date` (`expr`,`raw`), `conditional` (`cases:[{when:<expr>,value:<bound>}], default:<bound>`). Set `needs_review:true` for relative/dependent/version-specific checks.
For `relative_date`, `raw` is the **verbatim** bound text (e.g. `"(Today date – 60 days)"`) and `expr`
is a **normalized** machine form (e.g. `"today - 60d"`).

## 5. Repeated groups, grids, composite fields
- **Repeated group**: `{group_id, type, template_item_ids:[…], controller?, domain_source?, instances?}`.
  `repeat_n` → `controller.count_source` (e.g., `PREG3`); `per_selected_option` → `domain_source` (the
  multi-select var); `per_entity` → `domain_source` (the entry-set); `parallel_block` → enumerate
  `instances:[{key, gate, item_ids}]` (e.g., CIG/ECIG/…). Members set `membership.repeated_group`
  (and `iteration_role` for parallel blocks).
- **Grid**: `{grid_id, explicit_id, stem, shared_scale:[{code,label}], row_item_ids:[…], same_screen}`.
  Synthesize `grid_id` + `explicit_id:false` when the source has no `[GRID_…]` id (e.g., QoL domains).
- **Composite `_SRC`** (M4 addresses): `response.type:"composite"` + `composite_fields:[{name,type}]`
  (STREET_NUMBER/STREET_NAME/CITY/STATE/ZIP/COUNTRY). Reference sub-fields via the `field` key in
  expr nodes. **M3 `_SRC` is a single age field → `type:"integer"`, NOT composite.**

## 6. Schema-breaker catalog & policy
**Policy (firm):** never silently "fix" the source. Record a best-guess `parsed` + `confidence`
(`medium`/`low`) + verbatim `raw` + `needs_review:true` + an `interpretation_note`, and add an entry to
`build_meta.open_questions`. Known cases (line refs are in the source):

| Module | Issue | Guidance |
|--------|-------|----------|
| baseline_m1 (L1177) | `(SEX=1) AND ((age ≥ 40)]` unbalanced parens | infer `and[eq SEX 1, gte age 40]`, low conf |
| baseline_m1 (L751) | `(SEX2=0 AND 1)` literal "AND 1" | best guess `in SEX2 [0,1]`, low conf |
| baseline_m1 (L1983) | `MULT2 AND SIBCANC2 DISPLAYED TO RESPONDENT` | `and[<MULT2>, displayed SIBCANC2]`, flag bare `MULT2` |
| baseline_m2 (L3,L71) | unbalanced parens; mixed `or`/`OR` | infer grouping, low conf |
| baseline_m2 (L362) | imperative prose loop rule | store in `repeated_group.per_iteration_rules` |
| baseline_m3 (L339) | missing closing `]` | infer close, low conf |
| baseline_m3 (L896,L1370) | missing `=` (`SMMAR3_SRC 44`) | infer `eq …_SRC 44`, low conf |
| baseline_m4 (L2704,L3047) | unclosed/mismatched brackets | normalize, low conf, note |
| baseline_m4 (L2759) | ungrouped `A AND B OR C` | assume `(A∧B)∨C`, note assumption |
| baseline_m4 (L17 vs 27) | colon vs space sub-field notation | both → `subfield_*` |
| bio_menstrual (L12 vs 22) | **version drift** (`MENS2_v2r0` cited as `…v1r0`) | resolve to defined id, set leaf `resolved_from`, flag |
| bio_menstrual (L15) | relative-date range `(Today – 60 days)` | `bound.kind:"relative_date"`, `needs_review` |
| bio_research_appt (L19) | typo `à TO` | treat as route, note typo |
| screening (L33–40) | option-level `[DISPLAY IF …]` | `option.display_condition` |
| screening (L355,L1047) | "if 88 → de-select all" note | `exclusive_codes` + `is_exclusive` |
| bio_covid19 (L100…) | `max= COV13 response or 180 if null` | `bound.kind:"conditional"` |

**Question counts:** record both `stated_question_count` and `counted_question_count` (count `•`
bullets) and explain any delta in `count_reconciliation`. Deltas are expected (e.g., m4 ≈353 vs 322);
the validator **errors** only if `counted_question_count` ≠ the number of `kind:"question"` items.

## 7. External / system variables
Leaves not defined in the module carry `var_kind:"system"` (`age`, `yob`, `Current Year`,
`Today date`, `participant name`) or `var_kind:"external"` (+ `source_module`, e.g.
`SrvBlU_MENSTART_v2r0` from `bio_clinical`). Declare them in `module.external_variables` (or the
validator flags `unknown variable`). The validator resolves system/external vars via the leaf
`var_kind`, `module.external_variables`, or `--registry registry/variable_index.json`.

## 8. Enum cheat-sheet (must match the schema exactly)
- `module.naming_convention`: `short_uppercase` · `srv_versioned` · `mixed`
- `item.kind`: `question` · `display_text` · `section_header` · `terminal` · `loop_control` · `grid_row`
- `response.type`: `single_select` · `multi_select` · `integer` · `decimal` · `date` · `time` · `text` · `composite` · `scale`
- `option.flags[]`: `is_other` · `is_dontknow` · `is_refused` · `is_none` · `is_never` · `has_textbox` · `is_exclusive`
- `route.kind`: `goto` · `terminal`
- `routing.terminal.type`: `end_module` · `end_message` · `exit`
- `range_check` `bound.kind`: `const` · `var` · `system_var` · `relative_date` · `conditional`
- `repeated_group.type`: `repeat_n` · `per_selected_option` · `per_entity` · `parallel_block`
- expr `op`: `and` · `or` · `not` · `eq` · `ne` · `lt` · `lte` · `gt` · `gte` · `in` · `selected` · `answered` · `is_null` · `response_entered` · `displayed` · `subfield_any` · `subfield_all` · `address_entered` · `raw`
- `var_kind`: `question` · `derived` · `system` · `external`
- `confidence`: `high` · `medium` · `low`
- `dependency_edge.edge_type` (derived): `display` · `route` · `pipe` · `loop` · `grid`

## 9. Workflow recap
`build → validate (clean ERRORS) → independent verify (output/<id>.verify.md PASS) → fix → re-verify`.
Every `item` needs `provenance` (file + line range from `tools/extract.sh`). Leave `dependency_index`
as `{}` while building; `tools/validate.py --emit-deps` derives it. See the reference fixtures in
`tests/fixtures/` for a minimal valid module and the diagnostics a broken one triggers.
