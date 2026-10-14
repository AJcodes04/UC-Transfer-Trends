import { useCountUp } from '../hooks/useCountUp'

export default function CountUp({ value, decimals = 0 }) {
  return useCountUp(value).toFixed(decimals)
}
