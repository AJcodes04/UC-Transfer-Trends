import { useState, useEffect, useRef } from 'react'
import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || ''
const cache = new Map()

function useFetch(url) {
  const fullUrl = url ? `${API_BASE}${url}` : null
  const [data, setData] = useState(() => (fullUrl && cache.has(fullUrl) ? cache.get(fullUrl) : null))
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const prevUrl = useRef(fullUrl)

  useEffect(() => {
    if (!fullUrl) return

    if (cache.has(fullUrl)) {
      setData(cache.get(fullUrl))
      setLoading(false)
      setError(null)
      return
    }

    let cancelled = false
    setLoading(true)
    setError(null)

    axios
      .get(fullUrl)
      .then((res) => {
        cache.set(fullUrl, res.data)
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
  }, [fullUrl])

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

export function useArticulationColleges() {
  return useFetch('/api/articulation/colleges/')
}

export function useArticulationCampuses(ccCode) {
  return useFetch(ccCode ? `/api/articulation/${ccCode}/campuses/` : null)
}

export function useArticulationMajors(ccCode, ucCode) {
  return useFetch(ccCode && ucCode ? `/api/articulation/${ccCode}/${ucCode}/majors/` : null)
}

export function useArticulationDetail(ccCode, ucCode, majorSlug) {
  return useFetch(
    ccCode && ucCode && majorSlug
      ? `/api/articulation/${ccCode}/${ucCode}/${majorSlug}/`
      : null
  )
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
