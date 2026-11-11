# ERPgyjerp — 管伊佳 ERP UI + 接口自动化

把 `data/cases.xlsx` 里的 **125 条用例**（多单位 44 条、商品信息 43 条、仓库信息 38 条）
按编号落成可执行脚本，**同一套编号、两套实现**：

| 层 | 实现 | 条数 | 单条耗时 | 用途 |
| --- | --- | --- | --- | --- |
| UI（默认） | 在桌面 MyTest 浏览器里点页面 | 117 | 10~30 秒 | 端到端验证，看得到界面反馈 |
| 接口 | 直接打后端 `/jshERP-boot/*` | 71 | 0.2~3 秒 | 快速回归、校验服务端真实约束 |

两层都自带断言、测试数据回收，以及 **Markdown / Allure** 两种执行报告。
表里是「能自动跑的条数」，另有 UI 8 条 / 接口 7 条为阻塞（需人工或前置不具备），
脚本会如实标「阻塞」而不是假装通过，明细见「用例覆盖」。

## 前置条件

**UI 层（`--layer ui`，默认）**

1. 双击桌面 **MyTest.exe** 打开浏览器（它启动时带 `--remote-debugging-port=9231`，
   见 `MyTest.exe.lnk` 的启动参数），并在其中登录 https://cloud.gyjerp.com ；
2. 保持该浏览器窗口开着——脚本是「接入」它，不新开浏览器、不关闭它。

> 为什么走 CDP 接入而不是自己 launch：MyTest 里已有登录态和完整的业务现场，
> 直接接管可以跳过账号/验证码，也不会干扰用户正在看的页面。

**接口层（`--layer api`）**

1. 首次运行需要 MyTest 浏览器开着并已登录——从中取一次 `x-access-token` 并缓存到 `.api_token`；
2. 之后**浏览器不开也能跑**，可进 CI。token 失效（服务端返回登录过期）会自动回源重取，
   此时仍需浏览器在线；浏览器也不在时，每条用例的前置检查都会失败并记「阻塞」，整轮照常跑完，不会拿失效 token 硬跑成一片失败。

## 安装

```bash
cd D:/Automation/ERPgyjerp
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt

# 开发/CI 额外装 lint、提交守卫（纯执行环境可以不装）
./.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
./.venv/Scripts/python.exe -m pre_commit install

# Allure 报告生成器（Java 版 CLI，随项目装，不污染全局）
npm install --prefix tools/allure allure-commandline
```

Allure 需要机器上有 **Java 11+**（当前环境是 Java 21）。只跑用例不出 Allure 的话这一步可以跳过。

接口层不引入新依赖（HTTP 用标准库 `urllib`），Python 环境装好即可跑。

## 运行

### 可视化控制台（日常推荐）

```bash
./.venv/Scripts/python.exe dashboard_server.py
```

服务监听 http://127.0.0.1:8760/ ，起来后自动打开浏览器。控制台分两层：
`dashboard_server.py` 只做「解析参数 → 起服务」（138 行），实现在 `dashboard/` 包里
按职责分文件（探测 / 执行 / 路由 / 动作各自独立）；`dashboard/index.html` 是页面，
每次请求实时读取，改 HTML 不用重启服务。依赖方向见 `dashboard/__init__.py`。

一屏三块：

- **环境监控** —— 控制台服务、MyTest 浏览器（CDP 9231）、业务页面/登录页、目标站点、
  用例库条数、playwright 依赖，每 5 秒自动探一轮。没就绪的卡片上直接带修复按钮。
- **用例选择** —— UI / 接口层切换，按模块、标签、关键词筛选，逐条勾选或「全选可执行」；
  表格里直接标出该层「可执行 / 阻塞 / 该层无实现」，「该层无实现」的行不可勾选；阻塞行可以勾，执行时如实记「阻塞」并写进报告。
- **执行配置 + 实时日志** —— 勾好点「开始执行」，等价于跑
  `run_cases.py run --only <勾选的编号> [--layer api]`；日志实时流回页面，
  进度、通过/失败/阻塞/异常计数、报告入口都在同一块，随时可「停止」。

顶栏的 **「一键准备环境」** 会按当前检查结果决定做什么，只做缺的那步：

- MyTest 没启动 → 按钮显示「启动 MyTest」，点了拉起桌面快捷方式；
- 浏览器已开但没有业务页 → 显示「打开业务页」，点了在浏览器里新开一个；
- 都齐了 → 显示「环境已就绪」并置灰，不会重复启动。

参数：`--port 8800` 换端口（也可用环境变量 `ERP_DASH_PORT`）、`--no-browser` 不自动开浏览器。
面板只监听回环地址（`127.0.0.1` + `::1`，不对外暴露），写操作校验 Origin，「打开报告」只允许 `reports/` 下的文件。

**必须通过 http 地址访问，不要双击 `dashboard/index.html`。** 用 `file://` 打开时浏览器访问不到
`/api/*`，页面取不到任何数据；这种情况下页面顶部会直接写明原因和正确的访问地址。

两个和"看起来像页面坏了"有关的行为：

- 端口已被占用（比如重复启动）时**不会再起第二个实例**，而是提示「已有控制台在运行」并直接打开它；
- 服务中途停掉时页面顶部会出红色「控制台服务未连接」条，服务恢复后自动消失，不用手动刷新。

### 交互式（手动跑推荐）

```bash
./.venv/Scripts/python.exe run_cases.py
```

不带任何参数时先进菜单，选好范围再执行（UI / 接口两层都能从菜单启动）：

```
==================================================================
 管伊佳ERP 自动化
 UI 层 125 条（可自动 117）　接口层 78 条（可自动 71）
==================================================================
   1  全部执行（UI）
   2  按模块执行（UI）
   3  按标签执行（UI）
   4  输入用例编号（UI）
   5  接口层执行（全部 / 按模块 / 按编号）
   6  只看清单，不执行
   q  退出

 请选择 [1]:
```

- 选 2 / 3 会再列出模块或标签（各自带条数与可自动数），可单选也可多选：`1`、`1,3`、`1-3`
- 选 4 支持逗号与同前缀区间：`TC-DEP-001,TC-DEP-005`、`TC-DEP-001-010`
- 选完先显示「待执行 N 条」：回车开始、`u` 开始并回填用例表、`n` 返回重选
- 二级菜单里输 `b` 可返回主菜单，输错序号会原地重问，不会把你踢到顶层

选 5 进入接口层子菜单（不走浏览器，直接打后端）：

```
----------------------------------------------------------------
 接口层：直接打后端，不经过浏览器　78 条，可自动 71 条
----------------------------------------------------------------
   1  全部执行
   2  按模块执行
   3  输入用例编号
   4  只看清单
   b  返回主菜单

 请选择 [1]:
```

- 接口层的「按模块」只列该层有实现的模块（多单位 31 / 商品信息 22 / 仓库信息 25，含阻塞条目）
- 接口层的「输入用例编号」只认该层有的编号，纯 UI 的编号会被忽略并提示
- 确认页会标注「接口层」，回填按钮也换成提示：`u` 会**覆盖同编号的 UI 结果**，两层都跑过就别急着回填
- 在接口子菜单里按 `n` 回到**接口子菜单**继续选，按 `b` 才回主菜单
- 菜单执行与 `run_cases.py run --layer api` 等价，只是省得记参数

### 直接指定（脚本 / CI）

只要带了参数就不进菜单：

```bash
# 全部 125 条（可自动 117 条，约 60~70 分钟；8 条阻塞会直接跳过）
./.venv/Scripts/python.exe run_cases.py run

# 只看清单：哪些能自动、哪些需要人工
./.venv/Scripts/python.exe run_cases.py list

# 按模块 / 编号 / 标签 / 起始编号挑着跑
./.venv/Scripts/python.exe run_cases.py run --module DEP
./.venv/Scripts/python.exe run_cases.py run --only TC-UNIT-012,TC-UNIT-013
./.venv/Scripts/python.exe run_cases.py run --tag 新增 查询
./.venv/Scripts/python.exe run_cases.py run --from TC-MAT-001

# 跑完把结果回填用例表「执行结果」列（会先备份原表）
./.venv/Scripts/python.exe run_cases.py run --update-xlsx

# Allure 报告：默认单文件；off 关闭；multi 生成多文件版
./.venv/Scripts/python.exe run_cases.py run --allure off
./.venv/Scripts/python.exe run_cases.py run --allure multi
```

`--module` 可选值：`UNIT` 多单位、`MAT` 商品信息、`DEP` 仓库信息，可写多个（`--module UNIT DEP`）。
`--layer` 可选值：`ui`（默认，走页面）、`api`（打接口），详见下文「接口自动化」。

> 非交互环境（重定向、后台、CI）里即使不带参数也不会等输入，会直接跑全部并打一行提示，
> 不会把流水线挂住。想在终端里跳过菜单，用 `run_cases.py run`。

### 页面探查

新增用例或页面改版后核对选择器，不产生业务数据：

```bash
./.venv/Scripts/python.exe tools/probe.py            # 当前页面结构
./.venv/Scripts/python.exe tools/probe.py modal      # 多单位弹窗 / 校验 / 批量确认框
./.venv/Scripts/python.exe tools/probe.py product    # 商品页「多单位」下拉
./.venv/Scripts/python.exe tools/probe.py depot      # 仓库页表头列序 / 操作列链接 / 新增弹窗 / 设为默认 Popover
```

> `probe.py depot` 会把表头按 `cells[i]` 下标逐行打出来，**这是 `pages/depot_page.py` 里 `ROWS_JS`
> 列索引的唯一依据**——仓库页改版（加减字段、调列序）后先跑它，再对照输出改索引，别凭记忆。
> 它对弹窗只做「空表单保存」（会被校验拦住、不落库）和「设为默认 → 取消」，不会改真实数据。

> 旧写法 `run_cases.py --only ...`、`--list` 仍然可用，会自动映射到对应子命令。
> 原来的 `run_unit_crud.py`（独立 CRUD 冒烟）已删除——它的链路已被 `cases/` 中的用例完全覆盖，
> 需要冒烟时用 `run_cases.py run --tag 新增 查询`。

输出示例（2026-11-03 仓库信息模块实跑，36 条可自动）：

```
运行前缀 ATX85P，共 36 条用例

[ 1/36] TC-DEP-001 通过左侧菜单进入仓库信息页面
        · 偏差：菜单进入后浏览器标题未更新（'管伊佳ERP'）
        OK   通过（16.1s）
...
[23/36] TC-DEP-023 仓库名称超长与特殊字符
        · 缺陷：仓库名称含 emoji 时保存报「数据查询异常」，弹窗保持打开无法保存
        FAIL 失败（17.0s）｜仓库名称含 emoji 应可正常保存，实际触发「数据查询异常」
...

通过 35 / 失败 1 / 阻塞 0 / 异常 0　总计 36　用时 785s

报告：reports/run_20261103_182121.md
Allure：reports/allure-report/20261103_182121.html
```

退出码：`0` 全绿；`1` 有失败/异常；`2` 登录失效需要人工重新登录；`130` 手动中断（Ctrl-C）。

## 接口自动化（--layer api）

同一套**用例编号**，两套实现：`--layer ui` 走浏览器页面（默认），`--layer api` 直接打后端接口。
接口层一条用例通常 0.2~3 秒，UI 层 10~30 秒，回归用它快一个数量级。

当前接口层覆盖 **71 / 125** 条（多单位 28、商品信息 20、仓库信息 23）。剩下的是纯页面交互类
（左侧菜单进入、分页器、列设置、Popover 位置、试用到期等），没有对应接口语义，只在 UI 层跑。

```bash
# 接口层全量（78 条含 7 条阻塞，实测约 3 分钟）
./.venv/Scripts/python.exe run_cases.py run --layer api

# 按模块 / 编号 / 标签
./.venv/Scripts/python.exe run_cases.py run --layer api --module UNIT MAT
./.venv/Scripts/python.exe run_cases.py run --layer api --only TC-DEP-017,TC-DEP-025

# 看接口层的执行计划（78 条，含 7 条阻塞标注）
./.venv/Scripts/python.exe run_cases.py list --layer api

# 接口层的 Allure 报告同样可用
./.venv/Scripts/python.exe run_cases.py run --layer api --allure auto
```

### 接口约定（写用例前必读）

- 前缀 `/jshERP-boot`，认证只有一个请求头 `x-access-token`（39 位）；
- **业务失败也返回 HTTP 200**，必须看响应体的 `code`：`200` 成功、`300` 查询异常、
  `301` 写入异常、`500` 未知异常、`8000005` 业务提示；
- 错误提示优先取 `data.message`；取不到时 `extract_message` 会回退到 `data` 字符串和顶层 `message`，
  写断言别只读顶层 `message`；
- 列表接口不传 `field` 会返回全字段（编辑时可直接拿列表行构造 body）；传了 `field` 就只返回这些列；
- 删除/状态类沿用前端习惯：`ids` 形如 `"1,2,"`（每个 id 后面都带逗号），单条删除用 `{"id": x}`。

`framework/api_client.py` 管传输和错误码解析，`apis/base.py` 管通用语义，用例里只写业务：

| 方法 | 所在层 | 用途 |
| --- | --- | --- |
| `ok(...)` | client | 期望成功，非 200 业务码直接抛 `ApiError` |
| `reject(...)` | client | 期望被拒绝，返回 `(code, message)`；真的成功了算失败 |
| `code_msg(...)` | base | 把 `(HTTP 状态码, 响应体)` 归一成 `(业务码, 提示语)` |
| `add_raw / update_raw` | 各 api | 原样提交，返回 `(业务码, 提示语)`，不预设成败 |
| `find(...)` | 各 api | 按名称查单条（各模块匹配口径不同），用于断言落库结果 |
| `all(...)` | base | 按搜索条件查一批 |
| `ids_param(...)` | base | 拼 `"1,2,"` 形态的 ids 参数 |

### 认证与 token

首次从 MyTest 浏览器 localStorage 的 `pro__Access-Token` 取值并缓存到项目根 `.api_token`
（已加 gitignore，**不要提交**），之后浏览器不开也能跑；token 失效会自动回源重取。

token 打不开局面时，每条用例会在「前置：登录态检查」这一步失败并记「阻塞」——整轮仍会跑完，
但报告里是一片带原因的阻塞，不会用失效 token 硬跑成一片失败。接口层没有「等人工重新登录」这条路径，
需要时先打开 MyTest 登录一次即可。

### 数据纪律（接口层专属）

三条和 UI 层一致（前缀命名、先记账再落库、绝不碰既有数据），接口层最要紧的两条：

- 跑完按 **id 精确回收**：用例可能把名称改成 `null/(...)` 之类，按名字根本搜不到，必须用创建时记下的 id；
- 「本应被拦截却成功了」的用例，**先回滚脏数据再判失败**（快照对比找出新增行再删），
  避免脏数据污染后续用例，也避免把「后端没校验」误写成「脚本出错」。

完整规则（含前缀兜底、回收后清账、回收前后比总数）见文末「测试数据纪律 → 接口层补充」。

接口封装在 `apis/`（对标 `pages/`：`unit_api.py` / `material_api.py` / `depot_api.py`），
用例在 `cases/unit/api.py` / `cases/material/api.py` / `cases/depot/api.py`，
HTTP 客户端在 `framework/api_client.py`，造数与回收在 `framework/api_context.py`。

接口清单、请求体样例与实测校验口径见 [`docs/接口契约-多单位-商品-仓库.md`](docs/接口契约-多单位-商品-仓库.md)，
其中记录了「UI 有红字拦截、后端其实没校验」的一系列缺陷（空表单建商品、重名仓库、删除被引用单位等）。

### 重新采集接口

页面改版或要覆盖新模块时用这三个工具，产物落在 `tools/api_dump/`（已 gitignore，1MB 左右）：

```bash
./.venv/Scripts/python.exe tools/api_recorder.py            # 只读：加载/查询/翻页/开关弹窗，不落库
./.venv/Scripts/python.exe tools/api_recorder_write.py      # 写链路：测试前缀下跑完整 CRUD，抓 add/update/delete/状态
./.venv/Scripts/python.exe tools/api_recorder_write.py unit depot product   # 只抓指定模块
./.venv/Scripts/python.exe tools/api_probe_server.py        # 服务端校验行为探测：空值/缺字段/越界/重名
```

`api_recorder_write.py` 会真实造数据，但用的是本次运行前缀，跑完按前缀回收；
`api_probe_server.py` 探测完会按登记过的 id 清理并自检残留——但探测过程可能造出「本应拦截却成功」
的脏数据（例如名称被写坏的记录），自检发现异常就按提示手工补删。

## 报告

一次运行出两份报告，分工明确：

| 报告 | 位置 | 用途 |
| --- | --- | --- |
| Markdown | `reports/run_<时间戳>.md` | 表格一览，贴进缺陷单 / 日报，CI 日志友好 |
| **Allure** | `reports/allure-report/<时间戳>.html` | 交互式：按模块/标签分层、看步骤、看失败截图。文件名带时间戳，历史报告不覆盖 |

两层报告同名同格式，靠**报告头的「执行层」**区分（`UI` / `接口`）：
Markdown 报告头部的元信息区会写「执行层：接口（另有一层实现时，请分别执行）」，避免把接口结果误读成页面结果。

> 同一编号两层都跑过时，`--update-xlsx` 会互相覆盖「执行结果」列（后跑的盖掉先跑的）。
> 只想回填某一层的结论，就先只跑那一层再回填；要同时保留两层结论，建议一层回填一次、
> 中间导出一次表，或者只在缺陷单里引用另一层的结果。

Allure 默认生成**单文件**（数据内嵌在同一个 html 里），双击即可打开，不用起服务。

### Allure 里能看到什么

UI 层：

- 分层：`Suites` / `Behaviors` 按「一级模块 → 二级功能 → 标签 → 用例」排布，
  当前三个模块是：商品管理 → 多单位、商品管理 → 商品信息、**基础资料 → 仓库信息**；
- 每条用例拆成四段步骤：`前置：登录态检查` → `执行用例：<标题>` → `收尾：页面复位` → `收尾：数据回收`；
- 「执行用例」下面自动记录页面动作，例如
  `create('ATxxxxU01', [('箱', 10)])` → `fill_form(...)` → `save_success()`，失败时一眼看出停在哪步；
- 失败自动附**全页截图**；用例里 `ctx.note()` 记的偏差/缺陷候选会作为「观察记录」附件带上去；
- 严重程度取自用例表优先级（高→critical、中→normal、低→minor），用例编号作为 tag 便于搜索；
- Environment 区记录本次的域名、浏览器、数据前缀、执行范围。

接口层：分层与严重程度同上，同样四段步骤（`前置：登录态检查` → `执行用例` → `收尾：页面复位` →
`收尾：数据回收`），差别是：

- 没有失败截图，「页面复位」是空实现（接口层没有页面状态要复位）；
- 「前置」改成检查 token 能不能用，取不到就记「阻塞」而不是整批报错；
- **不记录逐条请求明细**——接口层的失败原因直接把服务端的 `code` 和 `message` 写进说明列，
  想看具体请求体去 Markdown 报告的说明列，或 `tools/api_dump/` 里的抓包原文。

### 状态映射

| 用例表口径 | Allure | 说明 |
| --- | --- | --- |
| 通过 | passed | |
| 失败 | failed | 断言不符，附失败截图 |
| 阻塞 | skipped | 人工用例或前置不具备，原因写在 message 里 |
| 异常 | broken | 脚本/环境报错，需要人看堆栈 |

### 常用开关

```bash
# Allure：默认 auto（单文件），off 关闭，multi 出多文件版
./.venv/Scripts/python.exe run_cases.py run --allure off
./.venv/Scripts/python.exe run_cases.py run --allure multi

# 排查问题时常用
./.venv/Scripts/python.exe run_cases.py run --keep-data            # 跑完不回收数据
./.venv/Scripts/python.exe run_cases.py run --data-prefix ATDEMO   # 指定运行前缀，便于复现与手工清理
./.venv/Scripts/python.exe run_cases.py run --relogin-wait 120     # 等人工重新登录的秒数
./.venv/Scripts/python.exe run_cases.py run --report-dir ./out     # 报告换个目录
```

每次运行默认清空 `reports/allure-results`，所以报告只反映本次，没有跨次合并的开关。

`multi` 生成的是目录版（`reports/allure-report/<时间戳>/index.html`），不能用 `file://` 直接打开
（浏览器会拦数据请求），要用 CLI 起本地服务：

```bash
node tools/allure/node_modules/allure-commandline/bin/allure open reports/allure-report/<时间戳>
```

## 质量门禁与定时任务

### 离线门禁（提交前 / CI 都跑这个）

```bash
./.venv/Scripts/python.exe tools/gate.py
```

不用浏览器、不连 ERP，20 秒内跑完五项：

| 检查 | 抓什么问题 |
| --- | --- |
| ruff | 语法错、未定义名、未用导入、导入排序、行宽 |
| compileall | 某个模块其实已经 import 不进去 |
| 分层边界守卫 | 用例层直接操作 DOM、页面对象重复、单文件超 500 行 |
| 用例注册基线 | **用例静默消失**（`cases/*/__init__.py` 漏一行 import，几十条用例就不再注册） |
| 控制台冒烟 | 真起一次面板，打首页 / 用例清单 / 404 / favicon，确认路由与清单都通 |

全绿才提交。`git commit` 时 pre-commit 还会再跑一次 ruff + 边界守卫（快的那两项）。

**用例数是有意的增减时**，刷新基线并一起提交：

```bash
./.venv/Scripts/python.exe tools/gate.py --update   # 写 docs/case_counts.json
```

基线存的是 125 个编号的完整清单（不是只有总数），所以「改名」「编号写错」也会被抓到。

### CI

`.github/workflows/ci.yml`：push 到 `main` 或开 PR 时在 `windows-latest` 上跑
`tools/gate.py`。**只跑离线门禁**——真正跑用例要桌面 MyTest 浏览器和真实登录态，
CI 上不具备，硬跑出来全是「阻塞」，绿得没有意义。

### 夜间接口层巡检

接口层不碰浏览器，可以无人值守，但需要真实 token（由桌面浏览器换取后缓存在 `.api_token`）。
所以它留在本机，由 Windows 任务计划程序触发：

```bash
# 手动跑一次
tools\nightly_api.cmd

# 注册成每天 02:30（约 1~3 分钟）
schtasks /Create /SC DAILY /ST 02:30 /TN "ERP-API-Nightly" ^
         /TR "D:\Automation\ERPgyjerp\tools\nightly_api.cmd" /F

# 取消
schtasks /Delete /TN "ERP-API-Nightly" /F
```

退出码就是「任务计划程序」里的 `Last Run Result`，日志追加到 `dashboard/.cache/nightly.log`：

| 退出码 | 含义 | 怎么处理 |
| --- | --- | --- |
| 0 | 全通过 | — |
| 1 | 有用例失败 | 看报告 |
| 2 | 一条都没选中 | 注册被改坏了，跑 `tools/gate.py` |
| 3 | 接口认证不可用（token 过期且浏览器没开） | 登录一次 ERP，手动跑一遍接口层把 token 写回 |

UI 层依赖桌面浏览器，没法无人值守，**每周手动跑一次全量**即可。

## 项目结构

```
ERPgyjerp/
├── run_cases.py                # 唯一执行入口：交互菜单 + run / list 子命令（--layer ui|api）
├── pyproject.toml              # ruff 配置（本项目不做发行包，依赖钉在 requirements*.txt）
├── .pre-commit-config.yaml     # 提交守卫：分层边界检查 + ruff
├── requirements.txt            # 运行依赖：playwright / openpyxl / allure-python-commons
├── requirements-dev.txt        # 开发依赖：ruff / pre-commit
├── .api_token                  # 接口层 token 缓存（已 gitignore，不要提交）
│
├── config/                     # 配置出口：外部一律 `from config import X`
│   ├── __init__.py             #   门面，将来按 ERP_ENV 选环境覆盖时调用方零改动
│   └── settings.py             #   系统地址 / CDP 端点 / 接口前缀 / 动作间隔
│
├── data/
│   └── cases.xlsx              # 用例来源，也是 --update-xlsx 的回填目标（回填前自动备份）
├── dashboard_server.py         # 控制台入口（138 行）：解析参数 → 起服务 → 打横幅
├── dashboard/                  # 控制台实现，依赖单向向下
│   ├── web.py                  #   HTTP 路由 + socket 服务（唯一对外一层，Origin/路径校验在此）
│   ├── env.py                  #   有副作用的动作：起浏览器 / 开业务页 / 打开报告
│   ├── health.py               #   六项只读探测 + 5s 后台轮询 + 快照
│   ├── cases_feed.py           #   用例清单：子进程导出 + 内存/磁盘双层缓存
│   ├── runs.py                 #   任务执行：RunSession（读子进程 stdout）/ RunManager
│   ├── paths.py                #   磁盘位置与 venv 解释器
│   ├── runtime.py              #   端口 / 周期 / 日志上限（PORT 是可变值，须用 runtime.PORT 访问）
│   ├── util.py                 #   异常摘要 + 探测短缓存
│   └── index.html              # 控制台单页：环境监控 + 用例选择 + 执行配置与日志
│                               #   （.cache/ 存用例清单缓存与 server.log，已 gitignore）
│
├── framework/                  # 与业务无关的执行骨架
│   ├── browser.py              # 通过 CDP 接入桌面 MyTest 浏览器 + 登录态守卫
│   ├── registry.py             # 用例注册表：@case 注册 UI 实现，@api_case 挂接口实现（同编号双轨）
│   ├── asserts.py              # 断言：check / check_eq / check_contains / blocked
│   ├── data.py                 # 测试数据工厂：运行前缀、命名、记账
│   ├── context.py              # UI 用例工具箱：页面对象 + 造数 + reset / cleanup
│   ├── runner.py               # 执行器：按 --layer 选实现、收尾、报告、回填 Excel
│   ├── api_client.py           # 接口客户端：token 取用/缓存/回源、统一错误码解析
│   ├── api_context.py          # 接口用例工具箱：apis 聚合 + 造数 + 按 id 精确回收
│   └── allure_report.py        # Allure 写入（步骤/截图/标签）+ 调 CLI 生成 HTML
│
├── pages/                      # 页面对象：只放选择器与页面交互，不含断言
│   ├── base_page.py            # AntD 通用：按钮 / toast / 确认框 / Popover / 浮层清理
│   ├── table_page.py           # 列表页公共层：查询 / 勾选 / 工具栏 / 分页 / 等待 / 数据回收
│   ├── unit_page.py            # 多单位：四个单位字段 + 行内删除（Popconfirm）
│   ├── product_page.py         # 商品信息：高级查询 / 复制 / 多单位勾选 / 三个 Tab / 批量编辑
│   └── depot_page.py           # 仓库信息：双查询框 + 负责人下拉 + 设为默认
│
├── apis/                       # 接口封装（对标 pages/）：只组装请求与解析响应，不含断言
│   ├── base.py                 # 公共基类：list / all / count、ids 形态、code_msg 错误码
│   ├── unit_api.py             # 多单位：list / getAllList / add / update / batchSetStatus / delete
│   ├── material_api.py         # 商品：list / add / update / 批量 / 条码 / 条码明细 / 类别树 / 属性
│   └── depot_api.py            # 仓库：list / getAllListWithStock / add / update / 状态 / 删除 / 设为默认
│
├── cases/                      # 用例：一个函数 = 一条用例
│   ├── __init__.py             # 按模块导入三个子包
│   ├── _helpers.py             # 公共小工具：单位名拼接、提示文案匹配
│   ├── unit/                   # 多单位 TC-UNIT-*
│   │   ├── __init__.py         # 本模块的导入清单；api 必须最后
│   │   ├── entry.py            # 页面入口 / 结构校验
│   │   ├── list_view.py        # 列表展示 / 全选 / 分页
│   │   ├── query.py            # 查询 / 重置 / 高级查询
│   │   ├── create.py           # 新增（含必填、配对、边界值）
│   │   ├── edit.py             # 编辑
│   │   ├── status.py           # 启用 / 禁用 / 批量
│   │   ├── delete.py           # 删除 / 取消删除
│   │   ├── linkage.py          # 商品端多单位下拉联动
│   │   ├── exception.py        # 异常 / 权限
│   │   ├── api.py              # 接口层实现（与 UI 层同编号双轨）
│   │   └── _const.py           # 模块内共享常量
│   ├── depot/                  # 仓库信息 TC-DEP-*（文件同上，无 linkage 之外的差异）
│   └── material/               # 商品信息 TC-MAT-*
│                               #   三个模块的文件名一一对应，找用例先按编号定模块、
│                               #   再按用例表「标签」列定文件
│
├── docs/
│   ├── 接口契约-多单位-商品-仓库.md   # 接口清单、请求体样例、实测校验口径、覆盖情况
│   ├── 重构规划.md             # 分层问题诊断与 P0~P3 路线图
│   ├── boundary_baseline.json  # 边界守卫的指标基线（只允许下降）
│   └── case_counts.json        # 用例注册基线（125 个编号的完整清单，gate.py 比对）
│
├── .github/workflows/ci.yml    # CI：push / PR 时在 windows-latest 上跑 tools/gate.py
│
├── tools/
│   ├── probe.py                # 页面探查：dom / modal / product / depot
│   ├── api_recorder.py         # 接口抓包（只读）：加载/查询/翻页，不落库
│   ├── api_recorder_write.py   # 接口抓包（写链路）：测试前缀下跑完整 CRUD
│   ├── api_probe_server.py     # 服务端校验行为探测：空值/缺字段/越界/重名
│   ├── check_boundaries.py     # 分层边界守卫：用例层不碰 DOM / 页面对象不重复 / 文件不超 500 行
│   ├── gate.py                 # 离线门禁：ruff + 编译 + 边界 + 用例注册基线 + 面板冒烟
│   ├── nightly_api.py          # 夜间接口巡检：只跑接口层，区分「失败」与「token 过期」
│   ├── nightly_api.cmd         # 给 Windows 任务计划程序调用的壳（ASCII-only，避免 cmd 乱码）
│   ├── api_dump/               # 抓包产物 md + json（已 gitignore，可随时重采）
│   └── allure/                 # 随项目安装的 allure-commandline（node_modules 不入库）
│
└── reports/                    # 运行产物（已 gitignore）
    ├── run_<时间戳>.md          # 人读报告（头部标注执行层 UI / 接口）
    ├── allure-results/         # Allure 原始结果，每次运行前清空
    └── allure-report/          # <时间戳>.html（默认）/ <时间戳>/index.html（--allure multi）
```

> `framework/__init__.py`、`pages/__init__.py` 只有包说明 docstring；`apis/__init__.py` 额外导出
> `UnitApi / MaterialApi / DepotApi` 三个类（`from apis import UnitApi` 可直接用）；
> `--update-xlsx` 产生的备份落在 `data/` 下，形如 `cases.bak_<时间戳>.xlsx`（已 gitignore）。

## 用例覆盖

| 范围 | 条数 | UI 层 | 接口层 | 说明 |
| --- | --- | --- | --- | --- |
| 合计 | 125 | 117 可自动 | 71 有实现 | 多单位 44 + 商品信息 43 + 仓库信息 38 |
| 多单位 | 44 | 40 | 28 | |
| 商品信息 | 43 | 41 | 20 | |
| 仓库信息 | 38 | 36 | 23 | |

- **UI 层 117 条**：跑脚本即出结论，结果为 通过/失败；其余 8 条为阻塞（人工），见下表。
- **接口层 71 条**：与 UI 层共用编号，实跑计划 78 条（含 7 条阻塞）。
  其余 54 条没有接口版，都是纯页面交互（左侧菜单进入、分页器、列设置、Popover 位置、复制到新增等），
  接口层面没有对应语义，`--layer api` 会自动跳过，不会算失败。

阻塞原因（UI 层）：

| 编号 | 原因 |
| --- | --- |
| TC-UNIT-033 | 需要「已被商品引用」的单位；删除确认若被服务端放行会真实删业务数据，自动化不做破坏性验证 |
| TC-UNIT-036 | 说明型用例（顶部统计卡片属首页模块设计行为），无需断言，目视确认即可 |
| TC-UNIT-037 | 前置条件为账号试用到期（当前显示 2026-11-08），无法在不改账号状态的前提下构造 |
| TC-UNIT-044 | 依赖 TC-UNIT-033 与商品详情核对，同样涉及真实业务数据；**接口层例外**——用自己造的单位+商品即可安全验证，`--layer api` 下可跑 |
| TC-MAT-037 | 需要一条被采购/销售单据引用的商品，构造前置会改动真实业务数据 |
| TC-MAT-039 | 同 TC-UNIT-037，需账号试用到期 |
| TC-DEP-033 | 需要「已被业务单据引用」的仓库；构造引用会改动真实单据数据，属破坏性前置 |
| TC-DEP-037 | 同 TC-UNIT-037，需账号试用到期 |

接口层的 7 条阻塞就是上表除 `TC-UNIT-044` 之外的那 7 条（`TC-UNIT-033 / 036 / 037`、
`TC-MAT-037 / 039`、`TC-DEP-033 / 037`）：依赖真实业务单据、需账号状态变更、说明型，原因原样带进报告。

写用例的方式（同一个编号写两份实现，UI 打 `@case`，接口打 `@api_case`）：

```python
from framework.registry import case, api_case
from framework.asserts import check, check_eq, blocked

# UI 层：走页面
@case("TC-UNIT-013", "填写基本单位+副单位+比例保存", "新增", "高")
def tc_unit_013(ctx):
    unit = ctx.open_unit()
    basic = ctx.new_unit([("箱", 10)])          # 造数据（自动记账、跑完回收）
    check_eq(unit.read_row(basic)["other"], f"箱=10{basic}", "副单位列")

# 接口层：同一编号打接口，断言落库结果而不是界面
@api_case("TC-UNIT-013")
def tc_unit_013_api(ctx):
    _uid, name, _row = ctx.new_unit([("箱", 10)])
    row = ctx.unit.find(name)
    check(row is not None, "新增后应能查到")
    check_eq(str(row["ratio"]), "10", "比例应落库")
    check_eq(row["otherUnit"], "箱", "副单位应落库")
```

`@api_case` 只挂实现，标题/标签/优先级沿用 UI 层登记的，**两边口径天然一致**；
纯接口新增的用例（没有 UI 版）才用 `@api_case(cid, title, tag, priority)` 自带元信息建一条。

跑着跑着发现前置数据不具备（例如类别下拉是空的），用 `blocked("原因")` 主动记「阻塞」，
而不是写成断言失败——报告里会归到「阻塞」，Allure 里是 skipped，原因原样带出去。
条件不具备就跳过、不硬凑通过，条件不具备也别冤枉成缺陷。

## 实测发现（按最新一次全量）

### 接口层（2026-11-05：54 通过 / 17 失败 / 7 阻塞 / 0 异常，78 条 196 秒）

接口层最大价值：**把「前端拦住了」和「后端真拦住了」分开**。UI 上看到的红字大多是前端校验，
绕过页面直接调接口，17 条用例暴露出后端根本没校验。按性质归类：

| 性质 | 编号 | 实测 |
| --- | --- | --- |
| 接口被特殊字符打挂 | UNIT-011 / MAT-013 / DEP-011 | 查询条件含 emoji → HTTP 200 但 `code=300 数据查询异常`，三页全中 |
| 必填校验缺失 | UNIT-015 / 016 / 017 / 018、MAT-015 / 016 / 017 | 空表单、缺基本单位、只填副单位、只填比例、比例 `-1`——全部 `code=200` 建成功 |
| 唯一性只靠前端 | DEP-017 | 同名仓库 `code=200` 成功；`checkIsNameExist` 对已存在名称返回 `status:true`，但 `add` 接口自己不校验 |
| 编辑静默失败 | MAT-028 / DEP-025 | 编辑清空名称返回 `200 成功`，服务端忽略空值不改库——数据没坏，但前端会误报成功 |
| 编辑破坏数据 | UNIT-025 | 编辑清空基本单位返回 `200`，名称被写成 `null/(…)` 这类坏值，之后按名字搜不到 |
| 删除漏依赖校验 | UNIT-044 | 单位已被商品引用，删除仍 `200` 成功，商品悬空（依赖校验只做在前端） |
| 写入直接报错 | UNIT-014 | 填第三个副单位 → `code=301 数据写入异常`，第三个副单位存不进去 |
| 精度校验缺失 | UNIT-038 | 比例填四位小数 `1.5555` 成功落库为 `1.556`，前端「最多三位小数」只拦 UI |

对应的后端校验缺口，按页面归纳：

| 页面 | 后端没校验的东西 | 前端表现 |
| --- | --- | --- |
| 多单位 | 基本单位必填、副单位与比例成对、比例正负、比例小数位、第三个副单位 | 前端有红字/toast，看起来拦住了 |
| 商品信息 | 名称必填、单位必填、空表单 | 前端有红字，接口可空建 |
| 仓库信息 | 名称唯一性、名称必填（编辑时） | 前端有 `checkIsNameExist`，但接口不拦 |

> 这些结论都是实测出来的，不是推断。逐条的请求体与响应原文见
> [`docs/接口契约-多单位-商品-仓库.md`](docs/接口契约-多单位-商品-仓库.md) 第 3 节。

### 多单位 + 商品信息（2026-11-01：78 通过 / 2 失败 / 7 阻塞 / 0 异常）

| 编号 | 结论 | 实测现象 |
| --- | --- | --- |
| TC-UNIT-014 | **缺陷** | 只要填了「副单位3」，保存即返回 `301 数据写入异常`：弹窗照常关闭、列表无新数据、只有一条 toast。只填 1~2 个副单位正常 |
| TC-UNIT-043 | **缺陷**（与用例备注一致） | 空表单保存出的红字「请输入基本单位!」，取消重开弹窗后仍残留；填好基本单位也不消失 |
| TC-MAT-010 | 阻塞（前置不具备） | 商品类别表为 0 条，类别下拉无选项，「按类别查询命中」无法验证；建好类别数据即可转通过/失败 |
| TC-UNIT-001 / TC-MAT-001 | 偏差 | 从左侧菜单进入时浏览器标题仍是「管伊佳ERP」；只有直接访问 `/system/unit`、`/material/material` 才是「多单位 · 管伊佳ERP」「商品信息 · 管伊佳ERP」。页签、菜单高亮、地址均正确 |
| TC-UNIT-040 / 041 / 018 | 偏差（已在用例备注登记） | 比例 0、999999 均可保存，无正负/上限校验；`-1`、`abc` 被「抱歉，比例只能为数字，最多三位小数！」拦截 |
| TC-UNIT-042 | 偏差（已在用例备注登记） | 商品端「选择多单位」下拉里，同名单位会重复出现 |

另外：页面上没有面包屑元素，位置由页签栏（首页 / 多单位 或 首页 / 商品信息）承担，用例按此适配并记了偏差。

### 仓库信息（2026-11-03：35 通过 / 1 失败 / 0 阻塞 / 0 异常）

| 编号 | 结论 | 实测现象 |
| --- | --- | --- |
| TC-DEP-023 | **缺陷** | 仓库名称含 emoji（😀）保存即报「数据查询异常」：弹窗保持打开、数据不落库。引号 `"` 可正常保存；名称长度限制 2~30 字符正常拦截 |
| TC-DEP-014 | 偏差 | 空表单保存的红字是「请输入仓库名称! 未知异常」，比其他模块多出「未知异常」后缀 |
| TC-DEP-018 | 偏差 | 仓储费 / 搬运费无前端格式校验：负数、小数可直接保存；填非数字时后端静默失败——弹窗关闭、列表无记录、无任何提示 |
| TC-DEP-019 | 偏差 | 排序字段无数字校验，字符串可保存；是否真正影响列表顺序尚未确认 |
| TC-DEP-001 | 偏差 | 菜单进入后浏览器标题不更新（与 TC-UNIT-001 / TC-MAT-001 同一现象） |

另外：「负责人」下拉的选项来自账号管理，当前是 `aitest1029`、`testai01`；该下拉为空时 TC-DEP-020 会记「阻塞」而不是判失败。

## 实测到的页面契约（改前端后请重新核对）

### 多单位 `/system/unit`

- 表头列序：`勾选框 | # | 操作 | 单位名称 | 基本单位 | 副单位 | 副单位2 | 副单位3 | 状态`
  （`pages/unit_page.py` 的 `COL_*` 常量按此取值）
- 查询/重置按钮文案被 Ant Design 拆成「查 询」「重 置」，工具栏的「新增/删除/启用/禁用」不拆
- 新增/编辑是 Ant Design 弹窗 `.ant-modal`（标题「新增」/「编辑」），保存按钮为弹窗内 `.ant-btn-primary`
- 表单字段 id：`#basicUnit`（基本单位，必填）、`#otherUnit`+`#ratio`、
  `#otherUnitTwo`+`#ratioTwo`、`#otherUnitThree`+`#ratioThree`
- **基本单位限长 10 个字符**
- 单位名称由系统拼接：`基本单位/(副单位=比例基本单位)`
- 行内「删除」弹的是 Popconfirm「确定删除吗?」；该浮层**预渲染在 DOM 里**，必须带 `:visible` 取
- 工具栏删除/启用/禁用走 `.ant-modal-confirm`：启用禁用标题「确认操作」、删除标题「确认删除」，
  正文分别为「是否操作选中数据?」「是否删除选中数据?」，确认后勾选自动清空
- 校验提示分两种：空表单保存是**内联红字** `.ant-form-explain`（「请输入基本单位!」），
  其余拦截是**顶部 toast** `.ant-message-notice`（「抱歉，副单位不能为空！」等，约 3 秒消失）
- 分页 `.ant-pagination`：每页 10 条，总数文案「1-10 共26条」，>10 条才出现分页器
- 页面**没有**面包屑 `.ant-breadcrumb`，位置由页签栏（首页 / 多单位）承担，TC-001 已按此适配

### 仓库信息 `/system/depot`

- 表头 **12 列**，比多单位页多一个独立的 `#` 序号列，且「负责人 / 备注」排在「排序」之前：
  `勾选框 | # | 操作 | 仓库名称 | 仓库地址 | 仓储费 | 搬运费 | 负责人 | 备注 | 排序 | 状态 | 是否默认`
  （`pages/depot_page.py` 的 `ROWS_JS` 按下标取，改版后先用 `tools/probe.py depot` 核一遍）
- 操作列有**三个行内链接**：`设为默认` / `编辑` / `删除`（多单位页只有「删除」）
- 「设为默认」走 `.ant-popover`（不是 Popconfirm），文案「确定设为默认吗?」，按钮「取 消」「确 定」
- 表单字段 id：`#name`（必填，2~30 字符）、`#address`、`#warehousing`（元/天/KG）、
  `#truckage`（元）、`#sort`、`#remark`，负责人是弹窗内**唯一**的 `.ant-select`（占位「选择负责人」）
- 默认仓库规则：**列表为空时，第一条保存的仓库自动成为默认**；之后新增默认「否」，
  同一时间只有一条「是」，改默认只能靠行内「设为默认」
- 删除/启用/禁用同样走 `.ant-modal-confirm`，与多单位页一致
- 校验提示同样落在 `.ant-form-explain`，但**父级 `.ant-form-item` 不加 `has-error`**，
  不能按 has-error 筛，只能收集非空提示文本

### 商品信息 `/material/material`

- 表头与列索引见 `pages/product_page.py` 的 `COL_*` 常量；列表/查询/新增/编辑/复制/批量/多单位均在
  同一个页面对象里
- `#mnemonic`（助记码）是 **readonly**，由系统按名称自动生成，不能手动 fill
- 批量编辑点「保存」后先弹 `.ant-modal-confirm`「确认操作 / 是否操作选中的N条数据?」，
  点确定才发 `/material/batchUpdate`（`save_batch()` 处理）
- 新增弹窗里有两个 `.ant-btn-primary`（「插入行」和「保存」），必须 `filter(has_text="保存")`


## 登录过期怎么处理

管伊佳的会话由**服务端**判定失效，和本地 `pro__Access-Token` 的 7 天有效期无关——
常见现象是本地 token 还没到期，页面已弹「登录已过期」，把整页遮住，
此时所有点击都会被拦截、删除/保存会静默失败。

脚本对此的处理：

1. **启动即检测**，不再等到 15 秒点击超时才发现；
2. 检测到过期 → 自动点弹窗里的「重新登录」跳到登录页；
3. 停下来等你完成登录（账号密码浏览器已自动填充，**只需输入验证码**），
   登录成功后自动继续执行；
4. 服务端探活（`unit/list` 探针）兜住「前端没弹框但接口返回 `loginOut`」的静默失效；
5. 执行中掉登录 → 当前用例记「阻塞」，后续用例继续尝试，不会连环报错；
6. 等待超时则 exit code = 2，并打印「[需要重新登录] …」的可操作指引。

等待时长用环境变量控制（默认 180 秒）：

```bash
ERP_RELOGIN_WAIT=300 ./.venv/Scripts/python.exe run_cases.py   # 等更久
ERP_RELOGIN_WAIT=0   ./.venv/Scripts/python.exe run_cases.py   # 无人值守：立即失败
```

登录页有图形验证码（`#inputCode`），所以无法自动登录——必须人工输入一次。

### 接口层不同

接口层**没有**「等你重新登录」这条路径：token 失效时 `ApiClient` 会先回源到浏览器重取一次，
取不到（浏览器没开或也没登录）时，每条用例的前置检查都失败并记「阻塞」，不会用过期 token 硬跑成一片 `loginOut` 失败。

```bash
# token 缓存被清 / 服务端踢下线：开一次 MyTest 登录，再跑即可
./.venv/Scripts/python.exe run_cases.py run --layer api
```

只跑接口层时不需要设 `ERP_RELOGIN_WAIT`，这个变量只对 UI 层生效。

## 动作间隔规则（强制）

**每一次 UI 操作之后都要留出间隔，默认 1 秒**，避免脚本快过页面渲染和服务端校验。

### 唯一入口

所有 UI 动作必须走 `pages/` 的页面对象封装（`BasePage` 及其子类），**禁止在用例（`cases/`）里直接调 `page.click()` / `page.fill()`**：

| 动作 | 封装方法 | 所在类 | 间隔 |
|---|---|---|---|
| 点工具栏按钮 | `click_button(text)` | BasePage | 1s |
| 填输入框 | `fill(target, value)` | BasePage | 1s |
| 点确认框「确定」 | `click_confirm()` | BasePage | 1s |
| 关闭弹窗 | `cancel_modal()` | BasePage | 1s |
| 删除确认 / 取消 | `click_popconfirm_ok()` / `click_popconfirm_cancel()` | UnitPage / DepotPage | 1s |
| 翻页 | `goto_page()` / `next_page()` | UnitPage | 1s |

> 通用动作（按钮 / 输入 / 弹窗 / 浮层）在 `base_page.py`；勾选、翻页、行内删除确认这些
> 依赖具体表格结构的动作落在各页面对象里（多单位、仓库），用法一致，都夹带间隔。

`fill()` 同时接受选择器和 Locator，覆盖两种调用习惯：

```python
self.fill("#basicUnit", "瓶")                    # 选择器字符串
self.fill(modal.locator("#name"), "测试商品")     # Locator
```

### 有意采用更短间隔的高频动作

勾选、取消勾选、切换每页条数这类操作数量多、单次代价低，用更短间隔避免跑批时长失控：

| 动作 | 间隔 |
|---|---|
| `select_row()` / `select_all()` | 300ms |
| `clear_selection()` | 120ms |
| `set_page_size()` 点开条数下拉 | 400ms |

> 这三组都在页面对象里（`select_row` / `select_all` / `clear_selection` 三个页面都有，
> `set_page_size` 仅多单位页），间隔是写死的固定值，不随 `ERP_ACTION_DELAY_MS` 变化。

### 配置

默认 1000ms，可用环境变量覆盖：

```bash
ERP_ACTION_DELAY_MS=1500 ./.venv/Scripts/python.exe run_cases.py  # 网络慢时放慢
ERP_ACTION_DELAY_MS=400  ./.venv/Scripts/python.exe run_cases.py  # 跑大批量时压缩
ERP_ACTION_DELAY_MS=0    ./.venv/Scripts/python.exe run_cases.py  # 关闭间隔（仅调试）
```

## 测试数据纪律

- 每次运行生成独立前缀（`AT` + 4 位 36 进制时间片，如 `ATRVZG`），造的数据一律带前缀：
  - 单位名统一 9 字符：`<前缀><类型位><2 位序号>`，如 `ATRVZGU01`；
  - 商品名、仓库名同构：`ATRVZGM01`、`ATRVZGD01`（M = 商品，D = 仓库）；
- **先记账再落库**：即使创建中途失败，收尾也会去清掉半个数据；
- 收尾两条策略：按运行前缀模糊回收（覆盖绝大多数），
  对名字里不含前缀的极少数记录（如 TC-020 的超长/emoji 名）按名字精确回收；
- 回收前会再校验「名称或基本单位含运行前缀」，**绝不按关键字删既有业务数据**；
- 收尾按页面分三次走：多单位 → 商品信息 → 仓库信息，各自只在对应页面做模糊回收；
- 断言按「基本单位」列做整格精确比较，同名多行用序号区分（TC-019）。

### 接口层补充

前缀命名与「先记账再落库」完全复用，回收策略更严一档：

- **按 id 精确回收**，不靠名字。接口用例会把名称改坏（例如清空基本单位后名称变成
  `null/(…)` 这类坏值），按前缀根本搜不到，只有创建时记下的 id 靠得住；
- 两条路径：先按记账的 id 逐个/批量删，**再按运行前缀兜底扫一遍**
  （覆盖「创建成功但当时没拿到 id」的情况），兜底时同样校验名称含本次前缀；
- **「本应被拦截却成功」先回滚再判失败**：提交前拍一次 id 快照，成功后对比出新增行逐个删除，
  再把该用例判为失败。这样既不会留下脏数据，也不会把「后端没校验」误记成「脚本异常」；
- 回收后清账（`created` 清空），避免后续 cleanup 重复删已删的 id、把回收条数算虚；
- 回收前后各查一次总数，实跑后基线应与跑前完全一致（本次为 多单位 24 / 仓库 0 / 商品 3）。
