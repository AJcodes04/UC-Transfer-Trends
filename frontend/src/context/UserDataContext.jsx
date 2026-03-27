import { createContext, useState, useEffect, useCallback } from 'react'

const COURSES_KEY = 'uc_transfer_courses'
const SAVED_COMBOS_KEY = 'uc_transfer_saved_combos'

function readStorage(key, fallback) {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : fallback
  } catch {
    return fallback
  }
}

export const UserDataContext = createContext(null)

export function UserDataProvider({ children }) {
  const [courses, setCourses] = useState(() => readStorage(COURSES_KEY, []))

  useEffect(() => {
    localStorage.setItem(COURSES_KEY, JSON.stringify(courses))
  }, [courses])

  const addCourse = useCallback((course) => {
    setCourses((prev) => [...prev, { ...course, id: crypto.randomUUID() }])
  }, [])

  const removeCourse = useCallback((id) => {
    setCourses((prev) => prev.filter((c) => c.id !== id))
  }, [])

  const updateCourse = useCallback((id, updates) => {
    setCourses((prev) =>
      prev.map((c) => (c.id === id ? { ...c, ...updates } : c))
    )
  }, [])

  const clearCourses = useCallback(() => {
    setCourses([])
  }, [])

  const addCourses = useCallback((newCourses) => {
    setCourses((prev) => [
      ...prev,
      ...newCourses.map((c) => ({ ...c, id: crypto.randomUUID() })),
    ])
  }, [])

  const [savedCombos, setSavedCombos] = useState(() => readStorage(SAVED_COMBOS_KEY, []))

  useEffect(() => {
    localStorage.setItem(SAVED_COMBOS_KEY, JSON.stringify(savedCombos))
  }, [savedCombos])

  const saveCombo = useCallback((major, school) => {
    setSavedCombos((prev) => {
      if (prev.some((c) => c.major === major && c.school === school)) return prev
      return [...prev, { id: crypto.randomUUID(), major, school }]
    })
  }, [])

  // Overloaded: unsaveCombo(id) or unsaveCombo(major, school)
  const unsaveCombo = useCallback((majorOrId, school) => {
    setSavedCombos((prev) => {
      if (school !== undefined) {
        return prev.filter((c) => !(c.major === majorOrId && c.school === school))
      }
      return prev.filter((c) => c.id !== majorOrId)
    })
  }, [])

  const isComboSaved = useCallback(
    (major, school) => savedCombos.some((c) => c.major === major && c.school === school),
    [savedCombos]
  )

  const value = {
    courses, addCourse, removeCourse, updateCourse, clearCourses, addCourses,
    savedCombos, saveCombo, unsaveCombo, isComboSaved,
  }

  return (
    <UserDataContext.Provider value={value}>
      {children}
    </UserDataContext.Provider>
  )
}
