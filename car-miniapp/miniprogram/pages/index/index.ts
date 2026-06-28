import {
  asr,
  chat,
  chatImage,
  getContext,
  getUserId,
  ChatPayload,
  ChatReply,
  ChatResp,
} from '../../utils/request'
import { saveConsultation as saveUserConsultation } from '../../utils/user-api'
import { chooseVehicleImage, isChooseMediaCancel } from '../../utils/media'

type HomeMessageType = 'user' | 'agent' | 'loading'

type HomeMessage = {
  id: string
  type: HomeMessageType
  text?: string
  imageLabel?: string
  imagePath?: string
  agentName?: string
  intent?: string
  confidenceText?: string
  reply: ChatReply
  legal_note?: string
  error?: boolean
}

const EMPTY_REPLY: ChatReply = {
  title: '',
  summary: '',
  blocks: [],
  price_text: '',
  price_range: [],
}

const LOADING_REPLY: ChatReply = {
  title: '正在分析...',
  summary: '车小智正在调用真实 Agent，请稍等。',
  blocks: [],
  price_text: '',
  price_range: [],
}

const ERROR_REPLY: ChatReply = {
  title: '请求失败',
  summary: '暂时无法连接服务端，请确认后端已启动，并在微信开发者工具本地设置中关闭合法域名校验。',
  blocks: [{ type: 'warn', text: '如果是语音或拍照失败，请同时检查麦克风、相册和摄像头权限。' }],
  price_text: '',
  price_range: [],
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

function safeReply(value: ChatReply | undefined): ChatReply {
  if (!value) return { ...EMPTY_REPLY }
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
    inputText: '',
    canSend: false,
    loadingAgent: false,
    recording: false,
    transcribing: false,
    voiceStartAt: 0,
    scrollIntoView: '',
    messages: [] as HomeMessage[],
    context: {
      car_model: '2022款 丰田 卡罗拉 1.2T 豪华版',
      car_tag: '丰田 卡罗拉',
      vin: 'LFMA*********3456',
      mileage: '38,500 km',
      location: '北京',
    },
  },

  onShow() {
    this.loadContext()
    this.consumePendingAsk()
  },

  loadContext() {
    getContext(getUserId())
      .then((ctx) => {
        if (!ctx) return
        const parts = String(ctx.car_model || '').split(' ').filter(Boolean)
        const carTag = parts.length >= 3 ? `${parts[1]} ${parts[2]}` : ctx.car_model
        this.setData({
          context: {
            car_model: ctx.car_model,
            car_tag: carTag,
            vin: ctx.vin,
            mileage: ctx.mileage,
            location: ctx.location,
          },
        })
      })
      .catch((err) => {
        console.error('load context failed', err)
      })
  },

  consumePendingAsk() {
    let ask = ''
    try {
      ask = String(wx.getStorageSync('cxz_pending_ask') || '').trim()
      if (ask) wx.removeStorageSync('cxz_pending_ask')
    } catch (e) {
      ask = ''
    }
    if (ask) this.sendQuestion(ask, 'text', '')
  },

  onInput(event: WechatMiniprogram.Input) {
    const inputText = event.detail.value
    this.setData({ inputText, canSend: inputText.trim().length > 0 })
  },

  sendHomeText() {
    const text = (this.data.inputText || '').trim()
    if (!text) {
      wx.showToast({ title: '请输入问题', icon: 'none' })
      return
    }
    this.setData({ inputText: '', canSend: false })
    this.sendQuestion(text, 'text', '')
  },

  askHot(event: WechatMiniprogram.TouchEvent) {
    const ask = String(event.currentTarget.dataset.ask || '').trim()
    this.sendQuestion(ask || '发动机咕噜咕噜响', 'text', '')
  },

  goCamera(event: WechatMiniprogram.TouchEvent) {
    if (this.data.loadingAgent) return
    const label = String(event.currentTarget.dataset.label || '仪表盘')
    chooseVehicleImage(label)
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
        const text = String((res && res.text) || '').trim()
        if (!text) {
          wx.showToast({ title: '没听清，请重试', icon: 'none' })
          return
        }
        this.setData({ inputText: '', canSend: false })
        this.sendQuestion(text, 'text', '')
      })
      .catch((err) => {
        console.error('asr failed', err)
        const message = err && err.message ? String(err.message) : '语音转写失败'
        wx.showToast({ title: message.slice(0, 28), icon: 'none' })
      })
      .finally(() => {
        this.setData({ transcribing: false })
      })
  },

  sendQuestion(text: string, mode: ChatPayload['mode'], imageLabel: string, imagePath = '') {
    const question = (text || '').trim()
    if (!question || this.data.loadingAgent) return
    const userMessage = this.createUserMessage(question, imageLabel, imagePath)
    const loadingMessage = this.createLoadingMessage()
    const payload: ChatPayload = {
      user_id: getUserId(),
      text: question,
      mode,
      image_label: imageLabel,
    }

    this.appendMessages([userMessage, loadingMessage])
    this.setData({ loadingAgent: true })

    this.fetchChat(payload, imagePath)
      .then((resp) => {
        this.replaceMessage(loadingMessage.id, this.createAgentMessage(loadingMessage.id, resp))
        this.saveConsultation(payload, resp)
      })
      .catch((err) => {
        console.error('chat failed', err)
        this.replaceMessage(loadingMessage.id, this.createErrorMessage(loadingMessage.id))
        wx.showToast({ title: '请求失败', icon: 'none' })
      })
      .finally(() => {
        this.setData({ loadingAgent: false })
      })
  },

  fetchChat(payload: ChatPayload, imagePath = ''): Promise<ChatResp> {
    return payload.mode === 'image' && imagePath ? chatImage(imagePath, payload) : chat(payload)
  },

  saveConsultation(payload: ChatPayload, resp: ChatResp) {
    if (!resp.consultation_id) return
    saveUserConsultation({
      user_id: payload.user_id,
      consultation_id: resp.consultation_id,
      question: payload.text,
      agent: resp.agent,
      intent: resp.route.intent,
      title: resp.reply.title,
      summary: resp.reply.summary,
      reply_snapshot: resp.reply,
      sources: resp.sources || [],
    }).catch((err) => {
      console.warn('save consultation failed', err)
    })
  },

  createUserMessage(text: string, imageLabel: string, imagePath = ''): HomeMessage {
    return {
      id: nextMessageId('user'),
      type: 'user',
      text,
      imageLabel,
      imagePath,
      reply: { ...EMPTY_REPLY },
    }
  },

  createLoadingMessage(): HomeMessage {
    return {
      id: nextMessageId('loading'),
      type: 'loading',
      agentName: '车小智 Agent',
      intent: '识别中...',
      confidenceText: '0%',
      reply: { ...LOADING_REPLY },
    }
  },

  createAgentMessage(id: string, resp: ChatResp): HomeMessage {
    return {
      id,
      type: 'agent',
      agentName: resp.agent_meta.name,
      intent: resp.route.intent,
      confidenceText: confidenceText(resp.route.confidence),
      reply: safeReply(resp.reply),
      legal_note: resp.legal_note,
    }
  },

  createErrorMessage(id: string): HomeMessage {
    return {
      id,
      type: 'agent',
      agentName: '系统',
      intent: '请求失败',
      confidenceText: '0%',
      reply: { ...ERROR_REPLY },
      error: true,
    }
  },

  appendMessages(items: HomeMessage[]) {
    const messages = this.data.messages.concat(items)
    const tailId = items[items.length - 1].id
    this.setData({
      messages,
      scrollIntoView: `home-msg-${tailId}`,
    })
  },

  replaceMessage(id: string, next: HomeMessage) {
    const messages = this.data.messages.map((item) => (item.id === id ? next : item))
    this.setData({
      messages,
      scrollIntoView: `home-msg-${id}`,
    })
  },

  goKb() {
    wx.navigateTo({ url: '/pages/kb/kb' })
  },

  goProfile() {
    wx.navigateTo({ url: '/pages/profile/profile' })
  },

  goDetail(event: WechatMiniprogram.TouchEvent) {
    const code = String((event && event.currentTarget && event.currentTarget.dataset.code) || 'P0300')
    wx.navigateTo({ url: `/pages/detail/detail?code=${encodeURIComponent(code)}` })
  },
})
