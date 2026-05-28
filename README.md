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

其他服务当前按 **高频服务广度优先** 覆盖前置发现、资源级只读查询和 readiness 流程：

- ECS / VPC / RDS / IMS / EVS / EIP / ELB / NAT：按问题集频次优先进入默认 readiness 顺序
- IAM：认证上下文、profile、region、project/domain 检查
- VPC：VPC、子网、安全组等 list 发现，并支持 `ShowVpc` / `ShowSubnet` / `ShowSecurityGroup` 等目标查询
- IMS：镜像列表、OS 版本和 `GlanceShowImage` 镜像详情路径
- KPS：密钥对列表和 `ListKeypairDetail` 详情路径
- EIP：EIP、带宽、公网 IP 池、配额等 list/count 型发现入口，`ShowPublicip`，以及带确认门禁的 Plan -> Apply -> Verify 参考 flow
- ELB / EVS / NAT / RDS：已登记常用 list 查询和第一层 show/detail 查询；本地缺少 operation detail 时通过显式参数白名单保守执行
- CCE / CDN / DNS / SCM / CES：已按离线验证集登记最小查询入口；其中 CDN、DNS、SCM、CCE 已支持部分目标型查询
- OBS：不走普通 `hcloud <Service> <Operation>` 元数据路径，改用 KooCLI 集成的 `hcloud obs`/obsutil 适配器，支持 bucket list、bucket stat、lifecycle/policy get 和 planner-only lifecycle/policy/bucket 变更计划

这些非 ECS 链路适合用于真实变更前的上下文确认、资源发现和风险边界梳理；在本地 operation 元数据不完整时，不应宣称已经具备和 ECS 一样完整的参数级执行能力。`service-registry.json` 中的 `resource_query_operations` 只表示“已知资源 ID 后可查询”，不会被通用 discovery 默认执行。查询脚本会宽松匹配大小写或数据集里的 operation 写法，例如 `showvpc` 会解析到 `ShowVpc`。对 CDN 这类 KooCLI 只接受固定区域集合的服务，registry 会记录 `supported_cli_regions` 和 `preferred_cli_region`，discovery/smoke 会据此生成可执行的查询命令。OBS 这类非 OpenAPI-style 命令会通过 registry 的专用 runner 路由到 `hcloud_obs_readonly.py` / `hcloud_obs_change_plan.py`。

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
│   ├── hcloud_resource_query.py     # 显式参数的资源级只读查询
│   ├── hcloud_eip_change_flow.py      # EIP Plan -> Apply -> Verify 守护流程
│   ├── hcloud_obs_readonly.py        # OBS hcloud obs/obsutil 只读适配器
│   ├── hcloud_obs_change_plan.py     # OBS planner-only 变更计划
│   ├── hcloud_resource_detail_probe.py # list-then-detail 只读抽样
│   ├── hcloud_service_readiness.py  # 多服务只读 readiness 检查
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
python3 scripts/hcloud_service_readiness.py --service VPC --service ELB --region=<region> --project-id=<project-id> --pretty
python3 scripts/hcloud_resource_query.py --service EIP --operation ShowPublicip --param publicip_id=<publicip-id> --region=<region> --project-id=<project-id> --pretty
python3 scripts/hcloud_eip_change_flow.py --operation UpdatePublicip --publicip-id=<publicip-id> --arg=--publicip_id=<publicip-id> --region=<region> --project-id=<project-id> --pretty
python3 scripts/hcloud_obs_readonly.py --operation ListBuckets --limit=20 --pretty
python3 scripts/hcloud_resource_detail_probe.py --service EVS --service NAT --region=<region> --execute --pretty
python3 scripts/hcloud_readonly_smoke.py --service CDN --region=<region> --project-id=<project-id> --execute --strict --pretty
```

`check_question_coverage.py` 默认读取相邻项目中的 `agent_with_massive_apis/data/huawei_cloud/generated_questions`，并在存在时读取 `agent_with_massive_apis/data/huawei_cloud/data-by-changping/data.xlsx`。如果只单独 checkout 本 skill 仓库，可用 `--questions-dir` 和 `--xlsx-path` 指向本地数据路径，或用 `--skip-xlsx` 跳过 Excel 验证集。默认每个出现在问题集里的服务至少需要 10% registry 覆盖率，可用 `--default-min-registered-ratio` 或 `--min-registered-ratio SERVICE=RATIO` 调整。Excel 验证集里的已注册 operation 还会检查是否存在可执行路径：普通 list 查询走 registry 的 `query_runner`，需要资源 ID 的 show/list 查询走 `resource_query_runner`，变更类只允许 planner-only。

`hcloud_safe_exec.py` 的失败结果会包含 `error_type` 和 `error_details`。`error_details` 会把常见问题归类为 `credential`、`permission`、`region_or_endpoint`、`project`、`quota`、`parameter`、`not_found`、`network` 等，并给出下一步建议，方便 Agent 判断是配置问题、权限问题还是参数问题。

`hcloud_eip_change_flow.py` 默认只生成计划和后置 `ShowPublicip` 验证计划。真实提交必须显式使用 `--execute-submit --confirm-submit`，并建议先跑 `--execute-dryrun`；未确认时脚本会返回 `submit_guard_failure`，不会执行变更。

## 前置条件

- 华为云 KooCLI (hcloud) 已安装并配置
- Python 3.12+
- 已配置华为云认证（AK/SK 或 profile）

## 用户协助配置项

Agent 可以自动发现命令、生成计划、执行只读查询和做结果校验，但以下凭证和环境项需要用户提前配置或授权提供。

### 普通 hcloud OpenAPI 服务

适用于 ECS、VPC、RDS、EIP、ELB、EVS、IMS、NAT、DNS、SCM、CES、CCE 等普通 `hcloud <Service> <Operation>` 命令。

- 已登录或已配置可用的 KooCLI profile。
- 默认或显式传入 `--cli-region`。
- 需要项目级 API 时，配置或传入对应 `project_id`。
- 账号需要具备目标服务的只读权限；变更类任务还需要对应写权限。

建议先用以下命令检查上下文：

```bash
python3 scripts/hcloud_context_inspect.py --pretty
```

### OBS hcloud obs / obsutil

OBS 不走普通 `hcloud OBS <Operation>` 元数据路径，而是使用 KooCLI 集成的 `hcloud obs`/obsutil 命令，因此需要单独确认 OBS 配置。

用户需要协助提供或完成：

- 有效的 OBS AK/SK；临时凭证还需要 security token。
- 正确的 OBS endpoint，例如与 bucket 所在站点匹配的 endpoint。
- 如果使用非默认 obsutil 配置文件，需要告知 `--config <path>`。
- 如果访问 requester-pays bucket，需要告知 payer 设置。

可用以下命令配置或检查 OBS 认证；不要把真实 AK/SK/token 写进仓库或发到对话里：

```bash
hcloud obs config -i=<AK> -k=<SK> -e=<OBS endpoint>
hcloud obs ls
```

本 skill 的只读验证入口：

```bash
python3 scripts/hcloud_obs_readonly.py --operation ListBuckets --limit=20 --execute --pretty
python3 scripts/hcloud_obs_readonly.py --operation StatBucket --bucket=<bucket-name> --execute --pretty
```

如果看到 `InvalidAccessKeyId` 或 `SignatureDoesNotMatch`，通常是 OBS AK/SK/token 或 endpoint 配置问题；普通 `hcloud configure` 能查询 ECS/VPC，不代表 `hcloud obs` 一定已经配置正确。

## License

[MIT](LICENSE)
