# huaweicloud-skill Manual Validation 2026-05-27

本文件记录多服务只读 smoke、planner-only 计划和资源 verifier 的实际验证结果。

## 环境前提

- `hcloud` 可执行，KooCLI version 7.2.2。
- 当前 profile：`default`。
- 当前 region：`cn-north-4`。
- 本次验证只执行查询，不创建、修改、绑定、解绑或删除云资源。

## 验证 1：多服务只读 smoke

### Command shape

```bash
python3 scripts/hcloud_readonly_smoke.py \
  --service EIP \
  --service VPC \
  --service IMS \
  --service KPS \
  --region=cn-north-4 \
  --project-id=<project-id> \
  --execute \
  --pretty
```

### Result

- `EIP ListPublicips` 成功，返回 1 个 EIP。
- `VPC ListVpcs` 成功，返回 1 个 VPC。
- `IMS ListImages` 成功，返回镜像列表。
- `KPS ListKeypairs` 成功，返回 5 个 keypair。

### Notes

- 普通沙箱网络下曾出现 DNS 解析失败；联网授权后成功。
- KPS 返回包含 public key，这是公钥信息，不应当按私钥处理，但最终回复仍不需要展开。

## 验证 2：低覆盖服务只读 smoke

### Command shape

```bash
python3 scripts/hcloud_readonly_smoke.py \
  --service ELB \
  --service EVS \
  --service RDS \
  --service NAT \
  --region=cn-north-4 \
  --project-id=<project-id> \
  --execute \
  --pretty
```

### Result

- `ELB ListLoadbalancers` 成功，返回 1 个 ELB，状态为 `ACTIVE` / `ONLINE`。
- `EVS ListVolumes` 成功，返回 0 个云硬盘。
- `RDS ListInstances` 成功，返回 1 个 RDS 实例，状态为 `ACTIVE`。
- `NAT ListNatGateways` 成功，返回 0 个 NAT gateway。

### Notes

- 并发请求时 VPC/ELB 出现过 TLS handshake timeout；顺序重试成功。
- 这说明低覆盖服务可以做只读查询，但仍不等于已经具备完整变更执行能力。

## 验证 3：扩展低覆盖服务只读 smoke

### Command shape

```bash
python3 scripts/hcloud_readonly_smoke.py \
  --service CCE \
  --service CDN \
  --service DNS \
  --service SCM \
  --service CES \
  --region=cn-north-4 \
  --project-id=<project-id> \
  --execute \
  --pretty
```

### Result

- `CCE ListClusters` 成功，返回 0 个 cluster。
- `DNS ListRecordSets` 成功，返回 6 条 record set。
- `SCM ListCertificates` 成功。
- `CES ListMetrics` 成功，返回指标列表。
- `CDN ListDomains` 初次使用 `cn-north-4` 时失败，错误提示 KooCLI 仅支持 `cn-north-1` 和 `ap-southeast-1`。

### Follow-up Fix

已在 registry 中为 CDN 增加 `supported_cli_regions` 和 `preferred_cli_region`。修复后再次执行：

```bash
python3 scripts/hcloud_readonly_smoke.py \
  --service CDN \
  --region=cn-north-4 \
  --project-id=<project-id> \
  --execute \
  --strict \
  --pretty
```

结果成功，计划中的命令实际使用 `--cli-region=cn-north-1`，`ListDomains` 返回 `total=0`。

## 验证 4：资源 verifier

### Command shape

```bash
python3 scripts/hcloud_resource_verify.py \
  --service EIP \
  --json-file=<parsed-json-file> \
  --target-id=<eip-id> \
  --expect-status ACTIVE \
  --expect-bound-to=<elb-id> \
  --require-match \
  --pretty
```

```bash
python3 scripts/hcloud_resource_verify.py \
  --service VPC \
  --json-file=<parsed-json-file> \
  --target-id=<vpc-id> \
  --expect-status ACTIVE \
  --expect-cidr 192.168.0.0/16 \
  --require-match \
  --pretty
```

```bash
python3 scripts/hcloud_resource_verify.py \
  --service ELB \
  --json-file=<parsed-json-file> \
  --target-id=<elb-id> \
  --expect-status ACTIVE \
  --expect-field operating_status=ONLINE \
  --require-match \
  --pretty
```

```bash
python3 scripts/hcloud_resource_verify.py \
  --service RDS \
  --json-file=<parsed-json-file> \
  --target-name=<rds-name> \
  --expect-status ACTIVE \
  --require-match \
  --pretty
```

### Result

- EIP verifier 成功，确认 EIP 为 `ACTIVE` 且绑定到目标 ELB。
- VPC verifier 成功，确认目标 VPC 为 `ACTIVE` 且 CIDR 符合预期。
- ELB verifier 成功，确认目标 ELB 为 `ACTIVE` 且 `operating_status=ONLINE`。
- RDS verifier 成功，确认目标 RDS 实例为 `ACTIVE`。

## 验证 5：planner-only 变更计划

### Command shape

```bash
python3 scripts/hcloud_service_change_plan.py \
  --service EIP \
  --operation CreatePublicip \
  --region=cn-north-4 \
  --project-id=<project-id> \
  --pretty
```

### Result

- 成功生成 `planning_only=true` 的变更计划。
- 风险等级为 `medium`。
- dry-run 命令包含 `--dryrun`。
- submit 命令只作为计划输出，不能在没有单独确认的情况下执行。

## 验证 6：data.xlsx 执行路径门禁

### Command shape

```bash
python3 scripts/check_question_coverage.py --pretty
```

### Result

- `generated_questions` 共检查 26 个 JSON 文件，448 个唯一 operation。
- `data.xlsx` 共解析 38 条人工 E2E 记录。
- workbook 中的普通列表查询映射到 `scripts/hcloud_resource_discovery.py`。
- workbook 中的目标型只读查询映射到 `scripts/hcloud_resource_query.py`，包括 CCE `ShowCluster/ListNodes`、CDN `ShowDomain`、EIP `ShowPublicip`、ELB `ListMembers`、RDS `ShowConfiguration`。
- `execution_path_error_count=0`。
- workbook 原始记录里的 RDS `ShowConfigurationDetail` 已映射到 KooCLI 实际可执行操作 `ShowConfiguration`。
- OBS 仍作为未注册服务记录在 `unregistered_services` 中，没有被当作当前门禁失败。

## 验证 7：service readiness 与资源级只读查询

### Command shape

```bash
python3 scripts/hcloud_service_readiness.py \
  --service VPC \
  --service EIP \
  --service RDS \
  --service ELB \
  --region=cn-north-4 \
  --project-id=<project-id> \
  --execute \
  --pretty
```

```bash
python3 scripts/hcloud_resource_query.py \
  --service EIP \
  --operation ShowPublicip \
  --param publicip_id=<publicip-id> \
  --region=cn-north-4 \
  --project-id=<project-id> \
  --execute \
  --pretty
```

```bash
python3 scripts/hcloud_resource_query.py \
  --service ELB \
  --operation ListMembers \
  --param pool_id=<pool-id> \
  --region=cn-north-4 \
  --project-id=<project-id> \
  --execute \
  --pretty
```

```bash
python3 scripts/hcloud_resource_query.py \
  --service RDS \
  --operation ShowConfigurationDetail \
  --param config_id=<config-id> \
  --region=cn-north-4 \
  --project-id=<project-id> \
  --execute \
  --pretty
```

### Result

- VPC/EIP/RDS/ELB readiness 成功执行；缺少显式目标 ID 的详情类检查被标记为 skipped，没有猜测参数。
- 资源级查询成功执行：
  - EIP `ShowPublicip` 返回 1 个目标资源。
  - ELB `ListMembers` 返回 2 个成员资源。
  - RDS `ShowConfigurationDetail` 通过别名映射执行 `ShowConfiguration`，返回 1 个参数模板对象。
- 扩展 readiness 对 EVS/NAT/CCE/CDN/DNS/SCM/CES 执行成功：
  - EVS/NAT/CCE/CDN/SCM 查询成功，当前账号/区域下部分服务返回 0 个资源。
  - DNS 返回 2 个 public zone 和 6 条 record set。
  - CES `ListMetrics` 返回 644 个 metric。

## 验证 8：高频服务广度优先扩展

### Command shape

```bash
python3 scripts/hcloud_service_readiness.py \
  --service ECS \
  --service IMS \
  --service KPS \
  --service IAM \
  --region=cn-north-4 \
  --execute \
  --pretty
```

另用摘要脚本顺序执行以下只读链路：先 list，再在存在资源时执行对应 detail 查询：

- VPC `ListVpcs` -> `ShowVpc`
- ELB `ListLoadbalancers` -> `ShowLoadBalancer`
- EVS `ListVolumes` -> `ShowVolume`
- NAT `ListNatGateways` -> `ShowNatGateway`
- IMS `ListImages` -> `GlanceShowImage`
- KPS `ListKeypairs` -> `ListKeypairDetail`

### Result

- ECS/IMS/KPS/IAM readiness 成功执行；ECS `ShowServer`、IMS `GlanceShowImage`、KPS `ListKeypairDetail` 因未传目标 ID 在 readiness 中安全 skipped。
- VPC list+detail 成功，当前区域发现 1 个 VPC 并成功执行 `ShowVpc`。
- ELB list+detail 成功，当前区域发现 1 个 ELB 并成功执行 `ShowLoadBalancer`。
- EVS `ListVolumes` 成功，当前区域 0 个 volume，因此未执行 `ShowVolume`。
- NAT `ListNatGateways` 成功，当前区域 0 个 NAT gateway，因此未执行 `ShowNatGateway`。
- IMS list+detail 成功，抽样镜像可执行 `GlanceShowImage`。
- KPS list+detail 成功，抽样 keypair 可执行 `ListKeypairDetail`。
- 小写 operation 计划验证通过：`listcloudservers` -> `ListCloudServers`，`showvpc` -> `ShowVpc`，`shownatgatewaydnatrule` -> `ShowNatGatewayDnatRule`。

### Notes

- 本验证只执行只读查询，不创建、修改、绑定、解绑或删除资源。
- 摘要脚本只输出成功状态和资源数量，不展开资源 ID、公钥、project ID 等明细。

## 验证 9：OBS 与 EVS/NAT detail probe

### Command shape

```bash
python3 scripts/hcloud_obs_readonly.py \
  --operation ListBuckets \
  --limit=20 \
  --execute \
  --pretty
```

```bash
python3 scripts/hcloud_obs_change_plan.py \
  --operation PutBucketLifecycle \
  --bucket=<bucket-name> \
  --local-file=<lifecycle-json-file> \
  --pretty
```

```bash
python3 scripts/hcloud_resource_detail_probe.py \
  --service EVS \
  --service NAT \
  --region=cn-north-4 \
  --execute \
  --pretty
```

### Result

- OBS `ListBuckets` 命令形态正确，实际执行到 `hcloud obs ls -limit=20`，但当前 obsutil 配置返回 `403 InvalidAccessKeyId`。
- `hcloud_obs_readonly.py` 已把该失败归类到 summary：`obs_status=403`、`obs_error_code=InvalidAccessKeyId`，并提示检查 `hcloud obs config`、OBS endpoint 和 obsutil AK/SK/token。
- OBS `PutBucketLifecycle` 只生成 planner-only submit 命令和 `GetBucketLifecycle` 后置验证计划，没有执行真实变更。
- EVS/NAT detail probe 成功执行 list 阶段；当前 `cn-north-4` 下 EVS volume 和 NAT gateway 都为 0，因此 detail 阶段按设计 skipped。

### Notes

- OBS 不走普通 `hcloud OBS <Operation>`；必须走 `hcloud obs`/obsutil 专用 adapter。
- EVS/NAT detail 能力已工具化，后续账号/区域出现资源时会自动执行 detail 查询。
  - CCE `ShowCluster/ListNodes` 和 CDN `ShowDomain` 因缺少目标 ID 被正确跳过。

### Retest After OBS Credential Configuration

用户重新配置 obsutil AK/SK 后，重新执行以下只读验证：

```bash
python3 scripts/hcloud_obs_readonly.py \
  --operation ListBuckets \
  --limit=20 \
  --execute \
  --pretty
```

```bash
python3 scripts/hcloud_obs_readonly.py \
  --operation StatBucket \
  --bucket=<bucket-name> \
  --execute \
  --pretty
```

结果：

- OBS `ListBuckets` 成功，summary 中 `bucket_count=1`。
- OBS `StatBucket` 成功，确认 bucket-scoped 只读路径也可执行。
- 该结果说明此前 `InvalidAccessKeyId` 是 OBS obsutil 配置问题，不是 `hcloud obs` 命令形态或 adapter 问题。

### Follow-up Fix

- readiness 的非 strict 执行模式现在只放过云端执行失败，不再掩盖 plan 阶段失败。
- RDS workbook 别名 `ShowConfigurationDetail` 映射到 KooCLI 实际操作 `ShowConfiguration`。
- RDS 参数模板详情响应是顶层对象，resource verifier 已支持这种响应形态。

## 验证 10：普通 hcloud 错误诊断与 EIP 变更闭环

### Command shape

```bash
python3 scripts/hcloud_safe_exec.py \
  --command-part=not-a-real-hcloud-command \
  --pretty
```

```bash
python3 scripts/hcloud_eip_change_flow.py \
  --operation UpdatePublicip \
  --publicip-id=<publicip-id> \
  --arg=--publicip_id=<publicip-id> \
  --region=cn-north-4 \
  --project-id=<project-id> \
  --pretty
```

```bash
python3 scripts/hcloud_eip_change_flow.py \
  --operation UpdatePublicip \
  --publicip-id=<publicip-id> \
  --arg=--publicip_id=<publicip-id> \
  --region=cn-north-4 \
  --project-id=<project-id> \
  --execute-submit \
  --pretty
```

### Result

- `hcloud_safe_exec.py` 失败结果现在包含 `error_details`，可把常见错误归类到 credential、permission、region_or_endpoint、project、quota、parameter、not_found、network 等。
- 本地 sandbox 中的无效 hcloud 命令返回 `APIE_ERROR`，并根据 `no such host` 进一步诊断为 `network`，给出网络/DNS/代理排查建议。
- EIP flow 默认只生成 service change plan 和 `ShowPublicip` 验证计划，不执行真实 submit。
- 未带 `--confirm-submit` 时，即使传入 `--execute-submit`，脚本也返回 `submit_guard_failure`，没有执行真实变更。

### Notes

- 本验证没有创建、修改、绑定、解绑或删除任何 EIP。
- 真实 EIP submit 仍需用户对具体 EIP、region、project、计费/网络影响、回滚方式和 dry-run 结果逐项确认。
