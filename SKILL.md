---
name: huaweicloud-skill
description: 使用 hcloud 命令行工具执行华为云资源查询、分析、规划和变更。适用于用户明确要走 CLI/KooCLI 路线，或任务需要通过 hcloud 直接发现 service/operation、构造命令、执行查询或变更、排查认证、网络、缓存与输出格式问题的场景。
version: "0.1.0"
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

## 什么时候使用

优先在以下场景使用本 skill：

- 用户明确提到 `hcloud`、`KooCLI`、CLI、命令行方式管理华为云。
- 任务需要直接通过 `hcloud` 查询或变更华为云资源。
- 任务需要查看 `service` / `operation` 列表、构造 `--cli-jsonInput`、使用 `--cli-query`、`--dryrun`、`--cli-waiter` 等 CLI 能力。
- 任务需要排查 `hcloud` 的认证、区域、项目、缓存、网络、输出格式问题。

## 与其他 Huawei skill 的边界

- `huawei_skill`
  - 走 MCP API 和 schema 精确调用。
  - 如果用户明确指定 MCP 路线，优先使用它，不要切到本 skill。
- `huawei_auto_mcp_skill`
  - 走自主 MCP 的 `run_task`。
  - 如果用户明确要自然语言直连自主 MCP，优先使用它。
- `huawei-terraform-skill`
  - 走 Terraform/OpenTofu。
  - 如果目标是生成或执行 IaC，优先使用它。
- 本 skill
  - 只处理 `hcloud` CLI 路线。
  - 除非用户要求比较方案，否则不要混用另一套方案的执行结果。

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
9. `references/playbooks/`
10. `references/source-map.md`
11. `examples/README.md`

原始 KooCLI 材料在 `materials/` 下，仅作为资料源，不应直接当作最终指令集使用。

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
   - 默认先加 `--dryrun`
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
- 脱敏命令和输出中的密钥类信息
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
- 检查关键字段是否缺失或为空
- 生成推荐的 `hcloud_safe_exec.py` dry-run 命令
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
- 避免只看到请求提交就误报资源创建完成

## 默认执行规则

- 不要为了默认上下文就先追问 AK/SK。
- 当前配置可用时，优先复用已有 profile。
- 系统参数统一优先使用 `cli-*` 新参数名。
- 查询类默认走 JSON 输出，不默认走 table。
- 复杂 body 优先 `--cli-jsonInput`，不要手工拼几百字符命令。
- ECS 创建类 JSON 先用 `hcloud_ecs_create_plan.py` 检查占位符和关键字段。
- 变更类默认先查证据，再 `--dryrun`，再执行。
- ECS 创建类真实提交后，必须用 `hcloud_ecs_wait_job.py` 或等价 `ShowJob` 查询跟到终态。
- `--cli-waiter` 有重复调用风险，默认只建议用于查询或状态轮询。
- 如果 live help 因网络或元数据问题失败，改走本地 meta cache 和 `references/`，不要瞎猜参数。

## 当前首版覆盖

首版重点覆盖以下内容：

- Huawei CLI 基本上下文探查
- Huawei CLI 本地 meta cache 发现
- `hcloud` 命令发现与构造
- CLI 认证、区域、项目和缓存问题排查
- ECS 查询与创建前准备
- ECS 创建 JSON 本地校验、dry-run 命令生成和 job 终态轮询
- VPC 网络前置检查方法

当前首版对 ECS 的 guidance 最完整。对 IAM、VPC、IMS、KPS 主要提供工作流和发现方法，不承诺已经沉淀了全量稳定 operation 清单。

当前首版已经补了本地 meta cache 发现脚本和创建类示例模板，但 `VPC`、`IMS`、`KPS` 在当前机器上没有本地详细缓存，service 级动态发现也会受到网络限制。

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
- 不要在同一个任务里同时混用 CLI 路线和 MCP 路线，除非用户明确要求。
