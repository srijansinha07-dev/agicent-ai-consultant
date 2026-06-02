import type { Source } from '@/types/chat'

const LOW_QUALITY = new Set([
  'agicent',
  'home',
  'website',
  'services',
  'contact',
  'blog',
  'category',
])

function isSlugLike(label: string): boolean {
  const t = label.trim()
  return t.includes('-') && !t.includes(' ') && t.length < 50
}

export function isQualityResourceLabel(label: string): boolean {
  const t = label.trim()
  if (t.length < 12) return false
  const lower = t.toLowerCase()
  if (LOW_QUALITY.has(lower)) return false
  if (isSlugLike(t)) return false
  if (/^[a-z0-9_/-]+$/i.test(t) && t.includes('-')) return false
  return true
}

function titleFromChunkText(text: string): string | null {
  const lines = text.split('\n').map((l) => l.trim()).filter(Boolean)
  for (const line of lines) {
    if (/^URL:/i.test(line)) continue
    if (line.length >= 12 && line.length <= 100 && isQualityResourceLabel(line)) {
      return line
    }
  }
  return null
}

export function getResourceTitle(source: Source): string | null {
  if (source.label?.trim() && isQualityResourceLabel(source.label)) {
    return source.label.trim()
  }
  const fromText = titleFromChunkText(source.text)
  if (fromText) return fromText
  return null
}

export function getResourceUrl(source: Source): string | undefined {
  const raw = source.url?.trim()
  if (!raw) {
    const m = source.text.match(/^URL:\s*(\S+)/im)
    if (!m) return undefined
    const u = m[1].trim()
    if (u.startsWith('http')) return u
    return `https://${u.replace(/^\/+/, '')}`
  }
  if (raw.startsWith('http')) return raw
  return `https://${raw.replace(/^\/+/, '')}`
}

/** Deduplicated, quality-filtered resources for display. */
export function getDisplayResources(sources: Source[], max = 4): Source[] {
  const seen = new Set<string>()
  const out: Source[] = []

  for (const s of sources) {
    const title = getResourceTitle(s)
    const url = getResourceUrl(s)
    if (!title || !url) continue
    const key = url.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    out.push({ ...s, label: title, url })
    if (out.length >= max) break
  }

  return out
}
