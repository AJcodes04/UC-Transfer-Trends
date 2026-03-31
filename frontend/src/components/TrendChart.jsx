import { useState, useCallback } from 'react'
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts'
import { SegmentedControl } from '@mantine/core'
import { getUCColor } from '../utils/ucColors'

function ChartTooltip({ active, payload, label, suffix }) {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: 'white', border: '1px solid #ccc',
      borderRadius: 6, padding: '8px 12px', fontSize: 13,
      maxHeight: 300, overflowY: 'auto',
      boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
    }}>
      <p style={{ margin: 0, fontWeight: 600 }}>{label}</p>
      {[...payload]
        .filter((entry) => !entry.hide && entry.value != null)
        .sort((a, b) => (b.value ?? -1) - (a.value ?? -1))
        .map((entry) => (
          <p key={entry.name} style={{ margin: '2px 0', color: entry.color }}>
            {entry.name}: {entry.value}{suffix}
          </p>
        ))}
    </div>
  )
}

export default function TrendChart({
  data,
  xKey,
  series,
  type = 'line',
  yLabel,
  colorMap,
  yAxisOptions,
  onYAxisChange,
  yDomain,
  tooltipSuffix = '%',
}) {
  const [selectedKeys, setSelectedKeys] = useState([])

  const showAll = selectedKeys.length === 0

  const toggleKey = useCallback((key) => {
    setSelectedKeys((prev) => {
      if (prev.includes(key)) {
        return prev.filter((k) => k !== key)
      }
      return [...prev, key]
    })
  }, [])

  if (!data || data.length === 0) return null

  // Ensure every data point has every series key (null if missing) so connectNulls works
  const normalizedData = data.map((point) => {
    const filled = { ...point }
    for (const s of series) {
      if (!(s.key in filled)) filled[s.key] = null
    }
    return filled
  })

  const ChartComponent = type === 'bar' ? BarChart : LineChart

  const seriesColors = series.map((s, i) => ({
    ...s,
    color: colorMap?.[s.key] || getUCColor(s.key, i),
  }))

  return (
    <div style={{ position: 'relative' }}>
      {yAxisOptions && yAxisOptions.length > 1 && (
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
          <SegmentedControl
            size="xs"
            data={yAxisOptions}
            onChange={onYAxisChange}
            value={yAxisOptions.find((o) => o.label === yLabel)?.value || yAxisOptions[0].value}
          />
        </div>
      )}

      <ResponsiveContainer width="100%" height={350}>
        <ChartComponent data={normalizedData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey={xKey} />
          <YAxis
            label={yLabel ? { value: yLabel, angle: -90, position: 'insideLeft' } : undefined}
            domain={yDomain || ['auto', 'auto']}
          />
          <Tooltip
            content={<ChartTooltip suffix={tooltipSuffix} />}
            wrapperStyle={{ zIndex: 1000, pointerEvents: 'none' }}
          />
          {series.map((s, i) => {
            const color = colorMap?.[s.key] || getUCColor(s.key, i)
            const hidden = !showAll && !selectedKeys.includes(s.key)

            if (type === 'bar') {
              return (
                <Bar
                  key={s.key}
                  dataKey={s.key}
                  name={s.label}
                  fill={color}
                  hide={hidden}
                />
              )
            }

            return (
              <Line
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.label}
                stroke={color}
                connectNulls={true}
                strokeWidth={2}
                dot={false}
                hide={hidden}
              />
            )
          })}
        </ChartComponent>
      </ResponsiveContainer>

      <div style={{ display: 'flex', justifyContent: 'center', flexWrap: 'wrap', gap: 12, marginTop: 8 }}>
        <span
          onClick={() => setSelectedKeys([])}
          style={{
            fontSize: 13, cursor: 'pointer',
            fontWeight: showAll ? 700 : 400,
            color: showAll ? '#1295D8' : '#888',
          }}
        >
          Show All
        </span>
        {seriesColors.map((s) => {
          const isActive = showAll || selectedKeys.includes(s.key)
          return (
            <span
              key={s.key}
              onClick={() => toggleKey(s.key)}
              style={{
                fontSize: 13, cursor: 'pointer',
                color: s.color,
                opacity: isActive ? 1 : 0.4,
                fontWeight: !showAll && selectedKeys.includes(s.key) ? 700 : 400,
              }}
            >
              <svg width={10} height={10} style={{ marginRight: 4, verticalAlign: 'middle' }}>
                <circle cx={5} cy={5} r={5} fill={s.color} />
              </svg>
              {s.label}
            </span>
          )
        })}
      </div>
    </div>
  )
}
