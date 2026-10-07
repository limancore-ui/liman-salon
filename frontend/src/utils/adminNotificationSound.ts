const MUTE_STORAGE_KEY = 'liman.admin.notifications.soundMuted'

export function isAdminNotificationSoundMuted(): boolean {
  try {
    return localStorage.getItem(MUTE_STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

export function setAdminNotificationSoundMuted(muted: boolean): void {
  try {
    if (muted) {
      localStorage.setItem(MUTE_STORAGE_KEY, '1')
    } else {
      localStorage.removeItem(MUTE_STORAGE_KEY)
    }
  } catch {
    /* ignore storage errors */
  }
}

let sharedContext: AudioContext | null = null

function getAudioContextConstructor(): typeof AudioContext | undefined {
  if (typeof window === 'undefined') {
    return undefined
  }
  return (
    window.AudioContext ??
    (window as Window & { webkitAudioContext?: typeof AudioContext })
      .webkitAudioContext
  )
}

export function getAdminNotificationAudioContext(): AudioContext | null {
  const Ctx = getAudioContextConstructor()
  if (!Ctx) {
    return null
  }
  if (!sharedContext || sharedContext.state === 'closed') {
    sharedContext = new Ctx()
  }
  return sharedContext
}

export async function ensureAdminNotificationAudioReady(): Promise<AudioContext | null> {
  const ctx = getAdminNotificationAudioContext()
  if (!ctx) {
    return null
  }
  if (ctx.state === 'suspended') {
    try {
      await ctx.resume()
    } catch {
      return null
    }
  }
  return ctx.state === 'running' ? ctx : null
}

/** Short, quiet tone for new admin notifications (Web Audio API). */
export function playAdminNotificationSound(ctx: AudioContext): void {
  try {
    const start = ctx.currentTime
    const gain = ctx.createGain()
    gain.gain.setValueAtTime(0.0001, start)
    gain.gain.exponentialRampToValueAtTime(0.06, start + 0.015)
    gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.22)
    gain.connect(ctx.destination)

    const osc = ctx.createOscillator()
    osc.type = 'sine'
    osc.frequency.setValueAtTime(784, start)
    osc.frequency.exponentialRampToValueAtTime(523.25, start + 0.1)
    osc.connect(gain)
    osc.start(start)
    osc.stop(start + 0.24)
  } catch {
    /* ignore playback / autoplay failures */
  }
}
