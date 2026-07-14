export const USER_ACTIVITY_EVENTS = [
  'pointerdown',
  'keydown',
  'wheel',
  'touchstart',
  'input',
  'change',
  'compositionend',
  'dragstart',
  'drop',
] as const

let pendingSessionActivity = false

export function markSessionActivity() {
  pendingSessionActivity = true
}

export function hasPendingSessionActivity(): boolean {
  return pendingSessionActivity
}

export function clearPendingSessionActivity() {
  pendingSessionActivity = false
}
