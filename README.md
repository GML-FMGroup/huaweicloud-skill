# huaweicloud-skill

基于华为云 KooCLI (hcloud) 的 AI Agent 执行型技能，让 Agent 能稳定完成华为云资源的查询、分析、规划和变更操作。

## 功能定位

本技能专注于 **hcloud CLI 路线**，核心能力是让 Agent 沿着一条完整链路完成华为云操作：

1. **识别上下文** — 探查 hcloud 安装状态、认证配置、默认区域和缓存情况
2. **发现 Service 和 Operation** — 通过本地元数据缓存或在线帮助发现可用的云服务和 API 操作
3. **构造安全命令** — 查询类默认 JSON 输出，变更类默认先 dry-run，复杂参数使用 cli-jsonInput
4. **执行查询或变更** — 通过安全执行包装脚本统一运行，自动脱敏和错误分类
5. **校验结果** — 异步任务跟踪到终态，空响应显式排查
6. **处理常见错误** — 按 USE_ERROR / NETWORK_ERROR / OPENAPI_ERROR / APIE_ERROR 分类处理

### 适用场景

- 用户明确提到 `hcloud`、`KooCLI`、CLI、命令行方式管理华为云
- 需要通过 `hcloud` 查询或变更华为云资源
- 需要查看 service / operation 列表、构造 `--cli-jsonInput`、使用 `--cli-query`、`--dryrun`、`--cli-waiter` 等 CLI 能力
- 需要排查 hcloud 的认证、区域、项目、缓存、网络、输出格式问题

## 使用示例

### 1. 上下文探查

在执行任何华为云操作前，先确认当前 hcloud 环境：

```bash
python3 scripts/hcloud_context_inspect.py --pretty
```

输出包括：hcloud 是否安装、当前 profile 配置、默认 region/project、本地元数据缓存状态。

### 2. 缓存预热

如果预计需要连续处理多条华为云任务，建议先预热缓存以减少 APIE_ERROR：

```bash
python3 scripts/hcloud_prewarm_cache.py --pretty
```

### 3. 查询 ECS 规格列表

```bash
python3 scripts/hcloud_safe_exec.py \
  --service ECS \
  --operation ListFlavors \
  --arg=--cli-region=cn-north-4 \
  --arg=--project_id=YOUR_PROJECT_ID \
  --arg=--limit=20 \
  --expect-json \
  --pretty
```

### 4. 查询 ECS 实例

```bash
python3 scripts/hcloud_safe_exec.py \
  --service ECS \
  --operation ListServersDetails \
  --arg=--cli-region=cn-north-4 \
  --arg=--project_id=YOUR_PROJECT_ID \
  --expect-json \
  --pretty
```

### 5. 本地元数据发现

在不依赖网络的情况下，查询本地缓存的 service/operation 信息：

```bash
# 列出本地已知服务
python3 scripts/hcloud_meta_lookup.py --list-services --pretty

# 查看 ECS 的 operation 摘要
python3 scripts/hcloud_meta_lookup.py --service=ECS --pretty

# 查看 ListFlavors 的详细参数元数据
python3 scripts/hcloud_meta_lookup.py \
  --service=ECS \
  --operation=ListFlavors \
  --region=cn-north-4 \
  --pretty
```

### 6. 创建 ECS（先 dry-run）

使用 `--cli-jsonInput` 传入复杂参数。先用本地脚本检查占位符和关键字段：

```bash
python3 scripts/hcloud_ecs_create_plan.py \
  --json-input-file=<path-to-filled-json> \
  --operation=CreateServers \
  --region=cn-north-4 \
  --pretty
```

JSON 模板可参考 `examples/` 目录下的文件，替换其中的占位值后使用。

校验通过后，按脚本输出的 `hcloud_safe_exec.py` 命令做 dry-run。真实提交返回 `job_id` 后，用下面的方式轮询到终态：

```bash
python3 scripts/hcloud_ecs_wait_job.py \
  --job-id=YOUR_JOB_ID \
  --region=cn-north-4 \
  --project-id=YOUR_PROJECT_ID \
  --pretty
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
│   ├── hcloud_ecs_create_plan.py   # ECS 创建 JSON 校验和命令生成
│   └── hcloud_ecs_wait_job.py      # ECS job 终态轮询
├── references/               # 整理后的参考资料
│   ├── workflow.md                 # 标准执行流程
│   ├── auth-and-context.md         # 认证与上下文规则
│   ├── command-construction.md     # 命令构造规则
│   ├── error-playbook.md           # 错误处理手册
│   ├── output-and-query.md         # 输出与查询规则
│   ├── cache-prewarm.md            # 缓存预热指南
│   ├── local-meta-discovery.md     # 本地元数据发现
│   ├── service-coverage.md         # 服务覆盖矩阵
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
    ├── test_hcloud_ecs_create_plan.py
    └── test_hcloud_ecs_wait_job.py
```

## 前置条件

- 华为云 KooCLI (hcloud) 已安装并配置
- Python 3.8+
- 已配置华为云认证（AK/SK 或 profile）

## License

[MIT](LICENSE)
