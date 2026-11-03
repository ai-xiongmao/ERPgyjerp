# ERPgyjerp — 管伊佳 ERP UI 自动化

在**桌面 MyTest 浏览器**里驱动管伊佳 ERP，把 `管伊佳ERP-测试用例.xlsx` 里的
**125 条用例**（多单位 44 条、商品信息 43 条、仓库信息 38 条）按编号落成可执行脚本，
自带断言、测试数据回收，以及 **Markdown / JSON / Allure** 三种执行报告。

## 前置条件

1. 双击桌面 **MyTest.exe** 打开浏览器（它启动时带 `--remote-debugging-port=9231`，
   见 `MyTest.exe.lnk` 的启动参数），并在其中登录 https://cloud.gyjerp.com ；
2. 保持该浏览器窗口开着——脚本是「接入」它，不新开浏览器、不关闭它。

> 为什么走 CDP 接入而不是自己 launch：MyTest 里已有登录态和完整的业务现场，
> 直接接管可以跳过账号/验证码，也不会干扰用户正在看的页面。

## 安装

```bash
cd D:/Automation/ERPgyjerp
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt

# Allure 报告生成器（Java 版 CLI，随项目装，不污染全局）
npm install --prefix tools/allure allure-commandline
```

Allure 需要机器上有 **Java 11+**（当前环境是 Java 21）。只跑用例不出 Allure 的话这一步可以跳过。

## 运行

```bash
# 全部 125 条（可自动 117 条，约 60~70 分钟；8 条阻塞会直接跳过）
./.venv/Scripts/python.exe run_cases.py

# 只看清单：哪些能自动、哪些需要人工
./.venv/Scripts/python.exe run_cases.py list

# 按编号 / 标签 / 起始编号挑着跑
./.venv/Scripts/python.exe run_cases.py run --only TC-UNIT-012,TC-UNIT-013
./.venv/Scripts/python.exe run_cases.py run --tag 新增 查询
./.venv/Scripts/python.exe run_cases.py run --from TC-MAT-001

# 跑完把结果回填用例表「执行结果」列（会先备份原表）
./.venv/Scripts/python.exe run_cases.py run --update-xlsx

# Allure 报告：默认单文件；off 关闭；multi 生成多文件版
./.venv/Scripts/python.exe run_cases.py run --allure off
./.venv/Scripts/python.exe run_cases.py run --allure multi

# 页面探查（新增用例或页面改版后核对选择器，不产生业务数据）
./.venv/Scripts/python.exe tools/probe.py            # 当前页面结构
./.venv/Scripts/python.exe tools/probe.py modal      # 多单位弹窗 / 校验 / 批量确认框
./.venv/Scripts/python.exe tools/probe.py product    # 商品页「多单位」下拉
./.venv/Scripts/python.exe tools/probe.py depot      # 仓库页表头列序 / 操作列链接 / 新增弹窗 / 设为默认 Popover
```

> `probe.py depot` 会把表头按 `cells[i]` 下标逐行打出来，**这是 `pages/depot_page.py` 里 `ROWS_JS`
> 列索引的唯一依据**——仓库页改版（加减字段、调列序）后先跑它，再对照输出改索引，别凭记忆。
> 它对弹窗只做「空表单保存」（会被校验拦住、不落库）和「设为默认 → 取消」，不会改真实数据。

> 省略子命令时默认 `run`，旧写法 `run_cases.py --only ...`、`--list` 仍然可用，会自动映射到对应子命令。
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

退出码：`0` 全绿；`1` 有失败/异常；`2` 登录失效需要人工重新登录。

## 报告

一次运行出两份报告，分工明确：

| 报告 | 位置 | 用途 |
| --- | --- | --- |
| Markdown | `reports/run_<时间戳>.md` | 表格一览，贴进缺陷单 / 日报，CI 日志友好 |
| **Allure** | `reports/allure-report/<时间戳>.html` | 交互式：按模块/标签分层、看步骤、看失败截图。文件名带时间戳，历史报告不覆盖 |

Allure 默认生成**单文件**（数据内嵌在同一个 html 里），双击即可打开，不用起服务。

### Allure 里能看到什么

- 分层：`Suites` / `Behaviors` 按「一级模块 → 二级功能 → 标签 → 用例」排布，
  当前三个模块是：商品管理 → 多单位、商品管理 → 商品信息、**基础资料 → 仓库信息**；
- 每条用例拆成四段步骤：`前置：登录态检查` → `执行用例：<标题>` → `收尾：页面复位` → `收尾：数据回收`；
- 「执行用例」下面自动记录页面动作，例如
  `create('ATxxxxU01', [('箱', 10)])` → `fill_form(...)` → `save_success()`，失败时一眼看出停在哪步；
- 失败自动附**全页截图**；用例里 `ctx.note()` 记的偏差/缺陷候选会作为「观察记录」附件带上去；
- 严重程度取自用例表优先级（高→critical、中→normal、低→minor），用例编号作为 tag 便于搜索；
- Environment 区记录本次的域名、浏览器、数据前缀、执行范围。

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

## 项目结构

```
ERPgyjerp/
├── run_cases.py                # 唯一执行入口：run / list 两个子命令
├── config.py                   # 系统地址、CDP 端点、动作间隔
├── browser.py                  # 通过 CDP 接入桌面 MyTest 浏览器 + 登录态守卫
├── requirements.txt            # playwright / openpyxl / allure-python-commons
├── 管伊佳ERP-测试用例.xlsx      # 用例来源，也是 --update-xlsx 的回填目标（回填前自动备份）
│
├── framework/                  # 与业务无关的执行骨架
│   ├── registry.py             # 用例注册表（@case 注册，编号即执行顺序）
│   ├── asserts.py              # 断言：check / check_eq / check_contains / blocked
│   ├── data.py                 # 测试数据工厂：运行前缀、命名、记账
│   ├── context.py              # 用例工具箱：页面对象 + 造数 + reset / cleanup
│   ├── runner.py               # 执行器：跑用例、收尾、报告、回填 Excel
│   └── allure_report.py        # Allure 写入（步骤/截图/标签）+ 调 CLI 生成 HTML
│
├── pages/                      # 页面对象：只放选择器与页面交互，不含断言
│   ├── base_page.py            # AntD 通用：按钮 / toast / 确认框 / Popover / 浮层清理
│   ├── unit_page.py            # 多单位：增删改查 + 勾选 + 批量 + 分页 + 状态
│   ├── product_page.py         # 商品信息：列表/查询/新增/编辑/复制/批量/多单位/列设置
│   └── depot_page.py           # 仓库信息：增删改查 + 设为默认 + 启用禁用 + 负责人下拉
│
├── cases/                      # 用例：一个函数 = 一条用例，文件名按标签划分
│   ├── _helpers.py             # 公共小工具：单位名拼接、提示文案匹配
│   ├── c_entry.py              # 页面入口：UNIT 001-003
│   ├── c_list.py               # 列表展示：UNIT 004/005/034/035/036
│   ├── c_query.py              # 查询：UNIT 006-011
│   ├── c_create.py             # 新增：UNIT 012-023/038/040/041/043
│   ├── c_edit.py               # 编辑：UNIT 024/025
│   ├── c_status.py             # 状态与批量：UNIT 026-029/039
│   ├── c_delete.py             # 删除：UNIT 030-033
│   ├── c_product.py            # 商品联动：UNIT 042（037/044 为人工登记）
│   ├── c_material.py           # 商品信息：MAT 001-043
│   └── c_depot.py              # 仓库信息：DEP 001-038
│
├── tools/
│   ├── probe.py                # 页面探查：dom / modal / product / depot
│   └── allure/                 # 随项目安装的 allure-commandline（node_modules 不入库）
│
└── reports/                    # 运行产物（已 gitignore）
    ├── run_<时间戳>.md          # 人读报告
    ├── run_<时间戳>.json        # 结构化结果：运行前缀、汇总、逐条用例结果
    ├── allure-results/         # Allure 原始结果，每次运行前清空
    └── allure-report/          # <时间戳>.html 单文件报告，双击即可用浏览器打开
```

> `framework/__init__.py`、`pages/__init__.py` 只有一行包说明 docstring，无逻辑；`--update-xlsx` 产生的备份
> 落在同一目录，形如 `管伊佳ERP-测试用例.bak_<时间戳>.xlsx`。

## 用例覆盖

| 范围 | 条数 | 说明 |
| --- | --- | --- |
| 合计 | 125 | 多单位 44 + 商品信息 43 + 仓库信息 38 |
| 可自动化 | 117 | 跑脚本即出结论，结果为 通过/失败（UNIT 40 / MAT 41 / DEP 36） |
| 阻塞（人工） | 8 | 见下表，脚本会如实标注「阻塞」，不会假装通过 |

阻塞原因：

| 编号 | 原因 |
| --- | --- |
| TC-UNIT-033 | 需要「已被商品引用」的单位；删除确认若被服务端放行会真实删业务数据，自动化不做破坏性验证 |
| TC-UNIT-036 | 说明型用例（顶部统计卡片属首页模块设计行为），无需断言，目视确认即可 |
| TC-UNIT-037 | 前置条件为账号试用到期（当前显示 2026-11-08），无法在不改账号状态的前提下构造 |
| TC-UNIT-044 | 依赖 TC-UNIT-033 与商品详情核对，同样涉及真实业务数据 |
| TC-MAT-037 | 需要一条被采购/销售单据引用的商品，构造前置会改动真实业务数据 |
| TC-MAT-039 | 同 TC-UNIT-037，需账号试用到期 |
| TC-DEP-033 | 需要「已被业务单据引用」的仓库；构造引用会改动真实单据数据，属破坏性前置 |
| TC-DEP-037 | 同 TC-UNIT-037，需账号试用到期 |

写用例的方式：

```python
from framework.registry import case
from framework.asserts import check_eq, blocked

@case("TC-UNIT-013", "填写基本单位+副单位+比例保存", "新增", "高")
def tc_unit_013(ctx):
    unit = ctx.open_unit()
    basic = ctx.new_unit([("箱", 10)])          # 造数据（自动记账、跑完回收）
    check_eq(unit.read_row(basic)["other"], f"箱=10{basic}", "副单位列")
```

跑着跑着发现前置数据不具备（例如类别下拉是空的），用 `blocked("原因")` 主动记「阻塞」，
而不是写成断言失败——报告里会归到「阻塞」，Allure 里是 skipped，原因原样带出去。
条件不具备就跳过、不硬凑通过，条件不具备也别冤枉成缺陷。

## 实测发现（按最新一次全量）

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

## 动作间隔规则（强制）

**每一次 UI 操作之后都要留出间隔，默认 1 秒**，避免脚本快过页面渲染和服务端校验。

### 唯一入口

所有 UI 动作必须走 `pages/base_page.py` 的封装，**禁止在用例（`cases/`）里直接调 `page.click()` / `page.fill()`**：

| 动作 | 封装方法 | 间隔 |
|---|---|---|
| 点工具栏按钮 | `click_button(text)` | 1s |
| 填输入框 | `fill(target, value)` | 1s |
| 点确认框「确定」 | `click_confirm()` | 1s |
| 关闭弹窗 | `cancel_modal()` | 1s |
| 删除确认 / 取消 | `click_popconfirm_ok()` / `click_popconfirm_cancel()` | 1s |
| 翻页 | `goto_page()` / `next_page()` | 1s |

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
