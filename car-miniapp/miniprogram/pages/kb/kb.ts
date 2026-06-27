Page({
  data: {
    activeTab: 'dtc',
    items: [
      { code: 'P0300', stars: '★★★☆☆', desc: '发动机缺火（随机/多缸）', cause: '点火线圈故障 / 火花塞老化 / 喷油嘴堵塞', meta: '零件 800-2000 · 工时 200-500 元', level: 'danger' },
      { code: 'P0171', stars: '★★☆☆☆', desc: '系统过稀（第1排）', cause: '空气流量计脏污 / 进气歧管漏气 / 燃油泵压力不足', meta: '零件 200-800 · 工时 100-300 元', level: '' },
      { code: 'P0420', stars: '★★★★☆', desc: '催化器系统效率低于阈值', cause: '三元催化器老化 / 氧传感器故障 / 发动机烧机油', meta: '零件 1500-4000 · 工时 300-800 元', level: 'warn' },
      { code: 'P0442', stars: '★☆☆☆☆', desc: '蒸发排放系统小泄漏', cause: '油箱盖密封不良 / 碳罐电磁阀故障', meta: '零件 100-500 · 工时 50-200 元', level: '' },
      { code: 'C0035', stars: '★★☆☆☆', desc: '左前轮速传感器电路故障', cause: 'ABS 传感器脏污或损坏 / 线束磨损', meta: '零件 200-600 · 工时 100-250 元', level: '' },
      { code: 'B1000', stars: '★★★★★', desc: '电控单元内部故障', cause: 'ECU 软件异常 / 硬件损坏', meta: '零件 2000-8000 · 工时 500-1500 元', level: '' },
    ],
  },

  switchTab(event: WechatMiniprogram.TouchEvent) {
    this.setData({ activeTab: String(event.currentTarget.dataset.tab || 'dtc') })
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

  goDetail() {
    wx.navigateTo({ url: '/pages/detail/detail' })
  },
})
