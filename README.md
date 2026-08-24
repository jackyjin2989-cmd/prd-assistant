# PRD Assistant

一个面向产品需求工作的可复用 Skill：聚焦核心产品功能与改动，按需核实现有页面，按需制作 HTML 原型。用户只需安装一次即可获得全部能力。

## 核心原则

`prd-assistant` 默认只写背景与目标、功能范围、页面/字段/角色/状态、业务规则、存量数据影响、验收和关键待确认项。除非用户明确要求，或内容本身直接决定产品行为，否则不写系统边界、架构、接口、发布灰度、算法策略、运营 SOP 等。

观察和原型均不是 PRD 的默认步骤。仅在用户明确要求，或会改变核心方案或验收的事实无法确认且存在授权页面时观察；截图模糊、PC/H5 等不单独触发。原型只实现用户明确要求及核心交互所需的最小平台、页面和状态，双端、截图对比与完整验证均按需。核心分歧集中追问并暂停定稿，非关键缺口可继续，待确认不得进入确定性验收。

## 能力

### PRD 写作

- 起草、补全、改写和审校 PRD
- A 微调型、B 模块级、C 跨产品复杂业务分层
- 内部只区分现状与问题，最终稿不暴露分析过程
- 修复矛盾、重复规则和编辑残留
- 生成可观察、可验证的产品验收标准

### 页面观察

在用户授权范围内观察页面结构、文案、交互和状态并输出证据。只负责观察和记录，不写 PRD，也不实现原型。

### HTML 原型

根据需求、截图、设计稿或观察记录创建自包含 HTML 交互原型，只实现用户明确要求及核心交互所需的最小范围。不访问网站或处理登录，双端、截图对比与完整验证均按需。

## 触发关系

| 用户目标 | 执行路径 |
|---|---|
| 写、改或评审 PRD | 直接写 PRD |
| 核实授权网站现状 | 页面观察 → 写 PRD |
| 用户明确要求 HTML 原型 | 生成原型 |
| 参考网站制作原型 | 页面观察 → 生成原型 |
| 参考网站制作原型并写 PRD | 页面观察 → 生成原型 → 写 PRD |

URL、截图模糊、PC/H5、页面改动、弹窗或响应式需求均不会单独触发观察或原型。材料不足但不影响核心结论时继续处理并标待确认；影响核心方案或验收时集中追问并暂停定稿。

## 目录

```text
├── prd-assistant/
│   ├── SKILL.md
│   └── references/
│       ├── input-intake.md
│       ├── 写法指南.md
│       ├── review-checklist.md
│       ├── 图片嵌入与截图指南.md
│       ├── 语言表述规范.md
│       ├── final-output-hygiene.md
│       ├── browser/
│       │   ├── observation.md
│       │   ├── tool-adapter.md
│       │   ├── snapshot-and-interaction.md
│       │   ├── auth-and-sessions.md
│       │   ├── evidence-and-diagnostics.md
│       │   └── observation-record.md
│       └── prototype/
│           ├── generation.md
│           ├── responsive-guide.md
│           ├── site-reference.md
│           └── visual-validation.md
└── scripts/
    └── validate_skills.py
```

## 安装

将 `prd-assistant` 目录复制到宿主约定的技能目录，并保留 `SKILL.md` 与 `references/` 结构。TRAE 仓库级安装示例：

```text
.trae/skills/prd-assistant/
├── SKILL.md
└── references/
    ├── browser/
    └── prototype/
```

## 验证

在仓库根目录运行：

```powershell
python scripts/validate_skills.py
```

脚本检查 Skill 目录与 frontmatter、全部必需参考文件（含 `browser/` 和 `prototype/` 子目录）、仓库内非图片 Markdown 链接、基础敏感文本模式、PRD 内容边界与观察/原型分流规则、图片指南的职责边界与关键规则、响应式和视觉验证无强制双端残留、写法指南含成功判定规则，并核对运行版与仓库版文件一致性。脚本不解析 Markdown 图片目标、不判断图片视觉内容或实际远程状态，也不替代人工语义审查。

## 隐私与版权

- 只访问用户明确授权的站点、页面、账号和操作范围。
- 密码、验证码、SSO 和多因素认证由用户自行完成。
- 不交付认证状态、内部地址或个人信息。
- 对截图、记录和测试数据做最小化与脱敏处理。
- 不绕过权限、验证码、反自动化限制或访问控制。
- 不复制第三方受限制文本、源码、视觉资产、商标或字体。

## 贡献

规则应放在对应参考文档，避免跨文件重复。修改后运行验证脚本，并人工检查内容边界、矛盾、重复和最终交付清洁度。

## 许可证

MIT，见 [LICENSE](LICENSE)。
