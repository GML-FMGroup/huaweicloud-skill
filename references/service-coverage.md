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
| `VPC` | Medium | 有 workflow、playbook 和 list-only discovery 入口 | 本地可发现 VPC list/count 型 operation；部分 operation detail 不完整，执行时需要结合 metadata 和返回错误校正参数 |
| `IMS` | Medium | 有 workflow、playbook 和 list-only discovery 入口 | 本地可发现镜像 list 型 operation；资源级 member/tag 操作需要目标 ID，不作为通用 discovery 入口 |
| `KPS` | Medium | 有 workflow、playbook 和 list-only discovery 入口 | 本地已验证 `ListKeypairs` operation 名称；密钥创建和私钥处理需要专门风险 gate |
| `EIP` | Medium | 有 list/count 型 discovery 入口 | 本地可发现 EIP、带宽、公网 IP 池、配额等查询 operation；operation detail 缓存不完整时会保守省略可选参数 |
| `ELB` | Low | 已登记常用查询入口 | service 可见但本地没有 operation detail；用于负载均衡验证和离线问题集覆盖，不等同于完整 ELB 执行能力 |
| `EVS` | Low | 已登记常用查询入口 | service 可见但本地没有 operation detail；云硬盘挂载、扩容、格式化仍需专门 planner |
| `NAT` | Low | 已登记常用查询入口 | service 可见但本地没有 operation detail；NAT 创建、绑定和删除仍未开放通用变更 |
| `RDS` | Low | 已登记常用查询入口 | service 可见但本地没有 operation detail；RDS detail 查询通常需要实例 ID 和引擎相关参数 |
| `CCE` / `CDN` / `DNS` / `SCM` / `CES` | Low | 已登记最小验证入口 | 来自人工 E2E 验证集和本地 service 存在性检查，仅用于前置发现和回归统计 |

`query_operations` 表示可作为通用 discovery 起点的查询。`resource_query_operations` 表示已知资源 ID 或上下文后才适合执行的查询，覆盖统计会计入，但 `hcloud_resource_discovery.py` 不会默认把它们当作 list-only 操作执行。

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
- `EIP`
- `ELB`
- `EVS`
- `NAT`
- `RDS`
- `CCE`
- `CDN`
- `DNS`
- `SCM`
- `CES`

结果：

- 在 `services_en.json` 中可以看到这些 service
- 本地 template cache 覆盖深度不一致；EIP / VPC 等可能只有 operation index，ELB / EVS / NAT / RDS 等当前只有 service 入口，缺少 per-operation detail
- `hcloud_resource_discovery.py` 可以按 registry 为这些服务生成 list-only 查询命令，但真实执行仍依赖本机 hcloud metadata 和账号权限
- `check_question_coverage.py` 可用外部 `generated_questions` 和 `data-by-changping/data.xlsx` 回归验证 schema、CRUD type、风险分类、registry 覆盖和人工验证步骤风险线索

## 对 agent 的实际意义

### 当用户任务在 ECS 范围内

可以较积极地：

- 做 command discovery
- 做 dry-run
- 做查询链路验证
- 对创建 JSON 做占位符和关键字段本地校验
- 真实创建返回 `job_id` 后轮询到终态

### 当用户任务在 VPC / IMS / KPS / IAM / EIP 范围内

当前更适合：

- 先做上下文确认
- 先用 service 级 discovery 和 playbook 梳理动作
- 把真实执行建立在进一步元数据可用之后

### 当用户任务在 ELB / EVS / NAT / RDS / CCE / CDN / DNS / SCM / CES 范围内

当前只把 registry 当作查询线索：

- 先确认本地 `hcloud <service> --help` 是否能拿到 operation 帮助
- 优先执行 list/count 类低风险查询
- 涉及创建、绑定、扩容、停用、删除、证书部署、集群变更等动作时，先补专门 planner 和验证器

不要伪装成已经有了和 ECS 一样完整的操作细节。
