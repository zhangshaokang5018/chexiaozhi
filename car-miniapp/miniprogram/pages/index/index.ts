import { getContext, getUserId } from '../../utils/request'
import { chooseVehicleImage, isChooseMediaCancel } from '../../utils/media'

Page({
  data: {
    inputText: '',
    context: {
      car_model: '2022款 丰田 卡罗拉 1.2T 豪华版',
      car_tag: '丰田 卡罗拉',
      vin: 'LFMA*********3456',
      mileage: '38,500 km',
      location: '北京',
    },
  },

  onShow() {
    this.loadContext()
  },

  // A-T5：我的车辆卡片改为 /api/context 拉取
  loadContext() {
    getContext(getUserId())
      .then((ctx) => {
        if (!ctx) return
        // 车型里取“品牌 车系”做标签（取末两个词，找不到就用整串）
        const parts = String(ctx.car_model || '').split(' ').filter(Boolean)
        const carTag = parts.length >= 3 ? `${parts[1]} ${parts[2]}` : ctx.car_model
        this.setData({
          context: {
            car_model: ctx.car_model,
            car_tag: carTag,
            vin: ctx.vin,
            mileage: ctx.mileage,
            location: ctx.location,
          },
        })
      })
      .catch((err) => {
        console.error('load context failed', err)
      })
  },

  goChat() {
    wx.navigateTo({ url: '/pages/chat/chat' })
  },
  onInput(event: WechatMiniprogram.Input) {
    this.setData({ inputText: event.detail.value })
  },
  sendHomeText() {
    const text = (this.data.inputText || '').trim()
    if (!text) {
      wx.navigateTo({ url: '/pages/chat/chat' })
      return
    }
    this.setData({ inputText: '' })
    wx.setStorageSync('cxz_pending_ask', text)
    wx.navigateTo({ url: '/pages/chat/chat' })
  },
  askHot(event: WechatMiniprogram.TouchEvent) {
    const ask = String(event.currentTarget.dataset.ask || '').trim()
    wx.setStorageSync('cxz_pending_ask', ask || '发动机咕噜咕噜响')
    wx.navigateTo({ url: '/pages/chat/chat' })
  },
  askImage(event: WechatMiniprogram.TouchEvent) {
    const label = String(event.currentTarget.dataset.label || '报价单')
    if (label === '故障码') {
      wx.setStorageSync('cxz_pending_ask', 'P0300 是什么意思')
      wx.navigateTo({ url: '/pages/chat/chat' })
      return
    }
    chooseVehicleImage(label)
      .then((image) => {
        wx.setStorageSync('cxz_pending_image', image)
        wx.navigateTo({ url: '/pages/chat/chat' })
      })
      .catch((err) => {
        if (!isChooseMediaCancel(err)) {
          console.error('choose image failed', err)
          wx.showToast({ title: '选择图片失败', icon: 'none' })
        }
      })
  },
  goCamera(event: WechatMiniprogram.TouchEvent) {
    const label = String(event.currentTarget.dataset.label || '仪表盘')
    wx.navigateTo({ url: '/pages/camera/camera?label=' + encodeURIComponent(label) })
  },
  goKb() {
    wx.navigateTo({ url: '/pages/kb/kb' })
  },
  goProfile() {
    wx.navigateTo({ url: '/pages/profile/profile' })
  },
  // A-T10：故障码入口 / 热门故障跳详情，带故障码参数
  goDetail(event: WechatMiniprogram.TouchEvent) {
    const code = String((event && event.currentTarget && event.currentTarget.dataset.code) || 'P0300')
    wx.navigateTo({ url: `/pages/detail/detail?code=${encodeURIComponent(code)}` })
  },
})
