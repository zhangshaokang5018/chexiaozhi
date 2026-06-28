import { getContext, getUserId } from '../../utils/request'

Page({
  data: {
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
    wx.switchTab({ url: '/pages/chat/chat' })
  },
  goKb() {
    wx.switchTab({ url: '/pages/kb/kb' })
  },
  goProfile() {
    wx.switchTab({ url: '/pages/profile/profile' })
  },
  // A-T10：故障码入口 / 热门故障跳详情，带故障码参数
  goDetail(event: WechatMiniprogram.TouchEvent) {
    const code = String((event && event.currentTarget && event.currentTarget.dataset.code) || 'P0300')
    wx.navigateTo({ url: `/pages/detail/detail?code=${encodeURIComponent(code)}` })
  },
})
