# AI智能瞭望、智能问数与智能聊天系统

## 项目概述

`cnAgentOS` 是一个基于 **Tornado MVC + SQLite + 服务端模板渲染** 的一体化 Web 系统，定位为：

- 面向用户侧的 `AI 智能问数工作台`
- 面向用户侧的 `仿微信智能聊天工作台`
- 面向管理侧的 `智能瞭望 / 数据仓库 / 模型引擎 / 数字员工 / 智能聊天管理 / 接口管理 / RBAC 管理后台`

项目当前已经不再是“仅有登录功能的基础骨架”，而是进入了 **可运行的业务集成阶段**：

- 前台已支持普通用户登录、注册、头像上传、智能问数、智能聊天、历史对话、模型切换、`@数字员工` 调用、SSE 流式响应
- 后台已支持用户管理、角色管理、权限管理、功能管理、模型引擎、接口管理、数字员工、智能聊天管理、瞭望采集、数据仓库与 AI 深度采集
- 数据层当前以 SQLite 为主，并通过数据库初始化逻辑完成自动建表与迁移补齐

---

## 当前已实现能力

### 用户侧

- 统一科技风登录页，支持普通用户登录 / 注册 / 管理员登录切换
- 注册支持头像上传，未上传时使用默认头像
- `智能问数工作台` 对话界面
- 历史任务列表、会话回访
- 历史任务删除
- 模型服务切换
- `@alias` 数字员工调用
- 普通 AI 对话与 SQLite 智能问数意图识别
- SSE 流式回复与 Markdown 渲染
- 天气 / 音乐数字员工卡片化展示
- `智能聊天` 三栏工作台，支持会话 / 好友 / 群聊 / 数字员工
- 好友申请、同意 / 拒绝、删除好友
- 私聊、群聊、文件发送、表情插入、未读红点与 SSE/轮询准实时同步

### 管理侧

- 动态后台框架与数据库驱动菜单
- 用户管理、角色管理、权限管理、功能管理
- 模型引擎管理与模型测试
- 接口管理与统一接口服务调用
- 数字员工管理
- 智能聊天管理
- 瞭望源管理、采集执行、数据仓库列表
- AI 深度采集、深采日志、简单统计
- 后台一级菜单已预留 `智能舆情` 占位入口，业务页面尚未开发

### 数据与基础设施

- SQLite 自动初始化与增量迁移
- 用户、角色、功能、模型、接口、采集、仓库、深采、问数会话、IM 会话等表结构
- Secure Cookie、XSRF 防护、密码哈希加密

---

## 技术栈

| 层级 | 技术 | 版本/说明 |
|------|------|-----------|
| 后端框架 | Tornado | 6.5.5 |
| 编程语言 | Python | 3.11+ |
| 数据库 | SQLite3 | 当前主存储 |
| 前端 UI | Layui | 2.13.6，本地化 |
| 响应式样式 | Bootstrap | 5.3.8，本地化 |
| 图标库 | FontAwesome | 5.15.4，本地化 |
| 模板引擎 | Tornado Template | 服务端渲染 |
| 模型接入 | OpenAI Compatible API | 云端/本地兼容协议模型 |
| 采集解析 | requests / BeautifulSoup / lxml / raw4ai | 页面抓取与深采解析 |

### 前端组件本地化说明

| 组件 | 压缩包位置 | 解压位置 |
|------|-----------|---------|
| Layui | `app/static/dist/layui-v2.13.6.zip` | `app/static/layui/layui-v2.13.6/` |
| Bootstrap | `app/static/dist/bootstrap-5.3.8-dist.zip` | `app/static/bootstrap/bootstrap-5.3.8-dist/` |
| FontAwesome | `app/static/dist/fontawesome-free-5.15.4-web.zip` | `app/static/fontawesome/fontawesome-free-5.15.4-web/` |

> 所有前端依赖均采用本地静态资源，不使用 CDN。

---

## 快速访问

服务启动后默认监听 `http://localhost:10086`

| 地址 | 说明 |
|------|------|
| `/auth/login` | 普通用户登录页 |
| `/auth/register` | 普通用户注册页 |
| `/admin/login` | 管理员登录页 |
| `/` | 用户侧智能问数工作台 |
| `/im` | 用户侧智能聊天工作台 |
| `/admin` | 管理后台首页 |

默认管理员账号：

```text
admin / admin888
```

---

## 核心业务模块

### 1. 统一认证

- 前台普通用户与后台管理员使用同一套用户表
- 通过角色区分“前台访问权限”和“后台访问权限”
- 前台与后台分别使用不同的 Secure Cookie
- 登录页面统一为一个科技风模板，按模式切换用户登录 / 用户注册 / 管理员登录

### 2. 智能问数工作台

- 入口页面：`/`
- 左侧包含：
  - 新建任务
  - 模型服务切换
  - 数字员工下拉入口
  - 历史对话列表
- 右侧为对话工作区，支持：
  - 普通 AI 对话
  - `@数字员工` 对话
  - AI 自动识别“普通问题”与“数据问题”
  - 数据问题自动转为 SQL 检索 SQLite 仓库
  - 流式输出 + Markdown 展示
  - 天气 / 音乐卡片展示
  - 会话删除与历史回放

### 3. 智能聊天工作台

- 入口页面：`/im`
- 整体为微信式三栏布局：
  - 左侧图标导航
  - 中间会话 / 好友 / 申请 / 群聊 / 数字员工列表
  - 右侧聊天会话区
- 支持：
  - 好友搜索、发送申请、同意 / 拒绝、删除好友
  - 私聊、群聊、群成员查看
  - SSE + 轮询回退的准实时消息同步
  - 未读红点、已读回落
  - 文件发送、图片预览、表情插入
  - `@数字员工` 触发员工回复
  - 天气 / 音乐卡片化消息展示

### 4. 模型引擎

- 管理模型服务的增删改查、启停与默认模型
- 支持 OpenAI 兼容接口格式
- 支持模型测试与 SSE 流式测试
- 记录 Token 用量、响应耗时、成功/失败日志
- 前台问数默认调用后台默认模型

### 5. 数字员工

- 支持两类员工：
  - AI 员工：绑定模型服务生成回答
  - 接口员工：调用接口管理中的 API 服务
- 用户侧通过 `@别名` 直接调度员工
- 管理侧支持员工配置、启停、别名管理

### 6. 接口管理

- 统一维护第三方 API 资源
- 支持接口 CRUD、测试、参数配置
- 为数字员工等模块提供统一服务调用入口

### 7. 瞭望管理与数据仓库

- 维护瞭望源
- 执行采集任务并将结果落库
- 在数据仓库中查看采集数据
- 支持对仓库数据进行 AI 深度采集
- 深采结果落入详情表并与源数据关联
- 支持单条/批量深采、日志与基础统计

### 8. RBAC 与动态菜单

- `functions` 表驱动后台菜单树
- `roles`、`role_functions` 管理角色与功能映射
- 默认超级管理员角色不可删除/修改
- 支持功能、角色、权限模块可视化维护

---

## 主要路由

### 用户侧路由

| 路由 | 说明 |
|------|------|
| `/` | 用户首页 / 智能问数工作台 |
| `/im` | 用户首页 / 智能聊天工作台 |
| `/auth/login` | 普通用户登录 |
| `/auth/register` | 普通用户注册 |
| `/auth/logout` | 普通用户退出 |
| `/api/chat/bootstrap` | 获取用户信息、模型、员工、会话列表 |
| `/api/chat/session` | 获取会话详情与历史消息 |
| `/api/chat/stream` | SSE 智能问数流式回复 |
| `/api/im` | 智能聊天主接口 |
| `/api/im/stream` | 智能聊天 SSE 实时同步 |
| `/api/im/upload` | 智能聊天文件上传 |
| `/api/employee/options` | 获取数字员工选项 |
| `/api/employee/chat` | 数字员工普通调用 |
| `/api/employee/stream` | 数字员工流式调用 |

### 管理侧路由

| 路由 | 说明 |
|------|------|
| `/admin/login` | 管理员登录 |
| `/admin/logout` | 管理员退出 |
| `/admin` | 管理后台首页 |
| `/admin/welcome` | 欢迎页 |
| `/admin/user/list` | 用户管理 |
| `/admin/function/list` | 功能管理 |
| `/admin/role/list` | 角色管理 |
| `/admin/permission/list` | 权限管理 |
| `/admin/model/list` | 模型引擎 |
| `/admin/interface/list` | 接口管理 |
| `/admin/employee/list` | 数字员工 |
| `/admin/im/list` | 智能聊天管理 |
| `/admin/surveillance/source/list` | 瞭望源管理 |
| `/admin/surveillance/collect` | 瞭望采集 |
| `/admin/warehouse/list` | 数据仓库 |

---

## 项目目录结构

```text
cnAgentOS/
├── app.py
├── README.md
├── requirements.md
├── requirements.txt
├── test.py
├── database/
│   └── app.db
├── venv/
└── app/
    ├── controllers/
    │   ├── base.py
    │   ├── auth.py
    │   ├── home.py
    │   ├── chat.py
    │   ├── employee.py
    │   ├── im.py
    │   ├── admin.py
    │   ├── admin_user.py
    │   ├── admin_function.py
    │   ├── admin_role.py
    │   ├── admin_permission.py
    │   ├── admin_model.py
    │   ├── admin_interface.py
    │   ├── admin_employee.py
    │   ├── admin_im.py
    │   └── admin_surveillance.py
    ├── models/
    │   ├── db.py
    │   ├── user.py
    │   ├── function.py
    │   ├── role.py
    │   ├── permission.py
    │   ├── model_engine.py
    │   ├── api_endpoint.py
    │   ├── digital_employee.py
    │   ├── im.py
    │   ├── surveillance.py
    │   ├── warehouse_deep.py
    │   └── user_chat.py
    ├── templates/
    │   ├── login.html
    │   ├── index.html
    │   ├── im.html
    │   ├── base.html
    │   └── admin/
    │       ├── index.html
    │       ├── welcome.html
    │       ├── user/list.html
    │       ├── function/list.html
    │       ├── role/list.html
    │       ├── permission/list.html
    │       ├── model/list.html
    │       ├── interface/list.html
    │       ├── employee/list.html
    │       ├── im/list.html
    │       ├── surveillance/source_list.html
    │       ├── surveillance/collect.html
    │       └── warehouse/list.html
    └── static/
        ├── css/
        ├── bootstrap/
        ├── fontawesome/
        ├── layui/
        ├── dist/
        ├── glasses.png
        └── img/
```

---

## 数据库概览

系统启动时会自动执行 `init_db()`，当前主要表包括：

| 表名 | 说明 |
|------|------|
| `users` | 用户与角色信息 |
| `functions` | 功能树 / 菜单树 |
| `roles` | 角色信息 |
| `role_functions` | 角色功能映射 |
| `model_services` | 模型服务配置 |
| `model_usage_logs` | 模型调用日志 |
| `surveillance_sources` | 瞭望源 |
| `surveillance_records` | 采集记录 |
| `surveillance_record_details` | 深采详情 |
| `surveillance_deep_tasks` | 深采任务 |
| `surveillance_deep_logs` | 深采日志 |
| `api_endpoints` | 接口管理 |
| `digital_employees` | 数字员工 |
| `im_friendships` | 好友关系与好友申请 |
| `im_conversations` | IM 会话 |
| `im_conversation_members` | 会话成员与已读状态 |
| `im_messages` | IM 消息明细 |
| `im_groups` | 群聊 |
| `im_group_members` | 群成员 |
| `im_files` | IM 文件资源 |
| `user_chat_sessions` | 用户会话 |
| `user_chat_messages` | 用户消息明细 |

---

## 运行方式

### 1. 使用现有虚拟环境

```powershell
.\venv\Scripts\Activate.ps1
python app.py
```

### 2. 重新创建环境

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

### 启动结果

- 默认端口：`10086`
- 自动初始化数据库与补齐表结构
- 当前默认开启：
  - `debug = True`
  - `autoreload = True`

---

## 依赖说明

当前 `requirements.txt` 主要依赖：

```text
tornado>=6.4
aiohttp>=3.10
requests>=2.32
beautifulsoup4>=4.12
lxml>=5.3
```

> `raw4ai` 用于深采链路协同，当前代码中已做兼容处理；如环境缺失，可按需要补装。

---

## 安全与配置说明

### Tornado 关键配置

```python
settings = dict(
    template_path=os.path.join(base_url, "app", "templates"),
    static_path=os.path.join(base_url, "app", "static"),
    cookie_secret="demo-cookie-secret-change-me",
    login_url="/auth/login",
    xsrf_cookies=True,
    debug=True,
    autoreload=True,
)
```

### 当前安全机制

- 全局 XSRF 防护
- Secure Cookie 登录态
- PBKDF2-HMAC-SHA256 密码加密
- 参数化 SQL
- 用户侧与管理侧角色隔离

### 生产环境上线前建议

1. 替换 `cookie_secret`
2. 关闭 `debug` 与 `autoreload`
3. 增加 HTTPS
4. 增加登录失败限制
5. 增加数据库备份与日志归档
6. 对瞭望源补充 SSRF 白名单限制

---

## 开发约定

- 遵循 MVC 分层，Controller 不直接拼装数据库细节
- 尽量让 Model 层承担业务逻辑与数据访问
- 统一使用本地静态资源，不引入远程 CDN
- 新增模块时同步维护：
  - `README.md`
  - `requirements.md`
  - 路由注册
  - 数据库初始化/迁移逻辑

---

## 后续规划

当前仍在持续推进的方向：

- 更细粒度的权限校验与数据权限
- 统一日志中心与异常治理
- 智能聊天与智能问数更多交互细节打磨
- 问数 / 聊天的会话重命名等管理增强
- 智能舆情模块落地
- 数智大屏模块
- 非关系型 / 向量存储扩展
- 自动化测试与部署规范化

详细状态请查看 `requirements.md`。

---

## 版本记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v0.1.0 | 2026-05-23 | 基础架构、认证与后台框架初始版本 |
| v0.2.0 | 2026-05-24 | 管理后台扩展到角色权限、模型引擎、接口管理、数字员工、瞭望管理、数据仓库与用户侧智能问数 |
| v0.3.0 | 2026-05-24 | 新增智能聊天子系统、好友申请流、头像链路、问数与聊天 UI/UX 深度打磨、后台智能聊天管理与智能舆情菜单占位 |
