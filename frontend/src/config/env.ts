const apiBaseUrl = import.meta.env.VITE_API_BASE_URL
const docId = import.meta.env.VITE_DOC_ID
const userId = import.meta.env.VITE_USER_ID
const embedMode = import.meta.env.VITE_EMBED_MODE === 'true'
const voiceEnabled = import.meta.env.VITE_VOICE_ENABLED === 'true'
const voiceMaxAudioMb = Number(import.meta.env.VITE_VOICE_MAX_AUDIO_MB) || 10

export const env = {
  apiBaseUrl: apiBaseUrl ?? '',
  docId: docId ?? '',
  userId: userId ?? '',
  embedMode,
  voiceEnabled,
  voiceMaxAudioMb,
} as const

export function assertEnvConfigured(): void {
  const missing: string[] = []
  if (!env.apiBaseUrl) missing.push('VITE_API_BASE_URL')
  if (!env.docId) missing.push('VITE_DOC_ID')
  if (!env.userId) missing.push('VITE_USER_ID')
  if (missing.length > 0) {
    throw new Error(`Missing required environment variables: ${missing.join(', ')}`)
  }
}
