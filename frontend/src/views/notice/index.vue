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

    <form v-if="showCreate" class="filter-bar" @submit.prevent="submitCreate">
      <label v-for="field in createFields" :key="field.name" class="filter-item">
        <span>{{ field.label }}</span>
        <input
          v-model="createForm[field.name]"
          :type="field.type"
          :placeholder="field.placeholder"
        />
      </label>
      <button class="btn primary" type="submit">保存通告单</button>
      <button class="btn ghost" type="button" @click="cancelCreate">取消</button>
    </form>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <label class="filter-item">
        <span>通告状态</span>
        <select v-model="statusFilter">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>当前状态</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td>
            {{ row.status ?? '—' }}
            <span v-if="row.abnormal" class="abnormal-tag">异常</span>
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
          <td :colspan="columns.length + 2" class="empty-state">暂无拍摄通告数据，可先登记拍摄通告单</td>
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
import { onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | boolean | null>

const ENDPOINT = '/api/notice'
const columns = ["通告编号", "拍摄日期", "集合时间", "拍摄地点", "拍摄场次", "出勤人员", "用车安排", "通告状态"]
const actions = ["下发通告", "开始执行", "确认完成"]
const statuses = ["待下发", "已下发", "执行中", "已完成"]
// 页面筛选条件与后端接口参数的对应关系，日期时间条件保持同一口径
const FILTER_PARAMS: Record<string, string> = { "通告编号": "keyword", "拍摄日期": "shoot_date", "集合时间": "assembly_time" }
const createFields = [
  { name: '通告编号', label: '通告编号', type: 'text', placeholder: '如 NOTI-0004' },
  { name: '拍摄日期', label: '拍摄日期', type: 'date', placeholder: '' },
  { name: '集合时间', label: '集合时间', type: 'datetime-local', placeholder: '' },
  { name: '拍摄地点', label: '拍摄地点', type: 'text', placeholder: '进入执行中前必填' },
  { name: '拍摄场次', label: '拍摄场次', type: 'text', placeholder: '' },
  { name: '出勤人员', label: '出勤人员', type: 'text', placeholder: '' },
  { name: '用车安排', label: '用车安排', type: 'text', placeholder: '' },
]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)
const statusFilter = ref('')
const stats = ref([{ label: '今日通告', value: 0 }, { label: '待下发通告', value: 0 }, { label: '未完成通告', value: 0 }])
const showCreate = ref(false)
const createForm = reactive<Record<string, string>>({})

function todayText() {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

function buildQuery() {
  const params = new URLSearchParams()
  for (const [field, value] of Object.entries(filters.value)) {
    const key = FILTER_PARAMS[field]
    if (key && value) {
      params.set(key, value)
    }
  }
  if (statusFilter.value) {
    params.set('status', statusFilter.value)
  }
  return params.toString()
}

function resetFilters() {
  filters.value = {}
  statusFilter.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = ''
  showCreate.value = true
}

function cancelCreate() {
  showCreate.value = false
  for (const field of createFields) {
    createForm[field.name] = ''
  }
}

async function submitCreate() {
  errorMessage.value = ''
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: { ...createForm } }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message ?? payload.detail ?? '拍摄通告单不符合规则，未保存')
    }
    cancelCreate()
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '拍摄通告单保存失败'
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message ?? '拍摄通告动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '拍摄通告操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}?${buildQuery()}`)
    if (!response.ok) {
      throw new Error('拍摄通告单列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    await refreshStats()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '拍摄通告列表读取失败'
  }
}

async function refreshStats() {
  try {
    const response = await request(`${ENDPOINT}?size=200`)
    if (!response.ok) {
      return
    }
    const payload = await response.json()
    const all: Row[] = payload.items ?? []
    const today = todayText()
    stats.value = [
      { label: '今日通告', value: all.filter((row) => String(row['拍摄日期'] ?? '') === today).length },
      { label: '待下发通告', value: all.filter((row) => row.status === '待下发').length },
      { label: '未完成通告', value: all.filter((row) => row.status !== '已完成').length },
    ]
  } catch {
    // 统计卡读取失败时保留上一次结果，不打扰列表操作
  }
}

onMounted(reload)
</script>
