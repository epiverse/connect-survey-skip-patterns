#!/usr/bin/env python3
"""Validate a serialized Connect survey module.

Runs (1) structural validation against schema/connect_survey.schema.json (via jsonschema),
then (2) referential/semantic checks that JSON Schema cannot express: id uniqueness, route-target
resolution, expression-variable resolution, condition-wrapper integrity, and question-count
reconciliation. Also derives the dependency_index (parent->child edges) and detects cycles in the
data-dependency (display+pipe+loop) subgraph.

Usage:
    python tools/validate.py <module.json> [--registry registry/variable_index.json]
                             [--emit-deps] [--json] [--strict]

Exit codes: 0 = clean (warnings allowed unless --strict); 1 = errors (or warnings under --strict);
2 = jsonschema missing / input not loadable.

See PLAN.md (master) and the Phase 0 plan for the contract. Diagnostic strings here are relied on by
tools/selftest.sh: "duplicate id", "unresolved route", "unknown variable", "interpretation_note",
"needs_review".
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "schema" / "connect_survey.schema.json"

# Expression-node ops that carry a single `var` reference.
_VAR_OPS = {"eq", "ne", "lt", "lte", "gt", "gte", "in", "selected",
            "answered", "is_null", "response_entered", "displayed",
            "subfield_any", "subfield_all"}
_LOGICAL_OPS = {"and", "or", "not"}

_TERMINAL_RE = re.compile(
    r"^(GO TO\s+)?(END(\s+OF\s+MODULE)?|END\s+MESSAGE(\s+\d+)?|EXIT.*)$", re.IGNORECASE)


# --------------------------------------------------------------------------- loading

def load_json(path: Path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid JSON in {path}: {exc}", file=sys.stderr)
        sys.exit(1)


# --------------------------------------------------------------------------- structural

def structural_errors(doc) -> list[str]:
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        print("ERROR: jsonschema not found - activate .venv or run: "
              "pip install -r requirements.txt", file=sys.stderr)
        sys.exit(2)
    schema = load_json(SCHEMA_PATH)
    validator = Draft202012Validator(schema)

    def most_specific(err):
        # Descend through oneOf/anyOf context to the deepest sub-error so messages name the
        # actual offending field (e.g. .interpretation_note) instead of a generic
        # "not valid under any of the given schemas". Our unions are discriminated by `op`/
        # `kind`, so the branch that almost matches yields the deepest (most relevant) error.
        while err.context:
            err = max(err.context, key=lambda e: len(e.absolute_path))
        return err

    errs = []
    for top in sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path)):
        err = most_specific(top)
        errs.append(f"structural: {err.json_path}: {err.message}")
    return list(dict.fromkeys(errs))  # dedupe, preserve order


# --------------------------------------------------------------------------- expr walking

def iter_expr_nodes(node):
    """Yield every expression node in a parsed tree (descending logical args)."""
    if not isinstance(node, dict):
        return
    yield node
    if node.get("op") in _LOGICAL_OPS:
        for arg in node.get("args", []):
            yield from iter_expr_nodes(arg)


def expr_var_refs(parsed, path):
    """Yield (path, var, var_kind) for every variable referenced in a parsed tree."""
    for n in iter_expr_nodes(parsed):
        op = n.get("op")
        if op in _VAR_OPS and "var" in n:
            yield (path, n["var"], n.get("var_kind"))
        elif op == "address_entered":
            for v in n.get("vars", []):
                yield (path, v, None)


def bound_var_refs(bound, path):
    if not isinstance(bound, dict):
        return
    kind = bound.get("kind")
    if kind == "var":
        yield (path, bound.get("var"), None)
    elif kind == "system_var":
        yield (path, bound.get("var"), "system")
    elif kind == "conditional":
        for case in bound.get("cases", []):
            yield from expr_var_refs(case.get("when"), path)
            yield from bound_var_refs(case.get("value"), path)
        yield from bound_var_refs(bound.get("default"), path)


# --------------------------------------------------------------------------- collectors

def collect_wrappers(doc):
    """Yield (path, condition_wrapper) for every condition wrapper in the document."""
    for i, item in enumerate(doc.get("items", [])):
        base = f"items[{i}]"
        if isinstance(item.get("display_condition"), dict):
            yield (f"{base}.display_condition", item["display_condition"])
        resp = item.get("response") or {}
        for j, opt in enumerate(resp.get("options", []) or []):
            if isinstance(opt.get("display_condition"), dict):
                yield (f"{base}.response.options[{j}].display_condition", opt["display_condition"])
        term = (item.get("routing") or {}).get("terminal") or {}
        if isinstance(term.get("condition"), dict):
            yield (f"{base}.routing.terminal.condition", term["condition"])
    for g, grid in enumerate(doc.get("grids", [])):
        if isinstance(grid.get("display_condition"), dict):
            yield (f"grids[{g}].display_condition", grid["display_condition"])
    for r, rg in enumerate(doc.get("repeated_groups", [])):
        for k, rule in enumerate(rg.get("per_iteration_rules", []) or []):
            if isinstance(rule, dict):
                yield (f"repeated_groups[{r}].per_iteration_rules[{k}]", rule)
        for k, inst in enumerate(rg.get("instances") or []):
            if isinstance(inst.get("gate"), dict):
                yield (f"repeated_groups[{r}].instances[{k}].gate", inst["gate"])


def collect_var_refs(doc):
    """Yield (path, var, var_kind) for every variable reference anywhere in the document."""
    for path, wrapper in collect_wrappers(doc):
        yield from expr_var_refs(wrapper.get("parsed"), f"{path}.parsed")
    for i, item in enumerate(doc.get("items", [])):
        resp = item.get("response") or {}
        rc = resp.get("range_check") or {}
        if isinstance(rc, dict):
            yield from bound_var_refs(rc.get("min"), f"items[{i}].response.range_check.min")
            yield from bound_var_refs(rc.get("max"), f"items[{i}].response.range_check.max")
        for p, pref in enumerate(item.get("piped_refs", []) or []):
            if isinstance(pref, dict) and "var" in pref:
                yield (f"items[{i}].piped_refs[{p}]", pref["var"], pref.get("var_kind"))
    for r, rg in enumerate(doc.get("repeated_groups", [])):
        ctrl = rg.get("controller") or {}
        if isinstance(ctrl, dict) and ctrl.get("count_source"):
            yield (f"repeated_groups[{r}].controller.count_source", ctrl["count_source"], None)
        if rg.get("domain_source"):
            yield (f"repeated_groups[{r}].domain_source", rg["domain_source"], None)


def collect_route_targets(doc):
    """Yield (path, target) for every route target string in the document."""
    for i, item in enumerate(doc.get("items", [])):
        routing = item.get("routing") or {}
        dn = routing.get("default_next")
        if isinstance(dn, str):
            yield (f"items[{i}].routing.default_next", dn)
        nr = routing.get("no_response_route") or {}
        if isinstance(nr, dict) and nr.get("target"):
            yield (f"items[{i}].routing.no_response_route", nr["target"])
        resp = item.get("response") or {}
        for j, opt in enumerate(resp.get("options", []) or []):
            route = opt.get("route") or {}
            if isinstance(route, dict) and route.get("target"):
                yield (f"items[{i}].response.options[{j}].route", route["target"])
            wrapper = opt.get("display_condition") or {}
            er = (wrapper.get("else_route") or {}) if isinstance(wrapper, dict) else {}
            if er.get("target"):
                yield (f"items[{i}].response.options[{j}].display_condition.else_route", er["target"])
        dc = item.get("display_condition") or {}
        er = (dc.get("else_route") or {}) if isinstance(dc, dict) else {}
        if er.get("target"):
            yield (f"items[{i}].display_condition.else_route", er["target"])
    for r, rg in enumerate(doc.get("repeated_groups", [])):
        if rg.get("summary_item"):
            yield (f"repeated_groups[{r}].summary_item", rg["summary_item"])


# --------------------------------------------------------------------------- resolution

def _norm(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def resolve_route(target, item_ids, section_norms, registry_vars):
    if target in item_ids:
        return "item"
    if _TERMINAL_RE.match(target.strip()):
        return "terminal"
    nt = _norm(target)
    if nt.endswith("SECTION") or nt in section_norms or any(nt == s or s in nt for s in section_norms if s):
        return "section"
    if target in registry_vars:
        return "external"
    return "unresolved"


def resolve_var(var, var_kind, item_ids, external_names, registry_vars):
    if var in item_ids:
        return "item"
    if var_kind in ("system", "derived"):
        return var_kind
    if var in external_names:
        return "external"
    if var in registry_vars:
        return "registry"
    return "unknown"


# --------------------------------------------------------------------------- checks

def check_duplicate_ids(items):
    errors, seen = [], set()
    for item in items:
        iid = item.get("id")
        if iid in seen:
            errors.append(f"duplicate id: {iid}")
        seen.add(iid)
    return errors


def check_id_format(items, convention):
    if convention == "short_uppercase":
        pat = re.compile(r"^[A-Z0-9_]+$")
    elif convention == "srv_versioned":
        pat = re.compile(r"^(GRID_)?Srv[A-Za-z]+_.+_v\d+r\d+$", re.IGNORECASE)
    else:
        return []  # mixed/unknown: skip
    return [f"id-format: '{it.get('id')}' does not match {convention}"
            for it in items if it.get("id") and not pat.match(it["id"])]


def check_wrappers(doc):
    errors = []
    for path, w in collect_wrappers(doc):
        conf = w.get("confidence")
        note = w.get("interpretation_note")
        if conf in ("medium", "low") and not (isinstance(note, str) and note.strip()):
            errors.append(f"interpretation_note required when confidence is {conf} (at {path})")
        parsed = w.get("parsed")
        if isinstance(parsed, dict) and parsed.get("op") == "raw" and w.get("needs_review") is not True:
            errors.append(f"op 'raw' requires needs_review=true (at {path})")
    return errors


def check_counts(doc, items):
    errors, warnings = [], []
    module = doc.get("module", {})
    stated = module.get("stated_question_count")
    counted = module.get("counted_question_count")
    actual = sum(1 for it in items if it.get("kind") == "question")
    if isinstance(counted, int) and counted != actual:
        errors.append(f"count mismatch: counted_question_count={counted} but {actual} question items present")
    if isinstance(stated, int) and isinstance(counted, int) and stated != counted:
        warnings.append(f"count delta: counted {counted} vs stated {stated} "
                        f"(expected for some modules; ensure count_reconciliation explains it)")
    return errors, warnings


# --------------------------------------------------------------------------- dependency index

def build_dep_index(doc, items):
    """Return (dep_index, edges). edges = list of (parent, child, edge_type)."""
    item_ids = {it.get("id") for it in items}
    edges = []

    def add_display(parsed, child):
        if child:
            for _, var, _ in expr_var_refs(parsed, ""):
                edges.append((var, child, "display"))

    for i, item in enumerate(items):
        cid = item.get("id")
        dc = item.get("display_condition")
        if isinstance(dc, dict):
            add_display(dc.get("parsed"), cid)
        resp = item.get("response") or {}
        for opt in resp.get("options", []) or []:
            odc = opt.get("display_condition")
            if isinstance(odc, dict):
                add_display(odc.get("parsed"), cid)
        # routing edges (source item -> target item)
        routing = item.get("routing") or {}
        targets = []
        dn = routing.get("default_next")
        if isinstance(dn, str):
            targets.append(dn)
        nr = routing.get("no_response_route") or {}
        if nr.get("target"):
            targets.append(nr["target"])
        for opt in resp.get("options", []) or []:
            route = opt.get("route") or {}
            if route.get("target"):
                targets.append(route["target"])
        for t in targets:
            if t in item_ids and cid:
                edges.append((cid, t, "route"))
        # pipe edges
        for pref in item.get("piped_refs", []) or []:
            if pref.get("var") and cid:
                edges.append((pref["var"], cid, "pipe"))

    # grid display edges -> each row
    for grid in doc.get("grids", []):
        dc = grid.get("display_condition")
        if isinstance(dc, dict):
            for row in grid.get("row_item_ids", []) or []:
                for _, var, _ in expr_var_refs(dc.get("parsed"), ""):
                    edges.append((var, row, "display"))

    # loop edges: controller/domain source -> each member item
    for rg in doc.get("repeated_groups", []):
        sources = []
        ctrl = rg.get("controller") or {}
        if ctrl.get("count_source"):
            sources.append(ctrl["count_source"])
        if rg.get("domain_source"):
            sources.append(rg["domain_source"])
        members = list(rg.get("template_item_ids", []) or [])
        for inst in rg.get("instances") or []:
            members.extend(inst.get("item_ids", []) or [])
        for src in sources:
            for m in members:
                edges.append((src, m, "loop"))

    dep_index = {}

    def node(name):
        return dep_index.setdefault(name, {"parents": [], "children": []})

    def has_edge(lst, var, et):
        return any(e["var"] == var and e["edge_type"] == et for e in lst)

    for parent, child, et in edges:
        if not has_edge(node(child)["parents"], parent, et):
            node(child)["parents"].append({"var": parent, "edge_type": et})
        if not has_edge(node(parent)["children"], child, et):
            node(parent)["children"].append({"var": child, "edge_type": et})
    return dep_index, edges


def detect_cycles(edges):
    """Detect cycles in the display+pipe+loop subgraph (route edges excluded)."""
    from graphlib import CycleError, TopologicalSorter
    graph = {}
    for parent, child, et in edges:
        if et == "route":
            continue
        graph.setdefault(child, set()).add(parent)
        graph.setdefault(parent, set())
    warnings = []
    try:
        TopologicalSorter(graph).prepare()
    except CycleError as exc:
        cycle = exc.args[1] if len(exc.args) > 1 else exc.args
        warnings.append("dependency cycle (review): " + " -> ".join(map(str, cycle)))
    return warnings


# --------------------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description="Validate a serialized Connect survey module.")
    ap.add_argument("module_json", type=Path)
    ap.add_argument("--registry", type=Path, default=None)
    ap.add_argument("--emit-deps", action="store_true", help="write dependency_index back into the file")
    ap.add_argument("--json", action="store_true", help="emit a machine-readable report")
    ap.add_argument("--strict", action="store_true", help="treat warnings as failures")
    args = ap.parse_args(argv)

    doc = load_json(args.module_json)
    items = doc.get("items", []) if isinstance(doc, dict) else []

    registry_vars = set()
    if args.registry:
        reg = load_json(args.registry)
        registry_vars |= set(reg.get("system_variables", {}))
        registry_vars |= set(reg.get("variables", {}))

    errors, warnings, notes = [], [], []

    errors += structural_errors(doc)
    errors += check_duplicate_ids(items)
    warnings += check_id_format(items, doc.get("module", {}).get("naming_convention"))
    errors += check_wrappers(doc)
    cerr, cwarn = check_counts(doc, items)
    errors += cerr
    warnings += cwarn

    item_ids = {it.get("id") for it in items}
    external_names = {ev.get("name") for ev in doc.get("module", {}).get("external_variables", [])}
    section_norms = set()
    for sec in doc.get("module", {}).get("sections", []):
        section_norms.add(_norm(sec.get("id", "")))
        section_norms.add(_norm(sec.get("title", "")))
    section_norms.discard("")

    for path, target in collect_route_targets(doc):
        cat = resolve_route(target, item_ids, section_norms, registry_vars)
        if cat == "unresolved":
            errors.append(f"unresolved route target: {target} (at {path})")
        elif cat == "external":
            notes.append(f"external route target: {target} (at {path})")

    for path, var, var_kind in collect_var_refs(doc):
        cat = resolve_var(var, var_kind, item_ids, external_names, registry_vars)
        if cat == "unknown":
            errors.append(f"unknown variable: {var} (at {path})")
        elif cat in ("external", "registry"):
            notes.append(f"external variable: {var} (at {path})")

    dep_index, edges = build_dep_index(doc, items)
    warnings += detect_cycles(edges)

    n_wrappers = sum(1 for _ in collect_wrappers(doc))
    n_needs_review = sum(1 for _, w in collect_wrappers(doc) if w.get("needs_review"))

    if args.emit_deps:
        doc["dependency_index"] = dep_index
        with open(args.module_json, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2, ensure_ascii=False)
            fh.write("\n")

    if args.json:
        print(json.dumps({
            "errors": errors, "warnings": warnings, "notes": notes,
            "dep_summary": {"nodes": len(dep_index), "edges": len(edges)},
            "summary": {"items": len(items), "conditions": n_wrappers,
                        "needs_review": n_needs_review},
        }, indent=2, ensure_ascii=False))
    else:
        if errors:
            print(f"ERRORS ({len(errors)}):")
            for e in errors:
                print(f"  - {e}")
        if warnings:
            print(f"WARNINGS ({len(warnings)}):")
            for w in warnings:
                print(f"  - {w}")
        if notes:
            print(f"NOTES ({len(notes)}):")
            for n in notes:
                print(f"  - {n}")
        print(f"summary: items={len(items)} conditions={n_wrappers} "
              f"needs_review={n_needs_review} dep_nodes={len(dep_index)} dep_edges={len(edges)} "
              f"errors={len(errors)} warnings={len(warnings)}")

    if errors or (args.strict and warnings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
