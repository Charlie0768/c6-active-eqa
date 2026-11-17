# Mac 上运行 OpenEQA 的主动探索环境

从仓库根目录执行。Apple M4 使用 osx-arm64 的普通 Habitat-Sim 0.3.3 包和 Python 3.9；本地 Qwen3-VL 使用另一个 Python 3.11 环境。通过 RGB 图片交接，两套依赖可以独立升级。服务器的 headless 参数依赖 EGL，Mac 使用本机图形会话。[Habitat 安装说明](https://github.com/facebookresearch/habitat-sim#installation) · [arm64 安装包](https://anaconda.org/aihabitat/habitat-sim/files)

```bash
conda create -y -p ./runs/habitat-env --override-channels -c conda-forge -c aihabitat python=3.9 habitat-sim=0.3.3 'numpy<2'
mkdir -p data/raw/route-a
curl -fL https://raw.githubusercontent.com/facebookresearch/open-eqa/main/data/open-eqa-v0.json -o data/raw/route-a/open-eqa-v0.json
curl -fL https://media.githubusercontent.com/media/matterport/habitat-matterport-3dresearch/main/example/hm3d-example-habitat-v0.2.tar -o data/raw/route-a/hm3d-example-habitat-v0.2.tar
shasum -a 256 data/raw/route-a/hm3d-example-habitat-v0.2.tar
mkdir -p data/raw/route-a/example
tar -xf data/raw/route-a/hm3d-example-habitat-v0.2.tar -C data/raw/route-a/example
```

住宅包 SHA-256 为 `bbafcfb13e84f404e95fb99022f0d6702571be795f3f711ad396d0bae5b33ef7`。官方题库本次下载的 SHA-256 为 `a64dd101133213fa3b5ca31e5af8216662471aa34894b443d803f497757557ee`。要复现安装环境，请先确定本机终端为 arm64。每次验证使用一个新的输出目录。[Matterport 样例与下载清单](https://github.com/matterport/habitat-matterport-3dresearch)

## 从样例扩展到正式测试

用题目记录中的 episode_history 对应 HM3D 住宅 ID，再按该 ID 加载验证集的 .basis.glb 和同住宅的导航网格。完整验证集需申请 Matterport 访问权，通过其数据下载工具下载。公开 Git 仓库只存代码与记录。参见 [HM3D 申请入口](https://matterport.com/habitat-matterport-3d-research-dataset) 和 [OpenEQA 原始数据说明](https://github.com/facebookresearch/open-eqa/blob/main/data/README.md)。

OpenEQA 的原始位姿下载链接在此次访问时返回 Dropbox 的 Link Expired 页面。下面的本机测试将固定种子生成的可行走点记入轨迹。正式实验须记录起点来源，同一题的所有策略从完全相同的位置和朝向出发。若用自定起点，应在报告中写明该协议差异。

## 本机实测与复现

```bash
scene=$(find data/raw/route-a/example -name GLAQ4DNUx5U.basis.glb -print -quit)
runs/habitat-env/bin/python scripts/habitat_smoke.py --scene "$scene" --output runs/habitat-demo
HF_HUB_OFFLINE=1 .venv-vl/bin/python scripts/habitat_question_smoke.py --run runs/habitat-demo --question-id b70465b8-53a3-436f-b12f-2d8cdf8f1856
```

第二条推理命令需先配置 MLX 并下载固定模型，见 [S03 环境记录](ENVIRONMENT.md)。M4 实测 Python 3.9.23、NumPy 1.26.4、Habitat-Sim 0.3.3，渲染器报告 Apple M4、OpenGL 4.1 Metal。住宅 GLAQ4DNUx5U 匹配 11 条官方题。480×270 彩色相机完成起点、右转 10°、前进 0.250 米、复位四次观测，复位帧与起始帧逐像素相同。样例只装了 RGB 渲染和导航资源，日志提示缺少语义标注。起始画面是石墙和窗口，看不见洗衣机。本地 2B 回答“洗衣机上面有什么”时输出 unknown。原题参考答案为 The dryer。这是起始视角的一次推理，待测问题引导探索能否找到洗衣区域。

## Windows RTX 3060 6 GB 的推理验收

先在这张卡上试 2B 4-bit、batch 1、短上下文，每步一图、最终最多四图。Windows 可用 Ollama 的 qwen3-vl:2b（Q4_K_M，下载约 1.9 GB），Mac 已测的是 MLX 量化，二者分别记后端版本。正式策略对比固定在同一后端。这条命令验证的是 Windows 读图；整套单机部署还需在同一台机器上验证 Habitat 与模型同时运行时的显存。

安装支持 NVIDIA 的 Windows 版 Ollama，复制本机测试的四张 PNG 到 Windows 的 frames 目录。在另一终端运行 `nvidia-smi -l 1` 记录专用显存，在 PowerShell 执行：

```powershell
ollama pull qwen3-vl:2b
$frames = @(Get-ChildItem ./frames/*.png | Sort-Object Name | Select-Object -First 4)
if ($frames.Count -ne 4) { throw "Expected four PNG frames" }
foreach ($n in 1,4) {
    $images = @($frames | Select-Object -First $n | ForEach-Object { [Convert]::ToBase64String([IO.File]::ReadAllBytes($_.FullName)) })
    $body = @{ model='qwen3-vl:2b'; stream=$false; options=@{num_ctx=4096; num_predict=64; temperature=0}; messages=@(@{role='user'; content='What is on top of the washing machine? Answer unknown if unseen.'; images=$images}) } | ConvertTo-Json -Depth 6
    Invoke-RestMethod -Uri http://localhost:11434/api/chat -Method Post -ContentType application/json -Body $body
    ollama ps
}
```

检查两次请求都完成且读入所需图片，记录模型 ID、加载位置（GPU/CPU）、耗时和显存余量。正式验收再用真实 20 步轨迹连续跑 10 题。若开发题上已有充足证据而 2B 常读错，才用同图对照 4B，并复测四图峰值。[Windows 支持](https://docs.ollama.com/windows) · [模型文件](https://ollama.com/library/qwen3-vl:2b) · [图像请求格式](https://docs.ollama.com/capabilities/vision)
