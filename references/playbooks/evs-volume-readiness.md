# EVS Volume Readiness Playbook

## 目标

确认云硬盘创建、挂载或扩容后的云侧状态，并区分云侧挂载成功和 ECS 内文件系统可用。

## 适用场景

- 创建 EVS 云硬盘
- 挂载到 ECS
- 扩容或变更磁盘类型
- 创建、查询或删除快照

## 标准检查

1. 查询 EVS 列表入口：

```bash
python3 scripts/hcloud_resource_discovery.py \
  --service EVS \
  --operation ListVolumes \
  --region=<region> \
  --project-id=<project-id> \
  --limit=20 \
  --pretty
```

2. 对云硬盘 JSON 结果做云侧验收：

```bash
python3 scripts/hcloud_resource_verify.py \
  --service EVS \
  --json-file=<safe-exec-result.json> \
  --target-id=<volume-id> \
  --expect-status IN-USE \
  --expect-bound-to=<server-id> \
  --require-match \
  --pretty
```

## 验收字段

- Volume ID
- 名称
- `status`
- 容量和类型
- 可用区
- attachment 中的 ECS ID / device

## ECS 内部验收

如果用户目标包括“格式化为 ext4 并挂载到 `/data`”，云侧 `in-use` 仍不等于任务完成。还必须通过 SSH、远程命令或等价通道验证：

- `lsblk` 能看到目标设备
- 文件系统类型符合预期
- `df -h` 能看到挂载点
- 写入测试文件成功

没有 ECS 内部执行能力时，只能声明“云硬盘已挂载到云侧目标”，不能声明“文件系统已经可用”。

## 最终输出

成功时给出 volume ID、状态、容量、挂载目标和 ECS 内部验收结果。失败时明确停在云侧挂载、系统识别、格式化还是挂载点阶段。
