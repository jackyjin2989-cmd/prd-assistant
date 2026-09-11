---
name: html-prototype-screenshot
description: 在 macOS 上不打扰用户地渲染本地 HTML（原型/页面）并截图做视觉验证，包括滚动到指定位置、切到指定页面后再截图。凡是需要「看一眼自己写的 HTML 长什么样」「验证布局/吸底/图表是否生效」「给 HTML 原型截图」时调用。本技能只做渲染与验证，不写 PRD。
agent_created: true
---

# 本地 HTML 截图验证（macOS 无头 Edge）

## 与 prd-assistant 的分工

两个技能只做各自那一半，不要互相抄：

- **本技能负责「怎么截、怎么量」**：命令、参数、探针注入、裁剪坐标、批量脚本、CSS 静默失效的坑。
- **`prd-assistant` 负责「判定标准」**：能不能截图与什么情况降级、逐项比对的先后、什么算通过、结论怎么写（见其 `references/prototype/visual-validation.md`）。
- 写 PRD 遇到「要不要截图 / 截了算不算过」→ 看 prd-assistant；落到具体命令与参数 → 看本技能。判定规则只维护一份，本技能不重复定义。

## 何时用

- 写完/改完本地 HTML（原型、报表、看板）后，要确认实际渲染效果。
- 要验证需要真实布局引擎才能确认的东西：`position:sticky/fixed` 吸底、flex/grid 分布、图表绘制、长文滚动、按钮禁用态。
- 不要只依赖 jsdom：jsdom 没有布局引擎，只能验结构（DOM 是否生成、脚本是否报错），不能验「位置对不对」。

## 核心命令

```bash
cd /tmp && ( "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge" \
  --headless=old --no-sandbox --disable-gpu --hide-scrollbars \
  --virtual-time-budget=3500 \
  --screenshot=/tmp/shot.png --window-size=1400,1000 \
  "file:///abs/path/to/page.html" >/dev/null 2>&1 & ) ; sleep 22 ; ls -la /tmp/shot.png ; pkill -f "Microsoft Edge"
```

要点：

- **必须 `--headless=old` 配 `--no-sandbox`**。用 `--headless=new` 会报 `sandbox initialization failed: Operation not permitted` + `GPU process isn't usable. Goodbye.`，截不出图。
- 进程**不会自动退出**，用 `&` 丢后台 + `sleep 20~25` 再取文件；取完 `pkill -f "Microsoft Edge"`。不要用 `timeout` 包住前台（会触发工具超时被自动转后台）。
- 一次只跑一个实例。同一个默认 profile 并发起两个 Edge 会互相锁 profile，两个截图都拿不到。
- 路径含中文要先 URL 编码，或直接把文件复制到 `/tmp/英文名.html` 再截。
- 文件路径用 `file:///` 绝对路径。

## 截「滚动之后 / 指定页面」的状态

无头截图只截首屏和初始状态。要验滚动或其它路由，先复制一份 HTML，在 `</body>` 前注入一段脚本：

```python
import io
s = io.open(src, encoding='utf-8').read()
s = s.replace('</body>', '<script>window.addEventListener("load",function(){'
              'document.getElementById("viewport").scrollTop=760;})</script>\n</body>')
io.open('/tmp/probe.html','w',encoding='utf-8').write(s)
```

- 滚动：`<滚动容器>.scrollTop = N`。
- 切页：调用页面自己的路由函数，如 `go('buy-result')`；没有路由函数就手动切 class，如 `document.querySelectorAll('.screen').forEach(s=>s.classList.toggle('on', s.id==='s-x'))`。
- 配合 `--virtual-time-budget=3500` 给脚本和动画留时间。

## 怎么判断吸底有没有生效

- 在**初始滚动位置**截图：吸底元素就应该已经贴在容器底部（因为它的静态位置在内容末尾、视野之外），而不是跟内容排在中间。
- 再截一张滚动后的：元素位置应保持贴底不变。
- 内容不足一屏的短页面也要截一张：吸底元素仍应在底部，而不是紧跟在内容后面。

## 与 `screencapture` 的区别

- `screencapture -x` 截的是用户整块屏幕，需要「屏幕录制」权限，而且要求窗口在前台 —— 会打扰用户、也不可靠。
- 无头 Edge 截图完全离线、不抢焦点、不碰用户屏幕，是首选。

## 常用配套校验

结构校验（脚本是否报错、DOM 是否按预期生成）用 jsdom 更快：

```bash
NODE_BIN=$(ls -d ~/.workbuddy/binaries/node/versions/22.* | tail -1)/bin/node
cd ~/.workbuddy/binaries/node/workspace
NODE_PATH=$PWD/node_modules "$NODE_BIN" /tmp/check.js
```

要点：**node 版本目录会随宿主升级变化**（如 `22.22.2-2` → `22.22.2-3`），路径写死会 `command not found`；用上面这行取最新版，或先 `ls ~/.workbuddy/binaries/node/versions/` 确认。

`check.js` 里用 `new JSDOM(html, {runScripts:'dangerously', pretendToBeVisual:true})` 加载本地文件，然后断言元素数量、文本内容、`[data-*]` 开关是否生效。视觉验证仍以无头 Edge 截图为准。

## 放大局部看细节

整屏截图看不清字号/配色/对齐时，先裁再放大再读：

```python
from PIL import Image
im = Image.open('/tmp/shot.png')
c = im.crop((610,150,1030,350))                 # 先按经验估个框
c = c.resize((int(c.width*2.5), int(c.height*2.5)), Image.LANCZOS)
c.save('/tmp/zoom.png')
```

裁错位置就按比例修正重裁，成本很低。要比对参考图时，用同一手法把参考图和自绘结果都放大，逐项目视比对。

## 量尺寸：比截图更准的 `--dump-dom`

「这行到底折没折」「这列够不够宽」不要靠肉眼估——让页面自己把 `getBoundingClientRect()` 报出来，用 `--dump-dom` 抓回来：

```bash
# 探针 HTML：load 后切状态、量尺寸、写进 document.title
# <script>window.addEventListener("load",function(){ ...; document.title='RESULT '+out.join(' | '); });</script>
( "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge" --headless=old --no-sandbox --disable-gpu \
  --virtual-time-budget=3000 --dump-dom "file:///tmp/probe_measure.html" 2>/dev/null | grep -o "RESULT[^<]*" | head -1 ) ; pkill -f "Microsoft Edge"
```

要点：

- **`| head -1` 必须加**：`--dump-dom` 会把整份 DOM（含探针脚本源码本身）打出来，`RESULT` 字样会命中两次。
- **不用 `&` + sleep**：`--dump-dom` 在前台等 2~3 秒就返回，比截图快得多（3 秒 vs 17 秒），适合反复试参数。

判读：

- **折行**：比较 `getBoundingClientRect().height` 与行高的整数倍。单行 ≈ line-height + 上下 padding；多一行高度会跳到约两倍 + `row-gap`（例如单行 25、两行 45）。
- **换行/裁切**：`el.scrollWidth > el.clientWidth` 即内容被挤。
- **找阈值**：在探针里遍历候选字号 `[9,9.5,10,10.5,11]`，逐个设 `style.fontSize` 后读高度，一次就能拿到「最大能塞下的字号」，不用反复截图猜。

流程建议：**先用 `--dump-dom` 定参数（快、给数字），再用截图确认整体观感（慢、给画面），最后才判断改完了。**

## 批量截多个页面 / 弹窗（写脚本，别一条条来）

要一次性截十几二十个页面、签页、弹窗（比如给 PRD 插全套截图）时，写成一段 Python 循环，比手敲命令稳得多：

```python
EDGE = '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'
SHOTS = [("01-模块-状态", "go('x');"), ("02-模块-状态", "go('y');ruleTab('out');"), ...]
for name, js in SHOTS:
    io.open(probe, 'w', encoding='utf-8').write(src.replace('</body>',
        '<script>window.addEventListener("load",function(){' + js + '});</script>\n</body>'))
    subprocess.Popen([EDGE, '--headless=old', '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
                      '--virtual-time-budget=3500', '--screenshot=' + raw,
                      '--window-size=1400,1000', 'file://' + probe],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(14)
    subprocess.run(['pkill', '-f', 'Microsoft Edge'], capture_output=True)
    time.sleep(1)
    Image.open(raw).crop((629, 27, 1021, 873)).save(dst)   # 只留手机区域
```

要点：

- **一次只能跑一个 Edge 实例**，所以脚本里必须串行：起进程 → `sleep 14` → `pkill` → 下一个。14 秒够用（比单条命令的 20 秒省）。
- **断点续跑**：循环开头判 `os.path.exists(dst): continue`，中断后重跑不会重复截已有的。
- **只截手机区域更好用**：手机位于 1400×1000 窗口的 `(629,27)-(1021,873)`（左侧 250px 侧栏 + stage 居中 390px 手机）。裁掉侧栏后是 392×846，插 PRD 或写文档都干净。布局改了要重新校这一组坐标。
- **弹窗要先打开再截**：探针里直接调触发函数（填值 → 勾协议 → `recalcX()` → `submitBtn.click()`），注意按钮 disabled 时 click 不触发，顺序别写反。
- **长页面按滚动分段**：先量出各模块 `offsetTop` 与 `scrollHeight`，再按段取 `scrollTop`；`scrollTop` 超过 `scrollHeight - clientHeight` 会被自动夹紧，所以最后一段可以直接给个很大的数。
- **按文档所述状态取图**：批量给文档截图前，先读文档里每个状态/开关写了什么效果（如「未采购晨星时不展示评级」），直接截那个状态，不要拿默认态顶替；改过文案、样式或状态逻辑后，受影响的图列入重拍清单重截。这条规则的完整定义与交付前核对清单归 `prd-assistant`，见其 `references/图片嵌入与截图指南.md`；本技能不重复定义。

## 三个会让 CSS 静默失效的坑（踩过）

1. **变量没定义 → 整条声明作废**。`background:var(--orange-soft)` 里 `--orange-soft` 若在 `:root` 没定义，浏览器不会报错，只是背景透明、颜色回落到继承值 —— 表现为「样式写了但完全没生效」。改配色前先 `grep "^:root" -A 10` 确认 token 真实存在；文件被大改过之后尤其容易丢变量。
2. **`font` 简写里 family 写 `inherit` 不可靠**。`font:600 21px/1.25 inherit` 这种写法有时被整条丢弃（字号退回输入框默认 13px 左右）。一律拆成长写：`font-family:inherit;font-size:21px;font-weight:600;line-height:1.25`。`font:inherit` 单独用没问题。
3. **容器套容器会显脏**。卡片里再放一个带灰底的圆角输入框、再套一层费率小卡，视觉上就是「盒子套盒子」。移动端表单优先扁平：大号无框输入 + 一条分割线 + 平铺文字，层级靠字号/颜色而不是边框。

改完这三类问题，务必重新截图确认，别只看代码。
