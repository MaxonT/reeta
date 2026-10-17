import { useRef, useState } from 'react'

// Push to talk: MediaRecorder captures audio for Whisper. The Web Speech API runs in parallel
// for live chalk writing and as a fallback transcript with timestamps relative to the recording start.
const SR = typeof window !== 'undefined' && (window.SpeechRecognition || window.webkitSpeechRecognition)

export function useRecorder() {
  const [recording, setRecording] = useState(false)
  const [live, setLive] = useState({ finals: [], interim: '' })
  const r = useRef({})

  async function start() {
    if (r.current.recorder) return
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const recorder = new MediaRecorder(stream)
    const chunks = []
    recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data)
    const t0 = performance.now()
    const finals = []
    let lastEnd = 0
    let rec = null
    if (SR) {
      rec = new SR()
      rec.continuous = true
      rec.interimResults = true
      rec.lang = 'en-US'
      rec.onresult = (ev) => {
        let interim = ''
        for (let i = ev.resultIndex; i < ev.results.length; i++) {
          const res = ev.results[i]
          if (res.isFinal) {
            const end = Math.round(performance.now() - t0)
            const text = res[0].transcript.trim()
            if (text) finals.push({ text: capitalize(text), start_ms: lastEnd, end_ms: end })
            lastEnd = end
          } else interim += res[0].transcript
        }
        setLive({ finals: [...finals], interim })
      }
      rec.onerror = () => {}
      rec.onend = () => { if (r.current.rec === rec) try { rec.start() } catch { /* already running */ } }
      try { rec.start() } catch { /* ignore */ }
    }
    recorder.start(250)
    r.current = { recorder, stream, rec, chunks, finals }
    setLive({ finals: [], interim: '' })
    setRecording(true)
  }

  function stop() {
    const { recorder, stream, rec, chunks, finals } = r.current
    if (!recorder) return Promise.resolve(null)
    r.current = {}
    setRecording(false)
    return new Promise((resolve) => {
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop())
        // give Web Speech a moment to flush its last final result
        setTimeout(() => {
          if (rec) { rec.onend = null; try { rec.stop() } catch { /* ignore */ } }
          resolve({ blob: new Blob(chunks, { type: recorder.mimeType || 'audio/webm' }), sentences: finals })
        }, 400)
      }
      recorder.stop()
    })
  }

  return { recording, live, start, stop, speechSupported: !!SR }
}

function capitalize(s) {
  const t = s.charAt(0).toUpperCase() + s.slice(1)
  return /[.!?]$/.test(t) ? t : t + '.'
}
