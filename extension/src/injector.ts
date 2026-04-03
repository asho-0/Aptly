import type { Rule, UserProfile, VaultData } from './types'

const GEWOBAG_WBS_ROOMS: Record<number, string> = {
  1: '1 Raum oder 1 1/2 und 2 Räume bis zu 50qm ',
  2: '2 Räume ',
  3: '3 Räume ',
  4: '4 Räume ',
  5: '5 Räume ',
  6: '6 Räume ',
  7: '7 Räume ',
}

function cloneRule(rule: Rule): Rule {
  return {
    selector: rule.selector,
    value: rule.value || '',
    valueKey: rule.valueKey,
    type: rule.type,
  }
}

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

function normalizeHost(hostname: string): string {
  return hostname.replace(/^www\./, '').toLowerCase()
}

function stringifyValue(value: string | number | boolean | null): string {
  if (value === null) return ''
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  return String(value)
}

function getDirectProfileValue(profile: UserProfile, valueKey: string): string | number | boolean | null {
  if (valueKey in profile) {
    return profile[valueKey as keyof UserProfile]
  }
  return null
}

function resolveRuleValue(domain: string, rule: Rule, profile: UserProfile): string | number | boolean | null {
  if (!rule.valueKey) {
    return rule.value
  }
  if (rule.valueKey === 'always_true') {
    return true
  }
  if (rule.valueKey === 'address_full') {
    return [profile.street, profile.house_number].filter(Boolean).join(' ').trim()
  }
  if (rule.valueKey === 'self_usage') {
    return 'Für mich selbst '
  }
  if (rule.valueKey === 'wbs_date') {
    return profile.wbs_date
  }
  if (rule.valueKey === 'wbs_income') {
    if (profile.wbs_income === null) return ''
    if (domain === 'gewobag.de') return `WBS ${profile.wbs_income}`
    return profile.wbs_income
  }
  if (rule.valueKey === 'wbs_rooms') {
    if (profile.wbs_rooms === null) return ''
    if (domain === 'gewobag.de') return GEWOBAG_WBS_ROOMS[profile.wbs_rooms] || `${profile.wbs_rooms} Räume `
    return profile.wbs_rooms
  }
  return getDirectProfileValue(profile, rule.valueKey)
}

function isTruthyRuleValue(value: string | number | boolean | null): boolean {
  if (typeof value === 'boolean') return value
  if (typeof value === 'number') return value > 0
  return String(value || '').trim().length > 0
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

function resolveElement(selector: string): HTMLElement | null {
  const found = document.querySelector<HTMLElement>(selector)
  if (!found) return null
  if (found.tagName.toLowerCase() !== 'input') return found
  const style = window.getComputedStyle(found)
  const hiddenInput = style.opacity === '0' || style.clip !== 'auto' || style.position === 'absolute'
  if (hiddenInput && found.parentElement) {
    return found.parentElement
  }
  return found
}

function getRulesForHost(domainRules: Record<string, Rule[]>, hostname: string): { domain: string; rules: Rule[] } {
  const normalizedHost = normalizeHost(hostname)
  const direct = domainRules[normalizedHost]
  if (direct) {
    return { domain: normalizedHost, rules: direct }
  }
  return { domain: normalizedHost, rules: [] }
}

function getTopHostname(): string {
  if (window === window.top) return normalizeHost(window.location.hostname)
  if (location.ancestorOrigins && location.ancestorOrigins.length > 0) {
    const topOrigin = location.ancestorOrigins[location.ancestorOrigins.length - 1]
    try {
      return normalizeHost(new URL(topOrigin).hostname)
    } catch {
      return normalizeHost(window.location.hostname)
    }
  }
  return normalizeHost(window.location.hostname)
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function applyValueRule(selector: string, value: string): Promise<boolean> {
  const element = resolveElement(selector)
  if (!element) return false
  if (element instanceof HTMLInputElement && (element.type === 'radio' || element.type === 'checkbox')) {
    element.checked = true
    element.dispatchEvent(new Event('input', { bubbles: true }))
    element.dispatchEvent(new Event('change', { bubbles: true }))
    return true
  }
  if (element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement || element instanceof HTMLSelectElement) {
    nativeSet(element, value)
    return true
  }
  simulateClick(element)
  if (value.trim()) {
    await sleep(500)
    const option = findOptionByText(value)
    if (option) simulateClick(option)
  }
  return true
}

async function applyClickRule(selector: string, value: string): Promise<boolean> {
  const element = resolveElement(selector)
  if (!element) return false
  simulateClick(element)
  if (value.trim()) {
    await sleep(500)
    const option = findOptionByText(value)
    if (option) simulateClick(option)
  }
  return true
}

async function applyCheckboxRule(selector: string, value: string | number | boolean | null): Promise<boolean> {
  if (!isTruthyRuleValue(value)) return true
  const element = document.querySelector<HTMLElement>(selector)
  if (!element) return false
  if (element instanceof HTMLInputElement && (element.type === 'checkbox' || element.type === 'radio')) {
    element.checked = true
    element.dispatchEvent(new Event('input', { bubbles: true }))
    element.dispatchEvent(new Event('change', { bubbles: true }))
    return true
  }
  simulateClick(element)
  return true
}

export function hydrateDomainRules(baseRules: Record<string, Rule[]>, profile: UserProfile): Record<string, Rule[]> {
  return Object.fromEntries(
    Object.entries(baseRules).map(([domain, rules]) => [
      domain,
      rules.map((rule) => {
        const cloned = cloneRule(rule)
        cloned.value = stringifyValue(resolveRuleValue(domain, cloned, profile))
        return cloned
      }),
    ]),
  )
}

export function stripRuleValues(domainRules: Record<string, Rule[]>): Record<string, Rule[]> {
  return Object.fromEntries(
    Object.entries(domainRules).map(([domain, rules]) => [
      domain,
      rules.map((rule) => ({
        selector: rule.selector,
        value: '',
        valueKey: rule.valueKey,
        type: rule.type,
      })),
    ]),
  )
}

export async function executeVaultFill(vault: VaultData): Promise<number> {
  const { domain, rules } = getRulesForHost(vault.domainRules, getTopHostname())
  let appliedCount = 0
  for (const rule of rules) {
    if (!rule.selector.trim()) continue
    const resolvedValue = resolveRuleValue(domain, rule, vault.profile)
    const action = rule.type || 'value'
    let applied = false
    if (action === 'click') {
      applied = await applyClickRule(rule.selector, stringifyValue(resolvedValue))
    } else if (action === 'checkbox') {
      applied = await applyCheckboxRule(rule.selector, resolvedValue)
    } else {
      applied = await applyValueRule(rule.selector, stringifyValue(resolvedValue))
    }
    if (applied) {
      appliedCount += 1
    }
    await sleep(200)
  }
  return appliedCount
}
