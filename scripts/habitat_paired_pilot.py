"""同一起始 RGB 的 Habitat B0/B1。两个命令分别在 Habitat 与 MLX 环境运行。"""
import argparse
import json
import time
import uuid
from importlib.metadata import version
from pathlib import Path

from PIL import Image

from one_step_episode import consume_action
from run_b0 import sha256_file
from run_b1_random import sample_actions, select_frame_steps

BUDGET = 20
# 距离单位为米，旋转角度为度。抬头／低头仅旋转相机。
CONTROLS = {"RotateRight": ("turn_right", 10), "RotateLeft": ("turn_left", 10),
            "MoveAhead": ("move_forward", 0.25), "LookUp": ("look_up", 10),
            "LookDown": ("look_down", 10)}


def render(args):
    import habitat_sim as hs
    from habitat_smoke import CAMERA_SHAPE, camera_config

    scene = args.scene.resolve(strict=True)
    navmesh = scene.with_suffix(".navmesh").resolve(strict=True)
    space = {action: hs.agent.ActionSpec(name, hs.agent.ActuationSpec(amount))
             for action, (name, amount) in CONTROLS.items()}
    sequence = sample_actions(args.seed, BUDGET)
    frames = []
    with hs.Simulator(camera_config(scene, space)) as sim:
        if not sim.pathfinder.load_nav_mesh(str(navmesh)):
            raise RuntimeError("Cannot load navigation mesh")
        args.run.mkdir(parents=True, exist_ok=False)
        sim.pathfinder.seed(17)
        start = hs.AgentState()
        start.position = sim.pathfinder.get_random_navigable_point()
        agent = sim.get_agent(0)
        agent.set_state(start)
        # B0 与 B1 共享同一张第 0 帧，彻底固定初始观察。
        used = 0
        for action in [None, *sequence]:
            if action is None:
                obs = sim.get_sensor_observations()
            else:
                used = consume_action(action, used, BUDGET)
                obs = sim.step(action)
            rgb = obs["rgb"][:, :, :3]
            if rgb.shape != (*CAMERA_SHAPE, 3) or rgb.max() == rgb.min():
                raise RuntimeError(f"Invalid RGB at step {used}")
            path = args.run / f"step-{used:02d}.png"
            Image.fromarray(rgb).save(path)
            state = agent.get_state()
            camera = state.sensor_states["rgb"]
            frames.append(dict(step=used, image=path.name, sha256=sha256_file(path),
                               action=action, collided=None if action is None else bool(obs["collided"]),
                               position=state.position.tolist(), rotation_wxyz=state.rotation.components.tolist(),
                               camera_rotation_wxyz=camera.rotation.components.tolist()))
    trace = dict(scene=scene.name, habitat_version=version("habitat-sim"), start_seed=17,
                 start_source="local seeded navigable point", action_seed=args.seed, controls=CONTROLS,
                 budget=BUDGET, actions_used=used, frames=frames)
    (args.run / "trace.json").write_text(json.dumps(trace, indent=2) + "\n")


def answer(args):
    from smoke_vl import parse_answer
    from vision_probe import mlx_engine

    output = args.run / f"{args.question_id}.json"
    if output.exists():
        raise FileExistsError(output)
    trace = json.loads((args.run / "trace.json").read_text())
    scene = trace["scene"].split(".")[0]
    rows = json.loads(args.data.read_text())
    questions = [r["question"] for r in rows if r["question_id"] == args.question_id
                 and r["episode_history"].startswith("hm3d-v0/")
                 and r["episode_history"].rsplit("-", 1)[-1] == scene]
    if len(questions) != 1:
        raise ValueError("Question must uniquely match the rendered HM3D scene")
    frames = trace["frames"]
    if trace["actions_used"] != BUDGET or [f["step"] for f in frames] != list(range(BUDGET + 1)):
        raise ValueError("Incomplete 20-action trajectory")
    predict, model = mlx_engine("2")
    records = []
    for condition, used in [("B0", 0), ("B1", BUDGET)]:
        steps = select_frame_steps(used)
        images = [args.run / frames[i]["image"] for i in steps]
        if any(sha256_file(p) != frames[i]["sha256"] for p, i in zip(images, steps)):
            raise ValueError("Selected image differs from the recorded RGB")
        prompt = (f"Use only the supplied photograph(s), numbered 1 to {len(steps)} in order. "
                  "Answer briefly in English and give the number of the photo that supports your answer. "
                  "If evidence is insufficient, answer unknown and give frame 0. "
                  'Return JSON only: {"answer":"...", "frame":0}. Question: ' + questions[0])
        begin = time.perf_counter()
        raw, peak = predict(prompt, images)
        parsed, _ = parse_answer(raw.strip())
        valid = (isinstance(parsed, dict) and isinstance(parsed.get("answer"), str)
                 and bool(parsed["answer"].strip()) and type(parsed.get("frame")) is int
                 and ((parsed["answer"].strip().lower() == "unknown" and parsed["frame"] == 0)
                      or (parsed["answer"].strip().lower() != "unknown" and 1 <= parsed["frame"] <= len(steps))))
        cited = steps[parsed["frame"] - 1] if valid and parsed["frame"] else None
        records.append(dict(condition=condition, actions_used=used, selected_steps=steps,
                            prompt=prompt, raw=raw, valid=valid, cited_step=cited,
                            elapsed_s=round(time.perf_counter() - begin, 3), peak_gb=peak))
    result = dict(question_id=args.question_id, question=questions[0], scene=scene,
                  trace_sha256=sha256_file(args.run / "trace.json"), model=model, predictions=records)
    with output.open("x") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
    print(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sim = sub.add_parser("render")
    sim.add_argument("--scene", type=Path, required=True)
    sim.add_argument("--seed", type=int, default=17)
    vl = sub.add_parser("answer")
    vl.add_argument("--question-id", required=True, type=uuid.UUID)
    vl.add_argument("--data", type=Path, default=Path("data/raw/route-a/open-eqa-v0.json"))
    for command in (sim, vl):
        command.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "render":
        render(args)
    else:
        args.question_id = str(args.question_id)
        answer(args)


if __name__ == "__main__":
    main()
