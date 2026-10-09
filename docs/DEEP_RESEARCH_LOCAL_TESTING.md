# DeepResearch 本地联调

## 边界

- `POST /investigate/research` 默认关闭；必须显式启用，并且请求客户端必须是 loopback（127.0.0.1 / ::1）。
- 这是开发入口，不是生产鉴权。不要把它通过公网反向代理、隧道或共享 Vite 开发服务器暴露出去。
- 复用 `EVENT_SCOUT_*` 模型配置。数据库连接使用 SQLite `mode=ro`，不会写入或创建数据库。
- 旧 EventScout 不变；前端 Investigate 不再调用旧 `/investigate`，也不使用 Mock / 模拟 Trace。

## 启动真实模型联调

1. 在本机 `backend/.env` 中保留已有档案配置，配置下面这些字段（不要提交 API key）：

```dotenv
DEEP_RESEARCH_DEV_ENABLED=true
EVENT_SCOUT_API_BASE_URL=<OpenAI-compatible 服务的 /v1 地址>
EVENT_SCOUT_MODEL=<模型名称>
EVENT_SCOUT_API_KEY=<本机凭据，如服务不需要则留空>
EVENT_SCOUT_TIMEOUT_SECONDS=60
```

2. 后端终端：

```powershell
Set-Location D:\myProjects\VtbArchiveAgent\backend
conda activate vtuber-archive
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

3. 另一个终端启动前端，保持使用真实 API（不要开启 Mock）：

```powershell
Set-Location D:\myProjects\VtbArchiveAgent\frontend
npm run dev -- --host 127.0.0.1
```

4. 通过 GET /vtubers 选择已有主播，不使用硬编码名单：

```powershell
$vtubers = Invoke-RestMethod http://127.0.0.1:8000/vtubers
$vtubers | Format-Table id, displayName
$vtuberId = Read-Host '输入上面已有的主播 id'
$body = @{ vtuberId = $vtuberId; query = '主播有没有提到车祸？' } | ConvertTo-Json
$report = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/investigate/research -ContentType 'application/json; charset=utf-8' -Body ([System.Text.Encoding]::UTF8.GetBytes($body)) -TimeoutSec 300
$report | ConvertTo-Json -Depth 12
```

也可打开 http://127.0.0.1:5173，选择主播 → Investigate → 输入完整问题 → 开始调查。预期显示 answer、findings、原文 citations、位置和 limitations。没有证据也应返回完整的空报告，不应编造答案。

正常研究使用 Planner 和 Report 各一次模型请求。每阶段仅针对可恢复的格式错误额外重试一次，因此最多四次串行请求；默认单次超时 60 秒。网络失败、超时、模型拒绝、规划语义错误及 Citation Guard 失败不自动重试。若提高后端超时，请相应提高手动请求的 TimeoutSec。浏览器离开页面会丢弃未完成的结果，但不会强制取消服务端已开始的同步模型调用。

结构化输出失败时，后端 logger app.investigation.deep_research 记录 stage、attempt、error_type 和脱敏字段路径/校验类型，不记录原始响应、证据内容或凭据。未知额外字段名显示为 &lt;extra&gt;。HTTP 错误只返回阶段、错误类型和尝试次数，不携带模型原文。

output_truncated 仅在服务返回 finish_reason=length 时确认；服务未提供该元数据时，不根据不完整 JSON 猜测截断原因。超过本地字符预算另报 response_too_large。

当前请求仍以 prompt 中的严格 JSON Schema 为约束，未默认发送 response_format 等供应商参数。客户端已有 extra_body 显式扩展能力，但本轮没有改动实际模型配置，也未验证 Kimi 的 JSON mode / JSON Schema 支持；需根据具体服务和模型版本确认后再单独启用。新增的 include_finish_reason 仅控制本地返回元数据，不发送给模型供应商，旧 EventScout 默认行为不变。

## 验收

- 报告返回 camelCase，`vtuberId` 与当前主播一致；没有旧 `trace` / `candidates`。
- 点击证据位置进入现有 `/v/:vtuberId/streams/:streamId?atMs=...`，`atMs` 是整场毫秒。
- Timeline 展开覆盖该时间的片段；没有覆盖片段时显示真实目标时间及空提示，不生成假节点。原 Bilibili 空降逻辑不变。
- 字幕保留 Part-local 和 Stream-global 时间；弹幕标为观众反应；Topic 标为已有归档解释，其单一 Part-local 范围允许为空。
- 切换主播或离开 Investigate 后，旧请求不能把结果写入新主播页面。
- Highlights 全局导航隐藏；旧页面链接返回主播档案；`GET /streams/{stream_id}/highlights` 保留。

## 错误契约

| 状态 | detail.code | 含义 |
| --- | --- | --- |
| 404 | research_disabled | 开发开关关闭 |
| 403 | research_local_only | 非本机请求 |
| 422 | FastAPI validation detail 数组 | 缺少 vtuberId/query、空白或超长问题、额外字段等 |
| 404 | vtuber_not_found | 主播不存在 |
| 503 | model_not_configured / archive_unavailable | 本地模型或档案配置不可用 |
| 502 | research_failed | 规划失败、模型失败或非法结构化 JSON |
| 502 | citation_validation_failed | 引用或来源校验失败，不返回部分报告 |
| 504 | model_timeout | 模型超时 |

测试完成后将 `DEEP_RESEARCH_DEV_ENABLED=false` 并重启后端。关闭状态不应触发模型请求。

## 自动化检查

```powershell
Set-Location D:\myProjects\VtbArchiveAgent\backend
$testTemp = Join-Path $env:TEMP ('vtb-research-' + [guid]::NewGuid().ToString('N'))
python -m pytest -q tests -p no:cacheprovider --basetemp $testTemp
Set-Location ..\frontend
npm run build
```

Fake Model 合约测试使用独立数据库，真实执行 DeepResearch 与 Citation Guard，不访问模型服务。真实模型联调可能产生费用；自动化测试通过不代表已验证实际供应商的模型输出质量。
