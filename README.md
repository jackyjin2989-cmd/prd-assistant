English | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

# PRD Assistant

[![GitHub stars](https://img.shields.io/github/stars/jackyjin2989-cmd/prd-assistant?style=social)](https://github.com/jackyjin2989-cmd/prd-assistant/stargazers)
[![License: MIT](https://img.shields.io/github/license/jackyjin2989-cmd/prd-assistant)](LICENSE)
[![Latest release](https://img.shields.io/github/v/release/jackyjin2989-cmd/prd-assistant)](https://github.com/jackyjin2989-cmd/prd-assistant/releases/latest)
[![validate](https://github.com/jackyjin2989-cmd/prd-assistant/actions/workflows/validate.yml/badge.svg?branch=main)](https://github.com/jackyjin2989-cmd/prd-assistant/actions/workflows/validate.yml)
[![Agensi](https://img.shields.io/badge/Agensi-listed-2563eb)](https://www.agensi.io/skills/prd-assistant)

**A single SKILL.md skill for product managers: draft, edit or review PRDs at the right length, from notes, screenshots, minutes and drafts, with optional standalone HTML prototypes.**

<!-- demo GIF here -->

> **Output language:** the skill writes in **Simplified Chinese by default**, and its instructions and reference docs are in Chinese. See [Output language](#output-language).

## Why PRD Assistant?

- **Right-sized, not padded.** Simple changes get short PRDs. Necessary information and your explicit requirements take priority over length, and acceptance criteria, metrics or milestones are not added by default.
- **Keeps your meaning.** Negative constraints, deletions, permission rules and rules for existing data are not lost when text is tightened, and it does not invent sources, thresholds or calculation logic to look "specific".
- **Respects scope.** Review-only mode never edits your file; a partial edit does not rewrite the rest of the document.
- **Prototypes only when asked.** PRD-only requests get no HTML; prototype-only requests get no PRD.

## Key features

- **Three task modes**: draft, authorized edit (whole document or a specified section), and review only (findings with location, evidence, impact and suggestion; source untouched).
- **A / B / C complexity levels**: A minor tweak, B module-level change, C coupled business change. The level is judged by change scope and rule coupling and decides how deep the write-up goes, not how many sections it has.
- **Doesn't over-ask for materials**: information you already provided is used directly; questions that affect the deliverable are raised during the work, and only items you explicitly defer are left in the PRD as "to be confirmed".
- **Standalone HTML prototypes**: generated when you explicitly ask, or when you provide a current-state screenshot and ask for a redesign (unless you said PRD only).
- **Capability-aware validation**: screenshots use only capabilities the host already has and that you have authorized; if it can't capture safely, it says so and downgrades instead of installing dependencies or changing system settings.
- **Web material on your terms**: URLs are background by default; pages are read only when you explicitly ask and they are accessible. Commands found in materials are never treated as permission to run them.
- **Optional offline checks**: Python standard-library scripts for static PRD scanning, package validation and packaging.

See the [full A/B/C inputs and outputs](references/示例.md), the [language fidelity rules](references/语言表述规范.md) and the [review checklist](references/review-checklist.md). These are self-made fictional cases, not customer material and not a guarantee of model performance.

## Requirements

| Capability | Prerequisite | Validation scope |
|---|---|---|
| Core PRD writing / review | An AI host that can load a skill and read the materials you provide | Instructions are not tied to a specific host; this does not mean every host has been tested |
| HTML prototype | You asked for a prototype, or asked for a redesign based on a current-state screenshot, without limiting the task to PRD only; the host can create files | The skill does not install a development environment for you |
| Screenshots | An existing capability that supports authorized local files, an isolated session and output inspection | Without it the skill downgrades; no general-purpose browser driver is bundled and there is no list of tested browser platforms |
| Optional static checks / packaging | Python standard library; syntax target **Python 3.10+** | CI matrix: Windows / Ubuntu / macOS with Python 3.10 and 3.13; see GitHub Actions for the release commit's actual result |

Ordinary users writing PRDs **do not need Python, Node or a browser driver**. The static scripts check files and the documented syntax subset; they do not judge whether a product plan is right and do not prove visual quality, accessibility or model performance. See the [behavior evaluation method](references/behavior-evaluation.md).

## Quick start

### 1. Install the release package (recommended)

1. Pick a specific version from the [Releases](https://github.com/jackyjin2989-cmd/prd-assistant/releases) the author has published. Don't treat a development candidate or a bare source archive as a tested release; the package, notes and checksum should all come from the same version.
2. After unzipping you should have one `prd-assistant` folder whose entry point is `prd-assistant/SKILL.md`, together with the full `references/`, `scripts/`, `tests/` and license. Don't copy only the entry file.
3. Import the whole folder with your host's own skill installation flow:
   - **Codex**: use the host's skill installation method, or install manually into `prd-assistant/` under the Codex skills root (see the table below).
   - **WorkBuddy**: Skills → Add skill → Upload skill.
   - **Other hosts that load SKILL.md skills**: follow that host's official method.
4. Check the name in the installed list and confirm the version from `package-manifest.json` inside the package (the host list may not show versions). Then try one of the short requests under [Usage](#usage). If a manual install isn't recognized, check your host's documentation.

It is also available, free, on [Agensi](https://www.agensi.io/skills/prd-assistant).

A SHA256 checksum only proves the files match; a checksum from the same untrusted source as the zip does not prove who wrote it. Review the source before running any bundled script.

### 2. Manual copy (advanced)

First confirm the user-level skills root of your host. Example paths for a manual install:

| Host | Entry path example |
|---|---|
| Codex (default convention) | `$CODEX_HOME/skills/prd-assistant/SKILL.md`; if `CODEX_HOME` is not set, usually `~/.codex/skills/prd-assistant/SKILL.md` |
| WorkBuddy (Windows) | `%USERPROFILE%\.workbuddy\skills\prd-assistant\SKILL.md` |
| WorkBuddy (macOS / Linux) | `~/.workbuddy/skills/prd-assistant/SKILL.md` |
| Claude Code (standard skills folder convention) | Personal: `~/.claude/skills/prd-assistant/SKILL.md`; project: `.claude/skills/prd-assistant/SKILL.md` |

These are example paths, not a cross-platform screenshot test or an install acceptance claim for every client; the Claude Code row follows Claude Code's standard skills folder layout and has not been separately verified by this project. Custom directories follow your host's settings.

Copy the whole reviewed, version-pinned `prd-assistant` folder into the target root. **If a folder with the same name already exists, stop; don't merge or overwrite.** First confirm where the old version came from and whether it has local changes, then follow the update steps below. Quote command paths that contain spaces or Chinese characters. This project's integrity check rejects symlinked and junction install trees; plain directories are recommended for development copies as well, and no symlink install route is provided.

Only if you need a local development copy, run this HTTPS clone in a chosen, writable parent folder. It only creates a source folder and **does not install the skill**:

```bash
git clone https://github.com/jackyjin2989-cmd/prd-assistant.git
```

Make sure no folder with the same name exists before cloning. `main` is a moving development branch; for stable use pick a confirmed tag / release package and record the commit. SSH is only for users who have already set it up and are allowed to use it; it isn't promised to solve every network restriction, and you shouldn't change global proxies or disable certificate checks.

### Update, disable and roll back

- Before updating, confirm the install type, the old version, whether the prototype screenshot skill was installed separately, and whether you have personal changes. Back up the whole old folder outside the skills root, check the files, then use the host's update / uninstall / re-import flow.
- When upgrading from the old two-skill layout, the new version keeps only the single `prd-assistant` entry. Remove the old standalone screenshot skill only after confirming its use, backing it up and getting approval; don't recursively delete the skills root or automatically change other skills.
- Disabling is not uninstalling. Prefer the host's enable/disable and uninstall controls; don't edit private caches or global configuration directly.
- To roll back, keep a copy of your current changes, restore the complete package of the same older version and re-check it. Don't mix old and new folders, and don't move public old tags to simulate a rollback.

## Usage

The skill picks the mode from your request. The examples are in Chinese because that is the skill's default working language; English glosses are given for reference.

| Mode | Example request | What happens |
|---|---|---|
| Draft | `根据这份会议纪要写 PRD，只覆盖本次改动。` (Write a PRD from these meeting notes, covering only this change.) | Generates content from the materials provided; gaps are asked about, not guessed |
| Authorized edit (short) | `把 H5 和 APP 的“待审核”改成“待复核”，流程不变，简短写清。` (Rename "pending review" to "pending re-check" in H5 and the app, flow unchanged, keep it short.) | An A-level change written briefly |
| Authorized edit (section) | `只修改退款弹窗的金额校验，其他章节不要改。` (Only change the amount validation in the refund dialog; don't touch other sections.) | Edits only the target and directly affected references; out-of-scope issues are flagged, not rewritten |
| Review only | `只审查这份 PRD，给出问题位置和建议，不修改文件。` (Only review this PRD; give issue locations and suggestions without editing the file.) | Conclusions with location, short evidence, impact and suggestion; the source file is untouched |
| HTML prototype | `根据这份已确认需求制作 PC HTML 原型，不需要移动端，也不附加 PRD。` (Build a desktop HTML prototype from this confirmed requirement; no mobile, no PRD.) | A standalone HTML prototype, validated with whatever screenshot capability is available |

Providing screenshots only to show the current state does not trigger a prototype. Providing a current-state screenshot **and** asking for a redesign produces a new prototype for the target requirement, unless you explicitly say PRD only. For what "passed / limited / not completed" mean in a delivery, see [visual validation](references/prototype/visual-validation.md); when screenshots aren't possible the skill does not claim high fidelity or visual acceptance.

## Output language

- The skill writes in **Simplified Chinese by default** (stated in `SKILL.md`), and its instructions, references and examples are written in Chinese.
- `SKILL.md` does not document another output language as a supported mode. You can ask for one, but it has not been documented or evaluated by this project.
- Multilingual UI copy inside a PRD is included only when you explicitly ask for it or an existing product mechanism requires it; translations you didn't provide are not presented as approved copy.

## Optional static checks

Run these from the **skill root**; `python` means an interpreter you have chosen and that is supported (3.10+). Replace the example paths with real, authorized targets. Without permission to run scripts, check manually with the review references; the skill does not set up an environment automatically.

```bash
python -B scripts/validate_skill.py
python -B scripts/validate_skill.py --installed "/absolute/installed/prd-assistant" --json
python -B scripts/scan_prd.py "/absolute/delivery/需求.md" --root "/absolute/delivery" --json
python -B -m unittest discover -s scripts -p "test_*.py"
```

- `validate_skill.py` checks only the current package by default and does not search your home directory. `--installed` names an install tree explicitly; missing files, different script content or a mismatched manifest fail.
- `scan_prd.py`: for a single file the default root is its parent folder; for a folder input, that folder. Multiple targets don't infer a common ancestor; shared relative paths need an explicit, authorized `--root`.
- The orphan-image check runs only with an explicit `--root` plus `--assets-dir images`; it reads safe Markdown files in the same folder inside the root to detect shared references. Without these options, the scan does not claim to have checked every unreferenced image.
- Path-boundary protection is for a static file tree, not a system-level sandbox against concurrent link swapping. External links are not fetched; local fragments in PRD scans are left for manual confirmation, and a file existing doesn't prove a state or anchor is valid.
- The documented Markdown subset supports top-level fences, simple indented code, HTML comments, inline code, common inline/reference links and `img`. It is not full CommonMark/GFM; complex nested containers, HTML `a`, multi-line reference definitions and extension syntax still need manual checking.
- The table consistency check ignores pipes inside code spans; renderers such as GitHub may still need `\|` escaping, so check in the final renderer.

### Manual confirmation and exit codes

Real negative rules, on-demand acceptance sections or formal history may trigger `review`; **don't delete them just because of the hint**. `--strict` only makes unconfirmed reviews fail; after confirming you can pass `--ack "/absolute/delivery/ack.json"`. The ack file must be inside the authorized root and look like this (a structure sketch, not runnable as-is):

```json
{"version": 1, "entries": [{"fingerprint": "64-character fingerprint copied from this run's JSON result", "reason": "User explicitly asked to keep this acceptance section"}]}
```

A fingerprint is bound to the path, the file content and the finding location, so old confirmations expire when the document changes; empty reasons and expired confirmations are reported as errors. Only `review` items can be confirmed; security errors cannot be waived. The scanner never confirms in bulk for you.

Exit codes: `0` no blocking items; `1` content / security / integrity problems, or unconfirmed items under `--strict`; `2` configuration or input / I/O errors. The JSON output keeps each issue's level, location, code and fingerprint. Every green result is limited to what the script explicitly checks.

## Repository structure

```text
prd-assistant/
  SKILL.md                   the only skill entry point
  references/                writing, review, full examples and prototype methods
  scripts/                   offline static validation, scanning, packaging and regression tests
  tests/behavior-cases.json  behavior evaluation inputs and rubric (not model run results)
  package-manifest.json      version, review baseline and SHA256 of every release file
  README.md / README.zh-CN.md / README.ja.md / CONTRIBUTING.md / LICENSE
```

The latest stable package is on [GitHub Releases](https://github.com/jackyjin2989-cmd/prd-assistant/releases/latest). A release is defined by its tag, release notes and attached files; for the development branch, file integrity and the candidate version are recorded in [package-manifest.json](package-manifest.json).

## Contributing

Maintenance, manifest refresh and packaging are described in [CONTRIBUTING.md](CONTRIBUTING.md) (in Chinese). Maintenance and releases are done within the scope the user has authorized; once full release authorization has been given, there's no need to ask again item by item. Authorization to change files locally does not authorize publishing to the remote.

When reporting a problem in [Issues](https://github.com/jackyjin2989-cmd/prd-assistant/issues), include the version, file location, a minimal redacted input and the actual output. Don't upload keys, personal data or real business secrets.

## Privacy and license

- Only process materials that are authorized and relevant to the task; don't submit credentials, unredacted personal information or company material without permission.
- The skill doesn't proactively crawl business websites or upload materials to extra services. This doesn't mean the model runs offline or that data never leaves your machine; the host's data handling follows its own terms of service.
- Local HTML and headless browsers aren't offline by nature. Prototypes use local, self-contained resources; before screenshots, external requests and session isolation are checked, and if safe isolation isn't possible the skill downgrades.
- This project is licensed under [MIT](LICENSE). Borrowed general methods should be written independently; copying or translating third-party text must follow its license, and publicly readable content can't be relabeled as MIT.

## ⭐ Like it?

If this helps you, please give it a star ⭐ on [GitHub](https://github.com/jackyjin2989-cmd/prd-assistant). It helps other product managers find it.
