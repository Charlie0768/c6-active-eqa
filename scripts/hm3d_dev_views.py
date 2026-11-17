"""从同一套住宅生成固定开发图。离线挑出证据，用于区分找不到线索和看不懂线索。"""
import argparse
import json
import math
from pathlib import Path

import habitat_sim
import magnum as mn
import numpy as np
from habitat_sim.utils.common import quat_from_angle_axis
from PIL import Image, ImageDraw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--height", type=int, default=270,
                        help="原生 16:9 相机的输出高度，如 270、540、720 或 1080")
    parser.add_argument("--navmesh", type=Path, help="两种 GLB 共用同一套住宅的导航网格")
    args = parser.parse_args()
    if args.height <= 0 or args.height % 9:
        parser.error("--height 需为 9 的正整数倍，以保持精确的 16:9 宽高比")
    scene = args.scene.resolve(strict=True)
    navmesh = (args.navmesh or scene.with_suffix(".navmesh")).resolve(strict=True)
    args.output.mkdir(parents=True, exist_ok=False)
    cfg = habitat_sim.SimulatorConfiguration()
    cfg.scene_id = str(scene)
    cfg.enable_physics = False
    sensor = habitat_sim.CameraSensorSpec()
    sensor.uuid = "rgb"
    sensor.sensor_type = habitat_sim.SensorType.COLOR
    width = args.height * 16 // 9
    sensor.resolution = [args.height, width]
    sensor.position = mn.Vector3(0, 1.5, 0)
    agent_cfg = habitat_sim.agent.AgentConfiguration()
    agent_cfg.sensor_specifications = [sensor]
    views = []
    # 选点与题目和参考答案无关。瞬移仅用于准备这份离线读图开发集。
    with habitat_sim.Simulator(habitat_sim.Configuration(cfg, [agent_cfg])) as sim:
        if not sim.pathfinder.load_nav_mesh(str(navmesh)):
            raise RuntimeError(f"无法加载导航网格 {navmesh}")
        sim.pathfinder.seed(17)
        agent = sim.get_agent(0)
        for point in range(32):
            pos = sim.pathfinder.get_random_navigable_point()
            if point % 8 == 0:
                sheet = Image.new("RGB", (4 * 210, 8 * 137))
                draw = ImageDraw.Draw(sheet)
            for heading in range(4):
                state = habitat_sim.AgentState()
                state.position = pos
                state.rotation = quat_from_angle_axis(heading * math.pi / 2, np.array([0., 1., 0.]))
                agent.set_state(state)
                rgb = Image.fromarray(sim.get_sensor_observations()["rgb"][:, :, :3])
                name = f"p{point:02d}-{heading}.png"
                rgb.save(args.output / name)
                x, y = heading * 210, (point % 8) * 137
                sheet.paste(rgb.resize((210, 118)), (x, y))
                draw.text((x + 3, y + 119), name, fill="white")
                views.append(dict(image=name, position=list(pos), heading_deg=heading * 90))
            if point % 8 == 7:
                sheet.save(args.output / f"sheet-{point // 8}.jpg")
    manifest = dict(scene=scene.name, seed=17, width=width, height=args.height, views=views)
    (args.output / "views.json").write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
