// Todo campo de senha ganha "mostrar/ocultar" (pedido do Lucas, 16/11). Cobre campos criados depois (modais), sem duplicar o do login.js.
;(() => {
  const ja = (i) => i.dataset.olho || document.querySelector(`[data-ver="${i.id}"]`)
  function equipar(i) {
    if (ja(i)) return
    i.dataset.olho = '1'
    const caixa = document.createElement('div')
    caixa.style.position = 'relative'
    i.parentNode.insertBefore(caixa, i)
    caixa.appendChild(i)
    i.style.paddingRight = '72px'
    const b = document.createElement('button')
    b.type = 'button'
    b.textContent = 'mostrar'
    b.setAttribute('aria-label', 'Mostrar a senha')
    b.style.cssText = 'position:absolute;right:8px;top:50%;transform:translateY(-50%);background:none;border:0;color:inherit;opacity:.75;font-size:13px;font-weight:600;cursor:pointer;padding:6px'
    b.onclick = () => {
      const ver = i.type === 'password'
      i.type = ver ? 'text' : 'password'
      b.textContent = ver ? 'ocultar' : 'mostrar'
      b.setAttribute('aria-label', ver ? 'Ocultar a senha' : 'Mostrar a senha')
      i.focus()
    }
    caixa.appendChild(b)
  }
  const varrer = (r) => r.querySelectorAll && r.querySelectorAll('input[type="password"]').forEach(equipar)
  varrer(document)
  new MutationObserver((ms) => ms.forEach((m) => m.addedNodes.forEach((n) => n.nodeType === 1 && (n.matches?.('input[type="password"]') ? equipar(n) : varrer(n))))).observe(document.body, { childList: true, subtree: true })
})()
