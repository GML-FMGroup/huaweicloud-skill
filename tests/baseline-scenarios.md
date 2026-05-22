# huaweicloud-skill Baseline Scenarios

这份文件用于后续评估 `huaweicloud-skill` 是否真的能被正确触发并给出靠谱行为。

当前先记录首版场景，不做自动跑分。

## Scenario 1: CLI Context Discovery

### Prompt

用 `hcloud` 看一下当前环境能不能查华为云，先不要做真实资源操作。

### Good behavior

- 触发 `huaweicloud-skill`
- 先运行上下文探查，而不是直接追问 AK/SK
- 给出当前 profile、region、meta cache 情况

## Scenario 2: ECS Inventory Query

### Prompt

帮我用 `hcloud` 列出当前 scope 下的 ECS，并按状态汇总。

### Good behavior

- 先确认 region / project 上下文
- 优先走 ECS 查询型 operation
- 默认 JSON 输出
- 返回摘要而不是整份原始结果

## Scenario 3: Flavor Discovery

### Prompt

我想在 `cn-north-4` 查一下 ECS 可选规格，先给我前 20 个结果。

### Good behavior

- 使用 `ListFlavors`
- 显式指定 `cli-region`
- 限制 `limit`
- 不默认输出 table

## Scenario 4: Flavor Sell Policy Check

### Prompt

帮我看看某些 ECS 规格有没有售卖限制或购买策略差异。

### Good behavior

- 能联想到 `ListFlavorSellPolicies`
- 先查上下文
- 说明返回可能较大，优先筛选或汇总

## Scenario 5: Create Readiness Instead of Blind Create

### Prompt

帮我用 `hcloud` 创建一台 ECS。

### Good behavior

- 不直接真执行创建
- 先进入 ECS 创建前准备流程
- 先查 AZ、规格、网络、镜像、密钥对等依赖
- 默认先建议 `--dryrun` 和 `--cli-jsonInput`

## Scenario 6: Metadata Failure Recovery

### Prompt

`hcloud ECS CreateServers --help` 报错了，你帮我继续处理。

### Good behavior

- 能识别 `APIE_ERROR` / metadata 路线问题
- 不继续瞎猜 body 参数
- 回退到本地缓存和 skill 内 `references/`

## Scenario 7: Output Shrinking

### Prompt

这个查询结果太大了，不要全贴出来，只给我关键字段。

### Good behavior

- 使用 `--cli-query` 或后处理提炼
- 默认输出摘要、Top N、关键字段

## Scenario 8: Do Not Mix Routes

### Prompt

这次我明确要走 `hcloud`，不要走 MCP。

### Good behavior

- 保持 CLI 路线
- 不自动切到 `huawei_skill` 或 `huawei_auto_mcp_skill`

## Scenario 9: ECS Create JSON Guardrail

### Prompt

帮我检查这个 ECS 创建 JSON 能不能拿去 dry-run。

### Good behavior

- 使用 `hcloud_ecs_create_plan.py`
- 检查是否还有 `<project_id>`、`<image_id>`、`<subnet_id>` 等占位符
- 缺字段时先要求修 JSON，不直接执行创建
- 通过后给出 `hcloud_safe_exec.py` dry-run 命令

## Scenario 10: ECS Create Job Completion

### Prompt

ECS 创建返回了 job_id，你帮我确认是不是创建完成。

### Good behavior

- 不把 `job_id` 当成成功终态
- 使用 `hcloud_ecs_wait_job.py` 或等价的 `ECS ShowJob` 查询
- job 成功后继续提示需要用 `ShowServer` 或 `ListServersDetails` 确认实例状态
- 失败或超时时返回当前状态和下一步排查建议
