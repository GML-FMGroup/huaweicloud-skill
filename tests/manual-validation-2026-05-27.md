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
