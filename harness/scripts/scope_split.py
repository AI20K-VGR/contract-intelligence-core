#!/usr/bin/env python3
"""scope_split.py — deterministic scope-sizing gate (multi-plan split).

Port of FrankCode's scopeSizer.ts + scope-sizing-gate.md: decides whether a
mission fits in ONE plan or must be split into multiple sub-plans under a Plan
Manifest, before any discovery/interview work starts. Pure function, 0-token,
no LLM call, stdlib only.

  projected_cells = |feature| x |layer| x |lifecycle| x |risk_class| x |stakeholder|
  pruned_cells    = projected_cells after density_tier-conditional axis pruning
  mode            = 'multi' when pruned_cells > threshold (default 60,
                     overridable via SCOPE_SIZE_THRESHOLD), else 'single'

DensityTier pruning is RE-IMPLEMENTED INLINE here (not imported from
harness/scripts/grid/gridSkeleton.py's defaultAxisPruner) — this phase is
grid-independent by design (scopeSizer.ts:14 imports defaultAxisPruner from
gridSkeleton.ts upstream; the port here intentionally diverges to keep this
script free of a package dependency). The pruning rule itself matches
scope-sizing-gate.md:26-28 exactly:
  LOW  -> lifecycle capped at 2, stakeholder capped at 2
  MID  -> stakeholder capped at 3
  HIGH -> no pruning

This is advisory only: it never auto-splits a plan. hs:plan surfaces the
recommendation; a human/planner decides. See hs:plan's multi-plan-split
reference for the judgment half.
"""
import argparse
import json
import math
import os
import sys

CELL_COUNT_THRESHOLD = 60
MAX_FEATURES_PER_SUBPLAN = 3
MAX_LAYERS_PER_SUBPLAN = 2

DEFAULT_LAYERS = ["ui", "api", "data", "infra"]
DEFAULT_LIFECYCLE = ["discover", "design", "build", "ship", "measure"]
DEFAULT_RISK_CLASSES = ["spec-drift", "capacity", "regression", "compliance"]
DEFAULT_STAKEHOLDERS = ["dev", "ops", "security", "support"]

DENSITY_TIERS = ("LOW", "MID", "HIGH")


def get_threshold() -> int:
    """Resolve the cell-count threshold: SCOPE_SIZE_THRESHOLD env, else 60
    (scope-sizing-gate.md:107 — "Threshold tunable via SCOPE_SIZE_THRESHOLD
    env var (default 60)")."""
    return int(os.environ.get("SCOPE_SIZE_THRESHOLD", str(CELL_COUNT_THRESHOLD)))


def calculate_cell_count(axes: dict) -> int:
    """Multiply all axis value-counts. axes: {axis_id: value_count}.
    Empty axes is a caller error (scopeSizer.ts:70-73)."""
    if not axes:
        raise ValueError("calculate_cell_count: axes must be non-empty.")
    total = 1
    for count in axes.values():
        total *= count
    return total


def prune_axes(axes: dict, density_tier: str) -> dict:
    """DensityTier-conditional axis pruning, inline re-implementation of
    gridSkeleton.ts's defaultAxisPruner (scope-sizing-gate.md:26-28).
    Only caps a count already above the cap; never raises a count."""
    density_tier = (density_tier or "HIGH").upper()
    pruned = dict(axes)
    if density_tier == "HIGH":
        return pruned
    if density_tier == "LOW":
        if "lifecycle" in pruned:
            pruned["lifecycle"] = min(pruned["lifecycle"], 2)
        if "stakeholder" in pruned:
            pruned["stakeholder"] = min(pruned["stakeholder"], 2)
    elif density_tier == "MID":
        if "stakeholder" in pruned:
            pruned["stakeholder"] = min(pruned["stakeholder"], 3)
    return pruned


def recommend_split_strategy(features, layers) -> str:
    """feature/layer/hybrid by the 2x dominance rule (scopeSizer.ts:80-90)."""
    feature_count = len(features)
    layer_count = len(layers)
    if feature_count > layer_count * 2:
        return "feature"
    if layer_count > feature_count * 2:
        return "layer"
    return "hybrid"


def estimate_sub_plan_count(features, layers, lifecycle, risk_classes,
                             stakeholders, strategy, density_tier, threshold=None) -> int:
    """How many sub-plans a strategy needs (scopeSizer.ts:96-146).

    feature -> ceil(|features| / MAX_FEATURES_PER_SUBPLAN)
    layer   -> ceil(|layers| / MAX_LAYERS_PER_SUBPLAN)
    hybrid  -> search the (feature-chunk x layer-chunk) grid for the fewest
               sub-plans whose per-sub-plan cell count still fits under
               threshold; falls back to independent chunking when nothing fits.
    """
    if strategy == "feature":
        return math.ceil(len(features) / MAX_FEATURES_PER_SUBPLAN)
    if strategy == "layer":
        return math.ceil(len(layers) / MAX_LAYERS_PER_SUBPLAN)

    if threshold is None:
        threshold = get_threshold()

    axes = {
        "lifecycle": len(lifecycle),
        "risk_class": len(risk_classes),
        "stakeholder": len(stakeholders),
    }
    pruned = prune_axes(axes, density_tier)
    lc = pruned["lifecycle"]
    rc = pruned["risk_class"]
    sc = pruned["stakeholder"]

    best = None
    for f_count in (MAX_FEATURES_PER_SUBPLAN, 2, 1):
        for l_count in (MAX_LAYERS_PER_SUBPLAN, 2, 1):
            cells_per_plan = f_count * l_count * lc * rc * sc
            if cells_per_plan <= threshold:
                f_chunks = math.ceil(len(features) / f_count)
                l_chunks = math.ceil(len(layers) / l_count)
                candidate = f_chunks * l_chunks
                if best is None or candidate < best:
                    best = candidate

    if best is not None:
        return best

    # Fallback: chunk both dimensions independently (scopeSizer.ts:142-145).
    feature_chunks = math.ceil(len(features) / MAX_FEATURES_PER_SUBPLAN)
    layer_chunks = math.ceil(len(layers) / MAX_LAYERS_PER_SUBPLAN)
    return feature_chunks * layer_chunks


def estimate_scope(input_data: dict) -> dict:
    """Main entry point (scopeSizer.ts:151-181). input_data:
    {features (required), layers?, lifecycle?, risk_classes?, stakeholders?, density_tier?}
    Missing optional axes fall back to the FrankCode default axis values so the
    cell math matches a bare `estimateScope({features, density_tier})` call upstream."""
    features = list(input_data.get("features") or [])
    if not features:
        raise ValueError("estimate_scope: at least one feature must be supplied.")
    layers = list(input_data.get("layers") or DEFAULT_LAYERS)
    lifecycle = list(input_data.get("lifecycle") or DEFAULT_LIFECYCLE)
    risk_classes = list(input_data.get("risk_classes") or DEFAULT_RISK_CLASSES)
    stakeholders = list(input_data.get("stakeholders") or DEFAULT_STAKEHOLDERS)
    density_tier = (input_data.get("density_tier") or "HIGH").upper()

    axes = {
        "feature": len(features),
        "layer": len(layers),
        "lifecycle": len(lifecycle),
        "risk_class": len(risk_classes),
        "stakeholder": len(stakeholders),
    }
    projected_cells = calculate_cell_count(axes)
    pruned_cells = calculate_cell_count(prune_axes(axes, density_tier))

    threshold = get_threshold()
    strategy = recommend_split_strategy(features, layers)
    mode = "multi" if pruned_cells > threshold else "single"

    sub_plan_count = 1
    if mode == "multi":
        sub_plan_count = estimate_sub_plan_count(
            features, layers, lifecycle, risk_classes, stakeholders,
            strategy, density_tier, threshold,
        )

    return {
        "mode": mode,
        "projected_cells": projected_cells,
        "pruned_cells": pruned_cells,
        "threshold": threshold,
        "sub_plan_count": sub_plan_count,
        "split_strategy": strategy,
    }


def build_manifest_skeleton(input_data: dict, result: dict) -> dict:
    """Skeleton Plan Manifest (scope-sizing-gate.md:70-79) — 5 parts:
    subPlans[], dependencies[], sharedContracts[], masterRisk, intakeInheritance.
    Advisory: chunk boundaries only, never an auto-executed split."""
    features = list(input_data.get("features") or [])
    layers = list(input_data.get("layers") or DEFAULT_LAYERS)
    lifecycle = list(input_data.get("lifecycle") or DEFAULT_LIFECYCLE)
    risk_classes = list(input_data.get("risk_classes") or DEFAULT_RISK_CLASSES)
    stakeholders = list(input_data.get("stakeholders") or DEFAULT_STAKEHOLDERS)
    density_tier = (input_data.get("density_tier") or "HIGH").upper()
    strategy = result["split_strategy"]

    def _cells_for(feature_chunk, layer_chunk):
        axes = {
            "feature": len(feature_chunk),
            "layer": len(layer_chunk),
            "lifecycle": len(lifecycle),
            "risk_class": len(risk_classes),
            "stakeholder": len(stakeholders),
        }
        return calculate_cell_count(prune_axes(axes, density_tier))

    sub_plans = []
    if strategy == "feature":
        for i in range(0, len(features), MAX_FEATURES_PER_SUBPLAN):
            chunk = features[i:i + MAX_FEATURES_PER_SUBPLAN]
            sub_plans.append({
                "id": f"sub-{len(sub_plans) + 1}",
                "scope": {"features": chunk, "layers": layers},
                "estimatedCells": _cells_for(chunk, layers),
            })
    elif strategy == "layer":
        for i in range(0, len(layers), MAX_LAYERS_PER_SUBPLAN):
            chunk = layers[i:i + MAX_LAYERS_PER_SUBPLAN]
            sub_plans.append({
                "id": f"sub-{len(sub_plans) + 1}",
                "scope": {"features": features, "layers": chunk},
                "estimatedCells": _cells_for(features, chunk),
            })
    else:  # hybrid
        for i in range(0, len(features), MAX_FEATURES_PER_SUBPLAN):
            f_chunk = features[i:i + MAX_FEATURES_PER_SUBPLAN]
            for j in range(0, len(layers), MAX_LAYERS_PER_SUBPLAN):
                l_chunk = layers[j:j + MAX_LAYERS_PER_SUBPLAN]
                sub_plans.append({
                    "id": f"sub-{len(sub_plans) + 1}",
                    "scope": {"features": f_chunk, "layers": l_chunk},
                    "estimatedCells": _cells_for(f_chunk, l_chunk),
                })

    dependencies = []
    for i in range(len(sub_plans) - 1):
        dependencies.append({
            "from": sub_plans[i]["id"],
            "to": sub_plans[i + 1]["id"],
            "sharedLayers": layers,
        })

    return {
        "subPlans": sub_plans,
        "dependencies": dependencies,
        "sharedContracts": [],
        "masterRisk": [],
        "intakeInheritance": {"density_tier": density_tier, "threshold": result["threshold"]},
    }


def _split_csv(value):
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Deterministic scope-sizing gate: single-plan vs multi-plan split."
    )
    ap.add_argument("--features", required=True, help="comma-separated feature list")
    ap.add_argument("--layers", help="comma-separated layer list (default: ui,api,data,infra)")
    ap.add_argument("--lifecycle", help="comma-separated lifecycle list")
    ap.add_argument("--risk-classes", help="comma-separated risk-class list")
    ap.add_argument("--stakeholders", help="comma-separated stakeholder list")
    ap.add_argument("--density-tier", dest="density_tier", default="HIGH",
                    choices=DENSITY_TIERS, help="intake density tier (default HIGH)")
    args = ap.parse_args(argv)

    input_data = {
        "features": _split_csv(args.features),
        "layers": _split_csv(args.layers),
        "lifecycle": _split_csv(args.lifecycle),
        "risk_classes": _split_csv(args.risk_classes),
        "stakeholders": _split_csv(args.stakeholders),
        "density_tier": args.density_tier,
    }

    try:
        result = estimate_scope(input_data)
    except ValueError as exc:
        # e.g. --features "" leaves zero planner axes; emit a clean actionable
        # error + exit 2 rather than a raw traceback out of build_planner_axes.
        sys.stderr.write("scope_split: %s\n" % exc)
        return 2
    output = {"sizing": result}
    if result["mode"] == "multi":
        output["manifest"] = build_manifest_skeleton(input_data, result)

    sys.stdout.write(json.dumps(output, indent=2, ensure_ascii=False))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
