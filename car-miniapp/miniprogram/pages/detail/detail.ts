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

  // 立即咨询：把该故障码暂存，切到咨询 tab 自动提问（A-T6 同款通道）
  goChat() {
    try {
      wx.setStorageSync('cxz_pending_ask', `${this.data.code} 是什么意思？`)
    } catch (e) {
      console.error('store pending ask failed', e)
    }
    wx.switchTab({ url: '/pages/chat/chat' })
  },

  goBack() {
    wx.navigateBack()
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
