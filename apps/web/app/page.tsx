'use client'

import { useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Card,
  Col,
  Descriptions,
  Divider,
  Empty,
  Progress,
  Row,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { apiConnectionError, fetchApi } from './config'
import { SITE_NAME } from './branding'
import { AppShell, MetricCard, PageIntro } from './components/AppShell'

const { Paragraph, Text, Title } = Typography

type ApiRecord = Record<string, unknown>

type DashboardData = {
  meta: ApiRecord | null
  market: ApiRecord | null
  signals: ApiRecord[]
  candidates: ApiRecord[]
  portfolioPlan: ApiRecord | null
  paperSummary: ApiRecord | null
  paperPositions: ApiRecord[]
  paperTrades: ApiRecord[]
  report: ApiRecord | null
  runs: ApiRecord[]
  validations: ApiRecord[]
  performance: ApiRecord[]
  themeHeatMeta: ApiRecord | null
  themeHeatMethodology: ApiRecord | null
  themeHeat: ApiRecord[]
}

type CandidateRow = ApiRecord & {
  key: string
  display: string
  symbol: string
  name: string
  theme: string
  strategies: string[]
  risk_level: string
  resonance_level: string
  resonance_role: string
  resonance_score: number
  secondary_theme?: string
  concepts?: string[]
  reasons?: string[]
  resonance_reasons?: string[]
  strategy_count?: number
  score?: number
  source_signals?: Array<{
    entry_note?: string
    exit_note?: string
    invalidation_note?: string
  }>
}

type TableRow = ApiRecord & {
  key: string
}

type ThemeHeatPayload = {
  meta?: ApiRecord | null
  methodology?: ApiRecord | null
  items?: ApiRecord[]
}

type DashboardOverviewPayload = {
  meta?: ApiRecord | null
  market?: ApiRecord | null
  signals?: ApiRecord[]
  candidates?: ApiRecord[]
  portfolio_plan?: ApiRecord | null
  paper_summary?: ApiRecord | null
  paper_positions?: ApiRecord[]
  paper_trades?: ApiRecord[]
  report?: ApiRecord | null
  runs?: ApiRecord[]
  validations?: ApiRecord[]
  performance?: ApiRecord[]
  theme_heat_meta?: ApiRecord | null
  theme_heat_methodology?: ApiRecord | null
  theme_heat?: ApiRecord[]
}

type ThemeHeatRow = TableRow & {
  theme: string
  count: number
  heat_score: number
  is_mainline: boolean
  heat_stage: string
  continuation_score: number
  duration_label: string
  duration_reasons: string[]
  invalidation_signals: string[]
  watch_points: string[]
  leaders: string[]
  stats: ApiRecord
}

const initialData: DashboardData = {
  meta: null,
  market: null,
  signals: [],
  candidates: [],
  portfolioPlan: null,
  paperSummary: null,
  paperPositions: [],
  paperTrades: [],
  report: null,
  runs: [],
  validations: [],
  performance: [],
  themeHeatMeta: null,
  themeHeatMethodology: null,
  themeHeat: [],
}

const strategyLabelMap: Record<string, string> = {
  leader: '龙头',
  hotmoney: '游资',
  sentiment: '情绪',
  composite: '综合',
}

const riskColorMap: Record<string, string> = {
  low: 'green',
  medium: 'orange',
  high: 'red',
}

const resonanceColorMap: Record<string, string> = {
  A: 'red',
  B: 'volcano',
  C: 'gold',
  D: 'default',
}

const resonanceRoleMap: Record<string, string> = {
  mainline_leader: '主线龙头',
  frontline_core: '前排核心',
  secondary_rotation: '轮动补涨',
  follower: '跟风观察',
  noise: '噪声票',
}

function asString(value: unknown, fallback = ''): string {
  return typeof value === 'string' && value ? value : fallback
}

function asNumber(value: unknown, fallback = 0): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []
}

function isApiRecord(value: unknown): value is ApiRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function asRecordArray(value: unknown): ApiRecord[] {
  return Array.isArray(value) ? value.filter(isApiRecord) : []
}

function strategyLabel(value: string): string {
  return strategyLabelMap[value] || value
}

function percentValue(value: unknown): string {
  return `${asNumber(value)}%`
}

function normalizePaperSummary(value: ApiRecord | null | undefined): ApiRecord | null {
  if (!value) return null
  const portfolio = isApiRecord(value.portfolio) ? value.portfolio : null
  return portfolio ? { ...value, ...portfolio } : value
}

function dashboardOverviewToData(payload: DashboardOverviewPayload): DashboardData {
  return {
    meta: payload.meta || null,
    market: payload.market || null,
    signals: asRecordArray(payload.signals),
    candidates: asRecordArray(payload.candidates),
    portfolioPlan: payload.portfolio_plan || null,
    paperSummary: normalizePaperSummary(payload.paper_summary),
    paperPositions: asRecordArray(payload.paper_positions),
    paperTrades: asRecordArray(payload.paper_trades),
    report: payload.report || null,
    runs: asRecordArray(payload.runs),
    validations: asRecordArray(payload.validations),
    performance: asRecordArray(payload.performance),
    themeHeatMeta: payload.theme_heat_meta || null,
    themeHeatMethodology: payload.theme_heat_methodology || null,
    themeHeat: asRecordArray(payload.theme_heat),
  }
}

async function loadLegacyDashboardData(): Promise<DashboardData> {
  const openApi = await fetchApi<{ paths?: Record<string, unknown> }>('/openapi.json')
  const paths = openApi?.paths || {}
  const hasPath = (path: string) => Boolean(paths[path])

  const [
    meta,
    market,
    signals,
    candidates,
    portfolioPlan,
    paperSummary,
    paperPositions,
    paperTrades,
    report,
    runs,
    validations,
    performance,
    themeHeatPayload,
  ] = await Promise.all([
    fetchApi<ApiRecord | null>('/api/meta', null),
    fetchApi<ApiRecord | null>('/api/market/overview', null),
    fetchApi<ApiRecord[]>('/api/signals', []),
    hasPath('/api/candidates') ? fetchApi<ApiRecord[]>('/api/candidates', []) : Promise.resolve([]),
    hasPath('/api/portfolio-plan') ? fetchApi<ApiRecord | null>('/api/portfolio-plan', null) : Promise.resolve(null),
    hasPath('/api/paper/summary') ? fetchApi<ApiRecord | null>('/api/paper/summary', null) : Promise.resolve(null),
    hasPath('/api/paper/positions') ? fetchApi<ApiRecord[]>('/api/paper/positions', []) : Promise.resolve([]),
    hasPath('/api/paper/trades') ? fetchApi<ApiRecord[]>('/api/paper/trades', []) : Promise.resolve([]),
    fetchApi<ApiRecord | null>('/api/report/daily', null),
    fetchApi<ApiRecord[]>('/api/history/runs', []),
    fetchApi<ApiRecord[]>('/api/history/validations', []),
    fetchApi<ApiRecord[]>('/api/analytics/strategy-performance', []),
    fetchApi<ThemeHeatPayload>('/api/themes/heat', { items: [] }),
  ])

  return {
    meta,
    market,
    signals,
    candidates,
    portfolioPlan,
    paperSummary: normalizePaperSummary(paperSummary),
    paperPositions,
    paperTrades,
    report,
    runs,
    validations,
    performance,
    themeHeatMeta: themeHeatPayload.meta || null,
    themeHeatMethodology: themeHeatPayload.methodology || null,
    themeHeat: themeHeatPayload.items || [],
  }
}

async function loadDashboardData(): Promise<DashboardData> {
  try {
    const payload = await fetchApi<DashboardOverviewPayload>('/api/dashboard/overview')
    return dashboardOverviewToData(payload)
  } catch {
    return loadLegacyDashboardData()
  }
}

export default function Page() {
  const [data, setData] = useState<DashboardData>(initialData)
  const [selectedSignalKey, setSelectedSignalKey] = useState<string | null>(null)
  const [selectedThemeKey, setSelectedThemeKey] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let ignore = false

    async function load() {
      setLoading(true)
      setError('')

      try {
        const dashboardData = await loadDashboardData()

        if (ignore) return

        setData(dashboardData)
      } catch (err) {
        if (!ignore) {
          setError(err instanceof Error ? err.message : apiConnectionError().message)
        }
      } finally {
        if (!ignore) {
          setLoading(false)
        }
      }
    }

    load()

    return () => {
      ignore = true
    }
  }, [])

  const candidates = useMemo<CandidateRow[]>(() => {
    return data.candidates.map((record, index) => {
      const symbol = asString(record.symbol, '-')
      const name = asString(record.name, '未命名')
      return {
        ...record,
        key: `candidate-${symbol}-${index}`,
        display: `${name} (${symbol})`,
        symbol,
        name,
        theme: asString(record.theme, '未分类'),
        strategies: asStringArray(record.strategies),
        risk_level: asString(record.risk_level, 'medium'),
        resonance_level: asString(record.resonance_level, 'D'),
        resonance_role: asString(record.resonance_role, 'follower'),
        resonance_score: asNumber(record.resonance_score),
        secondary_theme: asString(record.secondary_theme, '-'),
        concepts: asStringArray(record.concepts),
        reasons: asStringArray(record.reasons),
        resonance_reasons: asStringArray(record.resonance_reasons),
        strategy_count: asNumber(record.strategy_count),
        score: asNumber(record.score),
        source_signals: asRecordArray(record.source_signals) as CandidateRow['source_signals'],
      }
    })
  }, [data.candidates])

  useEffect(() => {
    if (!candidates.length) {
      setSelectedSignalKey(null)
      return
    }
    if (!selectedSignalKey || !candidates.find((item) => item.key === selectedSignalKey)) {
      setSelectedSignalKey(candidates[0].key)
    }
  }, [candidates, selectedSignalKey])

  const selectedSignal = candidates.find((item) => item.key === selectedSignalKey) || null
  const themeHeat = useMemo<ThemeHeatRow[]>(() => {
    return data.themeHeat.map((record, index) => ({
      ...record,
      key: asString(record.theme, `theme-${index}`),
      theme: asString(record.theme, '未分类'),
      count: asNumber(record.count),
      heat_score: asNumber(record.heat_score),
      is_mainline: Boolean(record.is_mainline),
      heat_stage: asString(record.heat_stage, '观察'),
      continuation_score: asNumber(record.continuation_score),
      duration_label: asString(record.duration_label, '暂无'),
      duration_reasons: asStringArray(record.duration_reasons),
      invalidation_signals: asStringArray(record.invalidation_signals),
      watch_points: asStringArray(record.watch_points),
      leaders: asStringArray(record.leaders),
      stats: typeof record.stats === 'object' && record.stats !== null && !Array.isArray(record.stats) ? record.stats as ApiRecord : {},
    }))
  }, [data.themeHeat])
  const mainlineThemes = data.themeHeat.filter((item) => Boolean(item.is_mainline)).map((item) => asString(item.theme))
  const selectedTheme = themeHeat.find((item) => item.key === selectedThemeKey) || themeHeat[0] || null
  const selectedThemePeers = selectedSignal
    ? candidates.filter((item) => item.key !== selectedSignal.key && item.theme === selectedSignal.theme)
    : []
  const selectedThemeRank = selectedSignal
    ? data.themeHeat.findIndex((item) => asString(item.theme) === selectedSignal.theme) + 1
    : 0
  const candidatePlan = asRecordArray(data.portfolioPlan?.candidate_plan).map((item, index) => ({
    ...item,
    key: asString(item.symbol, `plan-${index}`),
  }))
  const strategyWeights = asRecordArray(data.portfolioPlan?.strategy_weights)
  const openPositions = data.paperPositions
    .filter((item) => item.status === 'open')
    .map((item) => ({ ...item, key: `pos-${String(item.id)}` }))
  const recentTrades = data.paperTrades.slice(0, 8).map((item) => ({ ...item, key: `trade-${String(item.id)}` }))
  const runs = data.runs.map((record) => ({ ...record, key: String(record.id) }))
  const validations = data.validations.map((record) => ({
    ...record,
    key: String(record.id),
    display: `${asString(record.name, '-')} (${asString(record.symbol, '-')})`,
  }))
  const performance = data.performance.map((record) => ({ ...record, key: asString(record.strategy, String(record.bucket || 'strategy')) }))

  useEffect(() => {
    if (!themeHeat.length) {
      setSelectedThemeKey(null)
      return
    }
    if (!selectedThemeKey || !themeHeat.find((item) => item.key === selectedThemeKey)) {
      setSelectedThemeKey(themeHeat[0].key)
    }
  }, [selectedThemeKey, themeHeat])

  const signalColumns: ColumnsType<CandidateRow> = [
    {
      title: '候选标的',
      dataIndex: 'display',
      width: 180,
      render: (value: string, record) => (
        <Space orientation="vertical" size={2}>
          <Text strong>{value}</Text>
          <Text type="secondary">{record.symbol}</Text>
        </Space>
      ),
    },
    {
      title: '策略共识',
      dataIndex: 'strategies',
      width: 180,
      render: (values: string[]) => (
        <Space wrap>
          {values.map((value) => <Tag color="blue" key={value}>{strategyLabel(value)}</Tag>)}
        </Space>
      ),
    },
    {
      title: '共振等级',
      dataIndex: 'resonance_level',
      width: 110,
      render: (value: string) => <Tag color={resonanceColorMap[value] || 'default'}>{value}</Tag>,
    },
    {
      title: '共振角色',
      dataIndex: 'resonance_role',
      width: 136,
      render: (value: string) => <Tag color="purple">{resonanceRoleMap[value] || value}</Tag>,
    },
    {
      title: '主题材',
      dataIndex: 'theme',
      width: 136,
      render: (value: string) => <Tag color="gold">{value || '未分类'}</Tag>,
    },
    {
      title: '共振分',
      dataIndex: 'resonance_score',
      width: 150,
      render: (value: number) => (
        <Space orientation="vertical" size={2} style={{ width: 120 }}>
          <Text strong>{value}</Text>
          <Progress percent={value} size="small" showInfo={false} />
        </Space>
      ),
    },
    {
      title: '风险',
      dataIndex: 'risk_level',
      width: 100,
      render: (value: string) => <Tag color={riskColorMap[value] || 'default'}>{value}</Tag>,
    },
  ]

  const planColumns: ColumnsType<TableRow> = [
    { title: '标的', dataIndex: 'display', key: 'display', width: 180 },
    { title: '目标仓位', dataIndex: 'target_weight_pct', key: 'target_weight_pct', width: 120, render: percentValue },
    { title: '共振等级', dataIndex: 'resonance_level', key: 'resonance_level', width: 120 },
    { title: '主题材', dataIndex: 'theme', key: 'theme', width: 140 },
    {
      title: '策略共识',
      dataIndex: 'strategies',
      key: 'strategies',
      width: 220,
      render: (values: unknown) => asStringArray(values).map(strategyLabel).join(' / '),
    },
  ]

  const runColumns: ColumnsType<TableRow> = [
    { title: '运行 ID', dataIndex: 'id', key: 'id', width: 220 },
    { title: '日期', dataIndex: 'trade_date', key: 'trade_date', width: 130 },
    { title: '数据源', dataIndex: 'source', key: 'source', width: 120 },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 220 },
  ]

  const validationColumns: ColumnsType<TableRow> = [
    { title: '标的', dataIndex: 'display', key: 'display', width: 180 },
    { title: '策略', dataIndex: 'strategy', key: 'strategy', width: 120 },
    { title: '1D%', dataIndex: 'return_1d', key: 'return_1d', width: 100 },
    { title: '3D%', dataIndex: 'return_3d', key: 'return_3d', width: 100 },
    { title: '5D%', dataIndex: 'return_5d', key: 'return_5d', width: 100 },
    { title: '结果', dataIndex: 'outcome_label', key: 'outcome_label', width: 120 },
  ]

  const perfColumns: ColumnsType<TableRow> = [
    { title: '策略', dataIndex: 'strategy', key: 'strategy', width: 120 },
    { title: '样本数', dataIndex: 'count', key: 'count', width: 100 },
    { title: '1日均值', dataIndex: 'avg_return_1d', key: 'avg_return_1d', width: 110 },
    { title: '3日均值', dataIndex: 'avg_return_3d', key: 'avg_return_3d', width: 110 },
    { title: '5日均值', dataIndex: 'avg_return_5d', key: 'avg_return_5d', width: 110 },
    { title: '1日胜率', dataIndex: 'win_rate_1d', key: 'win_rate_1d', width: 130 },
  ]

  const themeHeatColumns: ColumnsType<ThemeHeatRow> = [
    {
      title: '题材',
      dataIndex: 'theme',
      key: 'theme',
      width: 180,
      render: (value: string, record) => (
        <Space wrap>
          <Tag color="volcano">{value}</Tag>
          {record.is_mainline ? <Tag color="red">主线</Tag> : null}
        </Space>
      ),
    },
    {
      title: '强度/持续',
      dataIndex: 'continuation_score',
      key: 'continuation_score',
      width: 170,
      render: (value: number, record) => (
        <Space orientation="vertical" size={2} style={{ width: 130 }}>
          <Text strong>{record.heat_score} / {value}</Text>
          <Progress percent={value} size="small" showInfo={false} />
          <Text type="secondary">{record.heat_stage}</Text>
        </Space>
      ),
    },
    {
      title: '预计持续',
      dataIndex: 'duration_label',
      key: 'duration_label',
      width: 120,
      render: (value: string) => <Tag color="blue">{value}</Tag>,
    },
    { title: '出现数', dataIndex: 'count', key: 'count', width: 90 },
    {
      title: '代表个股',
      dataIndex: 'leaders',
      key: 'leaders',
      width: 280,
      render: (leaders: string[]) => (
        <Space wrap>
          {leaders.map((item) => <Tag key={item}>{item}</Tag>)}
        </Space>
      ),
    },
  ]

  const positionColumns: ColumnsType<TableRow> = [
    { title: '标的', dataIndex: 'name', key: 'name', width: 120 },
    { title: '仓位', dataIndex: 'target_weight_pct', key: 'target_weight_pct', width: 100, render: percentValue },
    { title: '开仓日', dataIndex: 'opened_trade_date', key: 'opened_trade_date', width: 130 },
    { title: '入场价', dataIndex: 'entry_price', key: 'entry_price', width: 100 },
  ]

  const tradeColumns: ColumnsType<TableRow> = [
    { title: '日期', dataIndex: 'trade_date', key: 'trade_date', width: 120 },
    { title: '标的', dataIndex: 'name', key: 'name', width: 120 },
    { title: '方向', dataIndex: 'side', key: 'side', width: 90 },
    { title: '价格', dataIndex: 'price', key: 'price', width: 100 },
    { title: '仓位', dataIndex: 'weight_pct', key: 'weight_pct', width: 100, render: percentValue },
  ]

  return (
    <AppShell>
      <Space orientation="vertical" size={16} style={{ width: '100%' }}>
        <PageIntro
          eyebrow="首页"
          title={SITE_NAME}
          description="研究优先的 A 股战法系统：汇总市场情绪、策略共振、组合建议、模拟持仓和验证表现。"
        />

        {error ? <Alert type="error" showIcon title="加载失败" description={error} /> : null}
        {asString(data.meta?.source) === 'sample_fallback' ? (
          <Alert
            type="warning"
            showIcon
            title="当前使用兜底样本"
            description="真实行情源暂时不可用，系统正在使用内置真实 A 股样本保持页面可运行；样本仅用于功能演示和策略流程验证，不代表实时市场推荐。"
          />
        ) : null}

        <Row gutter={[16, 16]}>
          <Col xs={24} sm={12} xl={6}>
            <MetricCard title="数据源" value={asString(data.meta?.source, '暂无')} />
          </Col>
          <Col xs={24} sm={12} xl={6}>
            <MetricCard title="交易日" value={asString(data.meta?.trade_date, '暂无')} />
          </Col>
          <Col xs={24} sm={12} xl={6}>
            <MetricCard title="情绪阶段" value={asString(data.market?.market_sentiment_stage, '暂无')} />
          </Col>
          <Col xs={24} sm={12} xl={6}>
            <MetricCard title="最高连板" value={asNumber(data.market?.highest_board)} />
          </Col>
        </Row>

        <Card title="今日策略组合建议" loading={loading}>
          <Row gutter={[16, 16]}>
            <Col xs={24} sm={12} xl={4}>
              <MetricCard title="风险模式" value={asString(data.portfolioPlan?.risk_mode, '暂无')} />
            </Col>
            <Col xs={24} sm={12} xl={4}>
              <MetricCard title="执行策略" value={asString(data.portfolioPlan?.execution_policy, '暂无')} />
            </Col>
            <Col xs={24} sm={12} xl={4}>
              <MetricCard title="风险预算" value={asNumber(data.portfolioPlan?.risk_budget_pct)} suffix="%" />
            </Col>
            <Col xs={24} sm={12} xl={4}>
              <MetricCard title="最大持仓数" value={asNumber(data.portfolioPlan?.max_positions)} />
            </Col>
            <Col xs={24} sm={12} xl={4}>
              <MetricCard title="单题材上限" value={asNumber(data.portfolioPlan?.max_theme_exposure_pct)} suffix="%" />
            </Col>
            <Col xs={24} sm={12} xl={4}>
              <MetricCard title="禁止交易" value={data.portfolioPlan?.no_trade ? '是' : '否'} />
            </Col>
          </Row>

          <Divider />
          <Space orientation="vertical" size={12} style={{ width: '100%' }}>
            <div>
              <Text strong>启用策略</Text>
              <div className="tag-block">
                {strategyWeights.length ? strategyWeights.map((item) => (
                  <Tag key={`sw-${asString(item.strategy)}`} color="blue">
                    {asString(item.label)}: 权重 {asNumber(item.weight_pct)}% / 暴露 {asNumber(item.planned_pct)}% / 上限 {asNumber(item.cap_pct)}%
                  </Tag>
                )) : <Text type="secondary">暂无策略权重。</Text>}
              </div>
            </div>
            <div>
              <Text strong>组合备注</Text>
              <ul className="compact-list">
                {asStringArray(data.portfolioPlan?.notes).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
            <Table
              className="app-table"
              pagination={false}
              dataSource={candidatePlan}
              columns={planColumns}
              scroll={{ x: 820 }}
              size="middle"
            />
          </Space>
        </Card>

        <Card title="模拟组合" loading={loading}>
          <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
            <Col xs={24} sm={12} xl={4}>
              <MetricCard title="持仓中" value={asNumber(data.paperSummary?.open_positions)} />
            </Col>
            <Col xs={24} sm={12} xl={4}>
              <MetricCard title="已平仓" value={asNumber(data.paperSummary?.closed_positions)} />
            </Col>
            <Col xs={24} sm={12} xl={4}>
              <MetricCard title="当前仓位" value={asNumber(data.paperSummary?.open_weight_pct)} suffix="%" />
            </Col>
            <Col xs={24} sm={12} xl={4}>
              <MetricCard title="浮动收益" value={asNumber(data.paperSummary?.unrealized_pnl_pct)} suffix="%" />
            </Col>
            <Col xs={24} sm={12} xl={4}>
              <MetricCard title="已实现收益" value={asNumber(data.paperSummary?.realized_pnl_pct)} suffix="%" />
            </Col>
            <Col xs={24} sm={12} xl={4}>
              <MetricCard title="胜率" value={asNumber(data.paperSummary?.win_rate_pct)} suffix="%" />
            </Col>
          </Row>
          <Row gutter={[16, 16]}>
            <Col xs={24} xl={12}>
              <div className="embedded-panel">
                <Text strong>当前持仓</Text>
                <Table
                  className="app-table"
                  pagination={false}
                  dataSource={openPositions}
                  columns={positionColumns}
                  scroll={{ x: 520 }}
                  size="small"
                />
              </div>
            </Col>
            <Col xs={24} xl={12}>
              <div className="embedded-panel">
                <Text strong>近期模拟交易</Text>
                <Table
                  className="app-table"
                  pagination={false}
                  dataSource={recentTrades}
                  columns={tradeColumns}
                  scroll={{ x: 560 }}
                  size="small"
                />
              </div>
            </Col>
          </Row>
        </Card>

        <Card title="今日研究摘要" loading={loading}>
          <Paragraph>{asString(data.report?.summary_cn, '暂无摘要')}</Paragraph>
          <Row gutter={[16, 16]}>
            <Col xs={24} md={12}>
              <Text strong>主线题材</Text>
              <div className="tag-block">
                {asStringArray(data.report?.mainline_themes).map((item) => <Tag key={item} color="red">{item}</Tag>)}
              </div>
            </Col>
            <Col xs={24} md={12}>
              <Text strong>强共振候选</Text>
              <div className="tag-block">
                {asStringArray(data.report?.focus_candidates).map((item) => <Tag key={item} color="volcano">{item}</Tag>)}
              </div>
            </Col>
            <Col xs={24} md={12}>
              <Text strong>观察名单</Text>
              <div className="tag-block">
                {asStringArray(data.report?.observe_candidates).map((item) => <Tag key={item} color="gold">{item}</Tag>)}
              </div>
            </Col>
            <Col xs={24} md={12}>
              <Text strong>回避名单</Text>
              <div className="tag-block">
                {asStringArray(data.report?.avoid_candidates).map((item) => <Tag key={item}>{item}</Tag>)}
              </div>
            </Col>
          </Row>
          <Divider />
          <Text strong>明日计划</Text>
          <ul className="compact-list">
            {asStringArray(data.report?.tomorrow_plan).map((item) => <li key={item}>{item}</li>)}
          </ul>
        </Card>

        <Row gutter={[16, 16]} align="stretch">
          <Col xs={24} xl={13}>
            <Card title="题材热度分析与持续时间预测" loading={loading} style={{ height: '100%' }}>
              <Space orientation="vertical" size={12} style={{ width: '100%' }}>
                <Alert
                  type="info"
                  showIcon
                  title={`市场情绪：${asString(data.themeHeatMeta?.market_stage_cn, '暂无')}`}
                  description={asString(data.themeHeatMethodology?.duration_note, '持续时间为模型估计，用于盘后研究和次日验证。')}
                />
              <Table
                className="app-table"
                columns={themeHeatColumns}
                dataSource={themeHeat}
                pagination={{ pageSize: 6 }}
                scroll={{ x: 900 }}
                size="middle"
                  rowClassName={(record) => record.key === selectedThemeKey ? 'selected-signal-row' : ''}
                  onRow={(record) => ({
                    onClick: () => setSelectedThemeKey(record.key),
                    style: { cursor: 'pointer' },
                  })}
              />
              </Space>
            </Card>
          </Col>
          <Col xs={24} xl={11}>
            <Card title="选中题材持续性拆解" loading={loading} style={{ height: '100%' }}>
              {selectedTheme ? (
                <Space orientation="vertical" size={12} style={{ width: '100%' }}>
                  <Space wrap>
                    <Tag color="volcano">{selectedTheme.theme}</Tag>
                    {selectedTheme.is_mainline ? <Tag color="red">主线</Tag> : null}
                    <Tag color="blue">{selectedTheme.heat_stage}</Tag>
                    <Tag color="geekblue">预计 {selectedTheme.duration_label}</Tag>
                  </Space>
                  <Row gutter={[12, 12]}>
                    <Col xs={12} md={6}>
                      <MetricCard title="热度分" value={selectedTheme.heat_score} />
                    </Col>
                    <Col xs={12} md={6}>
                      <MetricCard title="持续性分" value={selectedTheme.continuation_score} />
                    </Col>
                    <Col xs={12} md={6}>
                      <MetricCard title="平均涨幅" value={asNumber(selectedTheme.stats.avg_pct_change)} suffix="%" />
                    </Col>
                    <Col xs={12} md={6}>
                      <MetricCard title="最高连板" value={asNumber(selectedTheme.stats.top_board)} />
                    </Col>
                  </Row>
                  <Descriptions column={1} size="small" bordered>
                    <Descriptions.Item label="平均量比">{asNumber(selectedTheme.stats.avg_volume_ratio)}</Descriptions.Item>
                    <Descriptions.Item label="平均换手">{asNumber(selectedTheme.stats.avg_turnover_rate)}%</Descriptions.Item>
                    <Descriptions.Item label="资金强度">{asNumber(selectedTheme.stats.funding_score)}</Descriptions.Item>
                    <Descriptions.Item label="龙头强度">{asNumber(selectedTheme.stats.leadership_score)}</Descriptions.Item>
                  </Descriptions>
                  <div>
                    <Text strong>预测理由</Text>
                    <ul className="compact-list">
                      {selectedTheme.duration_reasons.map((item) => <li key={`duration-${item}`}>{item}</li>)}
                    </ul>
                  </div>
                  <div>
                    <Text strong>观察点</Text>
                    <ul className="compact-list">
                      {selectedTheme.watch_points.map((item) => <li key={`watch-${item}`}>{item}</li>)}
                    </ul>
                  </div>
                  <div>
                    <Text strong>失效信号</Text>
                    <ul className="compact-list">
                      {selectedTheme.invalidation_signals.map((item) => <li key={`invalid-${item}`}>{item}</li>)}
                    </ul>
                  </div>
                  <div>
                    <Text strong>代表个股</Text>
                    <div className="tag-block">
                      {selectedTheme.leaders.map((item) => <Tag key={`leader-${item}`}>{item}</Tag>)}
                    </div>
                  </div>
                </Space>
              ) : (
                <Empty description="点击题材后显示持续性拆解" />
              )}
            </Card>
          </Col>
        </Row>

        <Row gutter={[16, 16]} align="stretch">
          <Col xs={24}>
            <Card title="强共振候选池" loading={loading} style={{ height: '100%' }}>
              <Table
                className="app-table"
                columns={signalColumns}
                dataSource={candidates}
                pagination={{ pageSize: 6 }}
                scroll={{ x: 980 }}
                rowClassName={(record) => record.key === selectedSignalKey ? 'selected-signal-row' : ''}
                onRow={(record) => ({
                  onClick: () => setSelectedSignalKey(record.key),
                  style: { cursor: 'pointer' },
                })}
              />
            </Card>
          </Col>
        </Row>

        <Card title="选中核心说明">
          {selectedSignal ? (
            <Row gutter={[16, 16]}>
              <Col xs={24} lg={10}>
                <Title level={4} style={{ marginBottom: 4 }}>{selectedSignal.name}</Title>
                <Text type="secondary">{selectedSignal.symbol}</Text>
                <div className="tag-block">
                  {selectedSignal.strategies.map((value) => <Tag color="blue" key={value}>{strategyLabel(value)}</Tag>)}
                  <Tag color={resonanceColorMap[selectedSignal.resonance_level] || 'default'}>共振等级：{selectedSignal.resonance_level}</Tag>
                  <Tag color="purple">共振角色：{resonanceRoleMap[selectedSignal.resonance_role] || selectedSignal.resonance_role}</Tag>
                  <Tag color="gold">主题材：{selectedSignal.theme}</Tag>
                  <Tag color="lime">次题材：{selectedSignal.secondary_theme || '-'}</Tag>
                  <Tag color={riskColorMap[selectedSignal.risk_level] || 'default'}>风险：{selectedSignal.risk_level}</Tag>
                  <Tag color="magenta">共振分：{selectedSignal.resonance_score}</Tag>
                </div>
              </Col>
              <Col xs={24} lg={14}>
                <Descriptions column={1} size="small" bordered>
                  <Descriptions.Item label="主线判断">
                    {mainlineThemes.includes(selectedSignal.theme) ? '是，属于当前主线题材' : '否，暂不属于主线第一梯队'}
                  </Descriptions.Item>
                  <Descriptions.Item label="题材热度排名">
                    {selectedThemeRank > 0 ? `第 ${selectedThemeRank} 名` : '未进入热度榜'}
                  </Descriptions.Item>
                  <Descriptions.Item label="策略共识">
                    {selectedSignal.strategies.map(strategyLabel).join(' / ') || '单策略'}
                  </Descriptions.Item>
                  <Descriptions.Item label="入场说明">
                    {selectedSignal.source_signals?.[0]?.entry_note || '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="退出说明">
                    {selectedSignal.source_signals?.[0]?.exit_note || '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="失效条件">
                    {selectedSignal.source_signals?.[0]?.invalidation_note || '-'}
                  </Descriptions.Item>
                </Descriptions>
              </Col>
              <Col xs={24} md={12}>
                <Text strong>概念列表</Text>
                <div className="tag-block">
                  {(selectedSignal.concepts || []).slice(0, 8).map((concept) => (
                    <Tag key={`${selectedSignal.key}-${concept}`} color="cyan">{concept}</Tag>
                  ))}
                </div>
              </Col>
              <Col xs={24} md={12}>
                <Text strong>同题材代表股对比</Text>
                <div className="tag-block">
                  {selectedThemePeers.length > 0 ? selectedThemePeers.slice(0, 6).map((peer) => (
                    <Tag key={peer.key} color="magenta">
                      {peer.name}({peer.symbol}) · {peer.score}
                    </Tag>
                  )) : <Text type="secondary">当前候选池中暂无更多同题材代表股。</Text>}
                </div>
              </Col>
              <Col xs={24} md={12}>
                <Text strong>核心理由</Text>
                <div className="tag-block">
                  {(selectedSignal.reasons || []).map((reason) => (
                    <Tag key={`${selectedSignal.key}-reason-${reason}`} color="geekblue">{reason}</Tag>
                  ))}
                </div>
              </Col>
              <Col xs={24} md={12}>
                <Text strong>共振说明</Text>
                <div className="tag-block">
                  {(selectedSignal.resonance_reasons || []).map((reason) => (
                    <Tag key={`${selectedSignal.key}-resonance-${reason}`} color="magenta">{reason}</Tag>
                  ))}
                </div>
              </Col>
            </Row>
          ) : (
            <Empty description="点击候选行后显示对应标的说明" />
          )}
        </Card>

        <Row gutter={[16, 16]}>
          <Col xs={24} xl={10}>
            <Card title="历史运行" loading={loading}>
              <Table className="app-table" columns={runColumns} dataSource={runs} pagination={{ pageSize: 5 }} scroll={{ x: 690 }} />
            </Card>
          </Col>
          <Col xs={24} xl={14}>
            <Card title="验证结果" loading={loading}>
              <Table className="app-table" columns={validationColumns} dataSource={validations} pagination={{ pageSize: 5 }} scroll={{ x: 720 }} />
            </Card>
          </Col>
        </Row>

        <Card title="策略表现">
          <Table className="app-table" columns={perfColumns} dataSource={performance} pagination={false} scroll={{ x: 690 }} />
        </Card>
      </Space>
    </AppShell>
  )
}
