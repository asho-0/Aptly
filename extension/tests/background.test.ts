import { VAULT_DEFAULTS } from '../src/types'

function installChromeMock() {
  vi.stubGlobal('chrome', {
    alarms: {
      create: vi.fn(),
      onAlarm: { addListener: vi.fn() },
    },
    runtime: {
      onInstalled: { addListener: vi.fn() },
      onStartup: { addListener: vi.fn() },
      onMessage: { addListener: vi.fn() },
      getURL: vi.fn((path: string) => `chrome-extension://test/${path}`),
    },
    storage: {
      local: {
        get: vi.fn(async () => ({ vaultData: { ...VAULT_DEFAULTS } })),
        set: vi.fn(async () => undefined),
      },
      onChanged: { addListener: vi.fn() },
    },
    tabs: {
      onUpdated: { addListener: vi.fn(), removeListener: vi.fn() },
    },
    scripting: {
      executeScript: vi.fn(async () => []),
    },
  })
}

describe('background pairing diagnostics', () => {
  test('rejects localhost for external-device pairing', async () => {
    installChromeMock()
    const { validatePairingUrl } = await import('../src/background')

    expect(validatePairingUrl('ws://127.0.0.1:8080/ws/extension')).toEqual({
      ok: false,
      error: expect.stringContaining('127.0.0.1'),
    })
    expect(validatePairingUrl('ws://localhost:8080/ws/extension')).toEqual({
      ok: false,
      error: expect.stringContaining('localhost'),
    })
  })

  test('accepts reachable non-localhost websocket url', async () => {
    installChromeMock()
    const { validatePairingUrl } = await import('../src/background')

    expect(validatePairingUrl('wss://bot.example.com/ws/extension')).toEqual({
      ok: true,
      apiBase: 'https://bot.example.com',
      wsUrl: 'wss://bot.example.com/ws/extension',
    })
  })

  test('accepts https backend url and derives websocket endpoint', async () => {
    installChromeMock()
    const { validatePairingUrl } = await import('../src/background')

    expect(validatePairingUrl('https://bot.example.com')).toEqual({
      ok: true,
      apiBase: 'https://bot.example.com',
      wsUrl: 'wss://bot.example.com/ws/extension',
    })
  })
})
