// "Live runs are paused": the server's job error is exactly "<stage>: AI_KEY_UNAVAILABLE" when the AI key is missing or rejected.
// Every other failed job keeps the normal error message.
export const KEY_UNAVAILABLE = 'AI_KEY_UNAVAILABLE'
export const DEMO_VIDEO_URL = 'https://www.youtube.com/watch?v=LrNe8788cL0'
export const README_URL = 'https://github.com/TomNguyen132006/Lecturesque#readme'

export const isPaused = (job) => job?.status === 'error' && typeof job.error === 'string' && job.error.includes(KEY_UNAVAILABLE)
