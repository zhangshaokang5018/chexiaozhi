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

Page({
  data: {
    activeTab: 'dtc' as KbKind,
    tabs: DEFAULT_TABS,
    items: [] as KbItem[],
    loading: true,
    errorText: '',
    searchText: '',
    highOnly: false,
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

  refreshKb() {
    this.loadKb(this.data.activeTab)
  },

  loadKb(kind: KbKind) {
    this.setData({ loading: true, errorText: '' })
    getKb(kind, {
      q: this.data.searchText.trim(),
      level: this.data.highOnly ? 'high' : '',
      page: 1,
      page_size: 50,
    })
      .then((res: KbResp) => {
        this.setData({
          activeTab: kind,
          tabs: res.tabs && res.tabs.length ? res.tabs : this.data.tabs,
          items: res.items,
          total: res.total,
          loading: false,
          errorText: '',
        })
      })
      .catch((err) => {
        console.error('load kb failed', err)
        this.setData({
          loading: false,
          errorText: '知识库加载失败，请确认后端服务已启动',
        })
      })
  },

  askItem(event: WechatMiniprogram.TouchEvent) {
    const text = String(event.currentTarget.dataset.ask || '')
    if (!text) return
    wx.navigateTo({ url: `/pages/chat/chat?ask=${encodeURIComponent(text)}` })
  },

  goHome() {
    wx.navigateTo({ url: '/pages/index/index' })
  },

  goChat() {
    wx.navigateTo({ url: '/pages/chat/chat' })
  },

  goProfile() {
    wx.navigateTo({ url: '/pages/profile/profile' })
  },
})
