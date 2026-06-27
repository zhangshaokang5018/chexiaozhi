import {
  chat,
  ping,
  ChatAgentMeta,
  ChatPayload,
  ChatReply,
  ChatResp,
  ChatStep,
  PingResult,
} from '../../utils/request'

const LEGAL_NOTE = '所有建议仅供参考，请以当地授权维修点为准。'
const USER_ID = 'test_user_001'
const USE_MOCK = false
const MOCK_MODE = 'success' as string

const mockSuccess: ChatResp = {
  route: {
    agent: 'dtc',
    intent: '故障码解读',
    confidence: 0.92,
  },
  agent: 'dtc',
  agent_meta: {
    name: '故障码解读 Agent',
    desc: 'DTC 代码解析',
  },
  hit: true,
  reply: {
    title: 'P0300 故障码解读',
    summary: 'P0300 表示随机/多缸缺火，建议先从点火和进气系统低成本排查。',
    blocks: [
      {
        type: 'danger',
        label: '风险等级',
        value: '3/5，继续长时间行驶可能损伤三元催化器。',
        danger: true,
      },
      {
        type: 'kv',
        label: '可能原因',
        value: '火花塞、点火线圈、喷油嘴、进气漏气或燃油压力异常。',
      },
      {
        type: 'kv',
        label: '排查顺序',
        value: '先读冻结帧，再查火花塞和点火线圈，最后排查喷油和进气。',
      },
      {
        type: 'warn',
        text: '避坑：不要一上来就同意拆发动机，要求维修店先给出读码和逐项检测记录。',
      },
    ],
    price_text: '参考 800-2500 元',
    price_range: [800, 2500],
  },
  steps: [
    {
      name: '意图识别',
      status: 'done',
      detail: '故障码解读（92%）',
    },
    {
      name: '分发至 故障码解读 Agent',
      status: 'done',
    },
    {
      name: '知识库检索',
      status: 'done',
    },
    {
      name: '合成回复',
      status: 'done',
    },
  ],
  elapsed_ms: 238,
  legal_note: LEGAL_NOTE,
}

const mockLoading: ChatResp = {
  route: {
    agent: 'scheduler',
    intent: '识别中...',
    confidence: 0,
  },
  agent: 'scheduler',
  agent_meta: {
    name: '调度 Agent',
    desc: '意图路由中',
  },
  hit: false,
  reply: {
    title: '正在分析...',
    summary: 'AI 正在结合你的描述判断问题类型。',
    blocks: [],
    price_text: '',
    price_range: [],
  },
  steps: [
    {
      name: '意图识别',
      status: 'doing',
    },
    {
      name: '分发至 Agent',
      status: 'pending',
    },
    {
      name: '知识库检索',
      status: 'pending',
    },
    {
      name: '合成回复',
      status: 'pending',
    },
  ],
  elapsed_ms: 0,
  legal_note: LEGAL_NOTE,
}

const mockError: ChatResp = {
  route: {
    agent: 'scheduler',
    intent: '请求失败',
    confidence: 0,
  },
  agent: 'scheduler',
  agent_meta: {
    name: '调度 Agent',
    desc: '网络异常兜底',
  },
  hit: false,
  reply: {
    title: '请求失败',
    summary: '暂时无法连接服务端，请稍后重试或切换到 mock 模式演示。',
    blocks: [
      {
        type: 'warn',
        text: '请确认后端服务已启动，且微信开发者工具已勾选不校验合法域名。',
      },
    ],
    price_text: '',
    price_range: [],
  },
  steps: [
    {
      name: '意图识别',
      status: 'done',
    },
    {
      name: '请求 /api/chat',
      status: 'todo',
      detail: '网络请求失败',
    },
    {
      name: '知识库检索',
      status: 'pending',
    },
    {
      name: '合成回复',
      status: 'done',
    },
  ],
  elapsed_ms: 0,
  legal_note: LEGAL_NOTE,
}

type MessageType = 'user' | 'agent' | 'loading'

type Message = {
  id: string
  type: MessageType
  text?: string
  imageLabel?: string
  route?: {
    agent: ChatResp['agent']
    intent: string
    confidenceText: string
  }
  agentMeta?: ChatAgentMeta
  steps?: ChatStep[]
  reply?: ChatReply
  legal_note?: string
  error?: boolean
}

const welcomeMessage: Message = {
  id: 'welcome',
  type: 'agent',
  route: { agent: 'scheduler', intent: '欢迎使用', confidenceText: '100%' },
  agentMeta: { name: '系统', desc: '汽车维修翻译官' },
  reply: {
    title: '欢迎使用汽车维修翻译官',
    summary: '你可以描述症状、输入故障码、咨询报价，也可以用图片模式模拟识别报价单。',
    blocks: [
      { type: 'kv', label: '我能做', value: '故障码解读 / 症状分析 / 零件识别 / 报价审核' },
      { type: 'warn', text: LEGAL_NOTE },
    ],
    price_text: '',
    price_range: [],
  },
  legal_note: '',
}

let messageSeq = 0

function nextMessageId(prefix: string): string {
  messageSeq += 1
  return `${prefix}-${Date.now()}-${messageSeq}`
}

function confidenceText(confidence: number): string {
  const value = confidence <= 1 ? confidence * 100 : confidence
  return `${Math.round(value)}%`
}

function cloneChatResp(resp: ChatResp): ChatResp {
  return JSON.parse(JSON.stringify(resp)) as ChatResp
}

Page({
  data: {
    loading: true,
    connected: false,
    statusText: '尚未连接服务端',
    pingResult: null as PingResult | null,
    loadingAgent: false,
    msgTailId: 'welcome',
    scrollIntoView: 'msg-welcome',
    inputText: '',
    canSend: false,
    useMock: USE_MOCK,
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
    if (USE_MOCK) {
      this.setData({
        loading: false,
        connected: false,
        statusText: 'Mock 模式：未请求服务端',
        pingResult: null,
      })
      return
    }

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
          statusText: '服务未连接，可临时开启 USE_MOCK 演示',
          pingResult: null,
        })
      })
  },

  onInput(event: WechatMiniprogram.Input) {
    const inputText = event.detail.value
    this.setData({ inputText, canSend: inputText.trim().length > 0 })
  },

  send() {
    const text = (this.data.inputText || '').trim()
    if (!text || this.data.loadingAgent) return
    this.setData({ inputText: '', canSend: false })
    this.sendQuestion(text, 'text', '')
  },

  quickAsk(event: WechatMiniprogram.TouchEvent) {
    const text = String(event.currentTarget.dataset.text || '').trim()
    const mode = event.currentTarget.dataset.mode === 'image' ? 'image' : 'text'
    const imageLabel = String(event.currentTarget.dataset.imageLabel || '')
    if (!text || this.data.loadingAgent) return
    this.sendQuestion(text, mode, imageLabel)
  },

  uploadImage(event: WechatMiniprogram.TouchEvent) {
    const imageLabel = String(event.currentTarget.dataset.imageLabel || '报价单')
    this.sendQuestion('拍报价单', 'image', imageLabel)
  },

  sendQuestion(text: string, mode: ChatPayload['mode'], imageLabel: string) {
    const userMessage = this.createUserMessage(text, imageLabel)
    const loadingMessage = this.createLoadingMessage()
    const payload: ChatPayload = {
      user_id: USER_ID,
      text,
      mode,
      image_label: imageLabel,
    }

    this.appendMessages([userMessage, loadingMessage])
    this.setData({ loadingAgent: true })

    this.fetchChat(payload)
      .then((resp) => {
        this.replaceMessage(loadingMessage.id, this.createAgentMessage(loadingMessage.id, resp))
      })
      .catch((err) => {
        console.error('chat failed', err)
        this.replaceMessage(loadingMessage.id, this.createAgentMessage(loadingMessage.id, mockError, true))
        wx.showToast({ title: '请求失败', icon: 'none' })
      })
      .finally(() => {
        this.setData({ loadingAgent: false })
      })
  },

  fetchChat(payload: ChatPayload): Promise<ChatResp> {
    if (!USE_MOCK) return chat(payload)

    return new Promise((resolve, reject) => {
      setTimeout(() => {
        if (MOCK_MODE === 'error') {
          reject(new Error('mock chat error'))
          return
        }
        resolve(this.buildMockResp(payload))
      }, 500)
    })
  },

  buildMockResp(payload: ChatPayload): ChatResp {
    const resp = cloneChatResp(mockSuccess)
    if (payload.mode === 'image') {
      resp.route = { agent: 'part', intent: '图像识别/零件匹配', confidence: 0.9 }
      resp.agent = 'part'
      resp.agent_meta = { name: '零件识别 Agent', desc: '图像/名称匹配' }
      resp.reply.title = '图片识别模拟'
      resp.reply.summary = `已按图片模式识别：${payload.image_label || payload.text}`
      resp.reply.blocks = [
        { type: 'kv', label: '图片标签', value: payload.image_label || '报价单' },
        { type: 'kv', label: '识别结果', value: 'MVP 阶段为模拟识别，用于演示零件/报价单链路。' },
        { type: 'warn', text: '避坑：维修前要求店家展示配件包装、型号与旧件。' },
      ]
      resp.reply.price_text = '模拟识别结果，价格需结合报价单明细确认'
      resp.reply.price_range = []
    }
    return resp
  },

  createUserMessage(text: string, imageLabel: string): Message {
    return {
      id: nextMessageId('user'),
      type: 'user',
      text,
      imageLabel,
    }
  },

  createLoadingMessage(): Message {
    const id = nextMessageId('loading')
    return this.createAgentMessage(id, mockLoading)
  },

  createAgentMessage(id: string, resp: ChatResp, error = false): Message {
    return {
      id,
      type: error ? 'agent' : resp.elapsed_ms === 0 && resp.agent === 'scheduler' && resp.route.intent === '识别中...' ? 'loading' : 'agent',
      route: {
        agent: resp.agent,
        intent: resp.route.intent,
        confidenceText: confidenceText(resp.route.confidence),
      },
      agentMeta: resp.agent_meta,
      steps: resp.steps,
      reply: resp.reply,
      legal_note: resp.legal_note,
      error,
    }
  },

  appendMessages(items: Message[]) {
    const messages = this.data.messages.concat(items)
    const tailId = items[items.length - 1].id
    this.setData({
      messages,
      msgTailId: tailId,
      scrollIntoView: `msg-${tailId}`,
    })
  },

  replaceMessage(id: string, next: Message) {
    const messages = this.data.messages.map((item) => (item.id === id ? next : item))
    this.setData({
      messages,
      msgTailId: id,
      scrollIntoView: `msg-${id}`,
    })
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
      msgTailId: 'welcome',
      scrollIntoView: 'msg-welcome',
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
