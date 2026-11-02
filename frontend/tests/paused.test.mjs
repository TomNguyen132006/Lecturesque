// Run with: npm test (node's own test runner, no extra package).
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { isPaused, DEMO_VIDEO_URL, README_URL } from '../app/lib/paused.js'

test('the paused panel is for AI_KEY_UNAVAILABLE only', () => {
  assert.equal(isPaused({ status: 'error', error: 'cleaning: AI_KEY_UNAVAILABLE' }), true)
})

test('every other failure keeps the normal error message', () => {
  assert.equal(isPaused({ status: 'error', error: 'cleaning: model is down' }), false)
  assert.equal(isPaused({ status: 'error', error: 'judging: call failed after 4 attempt(s): http_503' }), false)
  assert.equal(isPaused({ status: 'error', error: null }), false)
  assert.equal(isPaused({ status: 'running', error: null }), false)
  assert.equal(isPaused({ status: 'done', error: 'AI_KEY_UNAVAILABLE' }), false)
  assert.equal(isPaused(null), false)
})

test('the links are the exact ones', () => {
  assert.equal(DEMO_VIDEO_URL, 'https://www.youtube.com/watch?v=LrNe8788cL0')
  assert.equal(README_URL, 'https://github.com/TomNguyen132006/Lecturesque#readme')
})
