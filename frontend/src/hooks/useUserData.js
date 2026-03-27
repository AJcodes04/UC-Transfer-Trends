import { useContext, useMemo } from 'react'
import { UserDataContext } from '../context/UserDataContext'
import { calculateGPA } from '../utils/gpa'

export function useCourses() {
  const ctx = useContext(UserDataContext)
  if (!ctx) throw new Error('useCourses must be used within UserDataProvider')
  const { courses, addCourse, removeCourse, updateCourse, clearCourses, addCourses } = ctx
  return { courses, addCourse, removeCourse, updateCourse, clearCourses, addCourses }
}

export function useSavedCombos() {
  const ctx = useContext(UserDataContext)
  if (!ctx) throw new Error('useSavedCombos must be used within UserDataProvider')
  const { savedCombos, saveCombo, unsaveCombo, isComboSaved } = ctx
  return { savedCombos, saveCombo, unsaveCombo, isComboSaved }
}

export function useGPA(filterKeys) {
  const { courses } = useCourses()

  return useMemo(() => {
    let filtered = courses
    if (filterKeys && filterKeys.size > 0) {
      filtered = courses.filter((c) => {
        const key = `${(c.prefix || '').trim().toUpperCase()} ${(c.number || '').trim().toUpperCase()}`
        return filterKeys.has(key)
      })
    }
    return calculateGPA(filtered)
  }, [courses, filterKeys])
}
