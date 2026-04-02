import { afterEach, beforeEach, vi } from 'vitest'
import { cleanup } from '@testing-library/svelte'

beforeEach(() => {
  vi.useRealTimers()
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
})
