"""用一个 HM3D 房屋实测 Habitat 相机、转向、前进和起点复位。"""
import argparse
import json
from pathlib import Path

import habitat_sim
import magnum as mn
import numpy as np
from PIL import Image


CAMERA_SHAPE = (540, 960)


def camera_config(scene, action_space=None):
    # Mac 的普通构建通过本机 OpenGL 渲染。只创建一个彩色相机。
    backend = habitat_sim.SimulatorConfiguration()
    backend.scene_id = str(scene)
    backend.enable_physics = False
    camera = habitat_sim.CameraSensorSpec()
    camera.uuid = "rgb"
    camera.sensor_type = habitat_sim.SensorType.COLOR
    height, width = CAMERA_SHAPE
    camera.resolution = [height, width]
    camera.position = mn.Vector3(0, 1.5, 0)
    agent_cfg = habitat_sim.agent.AgentConfiguration()
    agent_cfg.sensor_specifications = [camera]
    if action_space is not None:
        agent_cfg.action_space = action_space
    return habitat_sim.Configuration(backend, [agent_cfg])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    scene = args.scene.resolve(strict=True)
    navmesh = scene.with_name(scene.name.split(".")[0] + ".basis.navmesh")
    if not navmesh.is_file():
        parser.error(f"Missing navigation mesh: {navmesh}")
    args.output.mkdir(parents=True, exist_ok=False)

    height, width = CAMERA_SHAPE
    with habitat_sim.Simulator(camera_config(scene)) as sim:
        if not sim.pathfinder.load_nav_mesh(str(navmesh)):
            raise RuntimeError("Could not load the scene navigation mesh")
        # 此固定种子起点用于工程测试。正式实验另行登记每道题的起点。
        sim.pathfinder.seed(17)
        start = habitat_sim.AgentState()
        start.position = sim.pathfinder.get_random_navigable_point()
        agent = sim.get_agent(0)
        agent.set_state(start)
        frames, trace = [], []
        for index, action in enumerate(("start", "turn_right", "move_forward", "restore")):
            if action == "restore":
                agent.set_state(start)
            obs = (sim.get_sensor_observations() if action in ("start", "restore")
                   else sim.step(action))
            rgb = obs["rgb"][:, :, :3].copy()
            if rgb.shape != (height, width, 3) or rgb.min() == rgb.max():
                raise RuntimeError("Invalid camera image")
            name = f"{index}-{action}.png"
            Image.fromarray(rgb).save(args.output / name)
            state = agent.get_state()
            trace.append(dict(action=action, image=name, position=state.position.tolist(),
                              rotation=state.rotation.components.tolist()))
            frames.append(rgb)
        if np.array_equal(frames[0], frames[1]) or not np.array_equal(frames[0], frames[3]):
            raise RuntimeError("Turn or restore did not produce the expected images")
        record = dict(scene=scene.name, seed=17, trace=trace,
                      forward_m=float(np.linalg.norm(np.subtract(trace[2]["position"], trace[1]["position"]))))
        (args.output / "trace.json").write_text(json.dumps(record, indent=2) + "\n")
        print(json.dumps(record))


if __name__ == "__main__":
    main()
