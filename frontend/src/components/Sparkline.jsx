import { ResponsiveContainer, LineChart, Line, Tooltip, YAxis } from 'recharts'

const MUTED = '#adb5bd'

function SparkTooltip({ active, payload, format }) {
  if (!active || !payload?.length || payload[0].value == null) return null
  const { year, value } = payload[0].payload
  return (
    <div style={{ background: 'white', border: '1px solid #ccc', borderRadius: 4, padding: '2px 6px', fontSize: 11 }}>
      {year}: {format(value)}
    </div>
  )
}

export default function Sparkline({ data, accent = '#1295D8', format = (v) => v }) {
  if (!data || data.filter((d) => d.value != null).length < 2) return null
  const last = data[data.length - 1]
  return (
    <ResponsiveContainer width="100%" height={36}>
      <LineChart data={data} margin={{ top: 6, right: 6, bottom: 6, left: 6 }}>
        <YAxis hide domain={['dataMin', 'dataMax']} />
        <Tooltip content={<SparkTooltip format={format} />} cursor={false} wrapperStyle={{ pointerEvents: 'none' }} />
        <Line
          type="monotone"
          dataKey="value"
          stroke={MUTED}
          strokeWidth={2}
          connectNulls
          isAnimationActive={false}
          dot={(p) => (p.payload === last && p.value != null
            ? <circle key={p.key} cx={p.cx} cy={p.cy} r={4} fill={accent} stroke="white" strokeWidth={2} />
            : null)}
          activeDot={{ r: 4, fill: accent, stroke: 'white', strokeWidth: 2 }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
