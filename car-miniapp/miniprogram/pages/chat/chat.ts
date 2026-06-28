import {
  chat,
  chatImage,
  ping,
  asr,
  getContext,
  getUserId,
  ChatAgentMeta,
  ChatPayload,
  ChatReply,
  ChatResp,
  ChatStep,
  PingResult,
} from '../../utils/request'
import { saveConsultation as saveUserConsultation } from '../../utils/user-api'
import { chooseVehicleImage, isChooseMediaCancel } from '../../utils/media'

const LEGAL_NOTE = '所有建议仅供参考，请以当地授权维修点为准。'
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
  imagePath?: string
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
    summary: '你可以描述症状、输入故障码、咨询报价，也可以拍照识别报价单、零件或仪表盘。',
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

function safeSteps(value: ChatStep[] | undefined): ChatStep[] {
  return Array.isArray(value) ? value : []
}

function safeReply(value: ChatReply | undefined): ChatReply {
  if (!value) {
    return {
      title: '',
      summary: '',
      blocks: [],
      price_text: '',
      price_range: [],
    }
  }

  return {
    title: value.title || '',
    summary: value.summary || '',
    blocks: Array.isArray(value.blocks) ? value.blocks : [],
    price_text: value.price_text || '',
    price_range: Array.isArray(value.price_range) ? value.price_range : [],
  }
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
    recording: false,
    transcribing: false,
    voiceStartAt: 0,
    useMock: USE_MOCK,
    context: {
      car_model: '2022款 丰田 卡罗拉 1.2T 豪华版',
      vin: 'LFMA*********3456',
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

  onLoad(options: Record<string, string | undefined> = {}) {
    this.loadContext()
    // 兼容旧入口：若仍以 navigateTo?ask= 进入（非 tab 场景），onLoad 读取一次
    const ask = options && options.ask ? decodeURIComponent(options.ask) : ''
    this.checkConnection()
    if (ask) this.autoSend(ask)
  },

  onShow() {
    // 从「我的/编辑车辆」返回时刷新顶部车辆卡片
    this.loadContext()
    // 兼容知识库通过 storage 暂存的一键咨询问题。
    this.consumePendingAsk()
    this.consumePendingImage()
  },

  // A-T6：消费知识库一键咨询暂存的问题并自动发送一次
  consumePendingAsk() {
    let ask = ''
    try {
      ask = String(wx.getStorageSync('cxz_pending_ask') || '')
      if (ask) wx.removeStorageSync('cxz_pending_ask')
    } catch (e) {
      ask = ''
    }
    if (ask) this.autoSend(ask)
  },

  consumePendingImage() {
    if (this.data.loadingAgent) return
    let image: { label?: string; tempFilePath?: string } | null = null
    try {
      image = wx.getStorageSync('cxz_pending_image') || null
      if (image) wx.removeStorageSync('cxz_pending_image')
    } catch (e) {
      image = null
    }
    const label = String((image && image.label) || '').trim()
    const tempFilePath = String((image && image.tempFilePath) || '').trim()
    if (label && tempFilePath) {
      this.sendQuestion(`已选择${label}图片`, 'image', label, tempFilePath)
    }
  },

  // A-T5：顶部车辆卡片改为 /api/context 拉取，去掉写死
  loadContext() {
    if (USE_MOCK) return
    getContext(getUserId())
      .then((ctx) => {
        if (ctx) {
          this.setData({
            context: {
              car_model: ctx.car_model,
              vin: ctx.vin,
              mileage: ctx.mileage,
              location: ctx.location,
            },
          })
        }
      })
      .catch((err) => {
        console.error('load context failed', err)
      })
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

  // A-T6：自动发送一键咨询带入的问题
  autoSend(text: string) {
    const q = (text || '').trim()
    if (!q || this.data.loadingAgent) return
    this.setData({ inputText: '', canSend: false })
    this.sendQuestion(q, 'text', '')
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
    if (mode === 'image') {
      this.chooseAndSendImage(imageLabel || text)
      return
    }
    this.sendQuestion(text, mode, imageLabel)
  },

  uploadImage(event: WechatMiniprogram.TouchEvent) {
    const imageLabel = String(event.currentTarget.dataset.imageLabel || '报价单')
    this.chooseAndSendImage(imageLabel)
  },

  chooseAndSendImage(imageLabel: string) {
    if (this.data.loadingAgent) return
    chooseVehicleImage(imageLabel)
      .then((image) => {
        this.sendQuestion(`已选择${image.label}图片`, 'image', image.label, image.tempFilePath)
      })
      .catch((err) => {
        if (!isChooseMediaCancel(err)) {
          console.error('choose image failed', err)
          wx.showToast({ title: '选择图片失败', icon: 'none' })
        }
      })
  },

  // ===== 语音转文字：按住开始录音，松开发送转写 =====
  ensureRecorder() {
    const self = this as any
    if (self._recorder) return self._recorder
    const rm = wx.getRecorderManager()
    rm.onStop((res) => {
      this.setData({ recording: false })
      if (self._skipNextVoiceUpload) {
        self._skipNextVoiceUpload = false
        return
      }
      if (res && res.tempFilePath) {
        this.uploadVoice(res.tempFilePath)
      }
    })
    rm.onError(() => {
      this.setData({ recording: false })
      wx.showToast({ title: '录音失败，请检查麦克风权限', icon: 'none' })
    })
    self._recorder = rm
    return rm
  },

  startRecord() {
    if (this.data.transcribing || this.data.loadingAgent) return
    const rm = this.ensureRecorder()
    if (this.data.recording) return
    const self = this as any
    self._skipNextVoiceUpload = false
    this.setData({ recording: true, voiceStartAt: Date.now() })
    rm.start({
      format: 'mp3',
      duration: 60000,
      sampleRate: 16000,
      numberOfChannels: 1,
      encodeBitRate: 48000,
    })
  },

  finishRecord() {
    if (!this.data.recording) return
    const duration = Date.now() - Number(this.data.voiceStartAt || 0)
    const rm = this.ensureRecorder()
    if (duration < 500) {
      const self = this as any
      self._skipNextVoiceUpload = true
      rm.stop()
      wx.showToast({ title: '说话时间太短', icon: 'none' })
      return
    }
    rm.stop()
  },

  cancelRecord() {
    if (!this.data.recording) return
    const rm = this.ensureRecorder()
    const self = this as any
    self._skipNextVoiceUpload = true
    rm.stop()
    this.setData({ recording: false, voiceStartAt: 0 })
    wx.showToast({ title: '已取消录音', icon: 'none' })
  },

  uploadVoice(filePath: string) {
    this.setData({ transcribing: true })
    asr(filePath)
      .then((res) => {
        const text = (res && res.text) || ''
        if (!text) {
          wx.showToast({ title: '没听清，请重试', icon: 'none' })
          return
        }
        // 回填到输入框，用户可编辑后再发送
        this.setData({ inputText: text, canSend: text.trim().length > 0 })
        wx.showToast({ title: '已转写', icon: 'none' })
      })
      .catch((err) => {
        console.error('asr failed', err)
        wx.showToast({ title: '语音转写失败', icon: 'none' })
      })
      .finally(() => {
        this.setData({ transcribing: false })
      })
  },

  sendQuestion(text: string, mode: ChatPayload['mode'], imageLabel: string, imagePath = '') {
    const userMessage = this.createUserMessage(text, imageLabel, imagePath)
    const loadingMessage = this.createLoadingMessage()
    const payload: ChatPayload = {
      user_id: getUserId(),
      text,
      mode,
      image_label: imageLabel,
    }

    this.appendMessages([userMessage, loadingMessage])
    this.setData({ loadingAgent: true })

    this.fetchChat(payload, imagePath)
      .then((resp: ChatResp) => {
        this.replaceMessage(loadingMessage.id, this.createAgentMessage(loadingMessage.id, resp))
        this.saveConsultation(payload, resp)
      })
      .catch((err: unknown) => {
        console.error('chat failed', err)
        this.replaceMessage(loadingMessage.id, this.createAgentMessage(loadingMessage.id, mockError, true))
        wx.showToast({ title: '请求失败', icon: 'none' })
      })
      .finally(() => {
        this.setData({ loadingAgent: false })
      })
  },

  // 咨询记录快照非阻塞保存；MySQL 不可用时不影响当前对话展示。
  saveConsultation(payload: ChatPayload, resp: ChatResp) {
    if (!resp.consultation_id) return
    const snapshot = {
      user_id: payload.user_id,
      consultation_id: resp.consultation_id,
      question: payload.text,
      agent: resp.agent,
      intent: resp.route.intent,
      reply_snapshot: resp.reply,
      sources: resp.sources || [],
    }
    saveUserConsultation(snapshot).catch((err) => {
      console.warn('save consultation failed', err)
    })
  },

  fetchChat(payload: ChatPayload, imagePath = ''): Promise<ChatResp> {
    if (!USE_MOCK) {
      return payload.mode === 'image' && imagePath ? chatImage(imagePath, payload) : chat(payload)
    }

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
      resp.reply.title = '图片识别'
      resp.reply.summary = `已按图片模式识别：${payload.image_label || payload.text}`
      resp.reply.blocks = [
        { type: 'kv', label: '图片标签', value: payload.image_label || '报价单' },
        { type: 'kv', label: '识别结果', value: 'Mock 模式示例，真实模式会上传图片并调用视觉大模型。' },
        { type: 'warn', text: '避坑：维修前要求店家展示配件包装、型号与旧件。' },
      ]
      resp.reply.price_text = '价格需结合报价单明细确认'
      resp.reply.price_range = []
    }
    return resp
  },

  createUserMessage(text: string, imageLabel: string, imagePath = ''): Message {
    return {
      id: nextMessageId('user'),
      type: 'user',
      text,
      imageLabel,
      imagePath,
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
      steps: safeSteps(resp.steps),
      reply: safeReply(resp.reply),
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
    const pages = getCurrentPages()
    if (pages.length > 1) {
      wx.navigateBack()
      return
    }
    wx.reLaunch({ url: '/pages/index/index' })
  },

  goKb() {
    wx.navigateTo({ url: '/pages/kb/kb' })
  },

  goCamera(event: WechatMiniprogram.TouchEvent) {
    const label = String(event.currentTarget.dataset.label || '报价单')
    wx.navigateTo({ url: '/pages/camera/camera?label=' + encodeURIComponent(label) })
  },

  goProfile() {
    wx.navigateTo({ url: '/pages/profile/profile' })
  },
})
