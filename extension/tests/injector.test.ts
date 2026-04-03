import { executeVaultFill, hydrateDomainRules } from '../src/injector'
import type { VaultData } from '../src/types'

function createVault(overrides: Partial<VaultData> = {}): VaultData {
  return {
    autoFillEnabled: false,
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
      ...(overrides.profile ?? {}),
    },
    domainRules: overrides.domainRules ?? {},
  }
}

describe('injector', () => {
  test('hydrates normalized profile fields into rules', () => {
    const hydrated = hydrateDomainRules(
      {
        'degewo.de': [
          { selector: '#firstName', value: '', valueKey: 'first_name' },
          { selector: '#zip', value: '', valueKey: 'zip_code' },
        ],
        'wbm.de': [
          { selector: '#street', value: '', valueKey: 'address_full' },
        ],
        'gewobag.de': [
          { selector: '#date', value: '', valueKey: 'wbs_date' },
          { selector: '#income', value: '', valueKey: 'wbs_income' },
          { selector: '#rooms', value: '', valueKey: 'wbs_rooms' },
        ],
      },
      {
        salutation: 'Herr',
        first_name: 'Asho',
        last_name: 'Case',
        email: 'asho@example.com',
        phone: '+49123456789',
        street: 'Teststrasse',
        house_number: '1',
        zip_code: '10115',
        city: 'Berlin',
        persons_total: 2,
        wbs_available: true,
        wbs_date: '01.04.2026',
        wbs_rooms: 2,
        wbs_income: 140,
      },
    )

    expect(hydrated['degewo.de'][0].value).toBe('Asho')
    expect(hydrated['degewo.de'][1].value).toBe('10115')
    expect(hydrated['wbm.de'][0].value).toBe('Teststrasse 1')
    expect(hydrated['gewobag.de'][0].value).toBe('01.04.2026')
    expect(hydrated['gewobag.de'][1].value).toBe('WBS 140')
    expect(hydrated['gewobag.de'][2].value).toBe('2 Räume ')
  })

  test('executes without throwing when rules target interactive elements', async () => {
    vi.useFakeTimers()
    document.body.innerHTML = `
      <div id="wrapper">
        <input id="hidden-input" style="opacity: 0; position: absolute;" />
      </div>
      <button id="menu"></button>
      <div role="option" id="option">Für mich selbst </div>
      <button id="submit" type="submit">Submit</button>
    `

    const wrapper = document.querySelector<HTMLElement>('#wrapper')!
    const menu = document.querySelector<HTMLElement>('#menu')!
    const option = document.querySelector<HTMLElement>('#option')!

    const wrapperSpy = vi.spyOn(wrapper, 'click')
    const menuSpy = vi.spyOn(menu, 'click')
    const optionSpy = vi.spyOn(option, 'click')
    const host = window.location.hostname

    const promise = executeVaultFill(createVault({
      profile: {
        first_name: 'Asho',
      },
      domainRules: {
        [host]: [
          { selector: '#hidden-input', value: 'Asho' },
          { selector: '#menu', value: 'Für mich selbst ', type: 'click' },
        ],
      },
    }))

    await vi.runAllTimersAsync()
    await promise

    expect(wrapperSpy).toHaveBeenCalled()
    expect(menuSpy).toHaveBeenCalled()
    expect(optionSpy).toHaveBeenCalled()
  })

  test('checks checkbox rules backed by always_true', async () => {
    document.body.innerHTML = '<input id="privacy" type="checkbox" />'
    const checkbox = document.querySelector<HTMLInputElement>('#privacy')!
    const host = window.location.hostname

    const applied = await executeVaultFill(createVault({
      domainRules: {
        [host]: [
          { selector: '#privacy', value: '', valueKey: 'always_true', type: 'checkbox' },
        ],
      },
    }))

    expect(applied).toBe(1)
    expect(checkbox.checked).toBe(true)
  })
})
