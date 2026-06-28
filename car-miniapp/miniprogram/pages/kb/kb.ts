import { getKb, KbItem, KbKind, KbResp } from '../../utils/request'

type TabItem = {
  kind: KbKind
  label: string
  count: number
}

type KbDisplayItem = KbItem & {
  displayTitle: string
  displaySummary: string
  displayDetail: string
  displayMeta: string
  statusText: string
  displayTone: string
}

const DEFAULT_TABS: TabItem[] = [
  { kind: 'dtc', label: '故障码', count: 0 },
  { kind: 'cost', label: '维修成本', count: 0 },
  { kind: 'symptom', label: '症状关联', count: 0 },
]

const OVERVIEW_DTC_ORDER = ['P0300', 'P0171', 'P0420']

// 每页条数（MVP 知识库数据量小，取较小值以演示「加载更多」分页）
const PAGE_SIZE = 4

function safeItems(value: KbItem[] | undefined): KbItem[] {
  return Array.isArray(value) ? value : []
}

function safeTabs(value: TabItem[] | undefined, fallback: TabItem[]): TabItem[] {
  return Array.isArray(value) && value.length ? value : fallback
}

function stripCausePrefix(text: string): string {
  return String(text || '').replace(/^可能原因[:：]\s*/, '')
}

function rawNumber(value: unknown): number {
  return typeof value === 'number' ? value : Number(value || 0)
}

function itemMaxCost(item: KbItem): number {
  const raw = item.raw || {}
  return rawNumber(raw.price_part_high) + rawNumber(raw.price_labor_high) + rawNumber(raw.part_high) + rawNumber(raw.labor_high)
}

function itemTone(item: KbItem): string {
  if (item.level_class === 'danger') return 'danger'
  if (item.kind === 'dtc' && rawNumber(item.level) >= 3) return 'danger'
  if (item.kind === 'symptom' && item.level_text === '高') return 'danger'
  if (item.kind === 'symptom' && item.level_text === '中') return 'warn'
  if (itemMaxCost(item) >= 4000) return 'warn'
  return ''
}

function normalizeCardItem(item: KbItem): KbDisplayItem {
  const rawCause = typeof item.raw?.cause === 'string' ? item.raw.cause : ''
  const firstSymptom = item.title.split('/')[0].trim()
  const title =
    item.kind === 'cost' ? item.subtitle || item.title : item.kind === 'symptom' ? firstSymptom || item.title : item.title
  const summary =
    item.kind === 'cost' ? item.title : item.kind === 'symptom' ? item.summary.replace(/^关联[:：]\s*/, '') : item.summary
  const detail = item.kind === 'dtc' ? stripCausePrefix(rawCause || item.tip || item.detail) : item.detail
  const statusText =
    item.kind === 'cost'
      ? '👁 参考价'
      : item.kind === 'symptom' && item.level_text
        ? `👁 ${item.level_text}风险`
        : item.level_text
          ? `👁 ${item.stars ? `${item.stars} ` : ''}${item.level_text}`
          : ''

  return {
    ...item,
    displayTitle: title,
    displaySummary: summary,
    displayDetail: detail,
    displayMeta: item.price_text ? `💰 ${item.price_text}` : '',
    statusText,
    displayTone: itemTone(item),
  }
}

function normalizeCardItems(items: KbItem[]): KbDisplayItem[] {
  return items.map(normalizeCardItem)
}

function inferSearchKind(keyword: string, fallback: KbKind): KbKind {
  const q = keyword.trim()
  if (/^[PBCU]\d{4}$/i.test(q) || /故障码|OBD/i.test(q)) return 'dtc'
  if (/多少钱|价格|报价|费用|保养|维修|机油|刹车片|更换|换/.test(q)) return 'cost'
  if (/异响|抖|报警|水温|机油灯|刹车|声音|过热|冒烟|漏/.test(q)) return 'symptom'
  return fallback
}

function normalizeSearchQuery(keyword: string): string {
  const q = keyword.trim()
  if (/保养周期|保养|机油/.test(q)) return '更换机油机滤'
  if (/刹车片/.test(q)) return '刹车片'
  return q
}

function preferredDtcItems(items: KbDisplayItem[]): KbDisplayItem[] {
  const byTitle = new Map(items.map((item) => [item.title, item]))
  const preferred = OVERVIEW_DTC_ORDER.map((code) => byTitle.get(code)).filter(Boolean) as KbDisplayItem[]
  const rest = items.filter((item) => !OVERVIEW_DTC_ORDER.includes(item.title))
  return preferred.concat(rest)
}

Page({
  data: {
    activeTab: 'dtc' as KbKind,
    tabs: DEFAULT_TABS,
    items: [] as KbDisplayItem[],
    loading: true,
    loadingMore: false,
    errorText: '',
    searchText: '',
    queryText: '',
    highOnly: false,
    overviewMode: true,
    page: 1,
    total: 0,
    promptConfig:
      '你是一个专业的汽车维修翻译官。回答时先检索知识库；如果匹配到故障码或症状，请用专业、通俗、警示的口吻说明故障根源、预估费用区间和避坑建议。查不到时不要编造，应建议车主补充信息或寻求线下专业技师协助。',
  },

  onLoad() {
    this.loadOverview()
  },

  switchTab(event: WechatMiniprogram.TouchEvent) {
    const tab = String(event.currentTarget.dataset.tab || 'dtc') as KbKind
    this.setData({ activeTab: tab, searchText: '', highOnly: false })
    this.loadKb(tab)
  },

  onSearchInput(event: WechatMiniprogram.Input) {
    this.setData({ searchText: event.detail.value })
  },

  searchKb() {
    const query = this.data.searchText.trim()
    if (!query) {
      this.loadOverview()
      return
    }
    const kind = inferSearchKind(query, this.data.activeTab)
    this.setData({ activeTab: kind, highOnly: false })
    this.loadKb(kind, normalizeSearchQuery(query))
  },

  clearSearch() {
    this.setData({ searchText: '', queryText: '', highOnly: false })
    this.loadOverview()
  },

  toggleHighOnly() {
    const highOnly = !this.data.highOnly
    this.setData({ highOnly })
    this.loadKb(this.data.activeTab)
  },

  quickSearch(event: WechatMiniprogram.TouchEvent) {
    const keyword = String(event.currentTarget.dataset.keyword || '').trim()
    const query = String(event.currentTarget.dataset.query || keyword).trim()
    const kind = String(event.currentTarget.dataset.kind || this.data.activeTab) as KbKind
    this.setData({
      activeTab: kind,
      searchText: keyword,
      highOnly: false,
    })
    this.loadKb(kind, query)
  },

  refreshKb() {
    if (this.data.overviewMode) {
      this.loadOverview()
      return
    }
    this.loadKb(this.data.activeTab, this.data.queryText)
  },

  loadOverview() {
    this.setData({
      loading: true,
      errorText: '',
      overviewMode: true,
      searchText: '',
      queryText: '',
      highOnly: false,
      page: 1,
    })
    Promise.all([
      getKb('dtc', { page: 1, page_size: 8 }),
      getKb('cost', { page: 1, page_size: 2 }),
      getKb('symptom', { page: 1, page_size: 2 }),
    ])
      .then(([dtcRes, costRes, symptomRes]) => {
        const dtcItems = preferredDtcItems(normalizeCardItems(safeItems(dtcRes.items))).slice(0, 3)
        const costItems = normalizeCardItems(safeItems(costRes.items)).slice(0, 2)
        const symptomItems = normalizeCardItems(safeItems(symptomRes.items)).slice(0, 2)
        const items = dtcItems.concat(costItems, symptomItems)
        this.setData({
          activeTab: 'dtc',
          tabs: safeTabs(dtcRes.tabs || costRes.tabs || symptomRes.tabs, this.data.tabs),
          items,
          total: items.length,
          loading: false,
          errorText: '',
        })
      })
      .catch((err) => {
        console.error('load kb overview failed', err)
        this.setData({
          loading: false,
          items: [],
          total: 0,
          errorText: '知识库加载失败，请确认后端服务已启动',
        })
      })
  },

  // 加载第一页（切 tab/搜索/刷新时调用，会重置列表）
  loadKb(kind: KbKind, queryText?: string) {
    const resolvedQuery = queryText !== undefined ? queryText : this.data.searchText.trim()
    this.setData({ loading: true, errorText: '', overviewMode: false, page: 1, queryText: resolvedQuery })
    getKb(kind, {
      q: resolvedQuery,
      level: this.data.highOnly ? 'high' : '',
      page: 1,
      page_size: PAGE_SIZE,
    })
      .then((res: KbResp) => {
        const items = normalizeCardItems(safeItems(res.items))
        this.setData({
          activeTab: kind,
          tabs: safeTabs(res.tabs, this.data.tabs),
          items,
          total: Number(res.total || items.length || 0),
          page: 1,
          loading: false,
          errorText: '',
        })
      })
      .catch((err) => {
        console.error('load kb failed', err)
        this.setData({
          loading: false,
          items: [],
          errorText: '知识库加载失败，请确认后端服务已启动',
        })
      })
  },

  // A-T10：加载更多，追加下一页（不重置已加载列表）
  loadMore() {
    if (this.data.loadingMore || this.data.loading) return
    if (this.data.items.length >= this.data.total) return
    const nextPage = this.data.page + 1
    this.setData({ loadingMore: true })
    getKb(this.data.activeTab, {
      q: this.data.queryText.trim(),
      level: this.data.highOnly ? 'high' : '',
      page: nextPage,
      page_size: PAGE_SIZE,
    })
      .then((res: KbResp) => {
        const items = normalizeCardItems(safeItems(res.items))
        this.setData({
          items: this.data.items.concat(items),
          total: Number(res.total || this.data.items.length + items.length || 0),
          page: nextPage,
          loadingMore: false,
        })
      })
      .catch((err) => {
        console.error('load more kb failed', err)
        this.setData({ loadingMore: false })
        wx.showToast({ title: '加载更多失败', icon: 'none' })
      })
  },

  openItem(event: WechatMiniprogram.TouchEvent) {
    const kind = String(event.currentTarget.dataset.kind || '')
    const id = String(event.currentTarget.dataset.id || '')
    if (kind === 'dtc' && id) {
      wx.navigateTo({ url: `/pages/detail/detail?code=${encodeURIComponent(id)}` })
      return
    }
    const text = String(event.currentTarget.dataset.ask || '')
    this.askText(text)
  },

  askItem(event: WechatMiniprogram.TouchEvent) {
    const text = String(event.currentTarget.dataset.ask || '')
    this.askText(text)
  },

  askText(text: string) {
    if (!text) return
    wx.setStorageSync('cxz_pending_ask', text)
    wx.reLaunch({ url: '/pages/index/index' })
  },

  goBack() {
    const pages = getCurrentPages()
    if (pages.length > 1) {
      wx.navigateBack()
      return
    }
    wx.reLaunch({ url: '/pages/index/index' })
  },

  goHome() {
    wx.reLaunch({ url: '/pages/index/index' })
  },

  goChat() {
    wx.reLaunch({ url: '/pages/index/index' })
  },

  goProfile() {
    wx.navigateTo({ url: '/pages/profile/profile' })
  },
})
