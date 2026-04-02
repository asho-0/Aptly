export function pickerScript(): void {
  const OUTLINE = '2px solid #ef4444';
  let lastEl: HTMLElement | null = null;
  const savedCursor = document.documentElement.style.cursor;
  document.documentElement.style.cursor = 'crosshair';

  function getCssPath(el: Element): string {
    const parts: string[] = [];
    let node: Element | null = el;
    while (node && node !== document.documentElement) {
      if (node.id) {
        parts.unshift('#' + node.id.replace(/([^\w-])/g, '\\$1'));
        break;
      }
      let tag = node.tagName.toLowerCase();
      const parent = node.parentElement;
      if (parent) {
        const same = Array.from(parent.children).filter((c) => c.tagName === node!.tagName);
        if (same.length > 1) tag += `:nth-of-type(${same.indexOf(node) + 1})`;
      }
      parts.unshift(tag);
      node = node.parentElement;
    }
    return parts.join(' > ') || el.tagName.toLowerCase();
  }

  function cleanup(): void {
    document.removeEventListener('mouseover', onOver, true);
    document.removeEventListener('mouseout', onOut, true);
    document.removeEventListener('click', onClick, true);
    document.removeEventListener('keydown', onKey, true);
    if (lastEl) lastEl.style.outline = '';
    document.documentElement.style.cursor = savedCursor;
  }

  function onOver(e: MouseEvent): void {
    const t = e.target as HTMLElement;
    if (lastEl && lastEl !== t) lastEl.style.outline = '';
    lastEl = t;
    t.style.outline = OUTLINE;
  }

  function onOut(e: MouseEvent): void {
    (e.target as HTMLElement).style.outline = '';
  }

  function onClick(e: MouseEvent): void {
    e.preventDefault(); e.stopPropagation(); e.stopImmediatePropagation();
    const selector = getCssPath(e.target as Element);
    cleanup();
    chrome.storage.local.set({ _tempPickedSelector: selector });
  }

  function onKey(e: KeyboardEvent): void {
    if (e.key === 'Escape') { cleanup(); }
  }

  document.addEventListener('mouseover', onOver, true);
  document.addEventListener('mouseout', onOut, true);
  document.addEventListener('click', onClick, true);
  document.addEventListener('keydown', onKey, true);
}