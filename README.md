# PRD Assistant

一组通用、可公开复用的产品需求、浏览器观察与 HTML 原型技能。三个 Skill 各自独立：`browser-observer` 采集授权页面证据，`prd-assistant` 整理需求，`html-prototype` 实现和验证原型。

## 技能

### `prd-assistant`

用于起草、补全和审校 PRD，支持：

- 纯文字、截图、网站观察记录、会议纪要、聊天记录、已有草稿、流程图和混合输入
- 已确认事实、产品判断、假设和开放问题分层
- 只追问会改变核心结论的问题
- A 微调型、B 模块级、C 跨系统复杂型分类，以信息闭环而非固定篇幅判断质量
- 多源规则冲突消解
- 可测试验收标准及 REQ/RULE/AC 追踪
- 非功能要求按需判断
- 最终交付清理，避免残留被否方案和会话过程
- 按目标分流 `browser-observer` 与 `html-prototype`

### `browser-observer`

用于在用户授权范围内观察网站并输出结构化证据，支持：

- 页面导航、标签页确认、结构化快照与元素引用
- 点击、输入非敏感测试值、选择、滚动和短等待
- 页面变化后重新快照，避免复用失效引用
- 默认、加载、空、错误、禁用、弹层、校验和权限状态观察
- PC/H5 响应式差异采集
- 控制台和网络异常诊断
- 用户手动登录、会话隔离、安全状态复用和清理
- 宿主浏览器优先、兼容 CLI 可选、无工具时降级为脱敏截图或录屏
- 页面、状态、步骤、截图、证据来源和未验证项的标准记录

它只负责观察和记录，不写 PRD，也不实现原型。

### `html-prototype`

用于根据需求、截图、设计稿或结构化观察记录创建自包含 HTML 交互原型，支持：

- PC 1440×900/1280×720 与 H5 390×844/360×800 设备矩阵
- 导航、表格、表单、弹层等组件级响应式适配
- 关键交互与默认、加载、空、错误、禁用等状态实现
- 稳定 `data-feature` ID 与需求追踪
- 语义 HTML、键盘操作和常见可访问性要求
- 固定环境下的截图基线和差异验证
- 将网站观察结果原创转译，不复制受限制源码、素材和品牌资产

它只消费观察记录，不负责访问网站或处理登录。

## 调用关系

| 用户目标 | 调用路径 |
|---|---|
| 只写或评审 PRD | `prd-assistant` |
| 只观察授权网站 | `browser-observer` |
| 用清晰截图制作原型 | `html-prototype` |
| 根据网站写 PRD | `browser-observer` → `prd-assistant` |
| 根据网站制作原型 | `browser-observer` → `html-prototype` |
| 根据网站制作原型并写 PRD | `browser-observer` → `html-prototype` → `prd-assistant` |
| 模糊或不完整截图 | 截图足以支持结论时直接使用；仅当关键信息无法辨认、需要验证动态行为，并且存在用户授权的可访问页面时，调用 `browser-observer` 补证据 |

`browser-observer` 不是模糊截图或现状核实的必选项。截图和已有材料足够时直接进入 PRD 或原型流程；没有授权页面时，将缺失信息标为待确认，不猜测、不强制观察。URL 输入也不默认生成原型，只需核实现状时可交付观察记录。

## 安装

仓库根目录提供三个技能。将需要的技能目录复制到支持 `SKILL.md` 的代理工作区技能目录；若宿主约定不同，请按宿主文档调整安装位置，并保留各 Skill 的 `SKILL.md` 与 `references/` 结构。

```text
├── browser-observer/
│   ├── SKILL.md
│   └── references/
│       ├── auth-and-sessions.md
│       ├── evidence-and-diagnostics.md
│       ├── observation-record.md
│       ├── snapshot-and-interaction.md
│       └── tool-adapter.md
├── prd-assistant/
│   ├── SKILL.md
│   └── references/
│       ├── input-intake.md
│       ├── 写法指南.md
│       ├── review-checklist.md
│       ├── 图片嵌入与截图指南.md
│       ├── 语言表述规范.md
│       └── final-output-hygiene.md
├── html-prototype/
│   ├── SKILL.md
│   └── references/
│       ├── site-reference.md
│       ├── responsive-guide.md
│       └── visual-validation.md
└── scripts/
    └── validate_skills.py
```

## 使用示例

```text
请把以下会议记录整理成 B 类 PRD，重点写清状态流转、权限、异常和待确认项。
```

```text
请观察我已授权的网站注册流程。登录由我手动完成，只记录页面结构、交互、状态与 PC/H5 差异，不制作原型。
```

```text
请基于这张已脱敏截图制作原创 HTML 原型，同时支持 1440×900 PC 和 390×844 H5，并验证关键状态。
```

```text
请先观察我已授权登录的网站，再根据观察记录制作原创原型并整理成 PRD。不要保存登录状态或真实个人数据。
```

## 隐私与版权

- 只访问用户明确授权的站点、页面、账号和操作范围。
- 密码、验证码、SSO 和多因素认证由用户自行完成。
- 不输出或交付认证状态、内部地址与个人信息。
- 对截图、记录和测试数据进行最小化与脱敏处理。
- 不绕过权限、验证码、反自动化限制或访问控制。
- 只吸收通用结构和交互规律，不复制第三方受限制文本、源码、视觉资产、商标或字体。
- 仓库内容保持通用、原创，不包含特定公司的专有设计体系。

## 验证

运行仓库自带检查脚本：

```powershell
python scripts/validate_skills.py
```

脚本检查三个 Skill 的目录、frontmatter、必需参考文件、Markdown 链接、敏感模式和内部绝对路径。它不能替代人工的版权、隐私与产品质量审查。

## 贡献

提交内容应保持通用、原创和可审计。新增浏览器能力时放入 `browser-observer`；新增 PRD 写法时放入 `prd-assistant`；新增原型实现与验证规则时放入 `html-prototype`，避免跨 Skill 重复。提交前运行验证脚本并人工复核改动。

## 许可证

MIT，见 [LICENSE](LICENSE)。许可证仅覆盖本仓库原创内容，不授予任何第三方商标、素材或内容的权利。
