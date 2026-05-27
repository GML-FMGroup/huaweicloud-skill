# huaweicloud-skill

基于华为云 KooCLI (hcloud) 的 AI Agent 执行型技能，让 Agent 能稳定完成华为云资源的查询、分析、规划和变更操作。

已加入 OpenClaw 生态，ClawHub 地址：[https://clawhub.ai/zfish-lu/huaweicloud](https://clawhub.ai/zfish-lu/huaweicloud)。

## 功能定位

本技能专注于 **hcloud CLI 路线**，核心能力是让 Agent 沿着一条完整链路完成华为云操作：

1. **识别上下文** — 探查 hcloud 安装状态、认证配置、默认区域和缓存情况
2. **发现 Service 和 Operation** — 通过本地元数据缓存或在线帮助发现可用的云服务和 API 操作
3. **构造安全命令** — 查询类默认 JSON 输出，变更类默认先 dry-run，复杂参数使用 cli-jsonInput
4. **执行查询或变更** — 通过安全执行包装脚本统一运行，自动脱敏和错误分类
5. **校验结果** — 异步 job 跟踪到终态，资源状态继续验证到可用，空响应显式排查
6. **处理常见错误** — 按 USE_ERROR / NETWORK_ERROR / OPENAPI_ERROR / APIE_ERROR 分类处理

### 适用场景

- 用户明确提到 `hcloud`、`KooCLI`、CLI、命令行方式管理华为云
- 需要通过 `hcloud` 查询或变更华为云资源
- 需要查看 service / operation 列表、构造 `--cli-jsonInput`、使用 `--cli-query`、`--dryrun`、`--cli-waiter` 等 CLI 能力
- 需要排查 hcloud 的认证、区域、项目、缓存、网络、输出格式问题

## 当前覆盖状态

当前最完整的是 **ECS 执行闭环**：

- ECS 查询：实例列表、规格列表、规格售卖策略等查询型 operation
- ECS 创建准备：镜像、规格、AZ、VPC、子网、安全组、密钥对等依赖检查
- ECS 创建校验：`cli-jsonInput` 占位符和关键字段本地校验
- ECS 变更防护：默认先生成 dry-run 命令，确认后再进入 submit
- ECS 异步校验：创建或变更返回 `job_id` 后，通过 `ShowJob` 轮询 job 终态
- ECS 资源校验：job 成功后，通过 `ListServersDetails` 验证目标实例达到 `ACTIVE`

其他服务当前主要覆盖 **前置发现和 readiness 流程**：

- IAM：认证上下文、profile、region、project/domain 检查
- VPC：VPC、子网、安全组、公网接入等网络依赖发现
- IMS：镜像选择和 image id 发现路径
- KPS：密钥对发现和 SSH 登录前检查
- EIP：EIP、带宽、公网 IP 池、配额等 list/count 型发现入口
- ELB / EVS / NAT / RDS：已登记常用只读 operation，适合做初步发现；本地缺少 operation detail 时会保守省略可选参数
- CCE / CDN / DNS / SCM / CES：已按离线验证集登记最小查询入口，当前只作为低覆盖验证和发现线索

这些非 ECS 链路适合用于真实变更前的上下文确认、资源发现和风险边界梳理；在本地 operation 元数据不完整时，不应宣称已经具备和 ECS 一样完整的参数级执行能力。`service-registry.json` 中的 `resource_query_operations` 只表示“已知资源 ID 后可查询”，不会被通用 discovery 默认执行。对 CDN 这类 KooCLI 只接受固定区域集合的服务，registry 会记录 `supported_cli_regions` 和 `preferred_cli_region`，discovery/smoke 会据此生成可执行的查询命令。

## 在常用 Agent 中使用

无论接入哪种 Agent，都需要满足以下基本条件：

- Agent 能读取本目录下的 `SKILL.md`
- `scripts/`、`references/`、`examples/` 与 `SKILL.md` 一起保留
- 运行环境中已安装并配置华为云 KooCLI (`hcloud`)
- 运行环境中有 Python 3.12+
- 执行真实云资源变更前，遵循本 skill 的 dry-run、脱敏、错误分类和异步终态校验规则
- API 字段语义优先查华为云官方文档：`https://support.huaweicloud.com/intl/zh-cn/`

### OpenClaw

推荐直接从 ClawHub 安装：

```bash
openclaw skills search huaweicloud
openclaw skills install zfish-lu/huaweicloud
openclaw skills list --eligible
```

安装后，在对话里明确要求走 KooCLI 路线即可触发本 skill，例如：

```text
使用 huaweicloud-skill，通过 hcloud 查询 cn-north-4 的 ECS 列表。先检查当前 hcloud 上下文，查询类结果用 JSON 输出。
```

如果需要更新 ClawHub 安装的版本：

```bash
openclaw skills update zfish-lu/huaweicloud
```

### Hermes Agent

如果 Hermes Agent 的技能系统支持 `SKILL.md` 目录结构，可以使用本地技能目录方式接入：

1. 将整个 `huaweicloud-skill/` 目录放入 Hermes Agent 的 skills 根目录下。
2. 确认目录结构至少包含 `SKILL.md`、`scripts/`、`references/`、`examples/`。
3. 在 Hermes Agent 的技能配置或启动配置中启用该 skills 根目录。
4. 对 Agent 下达任务时，明确要求使用 `huaweicloud-skill` 和 `hcloud` 路线。

示例提示词：

```text
请使用 huaweicloud-skill，通过 hcloud/KooCLI 检查当前华为云 CLI 上下文，然后列出当前 region 的 ECS，并给出实例 ID、状态、规格和 IP。
```

### Codex

Codex 环境中使用时，推荐把本目录作为一个完整 skill 安装到 Codex 可发现的 skills 目录，或在项目说明中明确指向本目录的 `SKILL.md`。

使用建议：

1. 保留完整目录，不要只复制 `SKILL.md`。
2. 在 Codex 对话或项目说明中明确：华为云 CLI 任务优先使用 `huaweicloud-skill`。
3. 让 Codex 先读取 `SKILL.md`，再按 `references/workflow.md` 执行。
4. 查询类任务优先走 `scripts/hcloud_safe_exec.py`；ECS 创建类任务优先走 `scripts/hcloud_ecs_create_plan.py`，真实提交后继续走 `scripts/hcloud_ecs_wait_job.py` 和 `scripts/hcloud_ecs_verify_active.py`。
5. 非 ECS 服务变更类任务优先走 `scripts/hcloud_service_change_plan.py`，它只生成计划和确认门禁，不直接提交变更；服务级区域限制会从 registry 继承。

示例提示词：

```text
读取 huaweicloud-skill/SKILL.md，按其中工作流使用 hcloud 查询 ECS。先运行上下文检查，不做真实变更。
```

### Claude Code

Claude Code 环境中使用时，可以按项目级或用户级 skills 目录机制接入：

1. 将 `huaweicloud-skill/` 作为完整技能目录放到 Claude Code 可发现的 skills 位置。
2. 确认 Claude Code 能看到 `huaweicloud-skill/SKILL.md`。
3. 在项目说明或对话中声明：涉及华为云 KooCLI / `hcloud` 的任务使用本 skill。
4. 对真实资源创建、绑定、修改、删除等操作，要求 Claude Code 先给出 dry-run 或参数校验结果，再请求确认。

示例提示词：

```text
使用 huaweicloud-skill 处理这个华为云任务。先检查 hcloud profile、region、project 和 meta cache；如果是变更操作，先 dry-run，不要直接提交。
```

### 其他支持 Skills 的 Agent

如果某个 Agent 支持从目录加载技能，最低接入方式是：

```text
skills/
└── huaweicloud-skill/
    ├── SKILL.md
    ├── scripts/
    ├── references/
    ├── examples/
    └── materials/
```

然后在 Agent 的系统提示、项目说明或技能注册配置中加入：

```text
当用户要求通过 hcloud、KooCLI、CLI 查询或变更华为云资源时，读取并遵循 skills/huaweicloud-skill/SKILL.md。
查询类默认 JSON 输出；变更类必须先 dry-run；异步任务必须轮询到终态。
```

## 目录结构

```
huaweicloud-skill/
├── SKILL.md                  # 技能入口定义（元数据、质量规则、工作流）
├── scripts/                  # Python 辅助脚本
│   ├── hcloud_context_inspect.py   # 上下文探查
│   ├── hcloud_safe_exec.py         # 安全执行包装
│   ├── hcloud_prewarm_cache.py     # 缓存预热
│   ├── hcloud_meta_lookup.py       # 本地元数据查询
│   ├── hcloud_resource_discovery.py # service registry 驱动的只读资源发现
│   ├── hcloud_readonly_smoke.py     # 多服务只读 smoke 查询计划/执行
│   ├── hcloud_change_plan.py        # 通用变更风险计划
│   ├── hcloud_service_change_plan.py # 服务级 planner-only 变更计划
│   ├── hcloud_resource_verify.py     # 多服务 JSON 结果验收
│   ├── hcloud_run_journal.py        # JSONL run journal
│   ├── check_materials_drift.py     # references 与 materials 漂移检查
│   ├── check_question_coverage.py   # generated_questions 和 data.xlsx 离线回归检查
│   ├── hcloud_core.py               # 轻量共享数据结构
│   ├── hcloud_ecs_create_plan.py   # ECS 创建 JSON 校验和命令生成
│   ├── hcloud_ecs_wait_job.py      # ECS job 终态轮询
│   └── hcloud_ecs_verify_active.py # ECS ACTIVE 资源状态验证
├── references/               # 整理后的参考资料
│   ├── workflow.md                 # 标准执行流程
│   ├── auth-and-context.md         # 认证与上下文规则
│   ├── command-construction.md     # 命令构造规则
│   ├── error-playbook.md           # 错误处理手册
│   ├── output-and-query.md         # 输出与查询规则
│   ├── cache-prewarm.md            # 缓存预热指南
│   ├── local-meta-discovery.md     # 本地元数据发现
│   ├── service-coverage.md         # 服务覆盖矩阵
│   ├── service-registry.json       # 机器可读 service 覆盖和路由
│   ├── materials-sources.json      # references 与原始材料映射
│   ├── source-map.md               # 资料分层与来源映射
│   └── playbooks/                  # 面向具体任务的执行手册
│       ├── ecs-create-readiness.md
│       ├── ecs-inventory.md
│       ├── iam-context-bootstrap.md
│       ├── ims-image-discovery.md
│       ├── kps-keypair-discovery.md
│       ├── vpc-network-readiness.md
│       └── vpc-resource-discovery.md
├── examples/                 # 示例模板
│   ├── ecs-create-dryrun.md
│   ├── ecs-create-servers.cli-jsonInput.json
│   └── ecs-create-postpaid-servers.cli-jsonInput.json
├── materials/                # KooCLI 原始文档资料
│   └── hcloud-docs-md/
└── tests/                    # 测试场景与验证记录
    ├── baseline-scenarios.md
    ├── trigger-cases.md
    ├── manual-validation-2026-04-23.md
    ├── test_hcloud_architecture_contracts.py
    ├── test_hcloud_ecs_create_plan.py
    ├── test_hcloud_ecs_wait_job.py
    ├── test_hcloud_ecs_verify_active.py
    ├── test_hcloud_meta_lookup.py
    └── test_hcloud_safe_exec.py
```

## 本地验证

```bash
python3 -m unittest discover tests
python3 scripts/check_materials_drift.py --pretty
python3 scripts/check_question_coverage.py --pretty
python3 scripts/hcloud_readonly_smoke.py --service EIP --service VPC --region=<region> --project-id=<project-id> --pretty
python3 scripts/hcloud_readonly_smoke.py --service CDN --region=<region> --project-id=<project-id> --execute --strict --pretty
```

`check_question_coverage.py` 默认读取相邻项目中的 `agent_with_massive_apis/data/huawei_cloud/generated_questions`，并在存在时读取 `agent_with_massive_apis/data/huawei_cloud/data-by-changping/data.xlsx`。如果只单独 checkout 本 skill 仓库，可用 `--questions-dir` 和 `--xlsx-path` 指向本地数据路径，或用 `--skip-xlsx` 跳过 Excel 验证集。默认每个出现在问题集里的服务至少需要 10% registry 覆盖率，可用 `--default-min-registered-ratio` 或 `--min-registered-ratio SERVICE=RATIO` 调整。

## 前置条件

- 华为云 KooCLI (hcloud) 已安装并配置
- Python 3.12+
- 已配置华为云认证（AK/SK 或 profile）

## License

[MIT](LICENSE)
