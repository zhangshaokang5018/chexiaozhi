// pages/chat/chat.ts
import { ping, PingResult } from '../../utils/request'

Page({
  data: {
    loading: true,
    connected: false,
    statusText: '尚未连接',
    pingResult: null as PingResult | null,
  },

  onLoad() {
    this.checkConnection()
  },

  checkConnection() {
    this.setData({ loading: true, statusText: '正在连接服务端…' })
    ping()
      .then((res) => {
        if (res && res.ok) {
          this.setData({
            loading: false,
            connected: true,
            statusText: '服务已连接',
            pingResult: res,
          })
        } else {
          this.setData({
            loading: false,
            connected: false,
            statusText: '服务返回异常',
            pingResult: res,
          })
        }
      })
      .catch((err) => {
        console.error('ping failed', err)
        this.setData({
          loading: false,
          connected: false,
          statusText: '连接失败，请确认服务端已启动',
          pingResult: null,
        })
      })
  },
})
