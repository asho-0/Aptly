import { hydrateDomainRules, stripRuleValues } from './injector'
import type { Rule, UserProfile, VaultData } from './types'
import { VAULT_DEFAULTS } from './types'

const KEEPALIVE_ALARM = 'ws-keepalive'
const RECONNECT_ALARM = 'ws-reconnect'
const RULES_FILE = 'autofilled-rules.json'
const WS_URL = (import.meta.env.VITE_WS_URL || '').trim()

type ExecuteFillMessage = {
  type: 'execute_fill'
  requestId: string
  payload: {
    apartmentUrl: string
    userData: UserProfile
  }
}

type ProfileUpdatedMessage = {
  type: 'profile_updated'
  payload: {
    profile: UserProfile
  }
}

type PairResponse = {
  token: string
  chatId: string
  profile: UserProfile
}

let socket: WebSocket | null = null
let baseDomainRulesCache: Record<string, Rule[]> | null = null

function cloneDomainRules(domainRules: Record<string, Rule[]>): Record<string, Rule[]> {
  return Object.fromEntries(
    Object.entries(domainRules).map(([domain, rules]) => [
      domain,
      rules.map((rule) => ({
        selector: rule.selector,
        value: rule.value || '',
        valueKey: rule.valueKey,
        type: rule.type,
      })),
    ]),
  )
}

function profileFromUnknown(value: unknown): UserProfile {
  if (!value || typeof value !== 'object') {
    return { ...VAULT_DEFAULTS.profile }
  }
  const data = value as Record<string, unknown>
  return {
    salutation: String(data.salutation || ''),
    first_name: String(data.first_name || ''),
    last_name: String(data.last_name || ''),
    email: String(data.email || ''),
    phone: String(data.phone || ''),
    street: String(data.street || ''),
    house_number: String(data.house_number || ''),
    zip_code: String(data.zip_code || ''),
    city: String(data.city || ''),
    persons_total: typeof data.persons_total === 'number' ? data.persons_total : data.persons_total ? Number(data.persons_total) : null,
    wbs_available: Boolean(data.wbs_available),
    wbs_date: String(data.wbs_date || ''),
    wbs_rooms: typeof data.wbs_rooms === 'number' ? data.wbs_rooms : data.wbs_rooms ? Number(data.wbs_rooms) : null,
    wbs_income: typeof data.wbs_income === 'number' ? data.wbs_income : data.wbs_income ? Number(data.wbs_income) : null,
  }
}

async function getVaultData(): Promise<VaultData> {
  const result = await chrome.storage.local.get(['vaultData'])
  return { ...VAULT_DEFAULTS, ...(result.vaultData || {}) }
}

async function saveVaultData(vault: VaultData): Promise<void> {
  await chrome.storage.local.set({ vaultData: vault })
}

function canInjectIntoUrl(url: string | undefined): boolean {
  if (!url) {
    return false
  }
  return /^(https?|file):/i.test(url)
}

function scheduleReconnect(): void {
  chrome.alarms.create(RECONNECT_ALARM, { delayInMinutes: 0.5 })
}

function mapWsToHttpBase(wsUrl: string): string {
  const parsed = new URL(wsUrl)
  parsed.protocol = parsed.protocol === 'wss:' ? 'https:' : 'http:'
  parsed.pathname = ''
  parsed.search = ''
  parsed.hash = ''
  return parsed.toString().replace(/\/$/, '')
}

async function loadBaseDomainRules(): Promise<Record<string, Rule[]>> {
  if (baseDomainRulesCache) {
    return cloneDomainRules(baseDomainRulesCache)
  }
  const response = await fetch(chrome.runtime.getURL(RULES_FILE))
  if (!response.ok) {
    throw new Error(`Failed to load ${RULES_FILE}`)
  }
  const parsed = await response.json() as { domainRules?: Record<string, Rule[]> }
  if (!parsed.domainRules || typeof parsed.domainRules !== 'object') {
    throw new Error(`${RULES_FILE} has invalid schema`)
  }
  baseDomainRulesCache = cloneDomainRules(parsed.domainRules)
  return cloneDomainRules(baseDomainRulesCache)
}

async function applyProfileToVault(profile: UserProfile): Promise<VaultData> {
  const baseRules = await loadBaseDomainRules()
  const vault = await getVaultData()
  const nextVault: VaultData = {
    ...vault,
    profile,
    domainRules: hydrateDomainRules(baseRules, profile),
  }
  await saveVaultData(nextVault)
  return nextVault
}

async function ensureSocket(): Promise<void> {
  if (!WS_URL) {
    return
  }
  const vault = await getVaultData()
  const token = vault.extensionToken.trim()
  if (!token) {
    return
  }
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
    return
  }
  socket = new WebSocket(WS_URL)
  socket.addEventListener('open', () => {
    socket?.send(JSON.stringify({ type: 'authenticate', token }))
  })
  socket.addEventListener('message', (event) => {
    void handleSocketMessage(event.data)
  })
  socket.addEventListener('close', () => {
    socket = null
    scheduleReconnect()
  })
  socket.addEventListener('error', () => {
    socket?.close()
  })
}

function injectedFill(vault: VaultData): void {
  function nativeSet(el: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement, value: string): void {
    const proto = el instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype
      : el instanceof HTMLSelectElement
        ? HTMLSelectElement.prototype
        : HTMLInputElement.prototype
    const descriptor = Object.getOwnPropertyDescriptor(proto, 'value')
    if (descriptor?.set) descriptor.set.call(el, value)
    else el.value = value
    el.dispatchEvent(new Event('input', { bubbles: true }))
    el.dispatchEvent(new Event('change', { bubbles: true }))
  }

  function simulateClick(el: HTMLElement): void {
    el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true }))
    el.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true }))
    el.click()
  }

  function findOptionByText(text: string): HTMLElement | null {
    const targetText = text.trim().toLowerCase()
    if (!targetText) return null
    const options = document.querySelectorAll<HTMLElement>('[role="option"], .ng-option, li')
    for (let i = options.length - 1; i >= 0; i -= 1) {
      const option = options[i]
      const optionText = (option.textContent || '').replace(/\s+/g, ' ').trim().toLowerCase()
      const nestedLabel = option.querySelector<HTMLElement>('[aria-label]')
      const ariaText = (nestedLabel?.getAttribute('aria-label') || '').trim().toLowerCase()
      if (optionText === targetText || ariaText === targetText) {
        return option
      }
    }
    return null
  }

  function getTopHostname(): string {
    if (window === window.top) return window.location.hostname
    if (location.ancestorOrigins && location.ancestorOrigins.length > 0) {
      const topOrigin = location.ancestorOrigins[location.ancestorOrigins.length - 1]
      try {
        return new URL(topOrigin).hostname
      } catch {
        return window.location.hostname
      }
    }
    return window.location.hostname
  }

  function resolveElement(selector: string): HTMLElement | null {
    let element = document.querySelector<HTMLElement>(selector)
    if (!element) return null
    const style = window.getComputedStyle(element)
    const hiddenInput = element.tagName.toLowerCase() === 'input'
      && (style.opacity === '0' || style.clip !== 'auto' || style.position === 'absolute')
    if (hiddenInput && element.parentElement) {
      element = element.parentElement
    }
    return element
  }

  const hostname = getTopHostname()
  const baseHost = hostname.replace(/^www\./, '')
  const rules = vault.domainRules[hostname] || vault.domainRules[baseHost] || []

  let delay = 0
  for (const rule of rules) {
    if (!rule.selector.trim()) continue
    const value = rule.value || ''
    setTimeout(() => {
      const element = resolveElement(rule.selector)
      if (!element) return
      if (element instanceof HTMLInputElement && (element.type === 'radio' || element.type === 'checkbox')) {
        element.checked = true
        element.dispatchEvent(new Event('input', { bubbles: true }))
        element.dispatchEvent(new Event('change', { bubbles: true }))
        return
      }
      if (element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement || element instanceof HTMLSelectElement) {
        nativeSet(element, value)
        return
      }
      simulateClick(element)
      if (value.trim()) {
        setTimeout(() => {
          const option = findOptionByText(value)
          if (option) simulateClick(option)
        }, 500)
      }
    }, delay)
    delay += 200
  }
}

async function tryFillViaContentScript(tabId: number): Promise<boolean> {
  try {
    const response = await chrome.tabs.sendMessage(tabId, { type: 'fill_form' }) as { ok: boolean; error?: string } | undefined
    if (!response?.ok) {
      throw new Error(response?.error || 'fill_form failed')
    }
    return true
  } catch {
    return false
  }
}

async function fillTab(tabId: number): Promise<{ ok: boolean; error?: string }> {
  const tab = await chrome.tabs.get(tabId)
  if (!canInjectIntoUrl(tab.url)) {
    throw new Error('This page does not allow extension autofill')
  }
  if (await tryFillViaContentScript(tabId)) {
    return { ok: true }
  }
  const vault = await getVaultData()
  await chrome.scripting.executeScript({
    target: { tabId, allFrames: true },
    func: injectedFill,
    args: [vault],
  })
  return { ok: true }
}

function waitForTabComplete(tabId: number): Promise<void> {
  return new Promise((resolve, reject) => {
    let settled = false
    const finish = (callback: () => void): void => {
      if (settled) return
      settled = true
      chrome.tabs.onUpdated.removeListener(listener)
      clearTimeout(timeoutId)
      callback()
    }
    chrome.tabs.get(tabId).then((tab) => {
      if (tab.status === 'complete') {
        finish(resolve)
      }
    }).catch(() => {
      finish(() => reject(new Error('Tab lookup failed')))
    })
    const timeoutId = setTimeout(() => {
      finish(() => reject(new Error('Tab load timed out')))
    }, 30000)
    const listener = (updatedTabId: number, changeInfo: chrome.tabs.TabChangeInfo): void => {
      if (updatedTabId !== tabId || changeInfo.status !== 'complete') {
        return
      }
      finish(resolve)
    }
    chrome.tabs.onUpdated.addListener(listener)
  })
}

async function sendFillResult(message: { requestId: string; status: 'success' | 'error'; error?: string }): Promise<void> {
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    return
  }
  socket.send(JSON.stringify({
    type: 'fill_result',
    requestId: message.requestId,
    status: message.status,
    error: message.error,
  }))
}

async function handleSocketMessage(rawMessage: string): Promise<void> {
  const message = JSON.parse(rawMessage) as ExecuteFillMessage | ProfileUpdatedMessage | { type: string; payload?: unknown }
  if (message.type === 'profile_updated') {
    await applyProfileToVault(profileFromUnknown((message as ProfileUpdatedMessage).payload?.profile))
    return
  }
  if (message.type !== 'execute_fill') {
    return
  }
  try {
    const executeMessage = message as ExecuteFillMessage
    await applyProfileToVault(profileFromUnknown(executeMessage.payload.userData))
    const tab = await chrome.tabs.create({ url: executeMessage.payload.apartmentUrl, active: true })
    if (!tab.id) {
      throw new Error('Created tab does not have an id')
    }
    await waitForTabComplete(tab.id)
    await fillTab(tab.id)
    await sendFillResult({ requestId: executeMessage.requestId, status: 'success' })
  } catch (error) {
    await sendFillResult({
      requestId: (message as ExecuteFillMessage).requestId,
      status: 'error',
      error: error instanceof Error ? error.message : String(error),
    })
  }
}

async function pairWithPin(pin: string): Promise<{ ok: boolean; error?: string; vault?: VaultData }> {
  if (!WS_URL) {
    return { ok: false, error: 'VITE_WS_URL is not configured' }
  }
  const apiBase = mapWsToHttpBase(WS_URL)
  const response = await fetch(`${apiBase}/api/pair`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pin }),
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => ({} as Record<string, string>))
    return { ok: false, error: String(payload.error || 'Invalid PIN') }
  }
  const paired = await response.json() as PairResponse
  const hydratedVault = await applyProfileToVault(profileFromUnknown(paired.profile))
  const nextVault: VaultData = {
    ...hydratedVault,
    extensionToken: paired.token,
    pairedChatId: paired.chatId,
    pairPin: pin,
  }
  await saveVaultData(nextVault)
  if (socket) {
    socket.close()
  } else {
    await ensureSocket()
  }
  return { ok: true, vault: nextVault }
}

async function resetPairing(): Promise<{ ok: boolean; vault: VaultData }> {
  if (socket) {
    socket.close()
    socket = null
  }
  const vault = await getVaultData()
  const nextVault: VaultData = {
    ...vault,
    pairPin: '',
    extensionToken: '',
    pairedChatId: '',
    profile: { ...VAULT_DEFAULTS.profile },
    domainRules: stripRuleValues(vault.domainRules),
  }
  await saveVaultData(nextVault)
  return { ok: true, vault: nextVault }
}

async function initializeBaseRules(): Promise<void> {
  const baseRules = await loadBaseDomainRules()
  const vault = await getVaultData()
  if (Object.keys(vault.domainRules).length > 0) {
    return
  }
  const nextVault: VaultData = {
    ...vault,
    domainRules: hydrateDomainRules(baseRules, vault.profile),
  }
  await saveVaultData(nextVault)
}

function setupKeepalive(): void {
  chrome.alarms.create(KEEPALIVE_ALARM, { periodInMinutes: 0.5 })
}

chrome.runtime.onInstalled.addListener(() => {
  setupKeepalive()
  void initializeBaseRules()
  void ensureSocket()
})

chrome.runtime.onStartup.addListener(() => {
  setupKeepalive()
  void initializeBaseRules()
  void ensureSocket()
})

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === KEEPALIVE_ALARM || alarm.name === RECONNECT_ALARM) {
    void ensureSocket()
  }
})

chrome.storage.onChanged.addListener((changes, areaName) => {
  if (areaName !== 'local' || !changes.vaultData) {
    return
  }
  if (socket) {
    socket.close()
  } else {
    void ensureSocket()
  }
})

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === 'request_fill_data') {
    getVaultData().then((vault) => {
      sendResponse({ success: true, vault })
    })
    return true
  }
  if (msg.type === 'pair_with_pin') {
    pairWithPin(String(msg.pin || '').trim())
      .then((result) => sendResponse(result))
      .catch((error: unknown) => {
        sendResponse({ ok: false, error: error instanceof Error ? error.message : String(error) })
      })
    return true
  }
  if (msg.type === 'reset_pairing') {
    resetPairing()
      .then((result) => sendResponse(result))
      .catch(() => {
        sendResponse({ ok: false, error: 'Failed to reset pairing' })
      })
    return true
  }
  if (msg.type === 'execute_fill_in_tab') {
    fillTab(Number(msg.tabId))
      .then((result) => sendResponse(result))
      .catch((error: unknown) => {
        sendResponse({ ok: false, error: error instanceof Error ? error.message : String(error) })
      })
    return true
  }
  return false
})

setupKeepalive()
void initializeBaseRules()
void ensureSocket()
