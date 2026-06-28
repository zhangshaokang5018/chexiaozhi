import { getKbDetail, KbItem } from '../../utils/request'

type DtcRaw = {
  code?: string
  desc?: string
  plain?: string
  cause?: string
  level?: number
  logic?: string
  price_part_low?: number
  price_part_high?: number
  price_labor_low?: number
  price_labor_high?: number
}

Page({
  data: {
    code: 'P0300',
    loading: true,
    errorText: '',
    item: null as KbItem | null,
    raw: {} as DtcRaw,
    totalLow: 0,
    totalHigh: 0,
    isDanger: false,
  },

  onLoad(options: Record<string, string | undefined> = {}) {
    const code = (options && options.code ? decodeURIComponent(options.code) : 'P0300').toUpperCase()
    this.setData({ code })
    this.loadDetail(code)
  },

  loadDetail(code: string) {
    this.setData({ loading: true, errorText: '' })
    getKbDetail('dtc', code)
      .then((item: KbItem) => {
        const raw = (item.raw || {}) as DtcRaw
        const totalLow = (raw.price_part_low || 0) + (raw.price_labor_low || 0)
        const totalHigh = (raw.price_part_high || 0) + (raw.price_labor_high || 0)
        this.setData({
          item,
          raw,
          totalLow,
          totalHigh,
          isDanger: item.level_class === 'danger',
          loading: false,
        })
      })
      .catch((err) => {
        console.error('load detail failed', err)
        this.setData({
          loading: false,
          errorText: '未找到该故障码详情，请确认代码或返回知识库查询。',
        })
      })
  },

  // 立即咨询：普通页面栈跳转并携带 ask 参数（A-T6 / A-T9N）
  goChat() {
    const ask = this.data.code + ' 是什么意思？'
    wx.setStorageSync('cxz_pending_ask', ask)
    wx.switchTab({ url: '/pages/chat/chat' })
  },

  goBack() {
    const pages = getCurrentPages()
    if (pages.length > 1) {
      wx.navigateBack()
      return
    }
    wx.switchTab({ url: '/pages/index/index' })
  },
  goHome() {
    wx.switchTab({ url: '/pages/index/index' })
  },
  goKb() {
    wx.switchTab({ url: '/pages/kb/kb' })
  },
  goProfile() {
    wx.switchTab({ url: '/pages/profile/profile' })
  },
})
