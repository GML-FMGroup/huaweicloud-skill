---
name: huaweicloud-skill
description: 使用 hcloud 命令行工具执行华为云资源查询、分析、规划和变更。适用于用户明确要走 CLI/KooCLI 路线，或任务需要通过 hcloud 直接发现 service/operation、构造命令、执行查询或变更、排查认证、网络、缓存与输出格式问题的场景。
version: "0.2.0"
---

# Huawei CLI Skill

## 核心定位

- 这是一套基于 `hcloud` 的华为云执行型 skill。
- 目标不是背命令，而是让 agent 能稳定完成一条完整链路：
  - 识别上下文
  - 发现 service 和 operation
  - 构造安全命令
  - 执行查询或变更
  - 校验结果
  - 处理常见错误

## 通用质量规则

这些规则面向真实云资源操作，不绑定任何内部场景。与其他说明冲突时，优先保证安全、可审计、可复现和可验证。

### 1. 异步任务必须跟到终态

- 创建或变更类命令返回 `job_id`、`server_id`、`accepted`、`submitted` 只表示请求已提交，不代表完成。
- 继续调用 `hcloud <Svc> ShowJob --job_id=...` 或对应的 `Show*` 查询，直到资源进入 `SUCCESS`、`ACTIVE`、`available` 等稳定终态。
- 在终态前，不要说"已完成"或"创建成功"；应说明当前状态、已提交的动作和下一步轮询方式。
- ECS 创建任务至少确认：job 成功、目标实例存在、实例状态为 `ACTIVE`。

### 2. 执行型任务要落到真实命令

- 用户要求部署、搭建、创建、开通、上线、绑定或修改资源时，除非用户只要方案咨询，否则不要只输出步骤清单。
- 先查询现状，再做必要的 `--dryrun` 或参数校验；确认风险边界后，执行实际的 `Create*`、`Update*`、`Bind*`、`Attach*` 等命令。
- 如果因为权限、配额、产品未开通、参数缺失、计费风险或安全边界无法继续，停止无效重试，给出已执行命令、关键返回、阻塞原因和需要谁处理。

### 3. 定量问题必须返回具体值

- 规格、价格、配额、售卖 SKU、可用区、镜像、实例类型等问题，要尽量返回具体 ID、数值、状态或列表。
- 优先用 `hcloud <Svc> List*`、`Show*`、`*SellPolicies`、`ShowQuota*` 等命令获取结构化结果。
- 如果账号或区域查不到数据，说明已调用的命令、返回为空或权限不足，不要退化成泛泛产品介绍。

### 4. 缺省参数先发现再选择

- 创建类任务缺少 image、flavor、AZ、VPC、subnet、keypair、root volume 等常见参数时，优先通过查询选择合理默认值，不要过早追问。
- 推荐顺序：
  1. 复用同 region 下最近一条 `ACTIVE` 同类资源的参数组合。
  2. 从公共列表里选普通、可用、低风险的默认项，例如 Linux 公共镜像、通用计算规格、可用 AZ、已有 VPC/子网。
  3. 若会产生明显费用、公网暴露、数据风险或业务命名歧义，再向用户确认。
- 最终回复要说明自动选择了哪些默认值，方便用户复核或覆盖。

### 5. 输出必须可核验

- 查询类任务结尾给出数据来源：核心 `hcloud` 命令、region、project 前缀和返回条数。
- 创建或变更类任务结尾给出动作链：创建/变更命令、job 或资源 ID、终态查询命令、最终状态。
- 不要把表格输出当成唯一证据；保留关键原始字段，例如资源 ID、状态、IP、CIDR、规格、端口和时间。

### 6. 可达服务必须闭环验证

- Web、Docker Remote API、数据库、负载均衡后端等任务不能只停在资源 `ACTIVE`；还要验证进程、端口和应用协议。
- 如果要依赖 `cloud-init` 安装软件，创建前把脚本做成幂等流程：先创建父目录，再写配置；先配置软件源，再安装；最后 `enable`、`restart` 服务。
- 对外可达服务至少检查三层：安全组规则、EIP/监听器/后端绑定、协议探测结果，例如 HTTP 200、Docker `/version` JSON、数据库连接成功。
- ELB 后端必须确认成员 `operating_status=ONLINE`；若 `CONNECT_FAILED`，优先排查后端安全组、服务进程是否监听、健康检查端口/路径、后端子网 ID 是否匹配。
- 如果没有远程命令能力，可用 EIP + 协议探测验证；如果协议探测不通，不要宣布应用部署成功。

### 7. ECS 初始化和远程排障

- 复杂 ECS 创建优先使用 `--cli-jsonInput` 或临时 JSON 文件，避免超长单行命令、base64、嵌套数组参数被 shell 转义破坏。
- 若创建 keypair 用于后续 SSH，必须把返回的 private key 保存到受限权限文件，例如 `chmod 600`，并记录 keypair 名称；否则不要把 SSH 当成可用降级路径。
- `cloud-init` 脚本中写 `/etc/docker/daemon.json`、systemd drop-in、Nginx 站点配置等文件前，先 `mkdir -p` 父目录。
- 对 Ubuntu 安装 Docker，优先选择当前区域可达的官方/云镜像源；安装失败时可降级为发行版仓库中的 `docker.io`，并说明降级影响。
- 远程暴露 Docker TCP 2375 属于高风险配置；只有用户明确要求时才开放，并在最终输出中提示这是未加密管理端口。

### 8. 幂等修复与保守收敛

- 创建前按资源名做幂等查询；发现同名资源时先读 `references/playbooks/resource-idempotency-reconcile.md`，选择 canonical resource 修复，不要继续创建同名资源。
- ECS 内服务、Docker Remote API、ELB HTTP 后端这类可达性任务，应优先读取对应 readiness playbook，使用可重复执行的初始化和验收流程。
- 收敛规则必须保守：只在明确硬阻塞、同一失败已基于新证据修复至少两轮仍无进展、或后续只剩外部等待且继续执行不会改变状态时，才停止并输出部分完成结果。
- 只要还有明确、低风险、与用户目标直接相关的下一步，不要提前交卷；也不要把未通过协议探测或健康检查的组件写成已完成。

## 什么时候使用

优先在以下场景使用本 skill：

- 用户明确提到 `hcloud`、`KooCLI`、CLI、命令行方式管理华为云。
- 任务需要直接通过 `hcloud` 查询或变更华为云资源。
- 任务需要查看 `service` / `operation` 列表、构造 `--cli-jsonInput`、使用 `--cli-query`、`--dryrun`、`--cli-waiter` 等 CLI 能力。
- 任务需要排查 `hcloud` 的认证、区域、项目、缓存、网络、输出格式问题。


## 资料入口

先看整理后的资料，再回到原始材料：

1. `references/workflow.md`
2. `references/auth-and-context.md`
3. `references/cache-prewarm.md`
4. `references/local-meta-discovery.md`
5. `references/service-coverage.md`
6. `references/command-construction.md`
7. `references/error-playbook.md`
8. `references/output-and-query.md`
9. `references/service-registry.json`
10. `references/playbooks/`
11. `references/source-map.md`
12. `examples/README.md`

原始 KooCLI 材料在 `materials/` 下，仅作为资料源，不应直接当作最终指令集使用。
华为云官方文档优先从 `https://support.huaweicloud.com/intl/zh-cn/` 查证；涉及 API 字段语义时，以官方文档和实际 `hcloud --dryrun`/查询结果为准。

## 默认工作流

1. 先确认上下文
   - 优先运行 `python3 scripts/hcloud_context_inspect.py --pretty`
   - 明确 `hcloud` 是否可用、当前 profile、默认 region、project、offline mode、meta cache 是否存在
2. 先发现，再执行
   - 先看 `hcloud --help`
   - 再看 `hcloud <service> --help`
   - 能拿到 operation 帮助时，再看 `hcloud <service> <operation> --help`
3. 查询类默认稳定化
   - 默认使用 `--cli-output=json`
   - 需要提炼时再加 `--cli-query`
   - 大结果默认先限制 `limit` 或筛选字段
4. 复杂参数不要硬拼长命令
   - 优先 `--skeleton`
   - 或使用 `--cli-jsonInput`
5. 变更类先做预执行
   - 默认先用 `python3 scripts/hcloud_change_plan.py ...` 生成风险摘要和 dry-run/submit 命令
   - 支持 dry-run 的操作默认先加 `--dryrun`
   - 复杂创建类优先先补齐依赖项，再进入真实执行
6. 返回为空时显式校验
   - 为空不代表失败
   - 必要时加 `--debug` 查看状态码
7. 失败时按错误类型处理
   - 先看 `references/error-playbook.md`
   - 不要在未知错误上反复重试同一个命令

## 推荐脚本入口

### 1. 上下文检查

```bash
python3 scripts/hcloud_context_inspect.py --pretty
```

用途：

- 看 `hcloud` 是否存在
- 看当前 profile 和 profile 列表
- 看 region、project、domain 是否显式配置
- 看本地 meta cache 和离线元数据包是否存在

### 2. 缓存预热

```bash
python3 scripts/hcloud_prewarm_cache.py --pretty
```

用途：

- 尝试下载离线元数据包
- 预热高频 service 的 help / operation help
- 输出预热前后缓存状态 summary

如果你预计接下来要让 agent 连续处理多条华为云真实业务，建议先跑一次。

### 3. 安全执行

```bash
python3 scripts/hcloud_safe_exec.py \
  --service ECS \
  --operation ListFlavors \
  --arg=--cli-region=cn-north-4 \
  --arg=--project_id=example-project-id \
  --arg=--limit=20 \
  --expect-json \
  --pretty
```

用途：

- 统一执行 `hcloud`
- 自动给出结构化 JSON 结果
- 脱敏命令、stdout/stderr、`parsed_json` 和 `--parsed-json-file` 中的密钥类信息
- 识别常见错误类型

对于 `configure` 一类系统命令，可改用：

```bash
python3 scripts/hcloud_safe_exec.py \
  --command-part=configure \
  --command-part=show \
  --expect-json \
  --pretty
```

### 4. 本地 meta cache 发现

```bash
python3 scripts/hcloud_meta_lookup.py --service=ECS --pretty
```

用途：

- 看本地缓存里有没有这个 service
- 看缓存了多少 operation
- 看某个 operation 有没有详细参数元数据
- 看本地缓存的 endpoint 和 region 信息
- operation detail 文件优先按 JSON 解析；若是普通 YAML，环境有 PyYAML 时会尝试 YAML 解析，否则返回明确的 `yaml_unavailable`

如果需要 operation 细节：

```bash
python3 scripts/hcloud_meta_lookup.py \
  --service=ECS \
  --operation=ListFlavors \
  --region=cn-north-4 \
  --pretty
```

### 5. ECS 创建计划校验

```bash
python3 scripts/hcloud_ecs_create_plan.py \
  --json-input-file=<path-to-filled-json> \
  --operation=CreateServers \
  --region=cn-north-4 \
  --pretty
```

用途：

- 校验 ECS 创建 JSON 是否还包含 `<project_id>` 等占位符
- 检查关键字段是否缺失或为空；嵌入式占位符如 `ecs-<env>` 也会拦截
- 默认把 `count` 限制在保守上限 10；更大数量需要 `--allow-large-count`
- 生成 JSON-friendly 的 `hcloud_safe_exec.py` dry-run 命令和可复制 shell 命令
- 防止在依赖未确认时直接进入真实创建

如果 dry-run 已通过，并且用户明确确认真实创建，再生成非 dry-run 命令：

```bash
python3 scripts/hcloud_ecs_create_plan.py \
  --json-input-file=<path-to-json> \
  --operation=CreateServers \
  --region=cn-north-4 \
  --mode=submit \
  --confirm-submit \
  --pretty
```

### 6. ECS job 终态轮询

```bash
python3 scripts/hcloud_ecs_wait_job.py \
  --job-id=<job-id> \
  --region=cn-north-4 \
  --project-id=<project-id> \
  --pretty
```

用途：

- 对 `CreateServers`、`CreatePostPaidServers` 等返回的 `job_id` 调用 `ECS ShowJob`
- 持续轮询直到 `SUCCESS`、`FAILED`、`ERROR` 等终态
- 输出 `verification_scope=job_terminal_only`，避免把 job 成功误报成 ECS 可用

### 7. ECS ACTIVE 资源验证

```bash
python3 scripts/hcloud_ecs_verify_active.py \
  --server-id=<server-id> \
  --region=cn-north-4 \
  --project-id=<project-id> \
  --pretty
```

用途：

- 在 `ShowJob SUCCESS` 后确认目标 ECS 存在
- 轮询 `ListServersDetails`，直到目标实例状态为 `ACTIVE`
- 支持按 `--server-id` 或 `--server-name` 验证

### 8. 只读资源发现

```bash
python3 scripts/hcloud_resource_discovery.py \
  --service ECS \
  --operation ListServersDetails \
  --region=cn-north-4 \
  --project-id=<project-id> \
  --limit=50 \
  --pretty
```

用途：

- 按 `references/service-registry.json` 生成 list-only 查询命令
- 对 ECS / IAM / VPC / IMS / KPS / EIP / ELB / EVS / NAT / RDS 等服务做创建前依赖发现
- `resource_query_operations` 是已知资源 ID 后的查询线索，不会被通用 discovery 默认执行
- 如果 registry 声明了 `supported_cli_regions`，脚本会把不支持的 `--region` 调整到 `preferred_cli_region`，例如 CDN discovery 使用 `cn-north-1`
- 默认只生成计划；只有显式 `--execute` 才执行查询

### 9. 通用变更风险计划

```bash
python3 scripts/hcloud_change_plan.py \
  --service ECS \
  --operation CreateServers \
  --region=cn-north-4 \
  --json-input-file=<path-to-json> \
  --pretty
```

用途：

- 对 `Create*`、`Update*`、`Delete*`、`Bind*`、`Attach*` 等变更操作生成风险摘要
- 生成 dry-run/submit 命令
- 在真实执行前明确确认、费用、范围和验证要求

### 10. 多服务只读 smoke

```bash
python3 scripts/hcloud_readonly_smoke.py \
  --service EIP \
  --service VPC \
  --region=cn-north-4 \
  --project-id=<project-id> \
  --pretty
```

用途：

- 按 registry 为多个服务生成最小只读查询计划
- 显式 `--execute` 时才通过 `hcloud_safe_exec.py` 运行只读查询
- 对 CDN 这类有固定 KooCLI 区域集合的服务，会沿用 discovery 的区域解析结果
- 默认不把 live 查询失败当成脚本失败；需要严格失败门槛时加 `--strict`

### 11. 服务级变更计划

```bash
python3 scripts/hcloud_service_change_plan.py \
  --service EIP \
  --operation CreatePublicip \
  --region=cn-north-4 \
  --project-id=<project-id> \
  --pretty
```

用途：

- 为 EIP / VPC / ELB / EVS / RDS / NAT / DNS / SCM / CDN 等服务生成 planner-only 变更计划
- 继承 `hcloud_change_plan.py` 的风险分类、dry-run/submit 命令和确认门禁
- 附加服务上下文、known limits 和后置验证建议
- 对 registry 声明的 `supported_cli_regions` 同样生效，避免为 CDN 这类服务生成已知不可用的区域命令
- 不执行真实变更；submit 命令必须单独获得用户确认后才可运行

### 12. 多服务资源验收

```bash
python3 scripts/hcloud_resource_verify.py \
  --service EIP \
  --json-file=<safe-exec-result.json> \
  --target-id=<publicip-id> \
  --expect-status BIND_ACTIVE \
  --expect-bound-to=<target-port-or-instance-id> \
  --require-match \
  --pretty
```

用途：

- 从 `hcloud_safe_exec.py` JSON 结果或原始服务 JSON 中提取资源列表
- 验证 EIP / VPC / ELB / EVS / NAT / RDS / CCE / CDN / DNS / SCM 的目标 ID、名称、状态、CIDR 或绑定关系
- 对 ELB 等双状态资源，可用 `--expect-field operating_status=ONLINE` 检查特定字段
- 只做验收判定，不访问云端；真实查询仍由 `hcloud_safe_exec.py` 或 discovery 脚本负责

### 13. 离线问题集回归

```bash
python3 scripts/check_question_coverage.py --pretty
```

用途：

- 检查 `generated_questions` 的 JSON 结构和 CRUD `type` 标注
- 用 `hcloud_change_plan.py` 回归验证读、改、删操作的风险分类
- 汇总问题集中 operation 对 service registry 的覆盖情况
- 如果 `data-by-changping/data.xlsx` 存在，也会检查人工 E2E 问题和验证方法，抽取验证步骤里的服务/operation，标出外部探测和带副作用的验证步骤
- 默认按 10% registry 覆盖率做最低门槛；可用 `--default-min-registered-ratio` 或 `--min-registered-ratio SERVICE=RATIO` 调整
- 默认读取相邻项目的 `agent_with_massive_apis/data/huawei_cloud/generated_questions`；单独使用本 skill 时可用 `--questions-dir` 指定路径

## 默认执行规则

- 不要为了默认上下文就先追问 AK/SK。
- 当前配置可用时，优先复用已有 profile。
- 系统参数统一优先使用 `cli-*` 新参数名。
- 查询类默认走 JSON 输出，不默认走 table。
- 复杂 body 优先 `--cli-jsonInput`，不要手工拼几百字符命令。
- ECS 创建类 JSON 先用 `hcloud_ecs_create_plan.py` 检查占位符和关键字段。
- 变更类默认先查证据，再用 `hcloud_change_plan.py` 生成风险计划，再 `--dryrun`，再执行。
- ECS 创建类真实提交后，必须先用 `hcloud_ecs_wait_job.py` 或等价 `ShowJob` 查询 job 终态，再用 `hcloud_ecs_verify_active.py` 或等价查询确认目标实例 `ACTIVE`。
- `--cli-waiter` 有重复调用风险，默认只建议用于查询或状态轮询。
- 如果 live help 因网络或元数据问题失败，改走本地 meta cache 和 `references/`，不要瞎猜参数。

## 当前首版覆盖

首版重点覆盖以下内容：

- Huawei CLI 基本上下文探查
- Huawei CLI 本地 meta cache 发现
- `hcloud` 命令发现与构造
- CLI 认证、区域、项目和缓存问题排查
- ECS 查询与创建前准备
- ECS 创建 JSON 本地校验、dry-run 命令生成、job 终态轮询和 ACTIVE 资源验证
- service registry、只读资源发现、通用变更风险计划、run journal、材料漂移检查和问题集回归检查
- VPC / IMS / KPS / IAM / EIP 创建前只读发现方法
- ELB / EVS / NAT / RDS / CCE / CDN / DNS / SCM / CES 的低覆盖查询登记，用于离线数据集回归和前置发现
- 多服务只读 smoke、planner-only 变更计划和 JSON 结果验收脚本

当前首版对 ECS 的 guidance 最完整。对 IAM、VPC、IMS、KPS、EIP 主要提供工作流和发现方法；对 ELB、EVS、NAT、RDS、CCE、CDN、DNS、SCM、CES 只提供低覆盖查询登记和 planner-only 计划，不承诺已经沉淀了全量稳定 operation 清单。

当前首版已经补了本地 meta cache 发现脚本和创建类示例模板；非 ECS 服务的 operation detail 缓存可能不完整，脚本会在缺少参数元数据时保守省略可选参数。

## 示例模板

示例文件放在 `examples/` 下。

当前重点提供：

- ECS `CreateServers` 的 `cli-jsonInput` 模板
- ECS `CreatePostPaidServers` 的 `cli-jsonInput` 模板
- 对应的 dry-run 命令说明

这些示例主要用于：

- 构造可审查的请求骨架
- 指导用户替换真实 ID 和参数
- 避免把几十个字段硬编码进一行命令

## 禁止事项

- 不要把 raw `materials/` 当成唯一事实来源直接复述。
- 不要在未确认上下文前直接执行高风险删除或不可逆变更。
- 不要把真实 AK/SK、token、密码写进文档、日志或最终回复。
- 不要把表格输出当成机器可稳定解析的默认格式。
- 本 skill 负责 CLI/KooCLI 路线；Terraform、MCP、IaC 等路线只在用户明确要求或项目路由规则指定时接管。
