Page({
  goHome() {
    wx.navigateTo({ url: '/pages/index/index' })
  },
  goChat() {
    wx.navigateTo({ url: '/pages/chat/chat' })
  },
  goKb() {
    wx.navigateTo({ url: '/pages/kb/kb' })
  },
  goReceipt() {
    wx.navigateTo({ url: '/pages/receipt/receipt' })
  },
})
