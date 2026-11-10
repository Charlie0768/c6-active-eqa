"""One real AI2-THOR action followed by a two-frame local VL answer.

The action is scripted in S04. Search policies and scoring belong to later
work units. Model input is built from a small allowlist, never full metadata.
"""

import argparse
import hashlib
import json
import platform
import resource
import subprocess
import sys
import time
from importlib.metadata import version
from pathlib import Path

from PIL import Image


ACTION = "RotateRight"
ALLOWED_ACTIONS = frozenset({"RotateRight", "RotateLeft", "MoveAhead", "LookUp", "LookDown"})
QUESTION = "这两张画面中是否看到了冰箱？"


def consume_action(action, used, budget):
    """Count attempted actions before execution, including a failed action."""
    if action not in ALLOWED_ACTIONS:
        raise ValueError(f"action is not allowed: {action}")
    if used >= budget:
        raise RuntimeError("action budget exhausted")
    return used + 1


def action_success(metadata):
    """Project simulator metadata to one model-visible boolean."""
    value = metadata.get("lastActionSuccess")
    if not isinstance(value, bool):
        raise ValueError("missing boolean lastActionSuccess")
    return value


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_frame(event, path):
    if event.frame is None:
        raise RuntimeError("AI2-THOR returned no RGB frame")
    Image.fromarray(event.frame).save(path)
    return {"frame_number": 1 if path.stem == "frame1" else 2,
            "file": path.name, "sha256": sha256_file(path),
            "shape": list(event.frame.shape)}


def make_observation(question, frames, action, success, used, budget):
    """The entire allowlisted input manifest for the VLM."""
    return {
        "question": question,
        "frames": frames,
        "previous_action": {"name": action, "success": success},
        "actions_used": used,
        "action_budget": budget,
    }


def make_prompt(observation):
    status = "成功" if observation["previous_action"]["success"] else "失败"
    return (
        "你会按顺序看到两张第一人称图像：图1是行动前，图2是行动后。"
        f"执行的动作是 {observation['previous_action']['name']}，动作{status}。"
        f"已用 {observation['actions_used']}/{observation['action_budget']} 次行动。"
        f"问题：{observation['question']}"
        '请只根据这两张图输出 JSON：{"answer":"是/否/不确定",'
        '"evidence_frame":1或2或null}。'
        "图1或图2只填实际提供证据的那一帧；不要猜测画面外内容。"
    )


def rss_bytes(pid):
    if not pid:
        return None
    result = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)],
                            capture_output=True, text=True, check=False)
    return int(result.stdout.strip()) * 1024 if result.returncode == 0 and result.stdout.strip() else None


def run_episode(args):
    from ai2thor.controller import Controller
    from mlx_vlm import generate, load
    from mlx_vlm.prompt_utils import apply_chat_template
    from mlx_vlm.utils import load_config
    from smoke_vl import MODEL_REPO, MODEL_REVISION, MODEL_WEIGHTS_SHA256, parse_answer

    model_file = args.model / "model.safetensors"
    if sha256_file(model_file) != MODEL_WEIGHTS_SHA256:
        raise ValueError("model weights differ from the S03 pinned checkpoint")

    started = time.perf_counter()
    controller = None
    try:
        controller = Controller(scene="FloorPlan1", width=300, height=300)
        controller_started = time.perf_counter()
        frame1 = save_frame(controller.last_event, args.output / "frame1.png")

        used = consume_action(ACTION, 0, 1)
        event = controller.step(action=ACTION)
        success = action_success(event.metadata)
        frame2 = save_frame(event, args.output / "frame2.png")
        acted = time.perf_counter()

        observation = make_observation(QUESTION, [frame1, frame2], ACTION, success, used, 1)
        prompt = make_prompt(observation)
        unity_pid = controller.unity_pid
        unity_rss_before = rss_bytes(unity_pid)
        unity_alive_before = controller.server.unity_proc.poll() is None

        model, processor = load(str(args.model.resolve()))
        config = load_config(str(args.model.resolve()))
        model_loaded = time.perf_counter()
        formatted_prompt = apply_chat_template(processor, config, prompt, num_images=2)
        image_placeholder_count = formatted_prompt.count("<|image_pad|>")
        if image_placeholder_count != 2:
            raise RuntimeError(f"expected two image placeholders, found {image_placeholder_count}")
        response = generate(model, processor, formatted_prompt,
                            image=[str((args.output / frame["file"]).resolve()) for frame in observation["frames"]],
                            max_tokens=128, temperature=0, seed=0, verbose=False)
        answered = time.perf_counter()
        unity_rss_after = rss_bytes(unity_pid)
        unity_alive_after = controller.server.unity_proc.poll() is None

        raw = response.text.strip()
        parsed, code_fence_removed = parse_answer(raw)
        valid = (isinstance(parsed, dict)
                 and set(parsed) == {"answer", "evidence_frame"}
                 and parsed["answer"] in ("是", "否", "不确定")
                 and parsed["evidence_frame"] in (1, 2, None)
                 and (parsed["answer"] != "是" or parsed["evidence_frame"] in (1, 2)))
        record = {
            "status": "completed" if valid else "invalid_answer_format",
            "scene": "FloorPlan1",
            "policy": "scripted_one_step",
            "model_repo": MODEL_REPO,
            "model_revision": MODEL_REVISION,
            "model_weights_sha256": MODEL_WEIGHTS_SHA256,
            "model_quantization": "MLX 4-bit community conversion",
            "ai2thor_version": version("ai2thor"),
            "mlx_vlm_version": version("mlx-vlm"),
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "model_input_allowlist": observation,
            "model_prompt": prompt,
            "formatted_prompt_sha256": hashlib.sha256(formatted_prompt.encode("utf-8")).hexdigest(),
            "image_placeholder_count": image_placeholder_count,
            "raw_answer": raw,
            "parsed_answer": parsed,
            "json_code_fence_removed": code_fence_removed,
            "valid_answer_json": valid,
            "prompt_tokens": response.prompt_tokens,
            "generation_tokens": response.generation_tokens,
            "timing_seconds": {
                "simulator_start": round(controller_started - started, 3),
                "capture_and_action": round(acted - controller_started, 3),
                "model_load": round(model_loaded - acted, 3),
                "model_generate": round(answered - model_loaded, 3),
                "total_before_cleanup": round(answered - started, 3),
            },
            "resource": {
                "mlx_peak_memory_gb": round(response.peak_memory, 3),
                "python_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                "unity_pid": unity_pid,
                "unity_rss_bytes_before_model": unity_rss_before,
                "unity_rss_bytes_after_model": unity_rss_after,
                "unity_alive_before_model": unity_alive_before,
                "unity_alive_after_model": unity_alive_after,
            },
            "paid_api_cost": 0,
        }
        (args.output / "episode.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return record
    finally:
        if controller is not None:
            controller.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=Path("models/qwen3-vl-2b-instruct-4bit"))
    parser.add_argument("--output", type=Path, default=Path("runs/s04-one-step"))
    args = parser.parse_args()
    if not (args.model / "model.safetensors").is_file():
        parser.error("pinned local model weights are missing")
    if args.output.exists() and any(args.output.iterdir()):
        parser.error(f"output directory is not empty: {args.output}")
    args.output.mkdir(parents=True, exist_ok=True)
    record = run_episode(args)
    print(json.dumps({
        "status": record["status"],
        "observation": record["model_input_allowlist"],
        "answer": record["parsed_answer"],
        "timing_seconds": record["timing_seconds"],
        "resource": record["resource"],
    }, ensure_ascii=False, indent=2))
    print(f"Full record: {(args.output / 'episode.json').resolve()}")
    if record["status"] != "completed":
        sys.exit("Model output failed JSON schema; inspect episode.json")


if __name__ == "__main__":
    main()
