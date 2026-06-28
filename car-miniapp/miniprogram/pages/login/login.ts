import { getStoredUserId, login, saveSession } from '../../utils/user-api'

function anonymousId(): string {
  const key = 'cxz_anonymous_id'
  const exists = String(wx.getStorageSync(key) || '')
  if (exists) return exists
  const next = `anon_${Date.now()}_${Math.random().toString(16).slice(2, 8)}`
  wx.setStorageSync(key, next)
  return next
}

Page({
  data: {
    userId: '',
    loading: false,
    errorText: '',
  },

  onShow() {
    this.setData({ userId: getStoredUserId() })
  },

  loginWechat() {
    if (this.data.loading) return
    this.setData({ loading: true, errorText: '' })
    login({ login_type: 'wechat', code: 'dev-wx-login-code' })
      .then((res) => {
        saveSession(res.user_id, res.session_token)
        wx.showToast({ title: '登录成功', icon: 'success' })
        this.backToProfile()
      })
      .catch((err) => {
        console.error('wechat login failed', err)
        this.setData({ errorText: '登录失败，请确认用户体系后端和 MySQL 已启动' })
      })
      .finally(() => {
        this.setData({ loading: false })
      })
  },

  loginGuest() {
    if (this.data.loading) return
    this.setData({ loading: true, errorText: '' })
    login({ login_type: 'guest', anonymous_id: anonymousId() })
      .then((res) => {
        saveSession(res.user_id, res.session_token)
        wx.showToast({ title: '已进入', icon: 'success' })
        this.backToProfile()
      })
      .catch((err) => {
        console.error('guest login failed', err)
        this.setData({ errorText: '游客登录失败，请稍后重试' })
      })
      .finally(() => {
        this.setData({ loading: false })
      })
  },

  goProfile() {
    this.backToProfile()
  },

  backToProfile() {
    if (getCurrentPages().length > 1) {
      wx.navigateBack()
      return
    }
    wx.redirectTo({ url: '/pages/profile/profile' })
  },
})
