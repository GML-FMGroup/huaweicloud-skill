# OBS Boundary Note

## 当前边界

`data-by-changping/data.xlsx` 的人工 E2E 数据里包含 OBS 桶和生命周期规则任务，但当前本机 KooCLI metadata 没有发现 `OBS` service。

## 处理原则

- 不要假装 `hcloud OBS` 路线已经可用。
- 如果用户明确要求 OBS，先确认可用工具链：KooCLI 是否支持该服务、是否应切换到 `obsutil`、SDK 或对象存储专用接口。
- 在工具链确认前，只能输出验证需求和参数清单，不直接生成不可验证的 hcloud 命令。

## 需要确认的能力

- bucket list / get metadata
- lifecycle get / put
- ACL / policy get
- storage class
- region / endpoint

## 后续 TODO

确认 OBS 工具路线后，再补：

- OBS discovery script
- OBS lifecycle planner
- OBS verifier
- 对应离线数据集覆盖项
