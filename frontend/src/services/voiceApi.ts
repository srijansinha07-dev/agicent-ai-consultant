import axios from 'axios'

import { env } from '@/config/env'
import { apiClient } from '@/services/api'

export interface VoiceTranscriptionResponse {
  text: string
  language: string
  confidence: number | null
}

export async function postVoiceTranscribe(
  audioBlob: Blob,
  filename = 'recording.webm',
): Promise<VoiceTranscriptionResponse> {
  const formData = new FormData()
  formData.append('audio', audioBlob, filename)

  try {
    const { data } = await apiClient.post<VoiceTranscriptionResponse>(
      '/api/voice/transcribe',
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 120000,
      },
    )

    return data
  } catch (err) {
    if (axios.isAxiosError(err)) {
      const detail = err.response?.data?.detail
      if (typeof detail === 'string') {
        throw new Error(detail)
      }
    }
    throw err
  }
}

export function isVoiceFeatureEnabled(): boolean {
  return env.voiceEnabled
}
