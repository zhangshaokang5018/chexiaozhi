import { ping, PingResult } from '../../utils/request'

const LEGAL_NOTE = '所有建议仅供参考，请以当地授权维修点为准。'

const IMAGE_PRESET: Record<string, string> = {
  brake: '识别：刹车片（磨损接近极限 · 建议厚度 3mm）',
  oil: '识别：仪表盘机油报警灯（红灯 严重）',
  bill: '识别：维修报价单 · 项目：更换机油机滤 800元',
}

type Block = {
  type?: 'kv' | 'warn'
  label?: string
  value?: string
  danger?: boolean
  good?: boolean
  text?: string
}

type Message = {
  id: number
  role: 'user' | 'bot'
  text?: string
  image?: string | null
  loading?: boolean
  route?: {
    intent: string
    confidenceText: string
  }
  agentMeta?: {
    name: string
    desc: string
  }
  steps?: Array<{
    name: string
    status: 'done' | 'doing' | 'pending'
  }>
  reply?: {
    title?: string
    blocks?: Block[]
    price_text?: string | null
  }
  legal_note?: string | null
}

const welcomeMessage: Message = {
  id: 0,
  role: 'bot',
  route: { intent: '欢迎使用', confidenceText: '100%' },
  agentMeta: { name: '系统', desc: '汽车维修翻译官' },
  reply: {
    title: '欢迎使用汽车维修翻译官',
    blocks: [
      { type: 'kv', label: '我能做', value: '故障码解读 / 症状分析 / 零件识别 / 报价审核' },
      { type: 'warn', text: LEGAL_NOTE },
    ],
    price_text: null,
  },
  legal_note: null,
}

Page({
  data: {
    loading: true,
    connected: false,
    statusText: '尚未连接服务端',
    pingResult: null as PingResult | null,
    loadingAgent: false,
    msgTailId: 0,
    inputText: '',
    context: {
      car_model: '2022款 丰田 卡罗拉 1.2T 豪华版',
      vin: 'LFMAP22CXXX123456',
      mileage: '38,500 km',
      location: '北京',
    },
    messages: [welcomeMessage] as Message[],
    showContext: false,
    showReceipt: false,
    receipt: {
      shop: '车智汇授权维修中心',
      car_model: '2022款 丰田 卡罗拉 1.2T 豪华版',
      vin: 'LFMAP22CXXX123456',
      location: '北京',
      created_at: '2026-06-27 13:20:00',
      items: [
        {
          item: '更换机油机滤',
          part_range: '300-500',
          labor_range: '100-200',
          avg: 550,
        },
      ],
      total: 550,
    },
  },

  onLoad() {
    this.checkConnection()
  },

  checkConnection() {
    this.setData({ loading: true, statusText: '正在连接服务端...' })
    ping()
      .then((res) => {
        this.setData({
          loading: false,
          connected: Boolean(res && res.ok),
          statusText: res && res.ok ? '服务已连接' : '服务返回异常',
          pingResult: res,
        })
      })
      .catch((err) => {
        console.error('ping failed', err)
        this.setData({
          loading: false,
          connected: false,
          statusText: '服务未连接，当前展示原型 mock 数据',
          pingResult: null,
        })
      })
  },

  onInput(event: WechatMiniprogram.Input) {
    this.setData({ inputText: event.detail.value })
  },

  send() {
    const text = (this.data.inputText || '').trim()
    if (!text) return
    this.addUserMessage(text, null)
    this.setData({ inputText: '' })
    this.addMockAgentReply(text)
  },

  quickAsk(event: WechatMiniprogram.TouchEvent) {
    const text = String(event.currentTarget.dataset.text || '')
    if (!text) return
    this.addUserMessage(text, null)
    this.addMockAgentReply(text)
  },

  uploadImage(event: WechatMiniprogram.TouchEvent) {
    const type = String(event.currentTarget.dataset.type || '')
    const label = IMAGE_PRESET[type] || '图像识别结果'
    this.addUserMessage('请帮我分析这张图片。', label)
    this.addMockAgentReply(label)
  },

  addUserMessage(text: string, image: string | null) {
    const id = Date.now()
    const messages = this.data.messages.concat([{ id, role: 'user', text, image } as Message])
    this.setData({ messages, msgTailId: id })
  },

  addMockAgentReply(text: string) {
    const id = Date.now() + 1
    const reply = this.buildMockReply(id, text)
    this.setData({
      loadingAgent: true,
      messages: this.data.messages.concat([{
        id,
        role: 'bot',
        loading: true,
        agentMeta: { name: '调度 Agent', desc: '意图路由中' },
        route: { intent: '识别中...', confidenceText: '0%' },
        steps: [
          { name: '意图识别', status: 'doing' },
          { name: '知识库检索', status: 'pending' },
          { name: '合成回复', status: 'pending' },
        ],
        reply: { title: '正在分析...', blocks: [], price_text: null },
      } as Message]),
      msgTailId: id,
    })

    setTimeout(() => {
      const messages = this.data.messages.slice()
      const index = messages.findIndex((item) => item.id === id)
      if (index >= 0) {
        messages[index] = reply
      }
      this.setData({ messages, msgTailId: id, loadingAgent: false })
    }, 500)
  },

  buildMockReply(id: number, text: string): Message {
    if (/p0300|故障码/i.test(text)) {
      return {
        id,
        role: 'bot',
        agentMeta: { name: '故障码解读 Agent', desc: 'DTC 代码解析' },
        route: { intent: '故障码解读', confidenceText: '90%' },
        steps: this.doneSteps('故障码解读 Agent'),
        reply: {
          title: '故障码解读',
          blocks: [
            { type: 'kv', label: '故障码', value: 'P0300', danger: true },
            { type: 'kv', label: '描述', value: '发动机缺火（随机/多缸）' },
            { type: 'kv', label: '可能原因', value: '点火线圈、火花塞、喷油嘴或进气泄漏' },
            { type: 'kv', label: '修复难度', value: '3/5 ★★★☆☆' },
            { type: 'warn', text: '如维修店建议整个发动机拆解，要求先按低成本方案逐项排查。' },
          ],
          price_text: '零件 800-2000 元 + 工时 200-500 元',
        },
        legal_note: LEGAL_NOTE,
      }
    }

    if (/报价|价格|费用|800|机油|保养|维修报价单/.test(text)) {
      return {
        id,
        role: 'bot',
        agentMeta: { name: '保养建议 Agent', desc: '报价/避坑指南' },
        route: { intent: '保养建议/报价审核', confidenceText: '90%' },
        steps: this.doneSteps('保养建议 Agent'),
        reply: {
          title: '保养建议 / 报价审核',
          blocks: [
            { type: 'kv', label: '维修项目', value: '更换机油机滤（紧凑型轿车）' },
            { type: 'kv', label: '零件参考价', value: '300-500 元' },
            { type: 'kv', label: '工时参考价', value: '100-200 元' },
            { type: 'kv', label: '市场总价', value: '400-700 元', good: true },
            { type: 'warn', text: '你报的 800 元超出市场价上限，建议再找 2-3 家报价对比。' },
            { type: 'warn', text: '避坑三件套：维修前书面报价、保留旧件、索取发票与保修单。' },
          ],
          price_text: '400-700 元（零件 300-500 + 工时 100-200）',
        },
        legal_note: LEGAL_NOTE,
      }
    }

    if (/识别|刹车片|机油报警灯|图片/.test(text)) {
      return {
        id,
        role: 'bot',
        agentMeta: { name: '零件识别 Agent', desc: '图像/名称匹配' },
        route: { intent: '图像识别/零件匹配', confidenceText: '90%' },
        steps: this.doneSteps('零件识别 Agent'),
        reply: {
          title: '零件识别',
          blocks: [
            { type: 'kv', label: '图像识别结果', value: text },
            { type: 'kv', label: '零件库匹配', value: '已在维修手册 / 配件数据库中检索到同型号配件' },
            { type: 'kv', label: '副厂件建议', value: '选用一线副厂，避免三无产品' },
            { type: 'warn', text: '维修前要求店家展示零件外包装并记录序列号。' },
          ],
          price_text: '原厂约 2x · 一线副厂约 1x · 杂牌约 0.5x（不推荐）',
        },
        legal_note: LEGAL_NOTE,
      }
    }

    return {
      id,
      role: 'bot',
      agentMeta: { name: '症状分析 Agent', desc: '异响/抖动/报警判断' },
      route: { intent: '症状分析', confidenceText: '85%' },
      steps: this.doneSteps('症状分析 Agent'),
      reply: {
        title: '症状分析',
        blocks: [
          { type: 'kv', label: '检测症状', value: '咕噜咕噜、异响' },
          { type: 'kv', label: '紧急程度', value: '中', danger: false },
          { type: 'kv', label: '关联故障点', value: '水泵故障 / 冷却液循环异常 / 排气管共振' },
          { type: 'kv', label: '专业判断', value: `结合你的 ${this.data.context.car_model} / ${this.data.context.mileage}，这是该里程区间的常见故障。` },
          { type: 'warn', text: '应急处理：先观察冷却液液位，打开引擎盖听是否来自水泵位置。' },
          { type: 'warn', text: '避坑：警惕先拆再说的套路，拆前必须书面报价。' },
        ],
        price_text: '零件 300-1500 元 + 工时 100-400 元',
      },
      legal_note: LEGAL_NOTE,
    }
  },

  doneSteps(agentName: string): Message['steps'] {
    return [
      { name: '意图识别', status: 'done' },
      { name: `分发至 ${agentName}`, status: 'done' },
      { name: '知识库检索', status: 'done' },
      { name: '合成回复', status: 'done' },
    ]
  },

  openContext() {
    this.setData({ showContext: true })
  },

  closeContext() {
    this.setData({ showContext: false })
  },

  ctxInput(event: WechatMiniprogram.Input) {
    const key = String(event.currentTarget.dataset.k || '')
    if (!key) return
    const context = { ...this.data.context, [key]: event.detail.value }
    this.setData({ context })
  },

  saveContext() {
    this.setData({ showContext: false })
    wx.showToast({ title: '已保存', icon: 'success' })
  },

  clearHistory() {
    this.setData({
      messages: [welcomeMessage],
      msgTailId: 0,
      showContext: false,
    })
  },

  showReceipt() {
    wx.navigateTo({ url: '/pages/receipt/receipt' })
  },

  closeReceipt() {
    this.setData({ showReceipt: false })
  },

  noop() {},

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
