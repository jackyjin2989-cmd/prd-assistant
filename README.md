# PRD Assistant

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![version](https://img.shields.io/badge/version-v1.0.0-blue.svg)](https://github.com/jackyjin2989-cmd/prd-assistant/releases/tag/v1.0.0)
[![validate](https://github.com/jackyjin2989-cmd/prd-assistant/actions/workflows/validate.yml/badge.svg)](https://github.com/jackyjin2989-cmd/prd-assistant/actions/workflows/validate.yml)
[![GitHub stars](https://img.shields.io/github/stars/jackyjin2989-cmd/prd-assistant?style=social)](https://github.com/jackyjin2989-cmd/prd-assistant/stargazers)

一个面向产品经理的可复用 Skill：从文字、截图、会议纪要或已有草稿中起草、补全和审校 PRD，聚焦核心产品功能与改动；用户明确要求时制作自包含 HTML 原型。

## 仓库里有什么

本仓库是一个**技能集合**（monorepo）：两个可独立安装的技能 + 一套仓库级工具链。仓库名沿用了第一个技能的名字，所以会出现 `prd-assistant/prd-assistant/` 这样的双层同名路径 —— 前一层是仓库，后一层是技能目录。

| 顶层目录 | 是什么 | 归属 |
|---|---|---|
| `prd-assistant/` | 技能一：起草与审校 PRD、定义原型规范与视觉判定 | 技能，可独立安装 |
| `html-prototype-screenshot/` | 技能二：渲染本地 HTML、截图与量尺寸 | 技能，可独立安装（通用，与 PRD 无关） |
| `scripts/` | 仓库级工具链：技能仓库校验、PRD 扫描、扫描自测 | 基础设施，不随技能安装 |
| `.github/workflows/` | CI：push / PR 时自动跑语法检查与上述校验 | 基础设施 |

两个技能职责分开、互不重复：

- **`prd-assistant`** —— 写与审校 PRD（本 README 的主体）。
- **`html-prototype-screenshot`** —— 在 macOS 上用无头 Edge 渲染本地 HTML 并截图、量尺寸。`prd-assistant` 只定义「能不能截、什么算通过」，具体命令与参数归它管。

一条规则只写一份：**能不能截、什么算通过、截图与正文是否一致** 归 `prd-assistant`；**怎么截、怎么量** 归 `html-prototype-screenshot`。`scripts/validate_skills.py` 用标记双向锁住这条分工，任一侧越界都会校验失败。

## 特性

**PRD 写作**

- 起草、补全、改写和审校 PRD，输出可直接评审的产品文档
- 按复杂度分层：A 微调型 / B 模块级 / C 跨产品复杂业务，模板是裁剪工具而非必填目录
- **简单需求必须简单写**：A 类半页以内；验收标准、本期不做、成功判定等默认不写，用户明确要求才补
- **边界扫描**：动笔前按清单查漏状态、字段、流程、权限的逻辑缺口，只扫流程与业务逻辑，不涉及并发等技术问题
- 内置 A/B 类示例与 AI 味正反对照，目标形态可直接对齐
- 审校以"研发读完对应章节即可动手实现"为北极星，自动修复矛盾、重复规则和编辑残留，最终稿不暴露分析过程
- **排版克制**：表格只承载有真实口径的行（枚举、取值来源、校验、状态流转），图下数值不拆表，避免过度表格化；同一页面、同一链路的相似截图横排合并，不让文档被图片拉长
- 语言遵循表述规范，消除套话和 AI 腔

**HTML 原型**

- 根据需求、截图或设计稿生成自包含、可直接打开的交互原型
- 只实现用户明确要求及核心交互所需的最小平台、页面和状态
- 支持截图驱动还原：先识别页面骨架、组件形态、内容密度和视觉令牌，再实现交互，禁止直接套用通用模板
- **截图能力判定**：截图前一次性判定环境能力，不可截图立即降级为代码层自查，禁止安装依赖、调试脚本或反复重试
- **浮层与量化校验**：日历、下拉等"点击外部关闭"组件的通用坑位提示；折行、溢出、浮层几何用测量定稿，不靠目测猜字号
- PC / H5 响应式按需执行

**不访问网站**

本 Skill 不访问网站，也不内置浏览器自动化。需要页面现状时由用户提供截图；无法提供的缺口标待确认。

## 快速开始

### 安装

**方式一：复制安装**（只用不改）

把技能目录复制到宿主约定的技能目录，保留 `SKILL.md` 与 `references/` 结构即可：

```
git clone https://github.com/jackyjin2989-cmd/prd-assistant.git
Copy-Item -Recurse prd-assistant\prd-assistant <宿主技能目录>\prd-assistant
Copy-Item -Recurse prd-assistant\html-prototype-screenshot <宿主技能目录>\html-prototype-screenshot
```

**方式二：开发模式（软链，改完即生效）**

要改技能内容时用这种方式：运行目录是指向仓库克隆的软链，`git pull` 一下运行版就更新，不用手动同步。

注意 **HTTPS 通道在部分公司网络下会被拦截**，用 SSH 形式克隆（`git@github.com:...`）。

```bash
# 1. 克隆（建议放固定位置，例如 ~/WorkBuddy/prd-assistant）
git clone git@github.com:jackyjin2989-cmd/prd-assistant.git ~/WorkBuddy/prd-assistant

# 2. 先备份原有运行目录（不要直接删）
mkdir -p ~/.workbuddy/backups/skills
mv ~/.workbuddy/skills/prd-assistant ~/.workbuddy/backups/skills/prd-assistant-$(date +%Y%m%d-%H%M)

# 3. 建软链（Windows 无权限时改用 junction：cmd /c mklink /J <链接> <目标>）
ln -s ~/WorkBuddy/prd-assistant/prd-assistant ~/.workbuddy/skills/prd-assistant

# 4. 验证（find 必须加 -L，否则统计不到软链下的文件）
ls -la ~/.workbuddy/skills | grep prd-assistant
find -L ~/.workbuddy/skills/prd-assistant -type f | wc -l
head -3 ~/.workbuddy/skills/prd-assistant/SKILL.md
```

第二个技能 `html-prototype-screenshot` 同样处理。回滚：删掉软链，把备份 `mv` 回原位。

日常流程：**改前先 `git pull`，改完立即 commit + push，同一时间只让一个 agent 改这个仓库**（多个 agent 通常软链到同一个克隆，同时改会互相覆盖工作区）。推送前跑 `python scripts/validate_skills.py`。

安装后的结构：

```
<宿主技能目录>/prd-assistant/
├── SKILL.md
└── references/
    └── prototype/    # HTML 原型规则
```

### 使用

直接用自然语言描述目标即可：

```
根据这份会议纪要写 PRD，只覆盖本次改动
```

```
这是现有页面截图，把"待审核"改为"待复核"，写 PRD
```

```
按这份 PRD 生成 PC 端 HTML 原型，不需要移动端
```

```
按这张截图还原可交互原型，保持原有后台风格和内容密度
```

## 触发规则

| 用户目标 | 执行路径 |
|---|---|
| 写、改或评审 PRD | 直接写 PRD |
| 用户明确要求 HTML 原型 | 生成原型 |
| 明确要求按截图还原原型 | 解构截图 → 生成原型 → 按能力判定做视觉验证 |
| 提供网站 URL | 不访问；请用户提供截图 |

原型不是 PRD 的默认步骤。截图只用于说明字段、文案或状态时直接写 PRD。第三方或来源不明截图只用于结构、组件和视觉语言参考，不作为逐像素复制目标。材料不足但不影响核心结论时继续处理并标待确认。

## 目录

```
├── prd-assistant/
│   ├── SKILL.md
│   └── references/
│       ├── input-intake.md
│       ├── 写法指南.md
│       ├── 边界扫描清单.md
│       ├── 示例.md
│       ├── review-checklist.md
│       ├── 图片嵌入与截图指南.md
│       ├── 语言表述规范.md
│       └── prototype/
│           ├── generation.md
│           ├── responsive-guide.md
│           └── visual-validation.md
├── html-prototype-screenshot/
│   └── SKILL.md
└── scripts/
    ├── validate_skills.py
    └── scan_prd.py
```

## 设计原则

- **简单需求简单写**：篇幅与复杂度匹配；宁短勿凑，默认章节最少化。
- **聚焦核心**：不为模板完整扩写技术方案、发布方案或运营 SOP。
- **按需取材**：现有材料足够时直接写，不默认生成原型或要求补截图。
- **截图尊重原貌**：用户明确要求按图制作时，截图决定骨架、组件、密度与视觉语言。
- **环境不折腾**：截图能力一次判定，失败即降级，不安装依赖不重试。
- **一处定义**：同一规则只完整描述一次，其他位置引用。
- **最终态交付**：直接呈现采用后的内容，移除被否方案和草稿残留。

## 验证

在仓库根目录运行：

```
python scripts/validate_skills.py
```

检查目录与 frontmatter、必需参考文件、非图片 Markdown 链接、编码完整性、基础敏感文本模式，以及各文件的策略标记（防止核心规则被静默删掉）。同时核对运行版技能目录与仓库版是否一致：优先读 `SKILLS_DIR` 环境变量，其次 `~/.workbuddy/skills`、`~/.trae/skills`、`<仓库父目录>/.trae/skills`；运行版是指向本仓库的软链时直接判定一致。

推送到 main 或提 PR 时由 GitHub Actions 自动执行（见 `.github/workflows/validate.yml`）。

### 扫 PRD（交付前收尾）

`validate_skills.py` 管的是技能仓库自身；产出的 PRD 用另一个脚本扫：

```
python scripts/scan_prd.py <PRD 文件或目录>
python scripts/scan_prd.py --strict <路径>     # 待人工确认项也按失败处理
```

检查内容：范围排除与迭代痕迹残留词、图片引用是否存在/是否用绝对路径/是否缺 alt/编号是否连续、同目录未被任何文档引用的图片、相对链接可达性、占位残留（TODO/待补图/截图占位）、编码损坏。

输出分两级：**❌ 错误**（引用失效、绝对路径、表格列数不一致、占位残留等，退出码 1）与 **⚠️ 待人工确认**（如「本期不做」可能是合规硬约束、标题层级跳级，需人判断）。扫描时跳过点目录与 `node_modules` 等依赖目录。

**用法边界**：路径指向**某个需求目录**（如 `.../某需求/`），不要指向含多个项目的父目录——代码库、依赖包、技能文档一起扫进来会产生大量无关结果。同理不要拿它扫技能自身的文档：技能文档里出现「本期不做」「待补图」这类字样是正常的策略描述。

### 维护约定：新增检查先测误报率

扫描类工具的第一杀手是**误报**：规则写宽了，使用者就不再跑它，工具等于没有。所以改 `scripts/scan_prd.py` 时固定三步：

1. 先拿真实 PRD 语料跑一遍，统计误报；
2. 误报多的规则要么收紧（加前后文限定），要么在用法边界里写清适用场景；
3. 在 `scripts/test_scan_prd.py` 补一条「应报」+ 一条「不应报」的用例，再跑测试。

`python scripts/test_scan_prd.py` 覆盖表格列数、标题层级、图片引用与编号、兄弟文档引用扣除、代码块豁免、占位与残留词、目录噪声跳过、CLI 退出码；CI 会一并执行。历史教训：裸 `XXX` 误报 `XXXX.txt.enc.TEMP`；未扣除兄弟文档引用，把别人引用的图报成未引用。

脚本检查 Skill 目录与 frontmatter、全部必需参考文件、仓库内非图片 Markdown 链接、编码完整性、基础敏感文本模式、"简单需求简单写"与内容边界规则、不访问网站与原型分流规则、截图能力判定与降级规则，并核对运行版与仓库版文件一致性。脚本不替代人工语义审查。

### 维护约定：标记类改动要反向验证

`validate_skills.py` 里的 REQUIRED / FORBIDDEN 标记是**分工的护栏**，不是文档装饰。新增或修改标记后，必须做一次反向验证：

1. 把该标记对应的内容临时注入（REQUIRED 标记则临时删掉），跑一次 `validate_skills.py`，确认**确实失败且报出正确原因**；
2. 还原后再跑一次确认通过；
3. 改完标记的当次提交里说明验证结果。

只在「期望通过」的方向验证是不够的 —— 标记写错（路径不对、字符串对不上）时校验照样是绿的，等于没有护栏。同理，把规则从一侧搬到另一侧时，要在原侧加一条 FORBIDDEN 标记，否则下次很容易又被抄回去。

## 隐私与版权

- 不访问网站；只处理用户主动提供的材料。
- 对截图、记录和测试数据做最小化与脱敏处理。
- 不复制第三方受限制文本、源码、视觉资产、商标或字体。

## 贡献

规则应放在对应参考文档，避免跨文件重复；新增或收敛规则时同步更新验证脚本的策略标记。修改后运行验证脚本，并人工检查内容边界、矛盾、重复和最终交付清洁度。

## 许可证

MIT，见 [LICENSE](LICENSE)。
