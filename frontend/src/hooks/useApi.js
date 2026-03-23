import { useState, useEffect } from 'react'
import axios from 'axios'

/**
 * Generic fetch hook — handles loading, error, and data states.
 * `url` can be null to skip fetching (useful when a param isn't ready yet).
 */
function useFetch(url) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!url) return

    let cancelled = false
    setLoading(true)
    setError(null)

    axios
      .get(url)
      .then((res) => {
        if (!cancelled) setData(res.data)
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || 'issue brah')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [url])

  return { data, loading, error }
}

export function useUniversities() {
  return useFetch('/api/universities/')
}

export function useMajors() {
  return useFetch('/api/majors/')
}

export function useGroupedMajors() {
  return useFetch('/api/majors/grouped/')
}

export function useDisciplines() {
  return useFetch('/api/disciplines/')
}

export function useGeneralStats() {
  return useFetch('/api/stats/general/')
}

export function useSchoolStats(school) {
  return useFetch(school ? `/api/stats/by-school/${encodeURIComponent(school)}/` : null)
}

export function useMajorStats(major) {
  return useFetch(major ? `/api/stats/by-major/${encodeURIComponent(major)}/` : null)
}

export function useCampusMajorStats(campus) {
  return useFetch(campus ? `/api/stats/campus-majors/${encodeURIComponent(campus)}/` : null)
}

export function useTransferData(filters) {
  const params = new URLSearchParams()
  if (filters?.university) params.set('university', filters.university)
  if (filters?.year) params.set('year', filters.year)
  if (filters?.major_name) params.set('major_name', filters.major_name)
  if (filters?.broad_discipline) params.set('broad_discipline', filters.broad_discipline)

  const query = params.toString()
  return useFetch(query ? `/api/transfer-data/?${query}` : '/api/transfer-data/')
}
