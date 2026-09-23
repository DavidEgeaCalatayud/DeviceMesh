import { useEffect, useMemo, useState } from 'react'
import type { Device } from '../../entities/device/types'
import type { MetricSeries, NetworkDiagnostic } from '../../entities/telemetry/types'
import { getMetricHistory, getNetworkDiagnostic } from '../../shared/api/client'

const RANGE_OPTIONS = {
  '1h': { label: '1h', milliseconds: 60 * 60 * 1000, bucketSeconds: 30 },
  '6h': { label: '6h', milliseconds: 6 * 60 * 60 * 1000, bucketSeconds: 120 },
  '24h': { label: '24h', milliseconds: 24 * 60 * 60 * 1000, bucketSeconds: 300 },
  '7d': { label: '7d', milliseconds: 7 * 24 * 60 * 60 * 1000, bucketSeconds: 1800 },
} as const

type RangeKey = keyof typeof RANGE_OPTIONS

const METRIC_OPTIONS = [
  { name: 'network.latency.ms', label: 'Latency' },
  { name: 'network.jitter.ms', label: 'Jitter' },
  { name: 'network.packet_loss.percent', label: 'Packet loss' },
  { name: 'host.cpu.utilization.percent', label: 'CPU utilization' },
  { name: 'host.memory.utilization.percent', label: 'Memory utilization' },
] as const

function formatMetric(value: number, unit: string | null): string {
  const formatted = Math.abs(value) >= 100 ? value.toFixed(0) : value.toFixed(1)
  if (unit === 'percent') return `${formatted}%`
  return unit ? `${formatted} ${unit}` : formatted
}

function shortTime(timestamp: string): string {
  return new Date(timestamp).toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function MetricChart({ series, label }: { series: MetricSeries; label: string }) {
  if (series.points.length === 0) {
    return <div className="chartEmpty">No samples in this window.</div>
  }

  const width = 720
  const height = 220
  const padding = 18
  const values = series.points.map((point) => point.value)
  const minimum = Math.min(...values)
  const maximum = Math.max(...values)
  const span = maximum - minimum || 1
  const horizontalSpan = width - padding * 2
  const verticalSpan = height - padding * 2
  const coordinates = series.points.map((point, index) => {
    const x = series.points.length === 1
      ? width / 2
      : padding + (index / (series.points.length - 1)) * horizontalSpan
    const y = padding + ((maximum - point.value) / span) * verticalSpan
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })
  const latest = series.points[series.points.length - 1]

  return <div className="metricChart">
    <div className="metricChartHeader">
      <div><strong>{label}</strong><div className="muted">{series.points.length} chart point(s){series.truncated ? ' · truncated' : ''}</div></div>
      <div className="chartLatest">{formatMetric(latest.value, series.unit)}</div>
    </div>
    <svg className="chartSvg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${label} history`}>
      <line x1={padding} y1={padding} x2={padding} y2={height - padding} className="chartGridLine" />
      <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} className="chartGridLine" />
      <polyline points={coordinates.join(' ')} className="chartLine" vectorEffect="non-scaling-stroke" />
    </svg>
    <div className="chartAxis">
      <span>{shortTime(series.points[0].timestamp)}</span>
      <span>{formatMetric(minimum, series.unit)} – {formatMetric(maximum, series.unit)}</span>
      <span>{shortTime(latest.timestamp)}</span>
    </div>
  </div>
}

export function DiagnosticSummary({ diagnostic }: { diagnostic: NetworkDiagnostic }) {
  return <div className="diagnosticSummary">
    <div className="diagnosticHeader">
      <div>
        <div className="eyebrow">Network diagnosis · last 15m</div>
        <h3>{diagnostic.state === 'unknown' ? 'Insufficient data' : diagnostic.state}</h3>
      </div>
      <span className={`diagnosticBadge ${diagnostic.state}`}>{diagnostic.coverage} coverage</span>
    </div>
    <div className="diagnosticSignals">
      {diagnostic.signals.map((signal) => <div className="diagnosticSignal" key={signal.name}>
        <span>{METRIC_OPTIONS.find((metric) => metric.name === signal.name)?.label ?? signal.name}</span>
        <strong>{formatMetric(signal.latest, signal.unit)}</strong>
        <small>avg {formatMetric(signal.average, signal.unit)} · {signal.samples} sample(s)</small>
      </div>)}
    </div>
    <ul className="diagnosticReasons">
      {diagnostic.reasons.map((reason) => <li key={reason}>{reason}</li>)}
    </ul>
    <div className="diagnosticMethod">Heuristic: {diagnostic.method}. Measured signals are shown separately from this approximate classification.</div>
  </div>
}

export function TelemetryHistoryPanel({ devices }: { devices: Device[] }) {
  const [requestedDeviceId, setRequestedDeviceId] = useState('')
  const [range, setRange] = useState<RangeKey>('24h')
  const [metricName, setMetricName] = useState('network.latency.ms')
  const [series, setSeries] = useState<MetricSeries | null>(null)
  const [diagnostic, setDiagnostic] = useState<NetworkDiagnostic | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const selectedDeviceId = useMemo(() => {
    if (requestedDeviceId && devices.some((device) => device.id === requestedDeviceId)) {
      return requestedDeviceId
    }
    return devices[0]?.id ?? ''
  }, [devices, requestedDeviceId])

  useEffect(() => {
    if (!selectedDeviceId) return
    const controller = new AbortController()
    const selectedRange = RANGE_OPTIONS[range]
    const end = new Date()
    const start = new Date(end.getTime() - selectedRange.milliseconds)

    const load = async () => {
      setLoading(true)
      setError(null)
      try {
        const [nextSeries, nextDiagnostic] = await Promise.all([
          getMetricHistory(
            selectedDeviceId,
            metricName,
            start,
            end,
            selectedRange.bucketSeconds,
            controller.signal,
          ),
          getNetworkDiagnostic(selectedDeviceId, 15, controller.signal),
        ])
        if (!controller.signal.aborted) {
          setSeries(nextSeries)
          setDiagnostic(nextDiagnostic)
        }
      } catch (reason: unknown) {
        if (!(reason instanceof DOMException && reason.name === 'AbortError')) setError(String(reason))
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }

    void load()
    return () => controller.abort()
  }, [metricName, range, selectedDeviceId])

  const metricLabel = METRIC_OPTIONS.find((metric) => metric.name === metricName)?.label ?? metricName
  const visibleSeries = series?.deviceId === selectedDeviceId ? series : null
  const visibleDiagnostic = diagnostic?.deviceId === selectedDeviceId ? diagnostic : null

  return <section className="card telemetryPanel">
    <div className="panelHeader telemetryHeader">
      <div><div className="eyebrow">Time-series observability</div><h2>Metrics & network diagnostics</h2></div>
      {loading && <span className="muted">Loading…</span>}
    </div>
    <div className="telemetryControls">
      <label>Device<select value={selectedDeviceId} onChange={(event) => setRequestedDeviceId(event.target.value)}>
        {devices.map((device) => <option value={device.id} key={device.id}>{device.hostname ?? device.id}</option>)}
      </select></label>
      <label>Metric<select value={metricName} onChange={(event) => setMetricName(event.target.value)}>
        {METRIC_OPTIONS.map((metric) => <option value={metric.name} key={metric.name}>{metric.label}</option>)}
      </select></label>
      <div className="rangeControl" aria-label="Metric range">
        {Object.entries(RANGE_OPTIONS).map(([key, option]) => <button
          className={`filterButton ${range === key ? 'active' : ''}`}
          key={key}
          onClick={() => setRange(key as RangeKey)}
        >{option.label}</button>)}
      </div>
    </div>
    {error && <div className="errorBanner">{error}</div>}
    <div className="telemetryGrid">
      <div>{visibleSeries ? <MetricChart series={visibleSeries} label={metricLabel} /> : <div className="chartEmpty">Select a device with telemetry.</div>}</div>
      <div>{visibleDiagnostic ? <DiagnosticSummary diagnostic={visibleDiagnostic} /> : <div className="chartEmpty">No network diagnosis available.</div>}</div>
    </div>
  </section>
}
