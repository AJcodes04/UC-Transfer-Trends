import { Progress } from '@mantine/core'
import StatsCard from './StatsCard'
import { useCountUp } from '../hooks/useCountUp'

export default function TransferUnitsCard({ units, target }) {
  const animated = useCountUp(units)
  const decimals = Number.isInteger(units) ? 0 : 1

  return (
    <StatsCard title="Transferable units" value={`${animated.toFixed(decimals)} / ${target}`}>
      <Progress
        value={Math.min(100, (animated / target) * 100)}
        transitionDuration={0}
        size="sm"
        mt="sm"
        aria-label="Transferable units progress"
      />
    </StatsCard>
  )
}
