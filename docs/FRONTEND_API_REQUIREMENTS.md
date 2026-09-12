# Frontend API Requirements

本文档描述当前 Vue 前端五个页面所依赖的 HTTP API Contract。它以 `frontend/src/types/index.ts` 和 `frontend/src/api/` 的现状为准，不代表后端已经实现这些业务能力。

## 1. 接入约定

- API Base URL 由 `VITE_API_BASE_URL` 控制，默认值为 `/api`。
- Vite 开发环境会把 `/api/*` 代理到 `http://127.0.0.1:8000/*`，并移除 `/api` 前缀。因此下文的后端实际路径均以 `/` 开头，不包含 `/api`。
- `VITE_USE_MOCK_API=true` 时，Stream、Event、Evidence、Search、Highlights、Investigate 由 `src/mock` 提供；设为 `false` 时，相同的 `src/api` 方法改为请求真实后端。
- `/health` 始终请求真实 FastAPI，不受 Mock 开关影响。
- 请求与响应使用 `application/json; charset=utf-8`。
- JSON 字段使用前端当前采用的 camelCase。后端若内部使用 snake_case，需要通过 Pydantic alias 或序列化层输出本文档中的字段名。
- `liveTime` 使用带时区的 ISO 8601 字符串，例如 `2026-08-28T21:05:00+08:00`。
- `startMs`、`endMs`、`timestampMs`、`durationMs` 均为从直播开始计算的毫秒数；`durationMs` 也用于整场直播时长。
- `confidence` 与 `score` 的范围为 `0` 到 `1`。
- 失败响应可以沿用 FastAPI 默认格式：`{"detail": "error message"}`。资源不存在时返回 `404`，请求参数无效时返回 `422`。

## 2. 当前实现状态

| Method | Path | 页面/用途 | 后端现状 |
| --- | --- | --- | --- |
| `GET` | `/health` | 全局服务状态 | 已实现 |
| `GET` | `/streams` | Archive 列表与筛选 | 未实现，当前 Mock |
| `GET` | `/streams/{streamId}` | Timeline 直播基础信息 | 未实现，当前 Mock |
| `GET` | `/streams/{streamId}/events` | Timeline Event 列表 | 未实现，当前 Mock |
| `GET` | `/events/{eventId}/evidence` | Timeline/Event Evidence | 未实现，当前 Mock |
| `GET` | `/events/search` | Search 历史事件检索 | 未实现，当前 Mock |
| `GET` | `/highlights` | Highlights 候选列表 | 未实现，当前 Mock |
| `POST` | `/investigate` | Investigate 调查结果 | 未实现，当前 Mock |

后端另外已有 `GET /debug/data-root`，但当前前端不依赖该调试接口，因此不属于页面 Contract。

## 3. 公共 JSON Shape

### Stream

```json
{
  "id": "stream-001",
  "title": "深夜杂谈｜聊聊新衣装准备和最近看的电影",
  "liveTime": "2026-08-28T21:05:00+08:00",
  "bvIds": ["BV1AR4y1N7xQ", "BV1w7HYziExt"],
  "hasDanmaku": true,
  "hasEvents": true,
  "durationMs": 8460000
}
```

| 字段 | 类型 | 必需 | 说明 | 当前数据来源 |
| --- | --- | --- | --- | --- |
| `id` | `string` | 是 | Stream 稳定唯一 ID，供路由和关联使用 | Mock |
| `title` | `string` | 是 | 直播标题 | Mock |
| `liveTime` | `string` | 是 | 带时区 ISO 8601 开播时间 | Mock |
| `bvIds` | `string[]` | 是 | 关联的 Bilibili BV 号列表 | Mock |
| `hasDanmaku` | `boolean` | 是 | 是否已导入弹幕 | Mock |
| `hasEvents` | `boolean` | 是 | 是否已有 Event 结果 | Mock |
| `durationMs` | `number` | 否 | 直播总时长；缺失时 Timeline 会退化为最后一个 Event 的结束时间 | Mock |

一场 Stream 可能关联多个 Bilibili BV 号。`bvIds` 始终使用数组表示，不使用分隔符拼接字符串。

### Event

```json
{
  "id": "event-001",
  "streamId": "stream-001",
  "startMs": 735000,
  "endMs": 1026000,
  "title": "第一次提到新衣装的准备进度",
  "summary": "回应弹幕提问，说明新衣装仍在调整细节。",
  "eventType": "announcement",
  "confidence": 0.93
}
```

`eventType` 当前允许：`talk | gameplay | reaction | announcement | collab`。Event 的全部字段目前均来自 Mock；其中 `summary`、`eventType`、`confidence` 最终应由事件处理流程生成。

### Evidence

```json
{
  "id": "evidence-001",
  "eventId": "event-001",
  "level": "E1_AUDIENCE_REACTION",
  "source": "弹幕高频片段",
  "content": "“新衣装”在 45 秒窗口内出现 37 次。",
  "timestampMs": 756000
}
```

`level` 当前允许：

- `E0_METADATA`：直播标题、时间、BV 号等结构化元数据；不能单独证明具体发言。
- `E1_AUDIENCE_REACTION`：弹幕密度、关键词与观众情绪反应；只说明观众侧信号。
- `E2_EVENT_INFERENCE`：基于元数据、弹幕或上下文得到的事件推断；不是主播原话。
- `E3_ASR_SUBTITLE`：由 ASR 或字幕得到的文本证据。
- `E4_VIDEO_VLM`：由视频画面或视觉模型得到的证据。
- `E5_HUMAN_VERIFIED`：经过人工回看核验的证据。

Evidence 的全部字段目前均来自 Mock。当前 V0 Mock 只包含符合已有元数据与弹幕来源的 `E0_METADATA`、`E1_AUDIENCE_REACTION`、`E2_EVENT_INFERENCE`；没有伪造 ASR、视频理解或人工核验结果。

### HighlightCandidate

```json
{
  "event": {
    "id": "event-004",
    "streamId": "stream-002",
    "startMs": 1944000,
    "endMs": 2180000,
    "title": "第一个高能追逐段落",
    "summary": "遭遇追逐事件，弹幕密度显著上升。",
    "eventType": "reaction",
    "confidence": 0.96
  },
  "score": 0.96,
  "reason": "全场最高弹幕密度峰值，情绪反应集中，片段边界清晰。",
  "reviewStatus": "pending"
}
```

`reviewStatus` 当前允许：`pending | approved | rejected`。当前审核按钮只修改页面本地状态，没有写回 API；`score`、`reason`、`reviewStatus` 目前均为 Mock。

## 4. Endpoint Contract

### 4.1 健康检查

**Method / Path**

```text
GET /health
```

**Request**

无参数、无 Body。

**Response `200`**

```json
{
  "status": "ok"
}
```

**当前实现**

已在 `backend/app/main.py` 实现，并由 App 侧栏真实调用。

---

### 4.2 获取直播档案列表

**Method / Path**

```text
GET /streams
```

**Query Params**

| 参数 | 类型 | 必需 | 说明 |
| --- | --- | --- | --- |
| `query` | `string` | 否 | 匹配直播标题或任一 BV 号 |
| `status` | `danmaku | events | pending` | 否 | `danmaku`=已有弹幕；`events`=已有 Event；`pending`=尚无 Event。选择“全部”时前端不发送该参数 |

**Response `200`**

```json
[
  {
    "id": "stream-001",
    "title": "深夜杂谈｜聊聊新衣装准备和最近看的电影",
    "liveTime": "2026-08-28T21:05:00+08:00",
    "bvIds": ["BV1AR4y1N7xQ", "BV1w7HYziExt"],
    "hasDanmaku": true,
    "hasEvents": true,
    "durationMs": 8460000
  }
]
```

**当前实现**

未实现。列表、筛选结果和所有字段当前均为 Mock。

---

### 4.3 获取单场直播

**Method / Path**

```text
GET /streams/{streamId}
```

**Path Params**

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `streamId` | `string` | Stream 唯一 ID |

**Response `200`**

单个 `Stream` JSON 对象，Shape 见 3.1。

**Response `404`**

```json
{
  "detail": "Stream not found"
}
```

**当前实现**

未实现。Timeline 的直播基础信息当前来自 Mock。

---

### 4.4 获取单场直播的 Event

**Method / Path**

```text
GET /streams/{streamId}/events
```

**Path Params**

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `streamId` | `string` | Stream 唯一 ID |

**Response `200`**

按 `startMs` 升序返回：

```json
[
  {
    "id": "event-001",
    "streamId": "stream-001",
    "startMs": 735000,
    "endMs": 1026000,
    "title": "第一次提到新衣装的准备进度",
    "summary": "回应弹幕提问，说明新衣装仍在调整细节。",
    "eventType": "announcement",
    "confidence": 0.93
  }
]
```

没有 Event 时返回空数组 `[]`，而不是 `404`。

**当前实现**

未实现。Event 列表及其全部字段当前均为 Mock。

---

### 4.5 获取 Event Evidence

**Method / Path**

```text
GET /events/{eventId}/evidence
```

**Path Params**

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `eventId` | `string` | Event 唯一 ID |

**Response `200`**

```json
[
  {
    "id": "evidence-001",
    "eventId": "event-001",
    "level": "E1_AUDIENCE_REACTION",
    "source": "弹幕高频片段",
    "content": "“新衣装”在 45 秒窗口内出现 37 次。",
    "timestampMs": 756000
  }
]
```

没有关联 Evidence 时返回空数组 `[]`。

**当前实现**

未实现。Evidence 及其全部字段当前均为 Mock。

---

### 4.6 搜索历史 Event

**Method / Path**

```text
GET /events/search
```

**Query Params**

| 参数 | 类型 | 必需 | 说明 |
| --- | --- | --- | --- |
| `query` | `string` | 否 | 人物、话题或事件关键词；空搜索允许返回默认结果 |
| `from` | `string` | 否 | 起始日期，`YYYY-MM-DD`，包含当天 |
| `to` | `string` | 否 | 结束日期，`YYYY-MM-DD`，包含当天 |
| `person` | `string` | 否 | 人物筛选标识；当前 UI 只有占位选项，“全部”时不发送 |
| `topic` | `string` | 否 | 话题筛选标识；“全部”时不发送 |

**Response `200`**

```json
[
  {
    "event": {
      "id": "event-001",
      "streamId": "stream-001",
      "startMs": 735000,
      "endMs": 1026000,
      "title": "第一次提到新衣装的准备进度",
      "summary": "回应弹幕提问，说明新衣装仍在调整细节。",
      "eventType": "announcement",
      "confidence": 0.93
    },
    "stream": {
      "id": "stream-001",
      "title": "深夜杂谈｜聊聊新衣装准备和最近看的电影",
      "liveTime": "2026-08-28T21:05:00+08:00",
      "bvIds": ["BV1AR4y1N7xQ", "BV1w7HYziExt"],
      "hasDanmaku": true,
      "hasEvents": true,
      "durationMs": 8460000
    },
    "matchedText": "回应弹幕提问，说明新衣装仍在调整细节。"
  }
]
```

`matchedText` 可选，用于返回命中的摘要或高亮上下文；当前前端直接显示纯文本，不要求 HTML 高亮。

**当前实现**

未实现。搜索结果当前来自 Mock。Mock 已处理关键词、日期与简单话题包含匹配；`person` 目前只是 UI 占位，没有实际过滤逻辑。

---

### 4.7 获取高光候选

**Method / Path**

```text
GET /highlights
```

**Request**

当前无 Query Params、无 Body。

**Response `200`**

```json
[
  {
    "event": {
      "id": "event-004",
      "streamId": "stream-002",
      "startMs": 1944000,
      "endMs": 2180000,
      "title": "第一个高能追逐段落",
      "summary": "遭遇追逐事件，弹幕密度显著上升。",
      "eventType": "reaction",
      "confidence": 0.96
    },
    "score": 0.96,
    "reason": "全场最高弹幕密度峰值，情绪反应集中，片段边界清晰。",
    "reviewStatus": "pending"
  }
]
```

建议按 `score` 降序返回。

**当前实现**

未实现。候选 Event、`score`、`reason`、`reviewStatus` 当前均为 Mock。审核操作只修改前端内存状态，本轮没有要求审核写回接口。

---

### 4.8 发起档案调查

**Method / Path**

```text
POST /investigate
```

**Request Body**

```json
{
  "query": "新衣装准备期间提到过哪些确定的信息？"
}
```

| 字段 | 类型 | 必需 | 说明 |
| --- | --- | --- | --- |
| `query` | `string` | 是 | 非空自然语言调查问题 |

**Response `200`**

```json
{
  "query": "新衣装准备期间提到过哪些确定的信息？",
  "trace": [
    {
      "id": "trace-1",
      "label": "正在搜索相关直播",
      "detail": "标题、时间范围与档案元数据",
      "status": "done"
    }
  ],
  "candidates": [
    {
      "event": {
        "id": "event-001",
        "streamId": "stream-001",
        "startMs": 735000,
        "endMs": 1026000,
        "title": "第一次提到新衣装的准备进度",
        "summary": "回应弹幕提问，说明新衣装仍在调整细节。",
        "eventType": "announcement",
        "confidence": 0.93
      },
      "stream": {
        "id": "stream-001",
        "title": "深夜杂谈｜聊聊新衣装准备和最近看的电影",
        "liveTime": "2026-08-28T21:05:00+08:00",
        "bvIds": ["BV1AR4y1N7xQ", "BV1w7HYziExt"],
        "hasDanmaku": true,
        "hasEvents": true,
        "durationMs": 8460000
      },
      "evidence": [
        {
          "id": "evidence-001",
          "eventId": "event-001",
          "level": "E1_AUDIENCE_REACTION",
          "source": "弹幕高频片段",
          "content": "“新衣装”在 45 秒窗口内出现 37 次。",
          "timestampMs": 756000
        }
      ],
      "confidence": 0.93
    }
  ]
}
```

`trace[].status` 当前允许：`done | active | pending`。当前前端使用单次 JSON 响应，不要求 SSE/WebSocket 流式接口；请求等待期间的逐步 Trace 动效由前端本地状态模拟。

**当前实现**

未实现。Trace、候选 Event、Evidence 和候选 `confidence` 当前均为 Mock。

## 5. 页面到 API 的依赖关系

| 页面 | API |
| --- | --- |
| Archive | `GET /streams` |
| Timeline | `GET /streams/{streamId}`、`GET /streams/{streamId}/events`、`GET /events/{eventId}/evidence` |
| Search | `GET /events/search` |
| Highlights | `GET /highlights` |
| Investigate | `POST /investigate` |
| 全局侧栏 | `GET /health` |

当前 Timeline 的“弹幕相对强度”曲线是前端根据直播时长和 Event 位置生成的视觉占位数据，不属于任何现有 TypeScript 接口。后端若未来提供真实密度序列，应另行扩展类型与 Contract，本轮不预设额外接口。

## 6. Mock 切换检查

当前页面和组件不直接引用 `src/mock`：

- View 只调用 `src/api` 或 Pinia Store。
- Archive Store 只调用 `src/api/streams.ts`。
- 只有 `src/api/*.ts` 会根据 `VITE_USE_MOCK_API` 选择 Mock Adapter 或真实 HTTP 请求。
- Highlights 的审核结果和 Investigate 请求期间的 Trace 进度属于页面临时 UI 状态，不是数据源旁路。

真实后端接口就绪后，将环境变量设为以下值即可切换业务请求：

```dotenv
VITE_API_BASE_URL=/api
VITE_USE_MOCK_API=false
```
