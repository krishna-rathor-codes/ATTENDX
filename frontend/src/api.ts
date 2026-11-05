export type Role = 'teacher' | 'student'
export type Status = 'present' | 'absent' | 'late'

export type User = { id: number; full_name: string; email: string; role: Role; student_id?: string | null }
export type Subject = { id: number; code: string; name: string; description?: string | null }
export type ClassRoom = { id: number; name: string; section: string; subject_id: number; subject_code: string; subject_name: string; enrolled_count: number; active_session_id?: number | null }
export type Summary = { class_id: number; class_name: string; subject_name: string; total_sessions: number; present_count: number; late_count: number; absent_count: number; percentage: number; below_threshold: boolean }
export type Session = { id: number; class_id: number; class_name: string; subject_name: string; token: string; qr_payload: string; starts_at: string; expires_at: string; closed_at?: string | null; marked_count: number }
export type RecordItem = { id: number; session_id: number; class_id: number; class_name: string; subject_name: string; student_id: number; student_name: string; student_email: string; status: Status; source: string; marked_at: string; note?: string | null }
export type Student = { id: number; full_name: string; email: string; student_id?: string | null }
export type Audit = { id: number; action: string; entity_type: string; entity_id?: string | null; details?: string | null; created_at: string; actor_name?: string | null }

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('attendx_token')
  const headers = new Headers(options.headers)
  if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(`${API_URL}${path}`, { ...options, headers })
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(error.detail || 'Request failed')
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export async function downloadReport(type: 'csv' | 'pdf', classId?: number) {
  const token = localStorage.getItem('attendx_token')
  const query = classId ? `?class_id=${classId}` : ''
  const response = await fetch(`${API_URL}/teacher/reports/${type}${query}`, { headers: { Authorization: `Bearer ${token}` } })
  if (!response.ok) throw new Error('Could not generate report')
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `attendx-attendance.${type}`
  link.click()
  URL.revokeObjectURL(url)
}
