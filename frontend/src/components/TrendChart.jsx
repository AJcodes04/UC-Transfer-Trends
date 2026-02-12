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

// A set of distinguishable colors for chart lines/bars
const COLORS = [
  '#228be6', '#fa5252', '#40c057', '#fab005', '#7950f2',
  '#fd7e14', '#15aabf', '#e64980', '#82c91e', '#be4bdb',
]

/**
 * Reusable chart wrapper.
 *
 * Props:
 *  - data: array of objects, each with an `xKey` field and one field per series
 *  - xKey: string — which field to use on the X axis (e.g. "year")
 *  - series: array of { key, label } — each series to plot
 *  - type: "line" | "bar" (default "line")
 *  - yLabel: optional Y-axis label
 */
export default function TrendChart({ data, xKey, series, type = 'line', yLabel }) {
  if (!data || data.length === 0) return null

  const ChartComponent = type === 'bar' ? BarChart : LineChart

  return (
    <ResponsiveContainer width="100%" height={350}>
      <ChartComponent data={data} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey={xKey} />
        <YAxis label={yLabel ? { value: yLabel, angle: -90, position: 'insideLeft' } : undefined} />
        <Tooltip />
        <Legend />
        {series.map((s, i) =>
          type === 'bar' ? (
            <Bar key={s.key} dataKey={s.key} name={s.label} fill={COLORS[i % COLORS.length]} />
          ) : (
            <Line
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.label}
              stroke={COLORS[i % COLORS.length]}
              strokeWidth={2}
              dot={false}
            />
          )
        )}
      </ChartComponent>
    </ResponsiveContainer>
  )
}
