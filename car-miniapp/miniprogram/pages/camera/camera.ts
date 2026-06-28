import { chooseVehicleImage, isChooseMediaCancel } from '../../utils/media'

const MODE_META: Record<string, { title: string; icon: string; tip: string }> = {
  仪表盘: {
    title: '拍故障灯',
    icon: '⚠️',
    tip: '请将故障灯对准方框内',
  },
  报价单: {
    title: '拍维修单',
    icon: '📋',
    tip: '请让项目、金额和配件型号清晰可见',
  },
  零件: {
    title: '拍零件',
    icon: '🔩',
    tip: '请拍清零件编码、品牌和包装标签',
  },
}

Page({
  data: {
    label: '仪表盘',
    title: MODE_META['仪表盘'].title,
    icon: MODE_META['仪表盘'].icon,
    tip: MODE_META['仪表盘'].tip,
    choosing: false,
  },

  onLoad(options: Record<string, string | undefined> = {}) {
    const label = decodeURIComponent(options.label || '仪表盘')
    this.setMode(label)
  },

  setMode(label: string) {
    const safeLabel = MODE_META[label] ? label : '仪表盘'
    const meta = MODE_META[safeLabel]
    this.setData({
      label: safeLabel,
      title: meta.title,
      icon: meta.icon,
      tip: meta.tip,
    })
  },

  switchMode(event: WechatMiniprogram.TouchEvent) {
    const label = String(event.currentTarget.dataset.label || '')
    if (label) {
      this.setMode(label)
      return
    }
    const labels = Object.keys(MODE_META)
    const idx = labels.indexOf(this.data.label)
    this.setMode(labels[(idx + 1) % labels.length])
  },

  takePhoto() {
    this.chooseAndGo()
  },

  pickFromAlbum() {
    this.chooseAndGo()
  },

  chooseAndGo() {
    if (this.data.choosing) return
    this.setData({ choosing: true })
    chooseVehicleImage(this.data.label)
      .then((image) => {
        wx.setStorageSync('cxz_pending_image', image)
        wx.switchTab({ url: '/pages/chat/chat' })
      })
      .catch((err) => {
        if (!isChooseMediaCancel(err)) {
          console.error('choose image failed', err)
          wx.showToast({ title: '选择图片失败', icon: 'none' })
        }
      })
      .finally(() => {
        this.setData({ choosing: false })
      })
  },

  goBack() {
    const pages = getCurrentPages()
    if (pages.length > 1) {
      wx.navigateBack()
      return
    }
    wx.switchTab({ url: '/pages/index/index' })
  },
})
