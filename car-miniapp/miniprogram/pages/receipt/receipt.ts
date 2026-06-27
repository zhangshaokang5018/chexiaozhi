Page({
  goBack() {
    wx.navigateBack()
  },
  goHome() {
    wx.navigateTo({ url: '/pages/index/index' })
  },
  goChat() {
    wx.navigateTo({ url: '/pages/chat/chat' })
  },
  goKb() {
    wx.navigateTo({ url: '/pages/kb/kb' })
  },
  goProfile() {
    wx.navigateTo({ url: '/pages/profile/profile' })
  },
})
