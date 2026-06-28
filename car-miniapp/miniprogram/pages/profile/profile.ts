import {
  clearSession,
  getConsultations,
  getProfile,
  getRepairs,
  getStats,
  getStoredUserId,
  getVehicle,
  updateProfile,
  updateVehicle,
  UserProfile,
  UserConsultationItem,
  UserRepairItem,
  UserStats,
  UserVehicle,
} from '../../utils/user-api'

const EMPTY_PROFILE: UserProfile = {
  user_id: '',
  nickname: '未登录车主',
  avatar_url: '',
  phone_masked: '',
  created_at: '',
  profile_completed: false,
}

const EMPTY_STATS: UserStats = {
  consult_count: 0,
  receipt_count: 0,
  estimated_saved: 0,
  favorite_count: 0,
}

const EMPTY_VEHICLE: UserVehicle = {
  user_id: '',
  car_model: '',
  vin: '',
  mileage: '',
  location: '',
}

function safeRepairs(value: UserRepairItem[] | undefined): UserRepairItem[] {
  return Array.isArray(value) ? value : []
}

function safeConsultations(value: UserConsultationItem[] | undefined): UserConsultationItem[] {
  return Array.isArray(value) ? value : []
}

type ProfileInputEvent = WechatMiniprogram.Input<
  WechatMiniprogram.IAnyObject,
  { field: 'nickname' | 'car_model' | 'vin' | 'mileage' | 'location' }
>

Page({
  data: {
    userId: '',
    loading: true,
    saving: false,
    errorText: '',
    profile: EMPTY_PROFILE,
    stats: EMPTY_STATS,
    vehicle: EMPTY_VEHICLE,
    repairs: [] as UserRepairItem[],
    consultations: [] as UserConsultationItem[],
  },

  onShow() {
    this.loadUserData()
  },

  loadUserData() {
    const userId = getStoredUserId()
    if (!userId) {
      this.setData({
        userId: '',
        loading: false,
        errorText: '',
        profile: EMPTY_PROFILE,
        stats: EMPTY_STATS,
        vehicle: EMPTY_VEHICLE,
        repairs: [],
        consultations: [],
      })
      return
    }

    this.setData({ userId, loading: true, errorText: '', repairs: [], consultations: [] })
    Promise.all([getProfile(userId), getStats(userId), getVehicle(userId)])
      .then(([profile, stats, vehicle]) => {
        this.setData({
          profile,
          stats,
          vehicle,
          loading: false,
          errorText: '',
        })
        this.loadRecordPreviews(userId)
      })
      .catch((err) => {
        console.error('load user data failed', err)
        this.setData({
          loading: false,
          repairs: [],
          consultations: [],
          errorText: '用户数据加载失败，请确认 /api/user/* 与 MySQL 已就绪',
        })
      })
  },

  loadRecordPreviews(userId: string) {
    Promise.all([
      getRepairs(userId, 1, 3).catch((err) => {
        console.error('load repairs preview failed', err)
        return null
      }),
      getConsultations(userId, 1, 3).catch((err) => {
        console.error('load consultations preview failed', err)
        return null
      }),
    ]).then(([repairs, consultations]) => {
      this.setData({
        repairs: repairs ? safeRepairs(repairs.items) : [],
        consultations: consultations ? safeConsultations(consultations.items) : [],
      })
    })
  },

  onFieldInput(event: ProfileInputEvent) {
    const field = event.currentTarget.dataset.field
    const value = event.detail.value
    if (field === 'nickname') {
      this.setData({ profile: { ...this.data.profile, nickname: value } })
      return
    }
    this.setData({ vehicle: { ...this.data.vehicle, [field]: value } })
  },

  saveProfile() {
    const user_id = this.data.userId
    if (!user_id || this.data.saving) return
    this.setData({ saving: true, errorText: '' })
    updateProfile({ user_id, nickname: this.data.profile.nickname })
      .then((profile) => {
        this.setData({ profile })
        wx.showToast({ title: '资料已保存', icon: 'success' })
      })
      .catch((err) => {
        console.error('save profile failed', err)
        this.setData({ errorText: '资料保存失败' })
      })
      .finally(() => {
        this.setData({ saving: false })
      })
  },

  saveVehicle() {
    const user_id = this.data.userId
    if (!user_id || this.data.saving) return
    const payload: { user_id: string; car_model: string; mileage: string; location: string; vin?: string } = {
      user_id,
      car_model: this.data.vehicle.car_model,
      mileage: this.data.vehicle.mileage,
      location: this.data.vehicle.location,
    }
    if (this.data.vehicle.vin && this.data.vehicle.vin.indexOf('*') === -1) {
      payload.vin = this.data.vehicle.vin
    }

    this.setData({ saving: true, errorText: '' })
    updateVehicle(payload)
      .then((vehicle) => {
        this.setData({ vehicle })
        wx.showToast({ title: '车辆已保存', icon: 'success' })
      })
      .catch((err) => {
        console.error('save vehicle failed', err)
        this.setData({ errorText: '车辆资料保存失败' })
      })
      .finally(() => {
        this.setData({ saving: false })
      })
  },

  goLogin() {
    wx.navigateTo({ url: '/pages/login/login' })
  },

  goPrivacy() {
    wx.navigateTo({ url: '/pages/privacy/privacy' })
  },

  logout() {
    clearSession()
    this.loadUserData()
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

  goReceipt() {
    wx.navigateTo({ url: '/pages/receipt/receipt' })
  },

  openRepair(event: WechatMiniprogram.TouchEvent) {
    const receiptId = String(event.currentTarget.dataset.receiptId || '')
    wx.navigateTo({ url: receiptId ? `/pages/receipt/receipt?receipt_id=${encodeURIComponent(receiptId)}` : '/pages/receipt/receipt' })
  },

  goConsultations() {
    wx.navigateTo({ url: '/pages/consultations/consultations' })
  },
})
