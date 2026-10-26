# Style Kit 与可检索招式库

## 两类资料

- 项目 `style-kit.json`：从 `assets/style-kit.json` 按需复制，记录当前批准方向的色彩、字体角色、身份锚点、构图与材质规则。引用 Brief 修订与真实参考 ID，不凭模板填入虚构字体或已确认状态。方向变化时同步重查。
- 招式卡：按问题检索可迁移的表现机制，必须含适用条件、反例和证据状态。不把风格标签、素材链接或提示词堆积视为招式库。

两者均按需读取，不要求每次加载整个库。先用当前目标和实际图像判断，再取通常 0–3 条相关卡；可无命中。

## 内置种子与证据

`references/techniques.json` 本身是结构化卡片索引，目前 7 张：6 张 proposed 方法假设，1 张 observed 历史记录。后者引用既有项目摘要，verification=reported，没有附私有图片，不算本轮生图实测。不得称“7 招均已验证”。

- `proposed`：可尝试的方法，未有本任务成图证据。
- `observed`：一次可描述的结果，保留正反证与来源；历史转述标 reported。
- `tested`：已在新任务实施并实际看过结果；标明任务与版本。
- `supported`：有跨任务或重复证据，且条件与失败边界可复查。

验证脚本本身通过，不会使艺术招式晋级。脚本只检索和检查卡片字段，不验证证据真实性、不自动升降级。

## 检索与新增

```text
python <skill目录>/scripts/techniques.py search --query "人物与环境 叙事 动作" --task-type character
python <skill目录>/scripts/techniques.py search --query "字高 可读性" --task-type type --limit 3
python <skill目录>/scripts/techniques.py list
python <skill目录>/scripts/techniques.py add --library <项目目录>/style-cards.json --card <本次卡片.json>
python <skill目录>/scripts/techniques.py search --query "目标未改善 光影偏移" --library <skill目录>/references/techniques.json --library <项目目录>/style-cards.json
```

支持 `character / illustration / editorial / promo / type` 多标签及 general。关键词检索 relevance_score 只说明文字相关性；必须读适用条件、反例和证据再决定是否用。不同任务可自行扩展标签，不依赖向量库或外部服务。

`--library` 可重复，指定后只读列出的库；默认只查内置库。不存在的库或字段错误如实报错，不默默忽略。ID 冲突且内容不同则拒绝，不以时间覆盖旧知识。

新增写到项目或用户明确指定的持久知识目录，使用稳定命名空间如 `RG-T001`；不在设计任务中改写 Skill 自带种子。`add` 拒绝覆盖同 ID；修订用新卡 ID 并记录替代或冲突关系。该命令只维护一个 JSON，采用单一写入者，不支持并发合并或跨文件事务。

卡片 JSON 必须包含：`id / title / status / task_types / tags / problem / mechanism / use_when / avoid_when / evidence`。evidence 是数组，每项含 `ref / observation / verification`，verification 为 reported、checked 或 unverified。非 proposed 至少要有记录，但这不是对其真实性的自动背书。

## 入库闭环

记录本轮使用的卡、预期机制、实际结果和失败；失败可以新增反例，不强行“成功”。自产图可作为结果证据，但验证方向和外部还原时仍回到批准参考。新会话由项目入口找到库并实际检索，不能许诺自动记忆。
