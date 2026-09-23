<script setup lang="ts">
type ArchiveStatus =
  | 'all'
  | 'danmaku'
  | 'highlights'
  | 'pending'

defineProps<{
  query: string
  status: ArchiveStatus
  count: number
  loading: boolean
}>()

const emit = defineEmits<{
  'update:query': [value: string]
  'update:status': [value: ArchiveStatus]
  search: []
}>()

function handleQueryInput(
  event: Event,
) {
  const target =
    event.target as HTMLInputElement

  emit(
    'update:query',
    target.value,
  )
}

function handleStatusChange(
  event: Event,
) {
  const target =
    event.target as HTMLSelectElement

  emit(
    'update:status',
    target.value as ArchiveStatus,
  )
}
</script>

<template>
  <form
    class="filter-bar"
    @submit.prevent="emit('search')"
  >
    <label class="search-field">
      <span class="sr-only">
        搜索标题或 BV 号
      </span>

      <span
        aria-hidden="true"
        class="search-symbol"
      ></span>

      <input
        :value="query"
        type="search"
        placeholder="搜索标题或 BV 号"
        @input="handleQueryInput"
      />

      <kbd>↵</kbd>
    </label>

    <label class="select-field">
      <span>状态</span>

      <select
        :value="status"
        @change="handleStatusChange"
      >
        <option value="all">
          全部档案
        </option>

        <option value="danmaku">
          已有弹幕
        </option>

        <option value="highlights">
          已有 Highlight
        </option>

        <option value="pending">
          待生成 Highlight
        </option>
      </select>
    </label>

    <button
      class="button button-secondary"
      type="submit"
      :disabled="loading"
    >
      {{
        loading
          ? '检索中'
          : '筛选'
      }}
    </button>

    <span class="result-count">
      {{ count }} 场直播
    </span>
  </form>
</template>