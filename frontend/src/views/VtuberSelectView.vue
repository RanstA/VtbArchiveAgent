<script setup lang="ts">
import {
  watch,
} from 'vue'

import {
  storeToRefs,
} from 'pinia'

import {
  useMockApi,
} from '@/api/client'

import ArchiveFilters
  from '@/components/archive/ArchiveFilters.vue'

import StreamTable
  from '@/components/archive/StreamTable.vue'

import {
  useArchiveStore,
} from '@/stores/archive'

import {
  useVtuberStore,
} from '@/stores/vtuber'

const archive =
  useArchiveStore()

const vtuberStore =
  useVtuberStore()

const {
  streams,
  loading,
  error,
  query,
  status,
  resultCount,
} = storeToRefs(
  archive,
)

const {
  currentVtuberId,
} = storeToRefs(
  vtuberStore,
)

function loadCurrentArchive() {
  const vtuberId =
    currentVtuberId.value

  if (!vtuberId) {
    return
  }

  void archive.load(
    vtuberId,
  )
}

/**
 * Router guard 会先设置 currentVtuberId。
 *
 * immediate 保证首次进入：
 *
 * /v/aza/archive
 *
 * 会立刻加载 Aza。
 *
 * VTuber workspace 改变时也会自动重新加载。
 */
watch(
  currentVtuberId,
  (vtuberId) => {
    if (!vtuberId) {
      return
    }

    void archive.load(
      vtuberId,
    )
  },
  {
    immediate: true,
  },
)
</script>

<template>
  <main
    class="page archive-page"
  >
    <header class="page-header">
      <div>
        <span class="eyebrow">
          ARCHIVE INDEX
        </span>

        <h1>
          直播档案
        </h1>
      </div>

      <div class="header-metric">
        <span>
          DATA SOURCE
        </span>

        <strong>
          {{
            useMockApi
              ? 'LOCAL / MOCK'
              : 'FASTAPI'
          }}
        </strong>
      </div>
    </header>

    <section
      class="content-panel"
    >
      <ArchiveFilters
        v-model:query="query"
        v-model:status="status"
        :count="resultCount"
        :loading="loading"
        @search="
          loadCurrentArchive
        "
      />

      <p
        v-if="error"
        class="error-banner"
      >
        {{ error }}
      </p>

      <StreamTable
        :streams="streams"
        :loading="loading"
      />
    </section>
  </main>
</template>