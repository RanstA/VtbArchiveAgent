# V0 Benchmark

# 项目定位

直播档案考古与高光发现 Agent。

把巨量录播转换为：`Stream → Event → Evidence`并支持四类需求：

- 岁月史书：定位主播是否聊过某件事

- 切片助手：发现可能值得回看的高光

- 名场面事件簿：按人物 / 话题 / 时间检索历史事件

- 回坑速通：快速了解某段时间发生了什么

# V0效果

从录播列表以及弹幕文件中：

- Event Detection

- Event Store

- Event Retrieval

- LangGraph Investigation

- Timeline / Search / Highlights

仅靠元数据 \+ 弹幕，可以有效发现直播事件和高光候选；

Agent 可以基于 Event Store 完成多步检索、上下文展开和证据说明。

# V0功能划分

## 档案导入

CSV 直播元数据

ASS 带时间戳的弹幕

## 事件检测

基于：弹幕密度、反应、人名 / 关键词集中、语义集中、话题及情绪感知，完成候选、Merge / Split以及最终事件输出

## Event Store \& Retrieval

SQLite \+ FTS5

Event 为核心检索单位

支持关键词、人物、时间、话题查询

需要时加入简单向量检索 \+ RRF

## LangGraph Investigation Agent

提供基础工具：

- search\_streams

- search\_events

- search\_danmaku

- inspect\_event

- expand\_context

- find\_highlights

Agent 能够：根据模糊问题制定检索路径、展开候选前后上下文；区分 Audience Reaction 与 Event Inference；证据不足时明确停止，不伪造主播原话

## 前端

至少包含：

- Archive      直播列表

- Timeline     单场直播事件时间线

- Search       历史事件搜索

- Highlights   高光候选

- Investigate  Agent 调查入口

## Eval

最小评测集衡量：

- Event Recall / Precision

- 时间边界 IoU / 误差

- Retrieval Recall@K

- 高光人工采用率

- Agent Evidence Grounding

- 人工回看时间压缩比例

# 技术路线

## Frontend

Vue 3 \+ Vite \+ TypeScript \+ Pinia \+ Vue Router \+ ECharts

## Backend

Python \+ FastAPI \+ Pydantic \+ pytest

## Agent

LangGraph，只用于 Investigation，不参与离线 Event Detection。

## Storage / Retrieval

SQLite \+ FTS5；语义检索需要时使用 FAISS / hnswlib。

## Data

代码放本机 SSD \+ Git；录播 / ASS / 派生数据放移动硬盘，通过 `RANSTA_DATA_ROOT` 配置。

# 目录

```Plain Text
vtuber-archive/
├── frontend/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── domain/
│   │   ├── ingestion/
│   │   ├── event_pipeline/
│   │   ├── retrieval/
│   │   ├── evidence/
│   │   ├── agent/
│   │   ├── repository/
│   │   └── services/
│   ├── tests/
│   └── evals/
├── docs/
└── scripts/
```



