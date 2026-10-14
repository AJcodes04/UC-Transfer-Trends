import { useEffect, useRef, useState } from 'react'
import { useReducedMotion } from '@mantine/hooks'

const DEFAULT_DURATION = 2000

const easeOut = (t) => 1 - (1 - t) ** 2

export function useCountUp(target, duration = DEFAULT_DURATION) {
  const value = Number.isFinite(target) ? target : 0
  const reduced = useReducedMotion(undefined, { getInitialValueInEffect: false })
  const [display, setDisplay] = useState(reduced ? value : 0)
  const fromRef = useRef(reduced ? value : 0)

  useEffect(() => {
    if (reduced) {
      fromRef.current = value
      setDisplay(value)
      return
    }
    if (fromRef.current === value) return

    const from = fromRef.current
    const start = performance.now()
    let frame = requestAnimationFrame(function tick(now) {
      const t = Math.min(1, (now - start) / duration)
      const next = t === 1 ? value : from + (value - from) * easeOut(t)
      fromRef.current = next
      setDisplay(next)
      if (t < 1) frame = requestAnimationFrame(tick)
    })

    return () => cancelAnimationFrame(frame)
  }, [value, duration, reduced])

  return display
}
