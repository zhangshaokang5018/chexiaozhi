// utils/request.ts
// 统一请求封装。

// 本地开发服务端地址。
// - 微信开发者工具：本机调试请用 http://localhost:5000，并在「详情 -> 本地设置」勾选
//   「不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书」。
// - 真机预览：把 localhost 换成电脑的局域网 IP，例如 http://192.168.1.10:5000。
export const BASE_URL = 'http://localhost:5000'

interface RequestOptions {
  url: string
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  data?: object
  header?: Record<string, string>
}

export function request<T = any>(options: RequestOptions): Promise<T> {
  const { url, method = 'GET', data, header } = options
  return new Promise<T>((resolve, reject) => {
    wx.request({
      url: `${BASE_URL}${url}`,
      method,
      data,
      header: {
        'content-type': 'application/json',
        ...(header || {}),
      },
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data as T)
        } else {
          reject(new Error(`HTTP ${res.statusCode}`))
        }
      },
      fail: (err) => {
        reject(err)
      },
    })
  })
}

// 基座阶段：检查服务端联通
export interface PingResult {
  ok: boolean
  name: string
  version: string
}

export function ping(): Promise<PingResult> {
  return request<PingResult>({ url: '/api/ping' })
}

export type ChatMode = 'text' | 'image'

export interface ChatPayload {
  user_id: string
  text: string
  mode: ChatMode
  image_label: string
}

export interface ChatRoute {
  agent: 'scheduler' | 'symptom' | 'dtc' | 'maintain' | 'part'
  intent: string
  confidence: number
}

export interface ChatAgentMeta {
  name: string
  desc: string
}

export interface ChatBlock {
  type?: 'kv' | 'warn' | 'danger'
  label?: string
  value?: string
  text?: string
  danger?: boolean
  good?: boolean
}

export interface ChatReply {
  title: string
  summary: string
  blocks: ChatBlock[]
  price_text: string
  price_range: number[]
}

export interface ChatStep {
  name: string
  status: 'done' | 'doing' | 'pending' | 'todo'
  detail?: string
}

export interface ChatResp {
  route: ChatRoute
  agent: ChatRoute['agent']
  agent_meta: ChatAgentMeta
  hit: boolean
  reply: ChatReply
  steps: ChatStep[]
  elapsed_ms: number
  legal_note: string
}

export function chat(payload: ChatPayload): Promise<ChatResp> {
  return request<ChatResp>({
    url: '/api/chat',
    method: 'POST',
    data: payload,
  })
}

export type KbKind = 'dtc' | 'cost' | 'symptom'

export interface KbQuery {
  q?: string
  level?: string
  page?: number
  page_size?: number
}

export interface KbItem {
  id: string
  kind: KbKind
  title: string
  subtitle: string
  summary: string
  detail: string
  level?: number | string
  level_text: string
  level_class: string
  stars?: string
  price_text: string
  tip: string
  ask_text: string
  tags: string[]
  raw: Record<string, unknown>
}

export interface KbResp {
  kind: KbKind
  count: number
  total: number
  page: number
  page_size: number
  items: KbItem[]
  tabs: Array<{
    kind: KbKind
    label: string
    count: number
  }>
}

function buildQuery(query?: KbQuery): string {
  if (!query) return ''
  const params: string[] = []
  Object.keys(query).forEach((key) => {
    const value = query[key as keyof KbQuery]
    if (value !== undefined && value !== '') {
      params.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
    }
  })
  return params.length ? `?${params.join('&')}` : ''
}

export function getKb(kind: KbKind, query?: KbQuery): Promise<KbResp> {
  return request<KbResp>({ url: `/api/kb/${kind}${buildQuery(query)}` })
}

// 语音转文字：上传录音文件到 /api/asr，返回识别文本
export interface AsrResp {
  ok: boolean
  text: string
  simulated: boolean // true=降级占位（未配置 Key 或识别失败）
  model: string
  error: string | null
}

export function asr(filePath: string): Promise<AsrResp> {
  return new Promise<AsrResp>((resolve, reject) => {
    wx.uploadFile({
      url: `${BASE_URL}/api/asr`,
      filePath,
      name: 'file',
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          try {
            resolve(JSON.parse(res.data) as AsrResp)
          } catch (e) {
            reject(new Error('ASR 响应解析失败'))
          }
        } else {
          reject(new Error(`HTTP ${res.statusCode}`))
        }
      },
      fail: (err) => reject(err),
    })
  })
}
