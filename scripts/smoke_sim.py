"""Run a small, repeatable AI2-THOR episode and save inspectable evidence.

This is a simulator diagnostic, not an EQA agent observation interface. The
trace intentionally contains only action feedback and the agent's own pose.
"""

import argparse
import hashlib
import json
import platform
from importlib.metadata import version
from pathlib import Path

import numpy as np
from ai2thor.controller import Controller
from PIL import Image


ACTIONS = ("RotateRight", "MoveAhead", "RotateLeft", "LookDown", "LookUp")


def inspect_event(event, run_number, step_number, action, output_dir):
    frame = event.frame
    if frame is None:
        raise RuntimeError("AI2-THOR returned no RGB frame")

    frame_name = f"run{run_number}_step{step_number:02d}.png"
    frame_path = output_dir / frame_name
    Image.fromarray(frame).save(frame_path)
    agent = event.metadata.get("agent", {})
    pose = {
        "position": agent.get("position"),
        "rotation": agent.get("rotation"),
        "cameraHorizon": agent.get("cameraHorizon"),
        "isStanding": agent.get("isStanding"),
    }
    return {
        "run": run_number,
        "step": step_number,
        "action": action,
        "success": None if action == "INITIAL" else event.metadata.get("lastActionSuccess"),
        "error": None if action == "INITIAL" else event.metadata.get("errorMessage") or None,
        "pose": pose,
        "frame": frame_name,
        "frame_sha256": hashlib.sha256(frame_path.read_bytes()).hexdigest(),
        "frame_shape": list(frame.shape),
    }


def comparable_state(record):
    return {key: record[key] for key in ("step", "action", "success", "error", "pose", "frame_shape")}


def frame_difference(first, second, output_dir):
    first_frame = np.asarray(Image.open(output_dir / first["frame"]), dtype=np.int16)
    second_frame = np.asarray(Image.open(output_dir / second["frame"]), dtype=np.int16)
    difference = np.abs(first_frame - second_frame)
    return {
        "exact_png_match": first["frame_sha256"] == second["frame_sha256"],
        "mean_absolute_pixel_difference": round(float(difference.mean()), 6),
        "max_absolute_pixel_difference": int(difference.max()),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", default="FloorPlan1")
    parser.add_argument("--output", type=Path, default=Path("runs/smoke"))
    parser.add_argument("--width", type=int, default=300)
    parser.add_argument("--height", type=int, default=300)
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        parser.error(f"output directory is not empty: {args.output}")
    args.output.mkdir(parents=True, exist_ok=True)

    controller = None
    runs = []
    try:
        controller = Controller(scene=args.scene, width=args.width, height=args.height)
        for run_number in (1, 2):
            event = controller.last_event if run_number == 1 else controller.reset(scene=args.scene)
            records = [inspect_event(event, run_number, 0, "INITIAL", args.output)]
            for step_number, action in enumerate(ACTIONS, start=1):
                event = controller.step(action=action)
                records.append(inspect_event(event, run_number, step_number, action, args.output))
            runs.append(records)
    finally:
        if controller is not None:
            controller.stop()

    with (args.output / "trace.jsonl").open("w", encoding="utf-8") as trace:
        for records in runs:
            for record in records:
                trace.write(json.dumps(record, ensure_ascii=False) + "\n")

    comparisons = []
    for first, second in zip(*runs):
        comparisons.append({
            "step": first["step"],
            "state_match": comparable_state(first) == comparable_state(second),
            **frame_difference(first, second, args.output),
        })
    summary = {
        "scene": args.scene,
        "actions": ACTIONS,
        "image_size": [args.width, args.height],
        "ai2thor_version": version("ai2thor"),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "frames": sum(map(len, runs)),
        "action_successes": [sum(r["success"] is True for r in records) for records in runs],
        "reset_comparisons": comparisons,
        "all_states_match_across_reset": all(row["state_match"] for row in comparisons),
        "all_pngs_match_exactly": all(row["exact_png_match"] for row in comparisons),
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Trace and PNG frames: {args.output.resolve()}")
    if not summary["all_states_match_across_reset"]:
        raise SystemExit("State/action replay differs after reset; inspect summary.json")


if __name__ == "__main__":
    main()
