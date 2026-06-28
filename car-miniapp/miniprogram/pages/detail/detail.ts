import { getKbDetail, KbItem, KbKind } from '../../utils/request'

type DetailLine = {
  text: string
}

type StepLine = {
  no: number
  text: string
}

type DetailData = {
  kind: KbKind
  id: string
  navTitle: string
  heroTitle: string
  heroSub: string
  heroTag: string
  reasonTitle: string
  reasonLines: DetailLine[]
  stepTitle: string
  steps: StepLine[]
  priceTitle: string
  priceLabel: string
  priceValue: string
  priceParts: DetailLine[]
  warnTitle: string
  warnText: string
  askText: string
  tone: string
}

type DtcRaw = {
  code?: string
  desc?: string
  plain?: string
  cause?: string
  level?: number
  logic?: string
  price_part_low?: number
  price_part_high?: number
  price_labor_low?: number
  price_labor_high?: number
}

type CostRaw = {
  cat?: string
  item?: string
  part_low?: number
  part_high?: number
  labor_low?: number
  labor_high?: number
  tip?: string
}

type SymptomRaw = {
  keywords?: string[]
  fault?: string
  level?: string
  tip?: string
  part_low?: number
  part_high?: number
  labor_low?: number
  labor_high?: number
}

const EMPTY_DETAIL: DetailData = {
  kind: 'dtc',
  id: '',
  navTitle: '故障码详情',
  heroTitle: '',
  heroSub: '',
  heroTag: '',
  reasonTitle: '',
  reasonLines: [],
  stepTitle: '',
  steps: [],
  priceTitle: '',
  priceLabel: '',
  priceValue: '',
  priceParts: [],
  warnTitle: '',
  warnText: '',
  askText: '',
  tone: '',
}

function line(text: string): DetailLine {
  return { text }
}

function numbered(items: string[]): StepLine[] {
  return items.filter(Boolean).map((text, index) => ({ no: index + 1, text }))
}

function splitParts(text: string): DetailLine[] {
  return String(text || '')
    .split(/[、,/，;；]/)
    .map((item) => item.trim())
    .filter(Boolean)
    .map(line)
}

function readNumber(raw: Record<string, unknown>, key: string): number {
  const value = raw[key]
  return typeof value === 'number' ? value : Number(value || 0)
}

function money(value: number | undefined): string {
  return `¥ ${Number(value || 0).toLocaleString()}`
}

function totalLow(raw: DtcRaw | CostRaw | SymptomRaw): number {
  const record = raw as Record<string, unknown>
  const part = readNumber(record, 'price_part_low') || readNumber(record, 'part_low')
  const labor = readNumber(record, 'price_labor_low') || readNumber(record, 'labor_low')
  return part + labor
}

function totalHigh(raw: DtcRaw | CostRaw | SymptomRaw): number {
  const record = raw as Record<string, unknown>
  const part = readNumber(record, 'price_part_high') || readNumber(record, 'part_high')
  const labor = readNumber(record, 'price_labor_high') || readNumber(record, 'labor_high')
  return part + labor
}

function priceParts(raw: DtcRaw | CostRaw | SymptomRaw): DetailLine[] {
  if ('price_part_low' in raw || 'price_labor_low' in raw) {
    const dtc = raw as DtcRaw
    return [
      line(`原厂/副厂零件：约 ${money(dtc.price_part_low)}-${money(dtc.price_part_high)}`),
      line(`工时费：约 ${money(dtc.price_labor_low)}-${money(dtc.price_labor_high)}`),
    ]
  }
  const common = raw as CostRaw | SymptomRaw
  return [
    line(`零件参考价：约 ${money(common.part_low)}-${money(common.part_high)}`),
    line(`工时费：约 ${money(common.labor_low)}-${money(common.labor_high)}`),
  ]
}

function buildDtcDetail(item: KbItem): DetailData {
  const raw = (item.raw || {}) as DtcRaw
  const level = Number(raw.level || item.level || 0)
  return {
    kind: 'dtc',
    id: item.id,
    navTitle: '故障码详情',
    heroTitle: raw.code || item.title,
    heroSub: raw.desc || item.summary,
    heroTag: `修复难度 ${item.stars || item.level_text}`,
    reasonTitle: '🎯 可能原因（按概率排序）',
    reasonLines: splitParts(raw.cause || item.tip.replace(/^可能原因[:：]\s*/, '')),
    stepTitle: '🚀 建议排查步骤',
    steps: numbered([
      '读取各缸缺火计数，定位是否集中于某一缸',
      '先更换火花塞或对调点火线圈，成本最低',
      '若故障仍在，观察喷油嘴与燃油压力',
      raw.logic || item.detail || '检查进气系统漏气与相关传感器数据',
    ]),
    priceTitle: '💰 费用参考',
    priceLabel: '市场总价区间',
    priceValue: `${money(totalLow(raw))} ~ ${money(totalHigh(raw))}`,
    priceParts: priceParts(raw),
    warnTitle: '⚠️ 避坑提示',
    warnText:
      level >= 4
        ? '该故障风险较高，请尽快到正规维修点检测，避免扩大损伤。维修前要求店家先给出排查路径和书面报价。'
        : '如维修店建议直接大拆发动机，请要求先按低成本方案逐项排查；多家门店报价再决策，避免过度维修。',
    askText: item.ask_text,
    tone: level >= 4 ? 'danger' : '',
  }
}

function buildCostDetail(item: KbItem): DetailData {
  const raw = (item.raw || {}) as CostRaw
  return {
    kind: 'cost',
    id: item.id,
    navTitle: '维修项目详情',
    heroTitle: raw.item || item.title,
    heroSub: raw.cat || item.subtitle || '维修项目',
    heroTag: '报价参考',
    reasonTitle: '🎯 项目说明',
    reasonLines: [
      line(`${raw.cat || item.subtitle || '当前车型'}常见维修项目：${raw.item || item.title}`),
      line('价格会受车型、零件品牌、城市和门店类型影响。'),
    ],
    stepTitle: '🚀 建议确认步骤',
    steps: numbered([
      '先确认报价是否拆分为零件费和工时费',
      '确认零件品牌、质保周期和是否成套更换',
      '要求门店先检查再报价，避免先拆后加价',
      raw.tip || item.tip || '对比 2-3 家门店报价后再决定。',
    ]),
    priceTitle: '💰 费用参考',
    priceLabel: '市场总价区间',
    priceValue: `${money(totalLow(raw))} ~ ${money(totalHigh(raw))}`,
    priceParts: priceParts(raw),
    warnTitle: '⚠️ 避坑提示',
    warnText: raw.tip || item.tip || '维修前确认零件品牌、数量、质保和工时，要求写入报价单。',
    askText: item.ask_text,
    tone: '',
  }
}

function buildSymptomDetail(item: KbItem): DetailData {
  const raw = (item.raw || {}) as SymptomRaw
  const keywords = Array.isArray(raw.keywords) ? raw.keywords : []
  const title = keywords[0] || item.title
  const high = raw.level === '高'
  return {
    kind: 'symptom',
    id: item.id,
    navTitle: '症状详情',
    heroTitle: title,
    heroSub: raw.fault || item.summary.replace(/^关联[:：]\s*/, ''),
    heroTag: `紧急程度 ${raw.level || item.level_text || '参考'}`,
    reasonTitle: '🎯 可能原因（按概率排序）',
    reasonLines: splitParts(raw.fault || item.summary.replace(/^关联[:：]\s*/, '')),
    stepTitle: '🚀 建议排查步骤',
    steps: numbered([
      '记录症状出现的速度、温度、挡位和路况',
      '先做外观与基础油液/磨损检查，排除低成本原因',
      '让门店给出检测证据，再决定是否更换零件',
      raw.tip || item.tip || '如涉及制动、转向、过热或机油报警，应优先停车检查。',
    ]),
    priceTitle: '💰 费用参考',
    priceLabel: '常见维修区间',
    priceValue: `${money(totalLow(raw))} ~ ${money(totalHigh(raw))}`,
    priceParts: priceParts(raw),
    warnTitle: '⚠️ 避坑提示',
    warnText:
      raw.tip ||
      item.tip ||
      (high ? '该症状风险较高，请尽快进厂检查，避免继续行驶扩大损伤。' : '先确认故障来源，再决定是否更换总成，避免过度维修。'),
    askText: item.ask_text,
    tone: high ? 'danger' : 'warn',
  }
}

function buildDetail(item: KbItem): DetailData {
  if (item.kind === 'cost') return buildCostDetail(item)
  if (item.kind === 'symptom') return buildSymptomDetail(item)
  return buildDtcDetail(item)
}

function safeDecode(value: string): string {
  try {
    return decodeURIComponent(value)
  } catch (e) {
    return value
  }
}

Page({
  data: {
    kind: 'dtc' as KbKind,
    id: 'P0300',
    loading: true,
    errorText: '',
    item: null as KbItem | null,
    detail: EMPTY_DETAIL,
  },

  onLoad(options: Record<string, string | undefined> = {}) {
    const kind = String(options.kind || 'dtc') as KbKind
    const id = safeDecode(String(options.id || options.code || 'P0300'))
    this.setData({ kind, id })
    this.loadDetail(kind, id)
  },

  loadDetail(kind: KbKind, id: string) {
    this.setData({ loading: true, errorText: '' })
    getKbDetail(kind, id)
      .then((item: KbItem) => {
        this.setData({
          item,
          detail: buildDetail(item),
          loading: false,
          errorText: '',
        })
      })
      .catch((err) => {
        console.error('load detail failed', err)
        this.setData({
          loading: false,
          errorText: '未找到该条维修指南详情，请返回知识库重新选择。',
        })
      })
  },

  goChat() {
    const ask = this.data.detail.askText || `${this.data.detail.heroTitle} 怎么处理？`
    wx.setStorageSync('cxz_pending_ask', ask)
    wx.reLaunch({ url: '/pages/index/index' })
  },

  goBack() {
    const pages = getCurrentPages()
    if (pages.length > 1) {
      wx.navigateBack()
      return
    }
    wx.reLaunch({ url: '/pages/kb/kb' })
  },

  goHome() {
    wx.reLaunch({ url: '/pages/index/index' })
  },

  goKb() {
    wx.navigateTo({ url: '/pages/kb/kb' })
  },

  goProfile() {
    wx.navigateTo({ url: '/pages/profile/profile' })
  },
})
