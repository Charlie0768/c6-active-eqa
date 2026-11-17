"""Keep Habitat alive while a separate MLX process sends one action at a time."""
import argparse
import json
import sys
from pathlib import Path

import habitat_sim as hs
from PIL import Image

from habitat_paired_pilot import BUDGET, RECOVERY_CONTROLS
from habitat_smoke import CAMERA_SHAPE, camera_config
from run_b0 import sha256_file

PREFIX = "C6_STEP "


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    scene = args.scene.resolve(strict=True)
    navmesh = scene.with_suffix(".navmesh").resolve(strict=True)
    args.run.mkdir(parents=True, exist_ok=False)
    space = {action: hs.agent.ActionSpec(name, hs.agent.ActuationSpec(amount))
             for action, (name, amount) in RECOVERY_CONTROLS.items()}
    frames = []
    with hs.Simulator(camera_config(scene, space)) as sim:
        if not sim.pathfinder.load_nav_mesh(str(navmesh)):
            raise RuntimeError("Cannot load navigation mesh")
        sim.pathfinder.seed(17)
        start = hs.AgentState()
        start.position = sim.pathfinder.get_random_navigable_point()
        sim.get_agent(0).set_state(start)
        for step in range(BUDGET + 1):
            if step:
                line = sys.stdin.readline()
                if not line:
                    raise RuntimeError("Controller disconnected before 20 actions")
                action = json.loads(line)["action"]
                if action not in RECOVERY_CONTROLS:
                    raise ValueError(f"Invalid action: {action}")
                obs = sim.step(action)
            else:
                action = None
                obs = sim.get_sensor_observations()
            rgb = obs["rgb"][:, :, :3]
            if rgb.shape != (*CAMERA_SHAPE, 3):
                raise RuntimeError(f"Invalid RGB shape at step {step}")
            path = args.run / f"step-{step:02d}.png"
            Image.fromarray(rgb).save(path)
            state = sim.get_agent(0).get_state()
            frames.append(dict(step=step, image=path.name, sha256=sha256_file(path),
                               action=action, collided=None if step == 0 else bool(obs["collided"]),
                               position=state.position.tolist(), rotation_wxyz=state.rotation.components.tolist()))
            trace = dict(scene=scene.name, start_seed=17, controls=RECOVERY_CONTROLS,
                         budget=BUDGET, actions_used=step, frames=frames)
            (args.run / "trace.json").write_text(json.dumps(trace, indent=2) + "\n")
            print(PREFIX + json.dumps({"step": step, "image": str(path.resolve()),
                                       "sha256": frames[-1]["sha256"],
                                       "collided": frames[-1]["collided"]}), flush=True)


if __name__ == "__main__":
    main()
