import axios, { type AxiosInstance } from 'axios'

import { env } from '@/config/env'
import type { ChatRequest, ChatResponse } from '@/types/chat'

const USER_ID_HEADER = 'x-user-id'

function createApiClient(): AxiosInstance {
  return axios.create({
    baseURL: env.apiBaseUrl,
    headers: {
      'Content-Type': 'application/json',
    },
  })
}

const client = createApiClient()

export async function postChat(
  payload: ChatRequest,
  userId: string = env.userId,
  sessionId?: string,
): Promise<ChatResponse> {
  const body: ChatRequest = sessionId
    ? { ...payload, session_id: sessionId }
    : payload
  const { data } = await client.post<ChatResponse>('/api/chat', body, {
    headers: {
      [USER_ID_HEADER]: userId,
    },
  })
  return data
}

export { client as apiClient, USER_ID_HEADER }

export type ConsultationConversationItem = { role: string; content: string }

export type ConsultationCreateRequest = {
  name: string
  email: string
  company: string
  project_description: string
  budget?: string
  timeline?: string
  conversation_history: ConsultationConversationItem[]
  session_id?: string
}

export type ConsultationCreateResponse = {
  ok: boolean
  consultation_id?: string
  summary?: string
  error?: string
}

export async function postConsultation(
  payload: ConsultationCreateRequest,
  userId: string = env.userId,
): Promise<ConsultationCreateResponse> {
  const { data } = await client.post<ConsultationCreateResponse>('/api/consultations', payload, {
    headers: {
      [USER_ID_HEADER]: userId,
    },
  })
  return data
}
export async function getCalendarSlots() {
  const { data } = await client.get('/api/calendar/slots')
  return data
}

export async function bookCalendarSlot(payload: any) {
  const { data } = await client.post('/api/calendar/book', payload)
  return data
}

// ── Admin Panel API Services ──────────────────────────────────────────────

export function getAdminToken(): string | null {
  try {
    return sessionStorage.getItem('agicent_admin_token')
  } catch {
    return null
  }
}

export function setAdminToken(token: string | null): void {
  try {
    if (token) {
      sessionStorage.setItem('agicent_admin_token', token)
    } else {
      sessionStorage.removeItem('agicent_admin_token')
    }
  } catch {
    // ignore
  }
}

function getAdminHeaders() {
  const token = getAdminToken()
  return {
    'x-admin-token': token ?? '',
  }
}

export async function adminLogin(key: string) {
  const { data } = await client.post<{ token: string; ok: boolean }>('/api/admin/login', { key })
  if (data.ok && data.token) {
    setAdminToken(data.token)
  }
  return data
}

export async function getAdminDashboard() {
  const { data } = await client.get('/api/admin/dashboard', {
    headers: getAdminHeaders(),
  })
  return data
}

export async function getAdminConsultants() {
  const { data } = await client.get<any[]>('/api/admin/consultants', {
    headers: getAdminHeaders(),
  })
  return data
}

export async function createAdminConsultant(consultant: any) {
  const { data } = await client.post('/api/admin/consultants', consultant, {
    headers: getAdminHeaders(),
  })
  return data
}

export async function updateAdminConsultant(id: string, consultant: any) {
  const { data } = await client.put(`/api/admin/consultants/${id}`, consultant, {
    headers: getAdminHeaders(),
  })
  return data
}

export async function deleteAdminConsultant(id: string) {
  const { data } = await client.delete(`/api/admin/consultants/${id}`, {
    headers: getAdminHeaders(),
  })
  return data
}

export async function getAdminBookings() {
  const { data } = await client.get<any[]>('/api/admin/bookings', {
    headers: getAdminHeaders(),
  })
  return data
}

export async function reassignBooking(id: string, newConsultantId: string) {
  const { data } = await client.post(`/api/admin/bookings/${id}/reassign`, {
    new_consultant_id: newConsultantId,
  }, {
    headers: getAdminHeaders(),
  })
  return data
}

export async function cancelBooking(id: string) {
  const { data } = await client.post(`/api/admin/bookings/${id}/cancel`, {}, {
    headers: getAdminHeaders(),
  })
  return data
}

export async function completeBooking(id: string) {
  const { data } = await client.post(`/api/admin/bookings/${id}/complete`, {}, {
    headers: getAdminHeaders(),
  })
  return data
}