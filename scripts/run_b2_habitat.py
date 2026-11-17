"""Run one 20-action question-guided OpenEQA episode with local MLX and Habitat."""
import argparse
import json
import re
import subprocess
import time
import uuid
from importlib.metadata import version
from pathlib import Path

from habitat_paired_pilot import BUDGET, RECOVERY_CONTROLS, normalize_prediction
from run_b0 import sha256_file
from run_b1_random import select_frame_steps

PREFIX = "C6_STEP "


def read_step(worker):
    while True:
        line = worker.stdout.readline()
        if not line:
            raise RuntimeError(f"Habitat worker stopped with exit code {worker.poll()}")
        if line.startswith(PREFIX):
            return json.loads(line[len(PREFIX):])


def infer(model, processor, config, prompt, images):
    from mlx_vlm import generate
    from mlx_vlm.prompt_utils import apply_chat_template

    formatted = apply_chat_template(processor, config, prompt, num_images=len(images))
    response = generate(model, processor, formatted, image=[str(p) for p in images],
                        temperature=0, seed=0, max_tokens=96, verbose=False)
    return response.text.strip(), round(response.peak_memory, 3)


def choose_action(raw, previous_collision):
    candidate = raw.strip()
    fence = re.fullmatch(r"```(?:json)?\s*\n(.*?)\n```", candidate,
                         flags=re.DOTALL | re.IGNORECASE)
    if fence:
        candidate = fence.group(1).strip()
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        parsed = None
    action = parsed.get("action") if isinstance(parsed, dict) else None
    if action in RECOVERY_CONTROLS:
        return action, True
    return ("RotateRight" if previous_collision else "MoveAhead"), False


def main():
    from mlx_vlm import load
    from mlx_vlm.utils import load_config

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", type=Path, required=True)
    parser.add_argument("--question-id", type=uuid.UUID, required=True)
    parser.add_argument("--data", type=Path, default=Path("data/raw/route-a/open-eqa-v0.json"))
    parser.add_argument("--model", type=Path, default=Path("models/qwen3-vl-2b-instruct-4bit"))
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    scene = args.scene.resolve(strict=True)
    rows = json.loads(args.data.read_text())
    questions = [r["question"] for r in rows if r["question_id"] == str(args.question_id)
                 and r["episode_history"].startswith("hm3d-v0/")
                 and r["episode_history"].rsplit("-", 1)[-1] == scene.name.split(".")[0]]
    if len(questions) != 1:
        parser.error("Question must match one HM3D scene")
    if args.run.exists():
        parser.error("Choose a new run directory")
    model, processor = load(str(args.model.resolve()))
    config = load_config(str(args.model.resolve()))
    habitat_python = Path("runs/habitat-env/bin/python").resolve(strict=True)
    command = [str(habitat_python), "-u", "scripts/habitat_step_worker.py",
               "--scene", str(scene), "--run", str(args.run)]
    started = time.perf_counter()
    decisions = []
    with (args.run.parent / (args.run.name + "-worker.log")).open("x") as worker_log:
        with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=worker_log, text=True, bufsize=1) as worker:
            try:
                current = read_step(worker)
                if current["step"] != 0:
                    raise RuntimeError("Worker did not start at step zero")
                for step in range(1, BUDGET + 1):
                    image = Path(current["image"])
                    if sha256_file(image) != current["sha256"]:
                        raise RuntimeError("Observation differs from worker manifest")
                    previous_collision = current["collided"] is True
                    prompt = ("You are exploring a home to answer the question. Current camera image only. "
                              "The previous move collided with an obstacle. " if previous_collision else
                              "You are exploring a home to answer the question. Current camera image only. ")
                    prompt += (f"Action {step} of 20. Choose exactly one action from "
                               "MoveAhead, RotateLeft, RotateRight. Turns are 90 degrees and moves are 0.25 m. "
                               "Use the image to seek evidence. Do not answer the question yet. "
                               "Return JSON only with an action key. "
                               f"Question: {questions[0]}")
                    raw, peak = infer(model, processor, config, prompt, [image])
                    action, valid = choose_action(raw, previous_collision)
                    worker.stdin.write(json.dumps({"action": action}) + "\n")
                    worker.stdin.flush()
                    next_observation = read_step(worker)
                    if next_observation["step"] != step:
                        raise RuntimeError("Worker step mismatch")
                    decisions.append(dict(step=step, observed_image=image.name,
                                          observed_sha256=current["sha256"], prompt=prompt,
                                          raw=raw, action=action, valid_action_json=valid,
                                          previous_collision=previous_collision, peak_gb=peak,
                                          result_collision=next_observation["collided"]))
                    (args.run / "decisions.json").write_text(json.dumps(decisions, indent=2) + "\n")
                    current = next_observation
                worker.stdin.close()
                if worker.wait(timeout=30):
                    raise RuntimeError("Worker failed after the final step")
            finally:
                if worker.poll() is None:
                    worker.terminate()
                    worker.wait(timeout=30)
    trace = json.loads((args.run / "trace.json").read_text())
    steps = select_frame_steps(BUDGET)
    selected = [args.run / trace["frames"][i]["image"] for i in steps]
    prompt = ("Use only these four photographs in order. Answer briefly in English. "
              "If evidence is insufficient, answer unknown and give frame 0. "
              'Return JSON only: {"answer":"...","frame":0}. Question: ' + questions[0])
    raw, peak = infer(model, processor, config, prompt, selected)
    answer, frame, valid = normalize_prediction(raw, len(selected))
    result = dict(question_id=str(args.question_id), question=questions[0], scene=scene.name,
                  model=str(args.model), model_weights_sha256=sha256_file(args.model / "model.safetensors"),
                  mlx_vlm_version=version("mlx-vlm"), budget=BUDGET, actions_used=len(decisions),
                  selected_steps=steps, answer=answer, raw=raw, valid_answer_json=valid,
                  cited_step=steps[frame - 1] if valid and frame else None,
                  decision_json_valid_count=sum(d["valid_action_json"] for d in decisions),
                  final_peak_gb=peak, elapsed_s=round(time.perf_counter() - started, 3),
                  trace_sha256=sha256_file(args.run / "trace.json"))
    (args.run / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
