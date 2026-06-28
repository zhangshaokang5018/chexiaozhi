import { getConsultations, getStoredUserId, UserConsultationItem } from '../../utils/user-api'

function safeItems(value: UserConsultationItem[] | undefined): UserConsultationItem[] {
  return Array.isArray(value) ? value : []
}

Page({
  data: {
    userId: '',
    loading: true,
    loadingMore: false,
    errorText: '',
    page: 1,
    pageSize: 20,
    total: 0,
    items: [] as UserConsultationItem[],
    active: null as UserConsultationItem | null,
  },

  onShow() {
    this.loadFirstPage()
  },

  loadFirstPage() {
    const userId = getStoredUserId()
    if (!userId) {
      this.setData({ userId: '', loading: false, errorText: '', items: [], active: null, total: 0, page: 1 })
      return
    }
    this.setData({ userId, loading: true, errorText: '', page: 1 })
    getConsultations(userId, 1, this.data.pageSize)
      .then((res) => {
        const items = safeItems(res.items)
        this.setData({
          items,
          active: items.length ? items[0] : null,
          total: Number(res.total || items.length || 0),
          loading: false,
        })
      })
      .catch((err) => {
        console.error('load consultations failed', err)
        this.setData({ loading: false, errorText: '咨询记录加载失败，请确认用户体系后端和 MySQL 已启动' })
      })
  },

  loadMore() {
    if (!this.data.userId || this.data.loading || this.data.loadingMore) return
    if (this.data.items.length >= this.data.total) return
    const nextPage = this.data.page + 1
    this.setData({ loadingMore: true })
    getConsultations(this.data.userId, nextPage, this.data.pageSize)
      .then((res) => {
        const items = safeItems(res.items)
        this.setData({
          items: this.data.items.concat(items),
          total: Number(res.total || this.data.items.length + items.length || 0),
          page: nextPage,
          loadingMore: false,
        })
      })
      .catch((err) => {
        console.error('load more consultations failed', err)
        this.setData({ loadingMore: false })
        wx.showToast({ title: '加载更多失败', icon: 'none' })
      })
  },

  openItem(event: WechatMiniprogram.TouchEvent) {
    const id = String(event.currentTarget.dataset.id || '')
    const active = this.data.items.find((item) => item.consultation_id === id) || null
    this.setData({ active })
  },

  goLogin() {
    wx.navigateTo({ url: '/pages/login/login' })
  },

  goBack() {
    wx.navigateBack()
  },
})
