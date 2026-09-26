<template>
  <section class="page" data-module="notice">
    <header class="page-head">
      <div>
        <h2>拍摄通告管理</h2>
        <p class="page-desc">维护拍摄通告单，围绕通告编号、拍摄日期、集合时间、拍摄地点做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记拍摄通告单</button>
        <button class="btn" type="button" @click="exportRows">导出拍摄通告清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">
            {{ column === '通告状态' ? statusText(row) : (row[column] ?? '—') }}
          </td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无拍摄通告数据，可先登记拍摄通告单</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条拍摄通告记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { fetchJson, request } from '@/api/client'

type Row = Record<string, string | number | boolean | null>

type Summary = {
  total: number
  pending: number
  abnormal: number
  by_status: Record<string, number>
}

const ENDPOINT = '/api/notice'
const columns = ["通告编号", "拍摄日期", "集合时间", "拍摄地点", "拍摄场次", "出勤人员", "用车安排", "通告状态"]
const actions = ["下发通告", "开始执行", "确认完成"]
const statuses = ["待下发", "已下发", "执行中", "已完成"]
const stats = ref([{"label": "今日通告", "value": 0}, {"label": "待下发通告", "value": 0}, {"label": "未完成通告", "value": 0}])

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

function statusText(row: Row) {
  const text = String(row['通告状态'] ?? '—')
  return row.abnormal ? `${text}（异常）` : text
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '拍摄通告单登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const result = await response.json()
    if (!response.ok || !result.ok) {
      throw new Error(result.message ?? '拍摄通告动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '拍摄通告操作失败'
  }
}

async function reloadStats() {
  try {
    const summary = await fetchJson<Summary>(`${ENDPOINT}/summary`)
    stats.value = [
      { label: '今日通告', value: summary.total },
      { label: '待下发通告', value: summary.by_status['待下发'] ?? 0 },
      { label: '未完成通告', value: summary.pending },
    ]
  } catch {
    stats.value = stats.value.map((item) => ({ ...item, value: 0 }))
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('拍摄通告单列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    await reloadStats()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '拍摄通告列表读取失败'
  }
}

onMounted(reload)
</script>
