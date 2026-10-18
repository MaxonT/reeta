// Play the Professor's own sentence. MediaRecorder webm files often cannot seek, so we decode the
// whole Lecture with Web Audio and play just [start_ms, end_ms] from the buffer.
import { api, authHeaders } from './api.js'

let ctx = null
const buffers = new Map()
let current = null

export async function playClip(lectureId, startMs, endMs, onEnd) {
  stopClip()
  if (!(endMs > startMs)) return false
  ctx = ctx || new (window.AudioContext || window.webkitAudioContext)()
  if (ctx.state === 'suspended') await ctx.resume()
  let buf = buffers.get(lectureId)
  if (!buf) {
    const res = await fetch(api.audioUrl(lectureId), { headers: authHeaders() })
    if (!res.ok) return false
    buf = await ctx.decodeAudioData(await res.arrayBuffer())
    buffers.set(lectureId, buf)
  }
  const src = ctx.createBufferSource()
  src.buffer = buf
  src.connect(ctx.destination)
  const start = Math.max(0, startMs / 1000 - 0.15)
  const dur = Math.min(buf.duration - start, (endMs - startMs) / 1000 + 0.45)
  src.onended = () => { if (current === src) current = null; onEnd?.() }
  src.start(0, start, dur)
  current = src
  return true
}

export function stopClip() {
  if (current) { try { current.stop() } catch { /* ignore */ } current = null }
}
