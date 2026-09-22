<script setup lang="ts">
import {
  onMounted,
} from 'vue'

import {
  storeToRefs,
} from 'pinia'

import {
  useVtuberStore,
} from '@/stores/vtuber'

const vtuberStore =
  useVtuberStore()

const {
  vtubers,
  loading,
  error,
} = storeToRefs(
  vtuberStore,
)

onMounted(() => {
  /**
   * 如果 Router 已经尝试加载 catalog
   * 并留下 error，
   * Selector 直接展示错误，
   * 不立即重复请求。
   */
  if (
    !vtuberStore.loaded
    && !vtuberStore.error
  ) {
    void vtuberStore
      .loadVtubers()
  }
})
</script>

<template>
  <main class="vtuber-select-page">
    <section class="vtuber-select-panel">
      <header>
        <span class="eyebrow">
          VTUBER ARCHIVE
        </span>

        <h1>
          选择档案馆
        </h1>

        <p>
          选择一位主播，进入对应的本地研究工作区。
        </p>
      </header>

      <div
        v-if="loading"
        class="catalog-state"
      >
        <strong>
          正在读取档案馆
        </strong>

        <p>
          正在连接本地 Archive 服务……
        </p>
      </div>

      <div
        v-else-if="error"
        class="catalog-state catalog-error"
      >
        <strong>
          无法读取档案馆
        </strong>

        <p>
          {{ error }}
        </p>

        <button
          type="button"
          class="retry-button"
          @click="
            vtuberStore.reloadVtubers
          "
        >
          重试
        </button>
      </div>

      <div
        v-else-if="
          vtubers.length === 0
        "
        class="catalog-state"
      >
        <strong>
          暂无 VTuber 档案
        </strong>

        <p>
          当前数据库中还没有登记任何主播。
        </p>
      </div>

      <div
        v-else
        class="vtuber-grid"
      >
        <RouterLink
          v-for="vtuber in vtubers"
          :key="vtuber.id"
          :to="{
            name: 'archive',
            params: {
              vtuberId:
                vtuber.id,
            },
          }"
          class="vtuber-card"
        >
          <span
            class="vtuber-monogram"
            aria-hidden="true"
          >
            {{
              vtuber.displayName
                .slice(0, 1)
            }}
          </span>

          <span class="vtuber-copy">
            <strong>
              {{
                vtuber.displayName
              }}
            </strong>

            <small class="mono">
              {{
                vtuber.id
              }}
              / ARCHIVE
            </small>
          </span>

          <span
            class="vtuber-arrow"
            aria-hidden="true"
          >
            ↗
          </span>
        </RouterLink>
      </div>
    </section>
  </main>
</template>

<style scoped>
.vtuber-select-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 56px 32px;
}

.vtuber-select-panel {
  width: min(720px, 100%);
}

header {
  margin-bottom: 30px;
}

h1 {
  margin: 10px 0 12px;
  color: var(--text-strong);
  font-size: clamp(
    2rem,
    5vw,
    3.2rem
  );
  font-weight: 650;
  letter-spacing: -.045em;
}

header p {
  margin: 0;
  color: var(--muted);
  font-size: .9rem;
}

.vtuber-grid {
  display: grid;
  grid-template-columns: repeat(
    2,
    minmax(0, 1fr)
  );
  gap: 14px;
}

.vtuber-card {
  min-height: 112px;
  display: flex;
  align-items: center;
  gap: 15px;
  padding: 20px;
  color: var(--text);
  background:
    var(--surface-glass);
  border:
    1px solid var(--line);
  border-radius:
    var(--radius-lg);
  box-shadow:
    var(--panel-shadow);
  text-decoration: none;
  backdrop-filter:
    blur(18px) saturate(125%);
  transition:
    border-color .16s ease,
    transform .16s ease,
    background-color .16s ease;
}

.vtuber-card:hover {
  transform:
    translateY(-2px);
  background:
    var(--surface-hover);
  border-color:
    var(--line-strong);
}

.vtuber-monogram {
  width: 48px;
  height: 48px;
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  color: var(--accent);
  background:
    var(--accent-soft);
  border: 1px solid
    color-mix(
      in srgb,
      var(--accent) 38%,
      var(--line)
    );
  border-radius: 14px;
  font-size: 1.05rem;
  font-weight: 700;
}

.vtuber-copy {
  min-width: 0;
}

.vtuber-copy strong,
.vtuber-copy small {
  display: block;
}

.vtuber-copy strong {
  color:
    var(--text-strong);
  font-size: 1rem;
}

.vtuber-copy small {
  margin-top: 7px;
  color: var(--faint);
  font-size: .68rem;
  letter-spacing: .08em;
}

.vtuber-arrow {
  margin-left: auto;
  color: var(--faint);
}

.vtuber-card:hover
.vtuber-arrow {
  color: var(--accent);
}

.catalog-state {
  padding: 26px;
  color: var(--muted);
  background:
    var(--surface-glass);
  border:
    1px solid var(--line);
  border-radius:
    var(--radius-lg);
  box-shadow:
    var(--panel-shadow);
}

.catalog-state strong {
  display: block;
  color:
    var(--text-strong);
  font-size: .95rem;
}

.catalog-state p {
  margin: 8px 0 0;
  font-size: .82rem;
}

.catalog-error {
  border-color:
    color-mix(
      in srgb,
      var(--accent) 28%,
      var(--line)
    );
}

.retry-button {
  margin-top: 18px;
  padding: 8px 14px;
  color:
    var(--text-strong);
  background:
    var(--surface-hover);
  border:
    1px solid
    var(--line-strong);
  border-radius: 8px;
  cursor: pointer;
  font: inherit;
  font-size: .78rem;
}

.retry-button:hover {
  border-color:
    var(--accent);
}

@media (
  max-width: 700px
) {
  .vtuber-grid {
    grid-template-columns: 1fr;
  }
}
</style>