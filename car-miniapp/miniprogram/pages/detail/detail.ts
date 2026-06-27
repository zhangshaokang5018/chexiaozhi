Page({
  goBack() {
    wx.navigateBack()
  },
  goChat() {
    wx.navigateTo({ url: '/pages/chat/chat' })
  },
  goHome() {
    wx.navigateTo({ url: '/pages/index/index' })
  },
  goKb() {
    wx.navigateTo({ url: '/pages/kb/kb' })
  },
  goProfile() {
    wx.navigateTo({ url: '/pages/profile/profile' })
  },
})
