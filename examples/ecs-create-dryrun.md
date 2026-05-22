# ECS Create Dry-Run Example

## 目标

先用 dry-run 验证命令和参数骨架，再决定是否真实创建。

## `CreateServers`

先检查模板是否已经替换完整：

```bash
python3 scripts/hcloud_ecs_create_plan.py \
  --json-input-file=examples/ecs-create-servers.cli-jsonInput.json \
  --operation=CreateServers \
  --region=cn-north-4 \
  --pretty
```

校验通过后，再执行脚本输出的 `commands.safe_exec`，或手动 dry-run：

```bash
hcloud ECS CreateServers \
  --cli-region=cn-north-4 \
  --dryrun \
  --cli-jsonInput=examples/ecs-create-servers.cli-jsonInput.json
```

## `CreatePostPaidServers`

先检查模板是否已经替换完整：

```bash
python3 scripts/hcloud_ecs_create_plan.py \
  --json-input-file=examples/ecs-create-postpaid-servers.cli-jsonInput.json \
  --operation=CreatePostPaidServers \
  --region=cn-north-4 \
  --pretty
```

校验通过后，再执行脚本输出的 `commands.safe_exec`，或手动 dry-run：

```bash
hcloud ECS CreatePostPaidServers \
  --cli-region=cn-north-4 \
  --dryrun \
  --cli-jsonInput=examples/ecs-create-postpaid-servers.cli-jsonInput.json
```

## 推荐先替换的字段

- `project_id`
- `availability_zone`
- `flavor_id`
- `image_id`
- `vpc_id`
- `subnet_id`
- `security_group_id`
- `key_name`

## 当前环境下的现实限制

如果 `CreateServers` 的 operation 详情当前仍然依赖 live metadata，而网络又不可用，那么 dry-run 也可能会卡在 metadata discovery。

这不是模板的问题，而是当前运行环境的限制。

因此：

- 模板先作为可审查骨架
- 本地计划脚本先拦截未替换占位符和明显缺失字段
- 真正跑 dry-run 时，再结合当前环境判断是否能继续
