# 项目状态、恢复与经验卡

## 只维护一套权威资料

| 资料 | 权威内容 |
|---|---|
| `brief.md` | 有效目标、约束、用户原话与变更记录 |
| `art-direction.md` | 采用/否决的表达及理由，引用 Brief 约束 ID |
| `TASK_STATE.json` | 当前阶段、最新制作版、选定稿、真实文件引用与下一步 |
| `review-log.md` | 实际观察、裁决、用户接受状态、运行记录与预算消耗 |
| `style-kit.json`（按需） | 当前方向的色彩、排版角色、构图、身份、材质与参考 ID |
| `style-cards.json` 或 `style-cards/`（按需） | 带条件、反例和证据的经验；JSON 库可供检索工具读取 |

`HANDOFF.md` 如需存在，只给入口、必读资料和一个下一步，不另写可独立变化的目标。项目素材和参考由用户当前任务决定，不捆绑任何旧图库。

## 本地工具的实际范围

`scripts/project.py` 仅需 Python 3 标准库；它不会生成图片、进行视觉识别、自动检索知识、切换模型或访问网络。

```text
python <skill目录>/scripts/project.py init <项目目录> --title "项目名称"
python <skill目录>/scripts/project.py add <项目目录> <真实文件> --id v001
python <skill目录>/scripts/project.py add <项目目录> <新版文件> --id v002 --parent v001 --edit-input unverified
python <skill目录>/scripts/project.py select <项目目录> v001 --reason "新版未改善目标且光影偏移"
python <skill目录>/scripts/project.py update <项目目录> --stage D5 --next "等待用户接受选定稿"
python <skill目录>/scripts/project.py status <项目目录>
```

用 `python` 或本机实际可用的 `python3`/`py`。不要照搬示例中的占位路径。

- `init` 新建状态及必要目录；已有状态就拒绝覆盖，已有 `brief.md` 不覆盖。
- `add` 复制非空的真实文件到新的版本目录；版本 ID 不得重复。它不证明文件是有效图像，也不自动记为已审图。
- `--parent` 记录制作关系。只有实际调用记录能证明旧版作为编辑输入时，才写 `--edit-input confirmed`；否则使用 `unverified`。新图无父版时默认 `not_applicable`。
- `select` 从已登记版复制选定稿，记录主版本与理由；选定目标已存在且字节不同则报错，不覆盖。它不等于用户已接受，也不替代看图。
- `update` 只修改阶段和下一步；不要据此伪造未完成阶段。
- `status` 返回登记文件是否存在且非空。不会核验审美、精确文字或编辑链路。

状态使用相对路径，保存前另存上一份状态。单个 JSON 通过替换写入；不宣称图片、日志和状态组成跨文件事务。采用单一写入者，不把同步盘当多机并发数据库。脚本失败时保留原稿并检查实际文件，不凭失败提示推导图片不存在。

生成调用的状态、剩余张数、耗时及未知费用写进 `review-log.md`。不要从登记文件数推算调用数：失败调用也会消耗预算，一个产物也可能来自多次尝试。

## 参考与检查点记录

```text
python <skill目录>/scripts/project.py reference <项目目录> --id ref01 --source references/ref.png --origin external --role style --inspection viewed --evidence "全图已看，参考空间与配色；不借用身份"
python <skill目录>/scripts/project.py checkpoint <项目目录> --name alignment --result pass --basis inherited --brief-revision BR001 --evidence "brief.md 中已有用户指定方向"
python <skill目录>/scripts/project.py checkpoint <项目目录> --name preflight --result pass --basis self_check --brief-revision BR001 --evidence "制作卡中的输入、字体、文案和预算已核对"
python <skill目录>/scripts/project.py checkpoint <项目目录> --name match --result partial --basis self_check --brief-revision BR001 --version v001 --evidence "review-log.md 中的实际匹配对照"
```

引用路径必须是项目内真实文件或明确 URL；记录 URL 不会下载或查看页面。origin 区分 user、external、generated、unknown；role 可重复，记录 identity、style、layout、edit_input 或 comparison。已知生成图即便由用户上传也标 generated。viewed 要求填写观察证据，但脚本不会看图；edit_input 角色不替代实际调用关联证明。

检查点只追加记录，含 Brief 修订、结论与决策依据；匹配结论还必须绑定已登记版本。状态变更不等于自动批准或审美通过，也不会自动运行后续动作。需求变更后按 BR 修订找对应结论，受影响的旧通过作历史记录，重新核对。旧 schema_version=1 项目不含这些字段仍可读取，新字段按需添加，不重建或覆盖旧版本。

## 何时保存

确认目标或新反馈后、实际产物到达后、审查/裁决后、准备切会话前保存。提交前记录本轮输入和保留项；中断后先查上轮是否完成，不自动重提未知调用。

小任务可保留在当前会话；一旦多轮或明确接续，就保存文件。不是每次都要建立完整文件树或长篇检查点。

## 新会话恢复顺序

1. 确认项目根，运行 `status` 或直接读取 `TASK_STATE.json`。
2. 读完整 `brief.md`、当前方向和最近相关反馈，不能只读交接摘要。
3. 核实最新制作版与选定主版；两者可能不同。实际查看本轮需要的图片。
4. 核对未完成调用、预算、阻碍和工具能力；结果未知就先查询或说明未知。
5. 检索当前问题相关的少量经验卡，通常 0–3 条；检查条件与反例。
6. 执行状态中的一个明确下一步。未获新出图意图时，不因恢复任务自动生成。

“文件保存了”“模型能复述标题”不构成恢复成功。必须在不依赖原聊天的任务中找回有效约束、真实版本及下一步，才可将恢复测试记为通过。

## 经验状态与冲突

`proposed` 是尚待验证的方法；`observed` 是单次观察；`tested` 是在新任务实施并实际看过结果；`supported` 需更多题材或重复任务和可复查证据。历史转述与本轮亲测分开标记。不得把上一环境的通过改写成当前机器已通过。

冲突时保留旧卡，补充适用条件、反例和新证据；不凭最新更新时间覆盖语义。初期使用关键词与短索引足够，不要求向量库、后台守护程序或全量聊天压缩。

用 `scripts/techniques.py` 对内置或项目 JSON 库做关键词检索和新增；具体字段、证据分级与命令见 `references/style-kit-and-techniques.md`。目录中的 Markdown 卡仍需实际阅读，不会自动进入 JSON 检索索引。

换电脑时带走 Brief、状态、实际版本、必要参考和使用中的源文件。使用相对路径，缺字体/渲染器明确报告；不迁移账号凭据，不假设当前账户权限随文件同步。日常图片不强制生成哈希清单。
