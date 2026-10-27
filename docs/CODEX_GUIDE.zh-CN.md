# Codex Visual Director · GPT 静态视觉工作流

版本 1.1.2 · 2026-10-27

GPT 负责需求、导演决策、布局、真实审图、定向修改、版本裁决与项目接续；绘画性内容使用当前宿主实际提供的 OpenAI 原生图像工具。准确文字与几何按需使用确定性代码。本版不接入 ComfyUI、第三方模型、外部生图服务或 Photoshop，不要求新增模型密钥。

[技能目录](../codex-visual-director/) · [核心指令](../codex-visual-director/SKILL.md) · [工具回归检查](../tests/test_codex_tools.py)

## 1. 本次升级

v1.1.2 沿用以下工具能力，补充视觉优先级和精简制作指令、原始身份持续对照、按景别验收，以及[参考还原与全身俯视实作经验](../codex-visual-director/references/field-lessons.md)。经验文档为有限实作观察，含反例；没有捆绑案例图片，也不能替代新任务实际审图。

D0–D5 保留。新增视觉选参、Brief 修订与检查点、开工卡、先匹配后细审、参考用途记录、可检索招式和小型排版模块。已有明确方向且授权充足时连续执行；不增加逐步审批，也不强制先生成三张候选图。

| 模块 | 当前实际提供 | 范围 |
|---|---|---|
| Layout Planner | 布局规范、可运行 PNG/SVG 渲染、墨迹几何检查 | 基础中英文横排与背景合成；不是任意字形或专业印前引擎 |
| Design Critique | 实际看图；先比对批准方向，再做 Brief / Design / Craft 三视角自查 | 匹配结论附可见证据，没有统一 70 分门槛 |
| Design Loop | 归因、单轮修改协议、预算、回退与停止；真实文件工具 | 不自带自动生图调度器；默认最多三次修改，有新方法及授权预算才延长 |
| Style Kit | 当前项目的色彩、字体角色、构图、身份与材质模板 | 引用当前 Brief 与参考，不自动继承旧项目风格 |
| 招式库 | 7 张结构化种子卡、关键词检索、向项目库新增 | 6 张 proposed、1 张历史 reported/observed；不自动验证或晋级 |
| 项目接续 | 相对路径状态、有效 Brief、版本与检查点 | 旧 schema_version=1 项目兼容；保存不等于已验证恢复 |

原 ChatGPT 中英文版本仍为 1.0.0，文件保持原样；本次升级针对单独的 Codex 版。

## 2. D0–D5

| 阶段 | 执行动作与完成依据 |
|---|---|
| D0 需求 | 读完整 Brief 与参考，编号 H 条件；必要时视觉选参；记录 BR 修订、术语可见特征及采用依据 |
| D1 导演 | 明确表达机制和布局，按问题检索少量招式；短自检确认输入、工具、字体、文案及预算可用 |
| D2 制作 | 实际调用原生图像工具或适当的确定性排版；登记真实结果，编辑输入未核验就保持 unverified |
| D3 审查 | 先判断是否匹配批准方向，再检查 Brief / Design / Craft；实际看全图和必要局部 |
| D4 裁决 | 根据目标收益与非目标偏移选择接受、修改、重做、回退或止损；回退必须取回真实旧稿 |
| D5 交付 | 交作品，记录选定主版、未达项和用户接受状态；经验按证据入库，给出下一步 |

Quick 任务可压缩执行。规则 VD-R01–VD-R10 用于引用技能要求，H01 等用于当前项目约束。默认一个 GPT；三视角自查不称三个独立模型。

## 3. 项目文件与工具

多轮或需要接续时，作品放在自己的项目目录，技能安装目录保留为工具源。主要文件为 brief.md、TASK_STATE.json、art-direction.md、review-log.md、真实版本及选定稿；按需增加 style-kit.json、style-cards.json 和使用中的布局源文件。

```text
python <skill目录>/scripts/project.py init <项目目录> --title "项目名"
python <skill目录>/scripts/project.py add <项目目录> <实际首稿.png> --id v001
python <skill目录>/scripts/project.py add <项目目录> <实际新版.png> --id v002 --parent v001 --edit-input unverified
python <skill目录>/scripts/project.py select <项目目录> v001 --reason "新版目标收益有限"
python <skill目录>/scripts/project.py status <项目目录>
```

project.py 仅需 Python 标准库。最新制作版与选定主版分开；不覆盖不同内容、不改写 Git 历史。新增 reference 与 checkpoint 子命令记录来源、用途、检查依据和 Brief 修订，具体命令见 [状态说明](../codex-visual-director/references/state-and-memory.md)。它们只登记，不自动看图、批准或验证实际编辑输入。

日常图片不强制 SHA256 或全图差分。不从登记文件数推算生图调用次数；费用未知就记录未知。

## 4. 可运行排版

```text
python <skill目录>/scripts/render_layout.py <项目目录>/layout.json --out <项目目录>/renders/v001 --font <实际字体文件>
```

依赖 Pillow 和 fonttools；字体由本机提供，技能不捆绑字体或自动下载。依赖不存在时报告具体缺项并遵从本机安装授权。project.py 和 techniques.py 不受这些排版依赖影响。

从 [布局样例](../codex-visual-director/assets/layout-example.json) 复制并修改。输出 PNG、含文字和嵌入字体子集的 SVG、实际墨迹报告。检查缺字、文字越界、安全区、文字重叠、保护区以及已声明的最低字高；未知字段与旧输出前缀会被拒绝。实际改标题后用新前缀重渲，验证变化生效。

样例是纯文字排版演示，没有右侧人物素材，不算成品插画。PNG 的几何检查不等于设计通过；SVG 在目标软件的字体呈现和可编辑性仍需重开验证，不保证跨渲染器像素一致。详细字段与边界见 [Layout Planner](../codex-visual-director/references/layout-planner.md)，字形任务另看 [字形规则](../codex-visual-director/references/type-glyph.md)。

## 5. 招式检索与经验

```text
python <skill目录>/scripts/techniques.py search --query "人物与环境 叙事 动作" --task-type character
python <skill目录>/scripts/techniques.py search --query "字高 可读性" --task-type type --limit 3
python <skill目录>/scripts/techniques.py add --library <项目目录>/style-cards.json --card <本次卡片.json>
```

使用标准库关键词检索，不依赖向量库、网络服务或其他模型。返回机制、条件、反例与证据；相关性分数不是审美评分。可无命中。新增经验写项目库，保留命名空间；同 ID 冲突拒绝覆盖，内置库不在设计任务中改写。

proposed → observed → tested → supported 由实际证据决定，脚本检查通过不会使艺术招式晋级。历史报告标 reported；保存卡片不等于模型训练、自动学习或自动跨会话记忆。完整说明见 [Style Kit 与招式库](../codex-visual-director/references/style-kit-and-techniques.md)。

## 6. 安装与更新

首次安装让本机 Codex 使用 $skill-installer，从 Alyzeus/gpt-visual-director 仓库的 codex-visual-director 子目录安装，核对 SKILL.md 的 name 和当前实际加载情况。只下载本仓库不算安装。

已有版本先找当前 Codex 实际加载的同名目录，备份目录及本地修改，再在原位更新完整 20 个文件。可能位于用户技能目录或项目目录；以本机实际加载路径为准，避免在另一个目录重复安装。安装目录里已有作品或个人经验时先迁出并保留。

可把下面的话交给本机 Codex：

```text
更新我已安装的 codex-visual-director：从 Alyzeus/gpt-visual-director 的 main 分支读取 codex-visual-director 目录，先定位当前实际加载位置并完整备份，保留本地修改和个人项目，再原位更新为 v1.1.2 的全部 20 个文件。核验核心版本、参考和三个脚本可读，运行不出图的检索与状态检查；检查排版依赖和字体，缺项如实报告。本轮不生成图片。更新后重新加载或新开会话验证 $codex-visual-director。
```

安装、实际加载、原生图像能力可用及作品达标分别检查。远端技能保存或 GitHub 发布均不代表已经改写 PC 本地文件。宿主安装规则参考 [Build skills](https://learn.chatgpt.com/docs/build-skills)；具体工具与模型以当前会话提供的能力为准。

## 7. 使用与接续

```text
使用 $codex-visual-director。为我设计一张 16:9 日系动画插画，重点是人物与环境融合的故事瞬间。已有方向就沿用，信息足够就制作首稿；先审方向匹配，再修最重要的问题。只使用 GPT 与当前原生图像工具，将实际版本与状态保存到指定项目目录。
```

接续时给项目根目录，要求读取 TASK_STATE.json、完整 Brief、当前方向和选定稿。核对 Brief 修订与检查点范围、最新制作版与主版、预算和结果未知的调用，再执行一个明确下一步。不要依赖聊天摘要覆盖原目标。

## 8. 验证记录与边界

v1.1.2 本次通过 Skill 格式与内部引用检查，三个工具脚本沿用 v1.1.0 未修改。新增经验来自角色特写、俯视与无人机全身等实作；全身人物案例为一次基线、三次编辑，四次原生调用均取得图片，最终仍有身份细节、腿部遮挡和无人机虚焦等未达项。未做独立盲评或有/无 Skill 的受控消融，不能据此给出稳定提升比例。以下为 v1.1.0 历史验证记录，不改写为此次重新运行。

v1.1.0 的本地工具检查共 48 项：项目状态与回退 20 项、招式检索与新增 8 项、真实字体排版 20 项。覆盖旧项目兼容、路径与冲突保护、参考和检查点记录、无命中与卡片冲突、中文 PNG、SVG 字体子集、改标题重渲、字体集合、缺字、越界和保护区等。测试图形均为程序构造的排版或色块，不是生图质量样本。

两个最终隔离 GPT 上下文任务通过：沿用已确定方向、只整理制作卡并检索未验证招式；实际查看批准参考与偏离稿，先识别方向不匹配再裁决。本次还实际查看了排版 PNG。未运行原生生图或精确局部改图，未在用户 Windows 上执行本轮更新，不把工具检查解释为审美或生图链路已验收。

可复跑工具检查：

```text
python tests/test_codex_tools.py --cjk-font <本机实际中文字体> --latin-font <本机实际拉丁字体> --output <临时测试目录>
```

需要 Python、Pillow、fonttools；字体不随测试下载。测试保留实际结果供检查，不联网也不调用模型。[27 个行为用例](../codex-visual-director/references/evaluations.md) 是验收设计，不能把它们全部记为已经运行。
