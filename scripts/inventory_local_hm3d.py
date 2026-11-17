"""List OpenEQA HM3D questions whose matching scene and navmesh exist locally."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, default=Path("data/raw/route-a/open-eqa-v0.json"))
    parser.add_argument("--scenes", type=Path, default=Path("data/raw/route-a/example"))
    parser.add_argument("--reference-trace", type=Path, default=Path("runs/habitat-washer-20/trace.json"))
    parser.add_argument("--output", type=Path, default=Path("data/local_hm3d_dev_inventory.json"))
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Choose a new output path to preserve the existing inventory")
    raw = json.loads(args.questions.read_text())
    local = {path.name.removesuffix(".basis.glb"): path
             for path in args.scenes.glob("*.basis.glb") if path.with_suffix(".navmesh").is_file()}
    selected = []
    for row in raw:
        history = row["episode_history"]
        if history.startswith("hm3d-v0/") and history.rsplit("-", 1)[-1] in local:
            selected.append({key: row[key] for key in
                             ("question_id", "episode_history", "category", "question")})
    selected.sort(key=lambda item: (item["episode_history"], item["question_id"]))
    trace = json.loads(args.reference_trace.read_text())
    start = trace["frames"][0]
    reference_scene = trace["scene"].removesuffix(".basis.glb")
    if reference_scene not in local:
        raise ValueError("Reference start belongs to a scene absent from local assets")
    manifest = {"schema_version": 1, "source_questions_sha256": sha256(args.questions),
                "purpose": "development candidates; no formal evaluation split assigned",
                "start_source": "local seed 17 navigable point, not an official OpenEQA pose",
                "reference_start": {"scene_id": reference_scene, "position": start["position"],
                                    "rotation_wxyz": start["rotation_wxyz"],
                                    "rgb_sha256": start["sha256"]},
                "scene_assets": [{"scene_id": scene_id, "glb": str(path),
                                  "navmesh": str(path.with_suffix(".navmesh"))}
                                 for scene_id, path in sorted(local.items())],
                "question_count": len(selected), "questions": selected}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"local_scene_question_counts": dict(Counter(
        q["episode_history"].rsplit("-", 1)[-1] for q in selected)),
        "question_count": len(selected), "output": str(args.output)}))


if __name__ == "__main__":
    main()
