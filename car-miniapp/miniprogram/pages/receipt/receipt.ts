import { getReceipt, getUserId, ReceiptResp } from '../../utils/request'
import { saveRepair as saveUserRepair } from '../../utils/user-api'

Page({
  data: {
    loading: true,
    errorText: '',
    receipt: null as ReceiptResp | null,
    isEmpty: false,
  },

  onLoad() {
    this.loadReceipt()
  },

  onShow() {
    // 从咨询页诊断后返回时刷新存根
    this.loadReceipt()
  },

  loadReceipt() {
    this.setData({ loading: true, errorText: '' })
    getReceipt(getUserId())
      .then((res: ReceiptResp) => {
        this.setData({
          receipt: res,
          isEmpty: !res.items || res.items.length === 0,
          loading: false,
        })
        this.saveRepair(res)
      })
      .catch((err) => {
        console.error('load receipt failed', err)
        this.setData({
          loading: false,
          errorText: '存根加载失败，请确认后端服务已启动',
        })
      })
  },

  // 维修存根快照非阻塞保存；MySQL 不可用时不影响当前存根展示。
  saveRepair(receipt: ReceiptResp) {
    if (!receipt.receipt_id || !receipt.items || receipt.items.length === 0) return
    const snapshot = {
      user_id: getUserId(),
      receipt_id: receipt.receipt_id,
      receipt_snapshot: receipt,
    }
    saveUserRepair(snapshot).catch((err) => {
      console.warn('save repair failed', err)
    })
  },

  // 复制明细到剪贴板
  copyDetail() {
    const r = this.data.receipt
    if (!r || !r.items || r.items.length === 0) {
      wx.showToast({ title: '暂无可复制的明细', icon: 'none' })
      return
    }
    const lines = [
      `${r.shop}`,
      `车辆：${r.car_model}`,
      `VIN：${r.vin}`,
      `时间：${r.created_at}`,
      '— 维修项目明细 —',
    ]
    r.items.forEach((it, i) => {
      lines.push(`${i + 1}. ${it.item}　零件 ${it.part_range} / 工时 ${it.labor_range}　约¥${it.avg}`)
    })
    lines.push(`预估合计：¥${r.total}`)
    wx.setClipboardData({
      data: lines.join('\n'),
      success: () => wx.showToast({ title: '明细已复制', icon: 'success' }),
    })
  },

  savePdf() {
    wx.showToast({ title: 'PDF 导出开发中', icon: 'none' })
  },

  goBack() {
    const pages = getCurrentPages()
    if (pages.length > 1) {
      wx.navigateBack()
      return
    }
    wx.navigateTo({ url: '/pages/profile/profile' })
  },
  goHome() {
    wx.reLaunch({ url: '/pages/index/index' })
  },
  goChat() {
    wx.reLaunch({ url: '/pages/index/index' })
  },
  goKb() {
    wx.navigateTo({ url: '/pages/kb/kb' })
  },
  goProfile() {
    wx.navigateTo({ url: '/pages/profile/profile' })
  },
})
