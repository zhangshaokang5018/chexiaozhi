// utils/request.ts
// 统一请求封装。基座阶段只用于请求 /api/ping。

// 本地开发服务端地址。
// - 微信开发者工具：本机调试请用 http://localhost:5000，并在「详情 -> 本地设置」勾选
//   「不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书」。
// - 真机预览：把 localhost 换成电脑的局域网 IP，例如 http://192.168.1.10:5000。
export const BASE_URL = 'http://localhost:5000'

interface RequestOptions {
  url: string
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  data?: Record<string, any>
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
