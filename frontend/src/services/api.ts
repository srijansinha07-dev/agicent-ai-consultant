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
): Promise<ChatResponse> {
  const { data } = await client.post<ChatResponse>('/api/chat', payload, {
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
