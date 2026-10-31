# ERPgyjerp — 管伊佳 ERP UI 自动化

在**桌面 MyTest 浏览器**里驱动管伊佳 ERP，当前已实现「商品管理 → 多单位」页面的
**新增 / 查询 / 修改 / 删除**全链路，并自带断言与测试数据清理。

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
```

## 运行

```bash
./.venv/Scripts/python.exe run_unit_crud.py
```

预期输出（6 步全绿，退出码 0）：

```
[1/6] 清理历史测试数据
[2/6] 新增：AT_U215608，副单位 AT_Z215608=12AT_U215608
        OK 单位名称=AT_U215608/(AT_Z215608=12AT_U215608)；状态=启用
[3/6] 查询：按单位名称搜索「AT_U215608」
        OK 命中 1 行
[4/6] 修改：基本单位 AT_U215608 → AT_V215608
        OK 新名称=AT_V215608/(AT_Z215608=12AT_V215608)
[5/6] 删除：AT_V215608
        OK 该行已从表格消失
[6/6] 校验无残留测试数据
        OK 表格干净
```

## 项目结构

```
ERPgyjerp/
├── .venv/                  # 虚拟环境（仅装 playwright，不自带浏览器内核）
├── config.py               # 系统地址、CDP 端点、超时
├── browser.py              # 通过 CDP 接入桌面 MyTest 浏览器
├── pages/
│   └── unit_page.py        # 多单位页面对象：search / create / update / delete
├── run_unit_crud.py        # 端到端入口：清理 → 增 → 查 → 改 → 删 → 复核
├── requirements.txt
└── README.md
```

## 页面对象用法（单步调用）

```python
from browser import connect
from pages.unit_page import UnitPage

with connect() as page:
    unit = UnitPage(page).open()

    unit.create("AT_U1", [("AT_Z1", 12)])   # 新增：基本单位 + [(副单位, 比例), ...]
    unit.search("AT_U1")                     # 按单位名称模糊查询
    unit.reset()                             # 清空查询条件
    unit.update("AT_U1", "AT_V1", [("AT_Z1", 12)])  # 改名 + 目标副单位（完整给出）
    unit.delete("AT_V1")                     # 删除单行
```

## 实测到的页面契约（改前端后请重新核对）

- 表头列序：`# | 操作 | 单位名称 | 基本单位 | 副单位 | 副单位2 | 副单位3 | 状态`
  （`pages/unit_page.py` 的 `COL_*` 常量按此取值）
- 新增/编辑是 Ant Design 弹窗 `.ant-modal`，保存按钮为弹窗内 `.ant-btn-primary`
- 表单字段 id：`#basicUnit`（基本单位，必填）、`#otherUnit`+`#ratio`、
  `#otherUnitTwo`+`#ratioTwo`、`#otherUnitThree`+`#ratioThree`
- **基本单位限长 10 个字符**（超长保存时报「长度在 1 到 10 个字符」）
- 单位名称由系统拼接：`基本单位/(副单位=比例基本单位)`，脚本断言了这一规则
- 行内「删除」弹的是 Popconfirm 气泡（文案「确定删除吗?」），不是模态框

## 登录过期怎么处理

管伊佳的会话由**服务端**判定失效，和本地 `pro__Access-Token` 的 7 天有效期无关——
常见现象是本地 token 还没到期，页面已弹「登录已过期」，把整页遮住，
此时所有点击都会被拦截、删除/保存会静默失败。

脚本对此的处理：

1. **启动即检测**，不再等到 15 秒点击超时才发现；
2. 检测到过期 → 自动点弹窗里的「重新登录」跳到登录页；
3. 停下来等你完成登录（账号密码浏览器已自动填充，**只需输入验证码**），
   登录成功后自动继续跑完 CRUD；
4. 服务端探活（`unit/list` 探针）兜住「前端没弹框但接口返回 `loginOut`」的静默失效；
5. 等待超时则 exit code = 2，并打印「[需要重新登录] …」的可操作指引。

等待时长用环境变量控制（默认 180 秒）：

```bash
ERP_RELOGIN_WAIT=300 ./.venv/Scripts/python.exe run_unit_crud.py   # 等更久
ERP_RELOGIN_WAIT=0   ./.venv/Scripts/python.exe run_unit_crud.py   # 无人值守：立即失败
```

登录页有图形验证码（`#inputCode`），所以无法自动登录——必须人工输入一次。

## 操作节奏

每个 UI 动作（点击按钮、填写字段、提交保存）之后默认间隔 **1 秒**，
避免脚本快过页面渲染 / 服务端校验而抢跑。按需覆盖：

```bash
ERP_ACTION_DELAY_MS=1500 ./.venv/Scripts/python.exe run_unit_crud.py   # 放得更慢
ERP_ACTION_DELAY_MS=0    ./.venv/Scripts/python.exe run_unit_crud.py   # 关闭间隔（追求速度时）
```

## 测试数据纪律

- 所有测试数据以 `AT_U` / `AT_V` / `AT_Z` 为前缀（避开 10 字符上限）；
- 每次运行前先按前缀清理历史残留，失败时 `finally` 兜底再清一次，
  因此可反复运行、不会在系统里堆垃圾数据；
- 断言按「基本单位」列做整格精确比较，避免「AT_U1」误命中「AT_U12」。

## 扩展新页面

照 `pages/unit_page.py` 的样子新建一个页面对象（构造时传入 `page`），
在 `run_*.py` 里 `connect()` 后实例化即可。先探明 DOM 再写选择器——
本项目所有定位都来自实测（id / placeholder / 可见文案），不靠猜样式类。
