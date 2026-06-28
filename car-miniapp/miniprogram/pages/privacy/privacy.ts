import { getPrivacy, getStoredUserId, updatePrivacy, UserPrivacy } from '../../utils/user-api'

const EMPTY_PRIVACY: UserPrivacy = {
  user_id: '',
  phone_authorized: false,
  show_vin: false,
  share_diagnosis_for_improvement: false,
  data_retention_days: 180,
}

type PrivacySwitchEvent = WechatMiniprogram.SwitchChange<
  WechatMiniprogram.IAnyObject,
  {
    field: 'phone_authorized' | 'show_vin' | 'share_diagnosis_for_improvement'
  }
>

Page({
  data: {
    userId: '',
    loading: true,
    saving: false,
    errorText: '',
    retentionOptions: [30, 90, 180, 365, 730],
    privacy: EMPTY_PRIVACY,
  },

  onShow() {
    this.loadPrivacy()
  },

  loadPrivacy() {
    const userId = getStoredUserId()
    if (!userId) {
      this.setData({ userId: '', loading: false, privacy: EMPTY_PRIVACY, errorText: '' })
      return
    }
    this.setData({ userId, loading: true, errorText: '' })
    getPrivacy(userId)
      .then((privacy) => {
        this.setData({ privacy, loading: false })
      })
      .catch((err) => {
        console.error('load privacy failed', err)
        this.setData({
          loading: false,
          errorText: '隐私设置加载失败，请确认用户体系后端和 MySQL 已启动',
        })
      })
  },

  onSwitch(event: PrivacySwitchEvent) {
    const field = event.currentTarget.dataset.field
    this.setData({ privacy: { ...this.data.privacy, [field]: event.detail.value } })
  },

  onRetentionChange(event: WechatMiniprogram.PickerChange) {
    const index = Number(event.detail.value)
    const data_retention_days = this.data.retentionOptions[index] || 180
    this.setData({ privacy: { ...this.data.privacy, data_retention_days } })
  },

  savePrivacy() {
    const user_id = this.data.userId
    if (!user_id || this.data.saving) return
    this.setData({ saving: true, errorText: '' })
    updatePrivacy({
      user_id,
      phone_authorized: this.data.privacy.phone_authorized,
      show_vin: this.data.privacy.show_vin,
      share_diagnosis_for_improvement: this.data.privacy.share_diagnosis_for_improvement,
      data_retention_days: this.data.privacy.data_retention_days,
    })
      .then((privacy) => {
        this.setData({ privacy })
        wx.showToast({ title: '已保存', icon: 'success' })
      })
      .catch((err) => {
        console.error('save privacy failed', err)
        this.setData({ errorText: '隐私设置保存失败' })
      })
      .finally(() => {
        this.setData({ saving: false })
      })
  },

  goLogin() {
    wx.navigateTo({ url: '/pages/login/login' })
  },

  goBack() {
    wx.navigateBack()
  },
})
