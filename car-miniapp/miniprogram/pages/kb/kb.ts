import { getKb, KbItem, KbKind, KbResp } from '../../utils/request'

type TabItem = {
  kind: KbKind
  label: string
  count: number
}

const DEFAULT_TABS: TabItem[] = [
  { kind: 'dtc', label: '故障码', count: 0 },
  { kind: 'cost', label: '维修成本', count: 0 },
  { kind: 'symptom', label: '症状关联', count: 0 },
]

// 每页条数（MVP 知识库数据量小，取较小值以演示「加载更多」分页）
const PAGE_SIZE = 4

function safeItems(value: KbItem[] | undefined): KbItem[] {
  return Array.isArray(value) ? value : []
}

function safeTabs(value: TabItem[] | undefined, fallback: TabItem[]): TabItem[] {
  return Array.isArray(value) && value.length ? value : fallback
}

Page({
  data: {
    activeTab: 'dtc' as KbKind,
    tabs: DEFAULT_TABS,
    items: [] as KbItem[],
    loading: true,
    loadingMore: false,
    errorText: '',
    searchText: '',
    highOnly: false,
    page: 1,
    total: 0,
    promptConfig:
      '你是一个专业的汽车维修翻译官。回答时先检索知识库；如果匹配到故障码或症状，请用专业、通俗、警示的口吻说明故障根源、预估费用区间和避坑建议。查不到时不要编造，应建议车主补充信息或寻求线下专业技师协助。',
  },

  onLoad() {
    this.loadKb('dtc')
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
    this.loadKb(this.data.activeTab)
  },

  clearSearch() {
    this.setData({ searchText: '', highOnly: false })
    this.loadKb(this.data.activeTab)
  },

  toggleHighOnly() {
    const highOnly = !this.data.highOnly
    this.setData({ highOnly })
    this.loadKb(this.data.activeTab)
  },

  quickSearch(event: WechatMiniprogram.TouchEvent) {
    const keyword = String(event.currentTarget.dataset.keyword || '').trim()
    const kind = String(event.currentTarget.dataset.kind || this.data.activeTab) as KbKind
    this.setData({
      activeTab: kind,
      searchText: keyword,
      highOnly: false,
    })
    this.loadKb(kind)
  },

  refreshKb() {
    this.loadKb(this.data.activeTab)
  },

  // 加载第一页（切 tab/搜索/刷新时调用，会重置列表）
  loadKb(kind: KbKind) {
    this.setData({ loading: true, errorText: '', page: 1 })
    getKb(kind, {
      q: this.data.searchText.trim(),
      level: this.data.highOnly ? 'high' : '',
      page: 1,
      page_size: PAGE_SIZE,
    })
      .then((res: KbResp) => {
        const items = safeItems(res.items)
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
      q: this.data.searchText.trim(),
      level: this.data.highOnly ? 'high' : '',
      page: nextPage,
      page_size: PAGE_SIZE,
    })
      .then((res: KbResp) => {
        const items = safeItems(res.items)
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

  askItem(event: WechatMiniprogram.TouchEvent) {
    const text = String(event.currentTarget.dataset.ask || '')
    if (!text) return
    wx.navigateTo({ url: '/pages/chat/chat?ask=' + encodeURIComponent(text) })
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
    wx.navigateTo({ url: '/pages/chat/chat' })
  },

  goProfile() {
    wx.navigateTo({ url: '/pages/profile/profile' })
  },
})
