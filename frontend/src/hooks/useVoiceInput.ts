import { useCallback, useEffect, useRef, useState } from 'react'

import { postVoiceTranscribe } from '@/services/voiceApi'
import { env } from '@/config/env'

export type VoiceInputStatus = 'idle' | 'recording' | 'processing' | 'error'

export interface VoiceTranscriptResult {
  text: string
  language: string
  /** Base64 data URI of the recorded audio — persists through page refresh. */
  audioUrl?: string
}

export interface UseVoiceInputReturn {
  status: VoiceInputStatus
  error: string | null
  isSupported: boolean
  startRecording: () => Promise<void>
  stopRecording: () => void
  cancelRecording: () => void
  processAudioFile: (file: File) => Promise<void>
}

function pickRecorderMimeType(): string | undefined {
  const candidates = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/ogg;codecs=opus',
    'audio/mp4',
  ]

  for (const mime of candidates) {
    if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(mime)) {
      return mime
    }
  }

  return undefined
}

function extensionForMime(mimeType: string): string {
  if (mimeType.includes('ogg')) return 'recording.ogg'
  if (mimeType.includes('mp4')) return 'recording.mp4'
  return 'recording.webm'
}

/**
 * Convert a Blob/File to a base64 data URI.
 * Unlike URL.createObjectURL(), data URIs are plain strings that survive
 * JSON serialisation and page refresh.
 */
function blobToDataUri(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as string)
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(blob)
  })
}

export function useVoiceInput(
  onTranscript: (result: VoiceTranscriptResult) => void,
): UseVoiceInputReturn {
  const [status, setStatus] = useState<VoiceInputStatus>('idle')
  const [error, setError] = useState<string | null>(null)

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const mediaStreamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<BlobPart[]>([])
  const mimeTypeRef = useRef<string>('audio/webm')

  // V2: always reference the latest onTranscript without closing over a stale value
  const onTranscriptRef = useRef(onTranscript)
  useEffect(() => {
    onTranscriptRef.current = onTranscript
  }, [onTranscript])

  const isSupported =
    typeof navigator !== 'undefined' &&
    typeof navigator.mediaDevices?.getUserMedia === 'function' &&
    typeof MediaRecorder !== 'undefined'

  const releaseStream = useCallback(() => {
    mediaStreamRef.current?.getTracks().forEach((track) => track.stop())
    mediaStreamRef.current = null
  }, [])

  const cancelRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.ondataavailable = null
      mediaRecorderRef.current.onerror = null
      mediaRecorderRef.current.stop()
    }
    mediaRecorderRef.current = null
    chunksRef.current = []
    releaseStream()
    setStatus('idle')
    setError(null)
  }, [releaseStream])

  const startRecording = useCallback(async () => {
    if (!isSupported) {
      setError('Voice input is not supported in this browser.')
      setStatus('error')
      return
    }

    if (status === 'recording' || status === 'processing') {
      return
    }

    setError(null)

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      mediaStreamRef.current = stream
      chunksRef.current = []

      const mimeType = pickRecorderMimeType()
      mimeTypeRef.current = mimeType ?? 'audio/webm'

      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream)

      mediaRecorderRef.current = recorder

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data)
        }
      }

      recorder.onerror = () => {
        setError('Recording failed. Please try again.')
        setStatus('error')
        cancelRecording()
      }

      recorder.onstop = async () => {
        releaseStream()
        mediaRecorderRef.current = null

        const blob = new Blob(chunksRef.current, {
          type: mimeTypeRef.current,
        })
        chunksRef.current = []

        if (!blob.size) {
          setError('No audio captured. Please try again.')
          setStatus('error')
          return
        }

        setStatus('processing')

        try {
          const filename = extensionForMime(mimeTypeRef.current)
          const result = await postVoiceTranscribe(blob, filename)
          const text = result.text.trim()

          if (!text) {
            setError('No speech detected. Please try again.')
            setStatus('error')
            return
          }

          // V2: call through ref so we always invoke the latest callback
          onTranscriptRef.current({
            text,
            language: result.language,
            audioUrl: await blobToDataUri(blob),
          })
          setStatus('idle')
          setError(null)
        } catch (err) {
          const message =
            err instanceof Error ? err.message : 'Transcription failed. Please try again.'
          setError(message)
          setStatus('error')
        }
      }

      recorder.start(1000)
      setStatus('recording')
    } catch (err) {
      releaseStream()
      const message =
        err instanceof Error && err.name === 'NotAllowedError'
          ? 'Microphone permission denied.'
          : 'Could not access microphone.'
      setError(message)
      setStatus('error')
    }
  }, [cancelRecording, isSupported, onTranscript, releaseStream, status])

  const stopRecording = useCallback(() => {
    const recorder = mediaRecorderRef.current
    if (!recorder || recorder.state === 'inactive') {
      return
    }
    recorder.stop()
  }, [])

  // V1: release microphone on unmount — prevents stream leaks if component
  // is destroyed while recording is active
  useEffect(() => {
    return () => {
      cancelRecording()
    }
  }, [cancelRecording])

  const processAudioFile = useCallback(
    async (file: File) => {
      if (status === 'recording' || status === 'processing') return

      const maxBytes = env.voiceMaxAudioMb * 1024 * 1024
      if (file.size > maxBytes) {
        setError(`File is too large (max ${env.voiceMaxAudioMb}MB).`)
        setStatus('error')
        return
      }

      setError(null)
      setStatus('processing')

      try {
        const result = await postVoiceTranscribe(file, file.name)
        const text = result.text.trim()

        if (!text) {
          setError('No speech detected in file. Please try again.')
          setStatus('error')
          return
        }

        onTranscript({
          text,
          language: result.language,
          audioUrl: await blobToDataUri(file),
        })
        setStatus('idle')
        setError(null)
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'Transcription failed. Please try again.'
        setError(message)
        setStatus('error')
      }
    },
    [status, onTranscript],
  )

  return {
    status,
    error,
    isSupported,
    startRecording,
    stopRecording,
    cancelRecording,
    processAudioFile,
  }
}
