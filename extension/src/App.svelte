<script lang="ts">
  import { onMount }      from 'svelte'
  import { pickerScript } from './picker'
  import { VAULT_DEFAULTS, type VaultData, type DomainRule } from './types'

  let status         = ''
  let statusOk       = true
  let importError    = ''
  let activeTab      = ''     
  let selectedDomain = ''     

  let vault: VaultData = {
    ...VAULT_DEFAULTS,
  }

  $: isPaired = Boolean(vault.extensionToken.trim() && vault.pairedChatId.trim())
  $: domains      = Object.keys(vault.domainRules)
  $: currentRules = vault.domainRules[selectedDomain] ?? []
  $: sortedDomains = domains.includes(activeTab)
      ? [activeTab, ...domains.filter(d => d !== activeTab)]
      : domains

  onMount(async () => {
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
      if (tab?.url) activeTab = new URL(tab.url).hostname.replace(/^www\./, '')
    } catch {}

    const local = await chrome.storage.local.get(['vaultData', '_tempPickedSelector'])
    
    if (local.vaultData) {
      vault = { ...vault, ...local.vaultData }
    } else {
      await persist()
    }

    selectedDomain = activeTab || Object.keys(vault.domainRules)[0] || ''

    const pickSession = await chrome.storage.session.get(['activePickDomain', 'activePickIndex'])
    
    if (local._tempPickedSelector && pickSession.activePickDomain) {
      const d = pickSession.activePickDomain
      const i = pickSession.activePickIndex
      if (vault.domainRules[d] && vault.domainRules[d][i]) {
        vault.domainRules[d][i].selector = local._tempPickedSelector
        vault = { ...vault }
        await persist()
      }
      await chrome.storage.local.remove(['_tempPickedSelector'])
      await chrome.storage.session.remove(['activePickDomain', 'activePickIndex'])
    }
  })

  async function persist(): Promise<void> {
    try { await chrome.storage.local.set({ vaultData: vault }) }
    catch (e) { flash(`✗ Save failed: ${String(e)}`, false) }
  }

  async function pairWithPin(): Promise<void> {
    const pin = vault.pairPin.trim()
    if (!pin) {
      flash('✗ Enter pairing PIN', false)
      return
    }

    const response = await chrome.runtime.sendMessage({ type: 'pair_with_pin', pin }) as
      { ok: boolean; error?: string; vault?: VaultData }

    if (!response?.ok || !response.vault) {
      flash(`✗ Pairing failed. ${response?.error ?? 'Check extension backend connection.'}`, false)
      return
    }

    vault = { ...vault, ...response.vault, pairPin: pin }
    await persist()
    flash('✓ Paired successfully', true)
  }

  async function resetPairing(): Promise<void> {
    const response = await chrome.runtime.sendMessage({ type: 'reset_pairing' }) as
      { ok: boolean; error?: string; vault?: VaultData }
    if (!response?.ok || !response.vault) {
      flash(`✗ ${response?.error ?? 'Could not reset pair'}`, false)
      return
    }
    vault = { ...vault, ...response.vault }
    selectedDomain = ''
    await persist()
    flash('✓ Pair cleared', true)
  }

  function addDomain(): void {
    if (!activeTab) {
      flash('✗ No active tab to read domain from', false)
      return
    }
    if (!vault.domainRules[activeTab]) {
      vault.domainRules[activeTab] = []
      vault          = { ...vault }
      persist()
    }
    selectedDomain = activeTab
  }

  function deleteDomain(d: string): void {
    const copy = { ...vault.domainRules }
    delete copy[d]
    vault          = { ...vault, domainRules: copy }
    if (selectedDomain === d) {
      selectedDomain = ''
    }
    persist()
  }

  function addRule(): void {
    if (!selectedDomain) return
    vault.domainRules[selectedDomain] = [
      ...(vault.domainRules[selectedDomain] ?? []),
      { selector: '', value: '', valueKey: '', type: 'value' },
    ]
    vault = { ...vault }
    persist()
  }

  function removeRule(i: number): void {
    vault.domainRules[selectedDomain] = currentRules.filter((_, idx) => idx !== i)
    vault = { ...vault }
    persist()
  }

  function isSubmitOrButton(selector: string): boolean {
    if (!selector) return false
    return /button|\[type=["']?submit["']?\]/i.test(selector)
  }


  function updateRule(i: number, key: keyof DomainRule, val: string): void {
    const rules = [...currentRules]
    rules[i]    = { ...rules[i], [key]: val }
    
    if (key === 'selector' && isSubmitOrButton(val)) {
      rules[i].value = ''
    }

    vault.domainRules[selectedDomain] = rules
    vault = { ...vault }
    persist()
  }

  async function pickElement(index: number): Promise<void> {
    await chrome.storage.session.set({
      activePickDomain: selectedDomain,
      activePickIndex:  index,
    })
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
    if (!tab?.id) return

    await chrome.scripting.executeScript({ 
      target: { tabId: tab.id, allFrames: true }, 
      func: pickerScript 
    })
    window.close()
  }

  async function executeFill(): Promise<void> {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
    if (!tab?.id) { flash('✗ No active tab', false); return }
    try {
      const res = await chrome.runtime.sendMessage({ type: 'execute_fill_in_tab', tabId: tab.id }) as
        { ok: boolean; error?: string } | undefined
      res?.ok
        ? flash('✓ Form filled!', true)
        : flash(`✗ ${res?.error ?? 'unknown error'}`, false)
    } catch {
      flash('✗ Fill failed on this page', false)
    }
  }

  function exportRules(): void {
    const sanitized: VaultData['domainRules'] = {}
    for (const [domain, rules] of Object.entries(vault.domainRules)) {
      sanitized[domain] = rules.map(r => ({
        selector: r.selector,
        value: '',
        valueKey: r.valueKey,
        type: r.type,
      }))
    }
    const blob = new Blob(
      [JSON.stringify({ domainRules: sanitized }, null, 2)],
      { type: 'application/json' }
    )
    const a    = document.createElement('a')
    a.href     = URL.createObjectURL(blob)
    a.download = 'autofiller-rules.json'
    a.click()
    URL.revokeObjectURL(a.href)
    flash('✓ Exported (values stripped)', true)
  }

  function importRules(e: Event): void {
    importError = ''
    const file  = (e.target as HTMLInputElement).files?.[0]
    if (!file) return

    const reader = new FileReader()
    reader.onload = async () => {
      try {
        const parsed = JSON.parse(reader.result as string) as {
          domainRules?: VaultData['domainRules']
        }
        if (!parsed.domainRules || typeof parsed.domainRules !== 'object') {
          importError = '✗ Invalid file — missing domainRules key.'
          return
        }
        for (const [domain, rules] of Object.entries(parsed.domainRules)) {
          vault.domainRules[domain] = [
            ...(vault.domainRules[domain] ?? []),
            ...rules.map((rule) => ({
              selector: rule.selector,
              value: rule.value ?? '',
              valueKey: rule.valueKey ?? '',
              type: rule.type ?? 'value',
            })),
          ]
        }
        vault = { ...vault }
        await persist()
        flash('✓ Rules imported & merged', true)
      } catch {
        importError = '✗ Could not parse JSON file.'
      }
    }
    reader.readAsText(file)
    ;(e.target as HTMLInputElement).value = ''
  }

  function flash(msg: string, ok: boolean): void {
    status   = msg
    statusOk = ok
    setTimeout(() => (status = ''), 3000)
  }

  function toggleDomain(domain: string): void {
    selectedDomain = selectedDomain === domain ? '' : domain
  }
</script>

<main class="w-[360px] bg-gray-950 text-gray-100 font-mono text-xs">

  <header class="flex items-center justify-between px-4 py-2.5 border-b border-gray-800">
    <h1 class="text-[11px] font-bold tracking-widest uppercase text-indigo-400">
      ⚡ Aptly
    </h1>
    <div class="flex items-center gap-3">
      <label class="flex items-center gap-1.5 cursor-pointer" title="Auto-fill on page load">
        <span class="text-gray-500 text-[10px]">Auto-Fill</span>
        <button
          class="relative inline-flex h-5 w-9 items-center rounded-full transition-colors"
          class:bg-indigo-600={vault.autoFillEnabled}
          class:bg-gray-700={!vault.autoFillEnabled}
          role="switch"
          aria-checked={vault.autoFillEnabled}
          on:click={() => { vault.autoFillEnabled = !vault.autoFillEnabled; persist() }}
        >
          <span
            class="inline-block h-3 w-3 transform rounded-full bg-white transition-transform"
            class:translate-x-5={vault.autoFillEnabled}
            class:translate-x-1={!vault.autoFillEnabled}
          />
        </button>
      </label>

    </div>
  </header>

  <div class="p-4 flex flex-col gap-5">

    <section>
      <div class="flex flex-col gap-2">
        <h2 class="section-title mb-0">Pair Extension</h2>
        {#if isPaired}
          <p class="text-[11px] text-emerald-300">Connected chat_id: {vault.pairedChatId}</p>
          <button class="btn-primary py-1.5 text-xs" on:click={resetPairing}>Create New Pair</button>
        {:else}
          <input
            class="field"
            type="text"
            placeholder="Backend URL: https://... or wss://..."
            value={vault.backendUrl}
            on:input={(e) => { vault.backendUrl = e.currentTarget.value.trim(); persist() }}
          />
          <input
            class="field"
            type="text"
            inputmode="numeric"
            maxlength="6"
            placeholder="Enter 6-digit Pairing PIN"
            value={vault.pairPin}
            on:input={(e) => { vault.pairPin = e.currentTarget.value.replace(/\D/g, '').slice(0, 6); persist() }}
          />
          <p class="text-[10px] leading-4 text-gray-500">
            If Orion runs on iPhone, `127.0.0.1` or `localhost` only works when the backend runs on that same device.
            You can paste either `https://host` or `wss://host/ws/extension` above. Use a reachable public host, VPN, or tunnel when iPhone and Mac are in different networks.
          </p>
          <button class="btn-primary py-1.5 text-xs" on:click={pairWithPin}>Connect</button>
        {/if}
      </div>
    </section>

    <section>
      <div class="flex items-center justify-between mb-2">
        <h2 class="section-title mb-0">Domain Rules</h2>
        <button
          class="text-[10px] text-indigo-400 hover:text-indigo-300 transition-colors"
          on:click={addDomain}
        >+ Domain</button>
      </div>

      {#if domains.length === 0}
        <p class="text-gray-600 text-[11px] italic">
          No domains yet. Navigate to a site and click "+ Domain".
        </p>
      {:else}
        <div class="flex flex-wrap gap-1 mb-2">
          {#each sortedDomains as d}
            <button
              class="px-2 py-0.5 rounded text-[10px] border transition-colors"
              class:bg-indigo-900={selectedDomain === d}
              class:border-indigo-500={selectedDomain === d}
              class:text-indigo-300={selectedDomain === d}
              class:bg-gray-900={selectedDomain !== d}
              class:border-gray-700={selectedDomain !== d}
              class:text-gray-400={selectedDomain !== d}
              on:click={() => toggleDomain(d)}
            >
              {d === activeTab ? '★ ' : ''}{d}
            </button>
          {/each}
        </div>

        {#if selectedDomain}
          <div class="space-y-1 mb-1.5">
            {#each currentRules as rule, i}
              <div class="flex items-center gap-1">
                <input
                  class="field w-36 text-emerald-300"
                  type="text"
                  placeholder="CSS selector"
                  value={rule.selector}
                  on:input={(e) => updateRule(i, 'selector', e.currentTarget.value)}
                />
                <input
                  class="field flex-1 min-w-0 transition-opacity"
                  class:opacity-40={isSubmitOrButton(rule.selector)}
                  class:cursor-not-allowed={isSubmitOrButton(rule.selector)}
                  class:bg-gray-800={isSubmitOrButton(rule.selector)}
                  type="text"
                  placeholder={isSubmitOrButton(rule.selector) ? 'Click only (no value)' : 'value'}
                  value={rule.value}
                  disabled={isSubmitOrButton(rule.selector)}
                  on:input={(e) => updateRule(i, 'value', e.currentTarget.value)}
                />
                <button
                  class="icon-btn text-amber-400 hover:bg-amber-900/30 hover:border-amber-600"
                  title="Pick element on page"
                  on:click={() => pickElement(i)}
                >🎯</button>
                <button
                  class="icon-btn text-gray-600 hover:text-red-400 hover:border-red-700"
                  title="Delete rule"
                  on:click={() => removeRule(i)}
                >✕</button>
              </div>
            {/each}
          </div>

          <div class="flex gap-1.5">
            <button
              class="flex-1 py-1 rounded border border-dashed border-gray-700
                     text-gray-500 hover:text-gray-300 hover:border-gray-500 transition-colors"
              on:click={addRule}
            >+ Add Rule</button>
            <button
              class="px-2 py-1 rounded border border-dashed border-red-900
                     text-red-800 hover:text-red-500 hover:border-red-600 transition-colors"
              title="Delete this domain"
              on:click={() => deleteDomain(selectedDomain)}
            >✕ Domain</button>
          </div>
        {/if}
      {/if}
    </section>

    <button
      class="btn-primary py-2 text-sm tracking-wide shadow-lg shadow-indigo-950"
      on:click={executeFill}
    >⚡ Execute Fill</button>

    {#if status}
      <p class="text-center text-[11px] -mt-3 whitespace-pre-line"
         class:text-emerald-400={statusOk}
         class:text-red-400={!statusOk}>{status}</p>
    {/if}

    <section class="border-t border-gray-800 pt-3">
      <h2 class="section-title">Export / Import Rules</h2>
      <div class="flex gap-2">
        <button
          class="flex-1 py-1.5 rounded border border-gray-700 text-gray-400
                 hover:text-gray-200 hover:border-gray-500 transition-colors text-[11px]"
          on:click={exportRules}
        >📤 Export (values stripped)</button>

        <label
          class="flex-1 py-1.5 rounded border border-gray-700 text-gray-400
                 hover:text-gray-200 hover:border-gray-500 transition-colors
                 text-[11px] text-center cursor-pointer"
        >
          📥 Import rules
          <input type="file" accept=".json" class="hidden" on:change={importRules} />
        </label>
      </div>
      {#if importError}
        <p class="text-red-400 text-[11px] mt-1">{importError}</p>
      {/if}
    </section>

  </div>

</main>

<style lang="postcss">
  :global(.section-title) {
    @apply text-[10px] uppercase tracking-widest text-gray-500 mb-2;
  }
  :global(.row)       { @apply flex items-center gap-2; }
  :global(.row-label) { @apply text-gray-400 w-10 shrink-0; }
  :global(.field) {
    @apply bg-gray-900 border border-gray-700 rounded px-2 py-1
           text-gray-100 placeholder-gray-600
           focus:border-indigo-500 focus:outline-none transition-colors;
    font-size: 11px;
  }
  :global(.icon-btn) {
    @apply shrink-0 px-1.5 py-1 rounded border border-gray-700
           bg-gray-800 transition-colors;
  }
  :global(.btn-primary) {
    @apply w-full rounded font-bold text-sm
           bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700
           text-white transition-colors;
  }
</style>
