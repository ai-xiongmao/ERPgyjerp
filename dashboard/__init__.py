"""控制台实现包。

为什么要拆：原 `dashboard_server.py` 908 行，一个文件同时管环境探测、任务执行、
HTTP 路由、进程启动四件事。任何一处改动都要在一个近千行的文件里找位置，
而且探测逻辑和路由逻辑没有任何边界可言。

现在按职责分层，依赖方向单向向下：

    dashboard_server.py      入口：参数 → 起服务
        └── web.py           路由 + socket 服务（唯一对外的一层）
              ├── env.py     环境补齐：起浏览器 / 开业务页 / 开报告
              │     └── health.py   六项探测 + 后台轮询
              │           └── cases_feed.py   用例清单（子进程导出 + 缓存）
              ├── runs.py    任务执行：RunSession / RunManager
              ├── lifecycle.py  进程收尾：登记服务实例 + 页面「关闭服务」时异步关停
              └── runtime.py / paths.py   常量
"""
