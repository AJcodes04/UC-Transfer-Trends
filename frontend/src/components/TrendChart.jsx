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
  Legend,
} from 'recharts'
import { getUCColor } from '../utils/ucColors'

// appends % to chart value
function PercentTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: 'white', border: '1px solid #ccc',
      borderRadius: 6, padding: '8px 12px', fontSize: 13,
    }}>
      <p style={{ margin: 0, fontWeight: 600 }}>{label}</p>
      {[...payload].sort((a, b) => (b.value ?? -1) - (a.value ?? -1)).map((entry) => (
        <p key={entry.name} style={{ margin: '2px 0', color: entry.color }}>
          {entry.name}: {entry.value != null ? `${entry.value}%` : 'N/A'}
        </p>
      ))}
    </div>
  )
}
// takes in array of objects, each object has an xKey for the xAxis which is ALWAYS year
export default function TrendChart({ data, xKey, series, type = 'line', yLabel, colorMap }) {
  // selectedKeys: empty array = show all, otherwise only show those keys
  const [selectedKeys, setSelectedKeys] = useState([])

  const showAll = selectedKeys.length === 0

  const toggleKey = useCallback((key) => {
    setSelectedKeys((prev) => {
      if (prev.includes(key)) {
        // Removing last selected key goes back to show all
        return prev.filter((k) => k !== key)
      }
      return [...prev, key]
    })
  }, [])

  if (!data || data.length === 0) return null

  const ChartComponent = type === 'bar' ? BarChart : LineChart

  return (
    <ResponsiveContainer width="100%" height={350}>
      <ChartComponent data={data} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey={xKey} />
        <YAxis label={yLabel ? { value: yLabel, angle: -90, position: 'insideLeft' } : undefined} />
        <Tooltip content={<PercentTooltip />} />
        <Legend
          content={({ payload }) => (
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
              {payload.map((entry) => {
                const isActive = showAll || selectedKeys.includes(entry.dataKey)
                return (
                  <span
                    key={entry.value}
                    onClick={() => toggleKey(entry.dataKey)}
                    style={{
                      fontSize: 13, cursor: 'pointer',
                      color: entry.color,
                      opacity: isActive ? 1 : 0.4,
                      fontWeight: !showAll && selectedKeys.includes(entry.dataKey) ? 700 : 400,
                    }}
                  >
                    <svg width={10} height={10} style={{ marginRight: 4, verticalAlign: 'middle' }}>
                      <circle cx={5} cy={5} r={5} fill={entry.color} />
                    </svg>
                    {entry.value}
                  </span>
                )
              })}
            </div>
          )}
        />
        {series.map((s, i) => {
          const color = colorMap?.[s.key] || getUCColor(s.key, i)
          const hidden = !showAll && !selectedKeys.includes(s.key)

          return type === 'bar' ? (
            <Bar
              key={s.key}
              dataKey={s.key}
              name={s.label}
              fill={color}
              hide={hidden}
            />
          ) : (
            <Line
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.label}
              stroke={color}
              strokeWidth={2}
              dot={false}
              hide={hidden}
            />
          )
        })}
      </ChartComponent>
    </ResponsiveContainer>
  )
}
