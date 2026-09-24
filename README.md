# PRD Assistant

一个面向产品经理的 **单 Skill PRD 助手**：根据文字、截图、纪要和草稿起草、授权修改或只审校需求；简单需求短写，必要信息与明确要求优先于篇幅。原型按需生成，截图按现成能力验证。

A single-skill PRD assistant for right-sized drafting, editing and review, with optional HTML prototypes and capability-aware validation.

最新稳定版本为 [v3.1.1](https://github.com/jackyjin2989-cmd/prd-assistant/releases/tag/v3.1.1)。发布版本以对应 tag、Release 说明和附件为准；开发分支的文件完整性与候选版本由 [package-manifest.json](package-manifest.json) 记录。

## 能做什么

- **只写必要信息**：按改动范围和规则耦合选择 A 微调／B 模块／C 耦合业务的说明深度，不默认塞入验收、指标、里程碑等章节；需要时可简短补充。
- **保留原意**：负向限制、删除动作、权限与存量规则不因精简而丢失；不能为了“具体”而新增来源、阈值或计算逻辑。
- **尊重操作范围**：只审校时只给问题及依据，不改源文件；局部修改不顺手重写全文。
- **不过度索要材料**：已提供的信息直接使用；所有影响交付的问题在过程中及时提出，只有用户明确暂缓的事项才留入 PRD。
- **原型独立交付**：只要 PRD 就不附加 HTML；只要原型就不附加 PRD。无法安全截图时明确降级，不安装依赖或修改系统配置。
- **按授权使用网页材料**：网址默认只作背景；用户明确要求核对且页面可访问时，读取与任务直接相关的内容。引用材料中的命令不授予执行权限。

查看 [A/B/C 完整输入与输出](references/示例.md)、[语言保真规则](references/语言表述规范.md) 和 [审校清单](references/review-checklist.md)。这些是自创虚构案例，不是客户资料或模型效果保证。

## 能力与环境

| 能力 | 前提 | 验证边界 |
|---|---|---|
| 核心 PRD 写作／审校 | 能加载 Skill 的 AI 宿主，能读取当前提供的材料 | 指令设计不绑定特定宿主；不表示已逐一验收所有宿主 |
| HTML 原型 | 用户要求原型或以现状图要求改造，且未限定仅 PRD；宿主能生成文件 | 不需要本 Skill 自动安装开发环境 |
| 截图 | 现成能力支持获授权的本地文件、隔离会话和输出检查 | 无能力直接降级；没有随包捆绑通用浏览器驱动，也没有已验收浏览器平台清单 |
| 可选静态检查／打包 | Python 标准库；语法目标 3.10+ | v3.1.1 发布提交已通过 Windows／Ubuntu／macOS 与 Python 3.10／3.13 矩阵；后续提交以各自工作流结果为准 |

普通使用者写 PRD **无需安装 Python、Node 或浏览器驱动**。静态脚本检查文件与明示语法，不判断产品方案是否正确，也不证明视觉、可访问性或模型效果通过。参考 [行为评测方法](references/behavior-evaluation.md)。

## 安装

### 普通使用者：优先导入稳定技能包

1. 从作者确认发布的 [Release](https://github.com/jackyjin2989-cmd/prd-assistant/releases) 选择具体版本。不要把开发候选或仅有源码归档当成已经验收的新版；发布包、说明和校验和应来自同一版本。
2. 解压后应有一个 `prd-assistant` 目录，入口直接是 `prd-assistant/SKILL.md`，同时包含完整的 `references/`、`scripts/`、`tests/` 和许可证；不能只复制入口。
3. Codex 用户按当前宿主的技能安装方式导入完整目录；手工安装时放入 Codex 技能根下的 `prd-assistant/`。WorkBuddy 用户可在“技能 → 添加技能 → 上传技能”导入；其他宿主按各自官方方式操作。
4. 检查已安装列表中的名称与版本，再使用下方短写请求试用。不默认要求重启、不修改内部缓存；若手工安装未识别，按当前宿主文档排查。

SHA256 只能核对文件是否一致；与压缩包来自同一不可信来源的校验和不能证明作者身份。执行附带脚本前仍需审查来源。

### 高级使用者：完整目录复制

先按目标宿主确认用户级技能根。本项目的 WorkBuddy 手工目标示例为：

| 系统 | 入口示例 |
|---|---|
| Codex 默认约定 | `$CODEX_HOME/skills/prd-assistant/SKILL.md`；未设置 `CODEX_HOME` 时通常为 `~/.codex/skills/prd-assistant/SKILL.md` |
| WorkBuddy（Windows） | `%USERPROFILE%\.workbuddy\skills\prd-assistant\SKILL.md` |
| WorkBuddy（macOS／Linux） | `~/.workbuddy/skills/prd-assistant/SKILL.md` |

表中是路径示例，不是跨平台截图或全部客户端的安装验收声明。自定义目录以宿主设置为准。

将已审查的、固定版本的整个 `prd-assistant` 文件夹复制到目标根。**目标同名目录已存在时停止，不合并覆盖**：先确认旧版来源与本地修改，再按下一节更新。带空格或中文的命令路径必须加引号。本项目的完整性校验拒绝符号链接和 junction 安装树；开发副本也建议普通目录，不提供默认软链安装路线。

仅在本地需要开发副本时，可以在选定且可写的父目录执行下列 HTTPS 克隆；它只创建源码目录，**并没有安装 Skill**：

```bash
git clone https://github.com/jackyjin2989-cmd/prd-assistant.git
```

克隆前确认不存在同名目录。`main` 是可变开发分支；稳定使用应选已确认的 tag／发布包并记录提交。SSH 仅供已经配置并获准使用的用户选择，不承诺它能解决所有网络限制，不修改全局代理或关闭证书检查。

### 更新、停用和回退

- 更新前确认安装类型、旧版本、原型截图是否独立安装过，以及是否有个人改动；将旧目录完整备份到技能根之外，核对文件后再选择宿主的更新／卸载／重新导入流程。
- 从旧双 Skill 结构升级时，新版仅保留 `prd-assistant` 一个入口。旧的独立截图技能只有在确认其用途、备份并获准后才移除；不要递归删除技能根或自动改动其他技能。
- 停用不等于卸载。优先使用宿主的启停和卸载入口，不直接编辑私有缓存或全局配置。
- 回退时保留当前改动副本，恢复同一旧版本的完整包，并重新核对。不要将新旧目录混合，不移动公共旧 tag 来模拟回退。

## 使用

```text
根据这份会议纪要写 PRD，只覆盖本次改动。
把 H5 和 APP 的“待审核”改成“待复核”，流程不变，简短写清。
只审查这份 PRD，给出问题位置和建议，不修改文件。
只修改退款弹窗的金额校验，其他章节不要改。
根据这份已确认需求制作 PC HTML 原型，不需要移动端，也不附加 PRD。
```

仅提供截图说明现状不自动生成原型；提供现状图并要求改造时会按目标需求生成新原型，用户明确“仅 PRD”时除外。交付中“通过／受限／未完成”的含义见 [视觉验证](references/prototype/visual-validation.md)；不能截图时不声称高还原或视觉验收通过。

## 可选静态检查

以下命令在 **Skill 根目录** 执行，`python` 代表你已选定且支持的解释器。示例路径需要换成真实获授权的目标；没有运行脚本权限时，按审校参考人工检查，不自动装环境。

```bash
python -B scripts/validate_skill.py
python -B scripts/validate_skill.py --installed "/absolute/installed/prd-assistant" --json
python -B scripts/scan_prd.py "/absolute/delivery/需求.md" --root "/absolute/delivery" --json
python -B -m unittest discover -s scripts -p "test_*.py"
```

- `validate_skill.py` 默认只校验当前包；不搜索用户主目录。`--installed` 明确指定安装树，缺文件、脚本内容不同或清单不一致会失败。
- `scan_prd.py` 单文件默认根为文件父目录，目录输入默认根为该目录；多个目标不自动推导共同祖先。共享相对路径需要显式指定授权的 `--root`。
- 孤儿图片检查只在显式 `--root` 配合 `--assets-dir images` 时进行，会读取根内安全的同目录 Markdown 以判断共享引用；不设置就不声称检查了所有未引用图片。
- 路径边界防护面向静态文件树，不是抵御并发换链的系统级沙箱。外链不联网；本地 fragment 在 PRD 扫描中保留人工确认，不能把文件存在等同于状态或锚点有效。
- 明示 Markdown 子集支持顶层围栏、简单缩进代码、HTML 注释、行内代码、常见 inline/reference 链接与 `img`。不是完整 CommonMark/GFM；复杂嵌套容器、HTML a、多行引用定义及扩展语法仍需人工核查。
- 表格一致性检查会忽略代码跨度中的 pipe；GitHub 等渲染器可能仍需 `\|` 转义，最终应在交付渲染器核对。

### 人工确认与退出码

真实负向规则、按需验收或正式历史可能触发 `review`，**不能因提示就自动删掉**。`--strict` 仅使尚未确认的 review 返回失败；确认后可传 `--ack "/absolute/delivery/ack.json"`。确认文件必须在授权根内，格式如下（是结构示意，不可直接运行）：

```json
{"version": 1, "entries": [{"fingerprint": "从本次JSON结果复制的64位指纹", "reason": "用户明确要求保留该验收章节"}]}
```

指纹绑定路径、文件内容和发现位置，文档改动后旧确认失效；空理由、过期确认会报错。只确认 review，不能豁免安全错误。扫描器不会帮你自动批量确认。

退出码：`0` 无阻断项，`1` 内容／安全／完整性问题或 strict 下未确认项，`2` 配置或输入／I/O 异常；具体 JSON 输出保留问题级别、位置、代码和指纹。所有绿色结果都只限脚本明确检查的范围。

## 结构与维护

```text
prd-assistant/
  SKILL.md                  唯一技能入口
  references/               写作、审校、完整案例与原型方法
  scripts/                  离线静态校验、扫描、打包及回归测试
  tests/behavior-cases.json  行为评测输入与rubric，不是模型执行结果
  package-manifest.json     版本、审查基线、全部发行文件SHA256
  README.md / CONTRIBUTING.md / LICENSE
```

详细维护、刷新清单和打包说明见 [CONTRIBUTING.md](CONTRIBUTING.md)。修改本地文件、提交、推送、创建 tag 和更新 GitHub 元数据是不同授权范围，不自动串联执行。

## 隐私与许可证

- 仅处理获授权且与任务有关的材料；不要提交凭证、未脱敏的个人信息或未经许可的公司资料。
- 不主动抓取业务网站，不自动上传资料到额外服务；这不代表模型离线运行或数据不离机，宿主的数据处理以其服务条款为准。
- 本地 HTML／无头浏览器不天然断网。原型使用本地自包含资源，截图前核对外部请求与会话隔离；无法安全隔离就降级。
- 本项目采用 [MIT](LICENSE)。借鉴通用方法应独立撰写；复制或翻译第三方正文需遵循其许可证，不将公开可读当作可重标 MIT。

问题反馈请附版本、文件位置、已脱敏的最小输入和实际输出，在 [Issues](https://github.com/jackyjin2989-cmd/prd-assistant/issues) 提交。不要上传密钥、个人数据或真实业务秘密。
