import type { Rule } from './types'
import type { VaultData } from './types'

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

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

function simulateClick(el: HTMLElement): void {
  el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: window }))
  el.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: window }))
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
  const isHiddenInput = element.tagName.toLowerCase() === 'input'
    && (style.opacity === '0' || style.clip !== 'auto' || style.position === 'absolute')
  if (isHiddenInput && element.parentElement) {
    element = element.parentElement
  }
  return element
}

async function applyRule(rule: Rule): Promise<boolean> {
  const element = resolveElement(rule.selector)
  if (!element) return false

  if (rule.type === 'checkbox') {
    if (element instanceof HTMLInputElement && (element.type === 'radio' || element.type === 'checkbox')) {
      element.checked = true
      element.dispatchEvent(new Event('input', { bubbles: true }))
      element.dispatchEvent(new Event('change', { bubbles: true }))
      return true
    }
    simulateClick(element)
    return true
  }

  if (element instanceof HTMLInputElement && (element.type === 'radio' || element.type === 'checkbox')) {
    element.checked = true
    element.dispatchEvent(new Event('input', { bubbles: true }))
    element.dispatchEvent(new Event('change', { bubbles: true }))
    return true
  }

  if (element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement || element instanceof HTMLSelectElement) {
    nativeSet(element, rule.value || '')
    return true
  }

  simulateClick(element)
  if ((rule.value || '').trim() !== '') {
    await sleep(500)
    const option = findOptionByText(rule.value || '')
    if (option) {
      simulateClick(option)
    }
  }
  return true
}

async function executeFill(vault: VaultData): Promise<void> {
  const hostname = getTopHostname()
  const baseHost = hostname.replace(/^www\./, '')
  const rules = vault.domainRules[hostname] || vault.domainRules[baseHost] || []

  for (const rule of rules) {
    if (!rule.selector.trim()) continue
    await applyRule(rule)
    await sleep(200)
  }
}

chrome.runtime.sendMessage({ type: 'request_fill_data' }, (res) => {
  if (res?.success && res.vault.autoFillEnabled) {
    setTimeout(() => {
      void executeFill(res.vault as VaultData)
    }, 800)
  }
})

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === 'fill_form') {
    chrome.runtime.sendMessage({ type: 'request_fill_data' }, (res) => {
      if (res?.success) {
        executeFill(res.vault as VaultData)
          .then(() => sendResponse({ ok: true }))
          .catch((error: unknown) => {
            sendResponse({ ok: false, error: error instanceof Error ? error.message : String(error) })
          })
      } else {
        sendResponse({ ok: false, error: 'Vault missing' })
      }
    })
    return true
  }
  return false
})
