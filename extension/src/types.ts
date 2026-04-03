export type RuleType = 'value' | 'click' | 'checkbox'

export interface Rule {
  selector: string
  value: string
  valueKey?: string
  type?: RuleType
}

export interface UserProfile {
  salutation: string
  first_name: string
  last_name: string
  email: string
  phone: string
  street: string
  house_number: string
  zip_code: string
  city: string
  persons_total: number | null
  wbs_available: boolean
  wbs_date: string
  wbs_rooms: number | null
  wbs_income: number | null
}

export interface VaultData {
  autoFillEnabled: boolean
  backendUrl: string
  domainRules: Record<string, Rule[]>
  pairPin: string
  extensionToken: string
  pairedChatId: string
  profile: UserProfile
}

export interface DomainRule extends Rule {}

export interface LocalStorage {
  vaultCipher: string
}

export interface SessionStorage {
  unlockedVault: VaultData
  sessionKey: string
}

export type BgRequest =
  | { type: 'request_fill_data' }
  | { type: 'fill_form' }

export type BgResponse =
  | { status: 'ok'; vault: VaultData }
  | { status: 'locked' }
  | { status: 'error'; message: string }

export const VAULT_DEFAULTS: VaultData = {
  autoFillEnabled: false,
  backendUrl: '',
  domainRules: {},
  pairPin: '',
  extensionToken: '',
  pairedChatId: '',
  profile: {
    salutation: '',
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
    street: '',
    house_number: '',
    zip_code: '',
    city: '',
    persons_total: null,
    wbs_available: false,
    wbs_date: '',
    wbs_rooms: null,
    wbs_income: null,
  },
}
