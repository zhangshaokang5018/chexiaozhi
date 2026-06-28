import { BASE_URL } from './request'

export const USER_ID_KEY = 'cxz_user_id'
export const SESSION_TOKEN_KEY = 'cxz_session_token'

type Method = 'GET' | 'POST' | 'PATCH'

interface RequestOptions {
  url: string
  method?: Method
  data?: object
}

export interface UserApiErrorBody {
  ok?: false
  error?: string
  recoverable?: boolean
}

function buildQuery(params: Record<string, string>): string {
  const query = Object.keys(params)
    .filter((key) => params[key] !== '')
    .map((key) => `${encodeURIComponent(key)}=${encodeURIComponent(params[key])}`)
    .join('&')
  return query ? `?${query}` : ''
}

export function userRequest<T>(options: RequestOptions): Promise<T> {
  const { url, method = 'GET', data } = options
  return new Promise<T>((resolve, reject) => {
    wx.request({
      url: `${BASE_URL}${url}`,
      method: method as WechatMiniprogram.RequestOption['method'],
      data,
      header: {
        'content-type': 'application/json',
      },
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data as T)
          return
        }
        const body = (res.data || {}) as UserApiErrorBody
        reject(new Error(body.error || `HTTP ${res.statusCode}`))
      },
      fail: (err) => reject(err),
    })
  })
}

export function getStoredUserId(): string {
  return String(wx.getStorageSync(USER_ID_KEY) || '')
}

export function getStoredSessionToken(): string {
  return String(wx.getStorageSync(SESSION_TOKEN_KEY) || '')
}

export function saveSession(user_id: string, session_token: string): void {
  wx.setStorageSync(USER_ID_KEY, user_id)
  wx.setStorageSync(SESSION_TOKEN_KEY, session_token)
}

export function clearSession(): void {
  wx.removeStorageSync(USER_ID_KEY)
  wx.removeStorageSync(SESSION_TOKEN_KEY)
}

export interface LoginPayload {
  login_type: 'wechat' | 'guest'
  code?: string
  anonymous_id?: string
}

export interface LoginResp {
  ok: true
  user_id: string
  session_token: string
  is_new_user: boolean
  profile_completed: boolean
}

export interface UserProfile {
  user_id: string
  nickname: string
  avatar_url: string
  phone_masked: string
  created_at: string
  profile_completed: boolean
}

export interface UserPrivacy {
  user_id: string
  phone_authorized: boolean
  show_vin: boolean
  share_diagnosis_for_improvement: boolean
  data_retention_days: number
}

export interface UserStats {
  consult_count: number
  receipt_count: number
  estimated_saved: number
  favorite_count: number
}

export interface UserVehicle {
  user_id: string
  car_model: string
  vin: string
  mileage: string
  location: string
}

export interface UserRepairItem {
  id: string
  title: string
  summary: string
  created_at: string
  total: number
}

export interface UserRepairs {
  user_id: string
  count: number
  items: UserRepairItem[]
}

export function login(payload: LoginPayload): Promise<LoginResp> {
  return userRequest<LoginResp>({ url: '/api/user/login', method: 'POST', data: payload })
}

export function getProfile(user_id: string): Promise<UserProfile> {
  return userRequest<UserProfile>({ url: `/api/user/profile${buildQuery({ user_id })}` })
}

export function updateProfile(payload: Pick<UserProfile, 'user_id'> & Partial<Pick<UserProfile, 'nickname' | 'avatar_url'>>): Promise<UserProfile> {
  return userRequest<UserProfile>({ url: '/api/user/profile', method: 'PATCH', data: payload })
}

export function getPrivacy(user_id: string): Promise<UserPrivacy> {
  return userRequest<UserPrivacy>({ url: `/api/user/privacy${buildQuery({ user_id })}` })
}

export function updatePrivacy(payload: Pick<UserPrivacy, 'user_id'> & Partial<Omit<UserPrivacy, 'user_id'>>): Promise<UserPrivacy> {
  return userRequest<UserPrivacy>({ url: '/api/user/privacy', method: 'PATCH', data: payload })
}

export function getStats(user_id: string): Promise<UserStats> {
  return userRequest<UserStats>({ url: `/api/user/stats${buildQuery({ user_id })}` })
}

export function getVehicle(user_id: string): Promise<UserVehicle> {
  return userRequest<UserVehicle>({ url: `/api/user/vehicle${buildQuery({ user_id })}` })
}

export function updateVehicle(payload: Pick<UserVehicle, 'user_id'> & Partial<Omit<UserVehicle, 'user_id'>>): Promise<UserVehicle> {
  return userRequest<UserVehicle>({ url: '/api/user/vehicle', method: 'PATCH', data: payload })
}

export function getRepairs(user_id: string): Promise<UserRepairs> {
  return userRequest<UserRepairs>({ url: `/api/user/repairs${buildQuery({ user_id })}` })
}
