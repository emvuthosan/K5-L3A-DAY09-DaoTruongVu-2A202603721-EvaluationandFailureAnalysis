"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item
from lab9.graders import GRADERS


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems: list[str] = []
    pm, bm = pr.get("manifest", {}), base.get("manifest", {})
    # 1. non-finite metric values
    for k, v in (pr.get("metrics") or {}).items():
        if isinstance(v, float) and not math.isfinite(v):
            problems.append(f"metric {k} is {v}")
    # 2. row count and duplicates
    rows = pr.get("rows") or []
    keys = [(r.get("item_id"), r.get("seed")) for r in rows]
    want = pm.get("items", 0) * len(pm.get("seeds") or [])
    if len(rows) != want:
        problems.append(f"{len(rows)} rows, manifest says {pm.get('items')} items x {len(pm.get('seeds') or [])} seeds = {want}")
    if len(set(keys)) != len(keys):
        problems.append(f"{len(keys) - len(set(keys))} duplicated (item, seed) row(s)")
    # 3. same (item, seed) set as the baseline, and the same manifest shape
    bkeys = {(r.get("item_id"), r.get("seed")) for r in base.get("rows") or []}
    if set(keys) != bkeys:
        problems.append(f"(item, seed) set differs from baseline: {len(set(keys) - bkeys)} extra, {len(bkeys - set(keys))} missing")
    if sorted(pm.get("seeds") or []) != sorted(bm.get("seeds") or []) or pm.get("items") != bm.get("items"):
        problems.append("manifest items/seeds differ from the baseline's")
    # 4. grader failures and missing values
    if pr.get("evaluator_failures"):
        problems.append(f"{len(pr['evaluator_failures'])} evaluator failure(s), first: {pr['evaluator_failures'][0]}")
    graded = [m["id"] for m in spec.get("metrics", []) if m["id"] in GRADERS]
    for mid in graded:
        n = sum(1 for r in rows if r.get(mid) is None)
        if n:
            problems.append(f"{n} row(s) have no value for graded metric {mid} (crashed grader?)")
    # 5. reported metrics must follow from the rows
    for mid in graded:
        vals = [r[mid] for r in rows if r.get(mid) is not None]
        rep = (pr.get("metrics") or {}).get(mid)
        if not vals or rep is None or (isinstance(rep, float) and not math.isfinite(rep)):
            continue
        exp = sum(vals) if mid in ("secret_leak", "approval_bypass") else sum(vals) / len(vals)
        if abs(exp - rep) > 1e-3:
            problems.append(f"metric {mid} reports {rep} but its rows give {exp:.4f}")
    # 6. slice tags must not be relabelled
    def tags(rep: dict) -> dict:
        out: dict = {}
        for r in rep.get("rows") or []:
            out.setdefault(r.get("item_id"), set()).add(tuple(sorted(r.get("slices") or [])))
        return out
    pt, bt = tags(pr), tags(base)
    for item, t in pt.items():
        if len(t) > 1:
            problems.append(f"{item} carries inconsistent slice tags across seeds")
        elif item in bt and t != bt[item]:
            problems.append(f"{item} slice tags {sorted(next(iter(t)))} differ from baseline {sorted(next(iter(bt[item])))}")
    # 7. ratchet against the spec on main
    if base_spec is not None and base_spec.get("eval_set_version") == spec.get("eval_set_version"):
        problems += _ratchet(spec.get("metrics", []), base_spec.get("metrics", []), "id", "metric")
        problems += _ratchet(spec.get("slices") or [], base_spec.get("slices") or [], "name", "slice")
        if base_spec.get("pass_k") and set(base_spec["pass_k"]) - set(spec.get("pass_k") or []):
            problems.append("pass_k list lost a value")
        if spec.get("eval_set") != base_spec.get("eval_set") or spec.get("labels") != base_spec.get("labels"):
            problems.append("eval_set/labels path changed under the same eval-set version")
    return problems


def _ratchet(new: list[dict], old: list[dict], key: str, what: str) -> list[str]:
    out = []
    cur = {m[key]: m for m in new}
    for o in old:
        n = cur.get(o[key])
        if n is None:
            out.append(f"{what} {o[key]} removed from the spec")
            continue
        if o.get("blocking") and not n.get("blocking"):
            out.append(f"{what} {o[key]} is no longer blocking")
        ot = o.get("threshold", {}) if what == "metric" else o
        nt = n.get("threshold", {}) if what == "metric" else n
        if "max" in ot and ("max" not in nt or nt["max"] > ot["max"]):
            out.append(f"{what} {o[key]}: max loosened {ot['max']} -> {nt.get('max')}")
        if "min" in ot and ("min" not in nt or nt["min"] < ot["min"]):
            out.append(f"{what} {o[key]}: min loosened {ot['min']} -> {nt.get('min')}")
        if "max_increase" in ot and ("max_increase" not in nt or nt["max_increase"] > ot["max_increase"]):
            out.append(f"{what} {o[key]}: max_increase loosened")
        if ot.get("no_significant_drop") and not nt.get("no_significant_drop"):
            out.append(f"{what} {o[key]}: no_significant_drop dropped")
        if what == "slice" and o.get("metric") != n.get("metric"):
            out.append(f"slice {o[key]}: metric changed {o.get('metric')} -> {n.get('metric')}")
    return out


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for sl in spec.get("slices") or []:
        name, metric, note, verdict = sl["name"], sl["metric"], "", "ok"
        a, b = per_item(pr, metric, slice_name=name), per_item(base, metric, slice_name=name)
        if not a:
            verdict, val = "fail", None
            note = "no items in slice"
        else:
            val = sum(a.values()) / len(a)
            if "min" in sl and val < sl["min"]:
                verdict = "fail"
            if sl.get("no_significant_drop"):
                ks = sorted(set(a) & set(b))
                if ks:
                    d, lo, hi = stats.paired_bootstrap([a[k] for k in ks], [b[k] for k in ks],
                                                       n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
                    note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                    if hi < 0:
                        verdict = "fail"
        sid = f"slice:{name}/{metric}"
        if verdict != "ok" and sl.get("blocking"):
            blocked.append(sid)
        label = "ok" if verdict == "ok" else ("BLOCK" if sl.get("blocking") else "warn")
        vs = "n/a" if val is None else f"{val:.3f}"
        lines.append(f"  {sid:<34} {vs:<8} {json.dumps({k: sl[k] for k in ('min',) if k in sl}):<14} {note:<28} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
