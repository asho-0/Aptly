import { render, screen } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'

import App from '../src/App.svelte'
import { VAULT_DEFAULTS, type VaultData } from '../src/types'

type ChromeMockOptions = {
  vaultData?: Partial<VaultData>
  pairResponse?: VaultData
  resetResponse?: VaultData
  activeUrl?: string
}

function createVault(overrides: Partial<VaultData> = {}): VaultData {
  return {
    ...VAULT_DEFAULTS,
    ...overrides,
    profile: {
      ...VAULT_DEFAULTS.profile,
      ...(overrides.profile ?? {}),
    },
    domainRules: overrides.domainRules ?? {},
  }
}

function installChromeMock(options: ChromeMockOptions = {}) {
  const storage = {
    vaultData: options.vaultData ? createVault(options.vaultData) : undefined,
    _tempPickedSelector: undefined as string | undefined,
  }
  const sessionStorage = {
    activePickDomain: undefined as string | undefined,
    activePickIndex: undefined as number | undefined,
  }
  const sendMessage = vi.fn(async (message: { type: string }) => {
    if (message.type === 'pair_with_pin') {
      return {
        ok: true,
        vault: options.pairResponse ?? createVault({
          pairPin: '123456',
          extensionToken: 'token-1',
          pairedChatId: '777000',
        }),
      }
    }
    if (message.type === 'reset_pairing') {
      return {
        ok: true,
        vault: options.resetResponse ?? createVault(),
      }
    }
    return { ok: false, error: 'unsupported message' }
  })

  const chromeMock = {
    tabs: {
      query: vi.fn(async () => [{ id: 1, url: options.activeUrl ?? 'https://degewo.de/listing' }]),
      sendMessage: vi.fn(async () => ({ ok: true })),
    },
    scripting: {
      executeScript: vi.fn(async () => []),
    },
    runtime: {
      sendMessage,
    },
    storage: {
      local: {
        get: vi.fn(async (keys: string[]) => {
          const result: Record<string, unknown> = {}
          for (const key of keys) {
            if (key in storage) {
              result[key] = storage[key as keyof typeof storage]
            }
          }
          return result
        }),
        set: vi.fn(async (value: Record<string, unknown>) => {
          Object.assign(storage, value)
        }),
        remove: vi.fn(async (keys: string[]) => {
          for (const key of keys) {
            delete storage[key as keyof typeof storage]
          }
        }),
      },
      session: {
        get: vi.fn(async (keys: string[]) => {
          const result: Record<string, unknown> = {}
          for (const key of keys) {
            if (key in sessionStorage) {
              result[key] = sessionStorage[key as keyof typeof sessionStorage]
            }
          }
          return result
        }),
        set: vi.fn(async (value: Record<string, unknown>) => {
          Object.assign(sessionStorage, value)
        }),
        remove: vi.fn(async (keys: string[]) => {
          for (const key of keys) {
            delete sessionStorage[key as keyof typeof sessionStorage]
          }
        }),
      },
    },
  }

  vi.stubGlobal('chrome', chromeMock)
  return { chromeMock, storage }
}

describe('App.svelte', () => {
  test('switches between unpaired and paired states', async () => {
    const user = userEvent.setup()
    const { chromeMock } = installChromeMock()

    render(App)

    const pinInput = await screen.findByPlaceholderText('Enter 6-digit Pairing PIN')
    expect(screen.getByRole('button', { name: 'Connect' })).toBeTruthy()

    await user.type(pinInput, '123456')
    await user.click(screen.getByRole('button', { name: 'Connect' }))

    await screen.findByText('Connected chat_id: 777000')
    expect(screen.getByRole('button', { name: 'Create New Pair' })).toBeTruthy()
    expect(chromeMock.runtime.sendMessage).toHaveBeenCalledWith({ type: 'pair_with_pin', pin: '123456' })

    await user.click(screen.getByRole('button', { name: 'Create New Pair' }))

    await screen.findByPlaceholderText('Enter 6-digit Pairing PIN')
    expect(screen.queryByText('Connected chat_id: 777000')).toBeNull()
    expect(chromeMock.runtime.sendMessage).toHaveBeenCalledWith({ type: 'reset_pairing' })
  })

  test('renders the Aptly header with lightning icon', async () => {
    installChromeMock()

    render(App)

    expect(await screen.findByText('⚡ Aptly')).toBeTruthy()
  })
})
