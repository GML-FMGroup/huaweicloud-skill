# Huawei CLI Service Coverage

本文件说明当前 `huaweicloud-skill` 对不同服务的覆盖深度。

## 覆盖等级说明

- `High`
  - 有本地 meta cache、helper script、playbook、实际验证
- `Medium`
  - 有服务级 guidance 或 playbook，但动态发现或本地缓存不完整
- `Low`
  - 只有服务存在性或文档层 guidance，暂未形成稳定执行路径

## 当前覆盖矩阵

机器可读版本见 `references/service-registry.json`。后续自动化脚本应优先消费 registry，本文件保留人类可读说明。

| Service | Coverage | 当前状态 | 说明 |
|---------|----------|----------|------|
| `ECS` | High | 最完整 | 本地有 `apis_en.json`、部分 operation detail cache，已验证 `ListFlavors` 的 meta lookup、dry-run、本地参数校验；已有创建 JSON 校验、ShowJob 轮询和 ACTIVE 资源验证脚本 |
| `IAM` | Medium | 可做上下文和 endpoint 发现 | 当前机器仅有 endpoint cache，operation 级 detail 仍不完整 |
| `VPC` | Medium | 有 workflow、playbook 和 list-only discovery 入口 | 当前机器无本地 template cache，service help fallback 会受网络限制 |
| `IMS` | Medium | 有 workflow、playbook 和 list-only discovery 入口 | 当前机器无本地 template cache，适合作为镜像发现方法论入口 |
| `KPS` | Medium | 有 workflow、playbook 和 list-only discovery 入口 | 当前机器无本地 template cache，适合作为密钥对发现方法论入口 |

## 已实测能力

### ECS

- `hcloud ECS --help`
- `hcloud_meta_lookup.py --service=ECS`
- `hcloud_meta_lookup.py --service=ECS --operation=ListFlavors`
- `hcloud ECS ListFlavors --dryrun`
- `hcloud_safe_exec.py` 包装查询和错误分类
- `hcloud_ecs_create_plan.py` 本地校验 ECS 创建 JSON 并生成 dry-run / submit 命令
- `hcloud_ecs_wait_job.py --print-command-only` 生成 `ShowJob` 轮询命令
- `hcloud_ecs_verify_active.py --print-command-only` 生成 `ListServersDetails` ACTIVE 验证命令
- `hcloud_change_plan.py` 为变更操作生成风险摘要和 dry-run/submit 命令

### 非 ECS

已实测：

- `IMS`
- `VPC`
- `KPS`

结果：

- 在 `services_en.json` 中可以看到这些 service
- 当前机器没有对应的本地 template cache
- `--allow-help-fallback` 仍会命中 `APIE_ERROR`
- `hcloud_resource_discovery.py` 可以按 registry 为这些服务生成 list-only 查询命令，但真实执行仍依赖本机 hcloud metadata 和账号权限

## 对 agent 的实际意义

### 当用户任务在 ECS 范围内

可以较积极地：

- 做 command discovery
- 做 dry-run
- 做查询链路验证
- 对创建 JSON 做占位符和关键字段本地校验
- 真实创建返回 `job_id` 后轮询到终态

### 当用户任务在 VPC / IMS / KPS / IAM 范围内

当前更适合：

- 先做上下文确认
- 先用 service 级 discovery 和 playbook 梳理动作
- 把真实执行建立在进一步元数据可用之后

不要伪装成已经有了和 ECS 一样完整的操作细节。
