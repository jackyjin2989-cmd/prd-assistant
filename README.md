# PRD Assistant

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![version](https://img.shields.io/badge/version-v2.0.0-blue.svg)](https://github.com/jackyjin2989-cmd/prd-assistant/releases/tag/v2.0.0)
[![validate](https://github.com/jackyjin2989-cmd/prd-assistant/actions/workflows/validate.yml/badge.svg)](https://github.com/jackyjin2989-cmd/prd-assistant/actions/workflows/validate.yml)

面向产品经理的 PRD 技能：从文字、截图、会议纪要或已有草稿中起草、补全和审校聚焦核心产品功能与改动的 PRD；用户明确要求时制作自包含 HTML 原型，并截图做视觉验证。

## 它做什么

- **按复杂度分层写作**：A 微调型 / B 模块级 / C 跨产品，模板是裁剪工具而非必填目录。**简单需求必须简单写** —— A 类半页以内，验收标准、本期不做等章节默认不写
- **审校闭环**：以「研发读完对应章节即可动手实现」为北极星，自动修矛盾、去重复、清编辑残留，不暴露分析过程
- **动笔前边界扫描**：查状态、字段、流程、权限的逻辑缺口；只扫业务逻辑，不碰并发等技术问题
- **按需生成原型**：自包含 HTML，先识别骨架、组件密度与视觉令牌，再实现交互；原型不是 PRD 的默认步骤
- **截图与量化验证**：截图前做一次**截图能力判定**，不可截图即降级为代码层自查，不装依赖不重试；折行、溢出、浮层几何用测量定稿，不靠目测猜字号
- **不访问网站**：需要页面现状时请用户提供截图，缺口标待确认

## 结构

仓库根就是技能根，`SKILL.md` 与 `references/` 直接放在根下：

```
SKILL.md              入口：适用范围、硬规则、工作流程
references/           写作、审校、边界扫描、示例、语言、图片规则
  └ prototype/        原型与截图（怎么搭 / 响应式 / 什么算通过 / 怎么截）
scripts/              校验与扫描工具，随技能一起安装
```

## 安装

**复制**（只用不改）—— 把仓库根整个复制到宿主技能目录即可：

```bash
git clone https://github.com/jackyjin2989-cmd/prd-assistant.git
```

**软链**（要改技能内容时用，`git pull` 即时生效）：

```bash
git clone git@github.com:jackyjin2989-cmd/prd-assistant.git ~/WorkBuddy/prd-assistant
ln -s ~/WorkBuddy/prd-assistant ~/.workbuddy/skills/prd-assistant
```

> HTTPS 在部分公司网络下会被拦截，用 SSH 形式克隆。
> Windows 无软链权限时改用 junction：`cmd /c mklink /J <链接> <目标>`。

## 使用

直接用自然语言说目标即可：

```
根据这份会议纪要写 PRD，只覆盖本次改动
这是现有页面截图，把「待审核」改为「待复核」，写 PRD
按这份 PRD 生成 PC 端 HTML 原型，不需要移动端
按这张截图还原可交互原型，保持原有后台风格和内容密度
```

截图只用于说明字段、文案或状态时直接写 PRD，不触发原型还原。

## 验证

```bash
python scripts/validate_skills.py       # 技能自身：结构、frontmatter、参考文件、链接、策略标记、运行版一致性
python scripts/scan_prd.py <PRD 路径>   # 产出的 PRD：残留词、图片引用与编号、表格列数、链接可达性
python scripts/test_scan_prd.py         # 扫描脚本自测
```

CI 在 push 与 PR 时自动执行，见 `.github/workflows/validate.yml`。
改这个仓库之前，先读 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 隐私与版权

不访问网站，只处理用户主动提供的材料；对截图、记录和测试数据做最小化与脱敏；不复制第三方受限制的文本、源码、视觉资产、商标或字体。

## 许可证

MIT，见 [LICENSE](LICENSE)。
