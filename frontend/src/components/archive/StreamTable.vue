<script setup lang="ts">
import type { Stream } from '@/types'
import { formatDateTime, formatTimestamp } from '@/utils/time'

defineProps<{ streams: Stream[]; loading: boolean }>()
</script>

<template>
  <div class="table-shell">
    <table class="stream-table">
      <thead>
        <tr>
          <th>直播标题</th>
          <th>直播时间</th>
          <th>BV 号</th>
          <th>弹幕</th>
          <th>EVENT</th>
          <th class="align-right">时长</th>
        </tr>
      </thead>
      <tbody v-if="!loading && streams.length">
        <tr v-for="stream in streams" :key="stream.id">
          <td class="stream-title-cell">
            <RouterLink :to="{ name: 'timeline', params: { streamId: stream.id } }">
              {{ stream.title }}
              <span aria-hidden="true">↗</span>
            </RouterLink>
          </td>
          <td class="mono muted">{{ formatDateTime(stream.liveTime) }}</td>
          <td class="mono">{{ stream.bvId }}</td>
          <td><span class="data-status" :class="{ ready: stream.hasDanmaku }">{{ stream.hasDanmaku ? 'READY' : 'MISSING' }}</span></td>
          <td><span class="data-status" :class="{ ready: stream.hasEvents }">{{ stream.hasEvents ? 'READY' : 'PENDING' }}</span></td>
          <td class="align-right mono muted">{{ stream.durationMs ? formatTimestamp(stream.durationMs) : '—' }}</td>
        </tr>
      </tbody>
    </table>
    <div v-if="loading" class="table-state">正在读取档案索引…</div>
    <div v-else-if="!streams.length" class="table-state">
      <strong>没有符合条件的直播</strong>
      <span>尝试清除搜索词或切换状态筛选。</span>
    </div>
  </div>
</template>
