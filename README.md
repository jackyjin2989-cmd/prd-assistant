# PRD Assistant

一组面向产品需求工作的可复用 Skill：`prd-assistant` 聚焦核心产品功能与改动，`browser-observer` 按需核实现有页面，`html-prototype` 按需制作 HTML 原型。

## 核心原则

`prd-assistant` 默认只写背景与目标、功能范围、页面/字段/角色/状态、业务规则、存量数据影响、验收和关键待确认项。

除非用户明确要求，或内容本身直接决定产品行为，否则不写：

- 系统边界、架构、接口、数据结构和开发实现
- 超时、重试、异步、外部依赖降级
- 发布、灰度、监控、回滚
- 算法或内部策略
- 缺陷修复过程、功能下线方案
- 运营操作手册或执行 SOP

观察和原型均不是 PRD 的默认步骤。现有材料足够时直接完成；只在用户明确要求，或关键产品事实必须核实时观察页面；只在用户明确要求原型/交互验证，或经确认文字无法表达核心方案时制作原型。

## 技能

### `prd-assistant`

- 起草、补全、改写和审校 PRD
- A 微调型、B 模块级、C 跨产品复杂业务分层
- 已确认事实、产品判断、假设和开放问题分层
- 修复矛盾、重复规则和编辑残留
- 生成可观察、可验证的产品验收标准
- 按需分流页面观察和 HTML 原型

### `browser-observer`

在用户授权范围内观察页面结构、文案、交互和状态并输出证据。它只负责观察和记录，不写 PRD，也不实现原型。

### `html-prototype`

根据需求、截图、设计稿或观察记录创建自包含 HTML 交互原型。它只负责原型实现和验证，不访问网站或处理登录。

## 调用关系

| 用户目标 | 调用路径 |
|---|---|
| 写、改或评审 PRD | `prd-assistant` |
| 核实授权网站现状 | `browser-observer` |
| 用户明确要求 HTML 原型 | `html-prototype` |
| 根据网站核实现状后写 PRD | `browser-observer` → `prd-assistant` |
| 参考网站制作原型 | `browser-observer` → `html-prototype` |
| 参考网站制作原型并写 PRD | `browser-observer` → `html-prototype` → `prd-assistant` |

URL、截图、页面改动、弹窗或响应式需求都不会单独触发原型。材料不足但不影响核心结论时，标为待确认即可。

## 目录

```text
├── browser-observer/
│   ├── SKILL.md
│   └── references/
├── prd-assistant/
│   ├── SKILL.md
│   └── references/
├── html-prototype/
│   ├── SKILL.md
│   └── references/
└── scripts/
    └── validate_skills.py
```

## 安装

将需要的 Skill 目录复制到宿主约定的技能目录，并保留 `SKILL.md` 与 `references/` 结构。TRAE 仓库级安装示例：

```text
.trae/skills/prd-assistant/
├── SKILL.md
└── references/
```

## 验证

在仓库根目录运行：

```powershell
python scripts/validate_skills.py
```

脚本检查三个 Skill 的目录、frontmatter、必需参考文件、Markdown 链接、敏感模式，以及 `prd-assistant` 的默认内容边界和观察/原型低成本分流规则。

## 隐私与版权

- 只访问用户明确授权的站点、页面、账号和操作范围。
- 密码、验证码、SSO 和多因素认证由用户自行完成。
- 不交付认证状态、内部地址或个人信息。
- 对截图、记录和测试数据做最小化与脱敏处理。
- 不绕过权限、验证码、反自动化限制或访问控制。
- 不复制第三方受限制文本、源码、视觉资产、商标或字体。

## 贡献

规则应放在对应 Skill，避免跨文件重复。修改后运行验证脚本，并人工检查内容边界、矛盾、重复和最终交付清洁度。

## 许可证

MIT，见 [LICENSE](LICENSE)。
