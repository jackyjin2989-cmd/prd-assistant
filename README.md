# PRD Assistant

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/jackyjin2989-cmd/prd-assistant?style=social)](https://github.com/jackyjin2989-cmd/prd-assistant/stargazers)

一个面向产品经理的可复用 Skill：从文字、截图、会议纪要或已有草稿中起草、补全和审校 PRD，聚焦核心产品功能与改动；需要时再核实授权页面、制作 HTML 原型。安装一次，三种能力齐备。

## 特性

**PRD 写作**

- 起草、补全、改写和审校 PRD，输出可直接评审的产品文档
- 按复杂度分层：A 微调型 / B 模块级 / C 跨产品复杂业务，模板是裁剪工具而非必填目录
- 默认只写背景与目标、功能范围、页面/字段/角色/状态、业务规则、存量数据影响、验收和关键待确认项
- 自动修复矛盾、重复规则和编辑残留，最终稿不暴露分析过程
- 生成"前置条件 / 操作 / 预期结果"式可观察、可验证的验收标准

**页面观察**

- 在用户授权范围内观察页面结构、文案、交互和状态，输出可复核的证据记录
- 快照驱动、只读优先；登录、验证码等敏感环节始终由用户掌控
- 只负责观察和记录，不写 PRD，也不实现原型

**HTML 原型**

- 根据需求、截图、设计稿或观察记录生成自包含、可直接打开的交互原型
- 只实现用户明确要求及核心交互所需的最小平台、页面和状态
- PC / H5 响应式、截图对比验证均按需执行，不默认扩范围

## 快速开始

### 安装

将 `prd-assistant` 目录复制到宿主约定的技能目录，保留 `SKILL.md` 与 `references/` 结构即可。以 TRAE 仓库级安装为例：

```powershell
git clone https://github.com/jackyjin2989-cmd/prd-assistant.git
Copy-Item -Recurse prd-assistant\prd-assistant .trae\skills\prd-assistant
```

安装后的结构：

```text
.trae/skills/prd-assistant/
├── SKILL.md
└── references/
    ├── browser/      # 页面观察规则
    └── prototype/    # HTML 原型规则
```

### 使用

直接用自然语言描述目标即可，Skill 会自行判断走哪条路径：

```text
根据这份会议纪要写 PRD，只覆盖本次改动
```

```text
这是现有页面截图，把"待审核"改为"待复核"，写 PRD 并附验收标准
```

```text
我已登录测试环境，核实订单列表的空状态和错误状态，据此补 PRD
```

```text
按这份 PRD 生成 PC 端 HTML 原型，不需要移动端
```

## 触发规则

| 用户目标 | 执行路径 |
|---|---|
| 写、改或评审 PRD | 直接写 PRD |
| 核实授权网站现状 | 页面观察 → 写 PRD |
| 用户明确要求 HTML 原型 | 生成原型 |
| 参考网站制作原型 | 页面观察 → 生成原型 |
| 参考网站制作原型并写 PRD | 页面观察 → 生成原型 → 写 PRD |

观察和原型均不是 PRD 的默认步骤。URL、截图模糊、PC/H5 等不单独触发观察或原型；仅在用户明确要求，或会改变核心方案或验收的事实无法确认且存在授权页面时才观察。材料不足但不影响核心结论时继续处理并标待确认；核心分歧集中追问并暂停定稿，待确认内容不得进入确定性验收。

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

## 设计原则

- **聚焦核心**：不为模板完整而扩写技术方案、发布方案或运营 SOP；用户明确要求时才补对应部分。
- **按需取材**：现有材料足够时直接写，不默认访问网站、生成原型、补截图或做多端验证。
- **一处定义**：同一规则只完整描述一次，其他位置引用，避免跨文件重复和口径漂移。
- **最终态交付**：直接呈现采用后的内容，移除被否方案、删除线和草稿残留。

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

规则应放在对应参考文档，避免跨文件重复；新增或收敛规则时同步更新验证脚本的策略标记。修改后运行验证脚本，并人工检查内容边界、矛盾、重复和最终交付清洁度。

## 许可证

MIT，见 [LICENSE](LICENSE)。
