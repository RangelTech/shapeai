// Login comum (Cortaí, Anima AI, Rendaí, Perfilaí, Atende AI, Posta AI): entrar SEMPRE com e-mail e senha.
// Código no e-mail só para criar a conta (confirmar o e-mail) e para 'esqueci a senha'. Senha é obrigatória.
// Na landing: <script src="/s/login.js" data-conta="/api/conta" data-destino="/app"></script> + <div class="modal" id="m-entrar"><div class="caixa">…
// No app: qualquer elemento [data-senha] abre "Minha senha" (criar ou trocar).
;(() => {
  const tag = document.currentScript
  const CONTA = tag?.dataset.conta || '/api/conta'
  const DESTINO = tag?.dataset.destino || '/app'
  const $ = (s, r = document) => r.querySelector(s)
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c])
  const post = async (url, corpo) => {
    const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corpo) })
    let j = {}
    try { j = await r.json() } catch {}
    if (!r.ok) throw new Error(typeof j.detail === 'string' ? j.detail : 'Não deu certo. Tente de novo.')
    return j
  }
  const largo = 'width:100%;margin-top:16px'
  const campoSenha = (id, rotulo, auto) => `<label for="${id}" style="margin-top:12px">${rotulo}</label>
    <div style="position:relative"><input id="${id}" type="password" autocomplete="${auto}" required minlength="${auto === 'current-password' ? 1 : 8}" style="padding-right:64px">
    <button type="button" data-ver="${id}" style="position:absolute;right:8px;top:50%;transform:translateY(-50%);background:none;border:0;color:inherit;opacity:.7;font-size:13px;cursor:pointer">mostrar</button></div>`

  const PASSOS = {
    senha: () => `<h3 id="m-tit">Entrar</h3><p>Use seu e-mail e sua senha.</p>
      <form data-f="senha"><label for="l-email">E-mail</label><input id="l-email" type="email" autocomplete="username" required placeholder="voce@email.com">
      ${campoSenha('l-senha', 'Senha', 'current-password')}
      <button class="btn btn-pri grande" style="${largo}" type="submit">Entrar</button></form>
      <button class="btn btn-sec" style="width:100%;margin-top:10px" type="button" data-ir="codigo">Primeira vez? Criar conta</button>
      <button class="link-demo" type="button" data-ir="esqueci">Esqueci minha senha</button>`,
    codigo: () => `<h3 id="m-tit">Criar conta</h3><p>Primeiro confirmamos o seu e-mail com um código de 6 números. Depois você cria a sua senha.</p>
      <form data-f="pedir"><label for="l-email">E-mail</label><input id="l-email" type="email" autocomplete="email" required placeholder="voce@email.com">
      <button class="btn btn-pri grande" style="${largo}" type="submit">Enviar código</button></form>
      <button class="link-demo" type="button" data-ir="senha">Já tenho conta</button>`,
    digitar: (e) => `<h3 id="m-tit">Digite o código</h3><p>Mandamos 6 números para ${esc(e)}. Confira também o spam.</p>
      <form data-f="codigo"><input id="l-codigo" class="cod" inputmode="numeric" autocomplete="one-time-code" maxlength="7" required placeholder="000000">
      <button class="btn btn-pri grande" style="${largo}" type="submit">Confirmar e-mail</button></form>
      <button class="link-demo" type="button" data-ir="codigo">Usar outro e-mail</button>`,
    criar: () => `<h3 id="m-tit">Crie sua senha</h3><p>E-mail confirmado. Agora escolha a senha que você vai usar para entrar.</p>
      <form data-f="criar">${campoSenha('l-nova', 'Senha (mínimo 8)', 'new-password')}
      <button class="btn btn-pri grande" style="${largo}" type="submit">Criar conta e entrar</button></form>`,
    esqueci: () => `<h3 id="m-tit">Esqueci minha senha</h3><p>Mandamos um código para o seu e-mail e você escolhe uma senha nova.</p>
      <form data-f="esqueci"><label for="l-email">E-mail</label><input id="l-email" type="email" autocomplete="email" required placeholder="voce@email.com">
      <button class="btn btn-pri grande" style="${largo}" type="submit">Enviar código</button></form>
      <button class="link-demo" type="button" data-ir="senha">Lembrei, voltar</button>`,
    redefinir: (e) => `<h3 id="m-tit">Senha nova</h3><p>Se ${esc(e)} tiver conta, chegou um código de 6 números.</p>
      <form data-f="redefinir"><label for="l-codigo">Código</label><input id="l-codigo" class="cod" inputmode="numeric" autocomplete="one-time-code" maxlength="7" required placeholder="000000">
      ${campoSenha('l-nova', 'Senha nova (mínimo 8)', 'new-password')}
      <button class="btn btn-pri grande" style="${largo}" type="submit">Salvar e entrar</button></form>
      <button class="link-demo" type="button" data-ir="esqueci">Mandar de novo</button>`,
  }

  function montar(modal, { aoEntrar }) {
    const caixa = $('.caixa', modal)
    const fechar = $('[data-fechar]', caixa)?.outerHTML || '<button class="x" data-fechar aria-label="Fechar">×</button>'
    let email = ''
    const corpo = document.createElement('div')
    const msgEl = document.createElement('div')
    msgEl.className = 'msg'; msgEl.setAttribute('role', 'alert')
    caixa.innerHTML = fechar; caixa.append(corpo, msgEl)
    const msg = (t, tipo = 'erro') => { msgEl.textContent = t || ''; msgEl.className = 'msg ' + tipo }
    const ir = (p) => {
      corpo.innerHTML = PASSOS[p](email); msg('')
      const ce = $('#l-email', corpo); if (ce && email) ce.value = email
      setTimeout(() => ($('#l-codigo', corpo) || (ce && !ce.value ? ce : null) || $('input[type=password]', corpo) || ce)?.focus(), 50)
    }
    caixa.addEventListener('click', async (e) => {
      const v = e.target.closest('[data-ver]')
      if (v) { const i = $('#' + v.dataset.ver, caixa); i.type = i.type === 'password' ? 'text' : 'password'; v.textContent = i.type === 'password' ? 'mostrar' : 'esconder'; return }
      const a = e.target.closest('[data-ir]')
      if (!a) return
      if (a.dataset.ir === 'pular') return aoEntrar()
      const ce = $('#l-email', corpo); if (ce?.value) email = ce.value.trim()
      ir(a.dataset.ir)
    })
    caixa.addEventListener('submit', async (e) => {
      e.preventDefault()
      const f = e.target.dataset.f, b = e.submitter; if (b) b.disabled = true; msg('')
      const val = (s) => $(s, corpo)?.value || ''
      try {
        if ($('#l-email', corpo)) email = val('#l-email').trim()
        if (f === 'senha') { await post('/api/entrar/senha', { email, senha: val('#l-senha') }); msg('Tudo certo! Abrindo…', 'ok'); return aoEntrar() }
        if (f === 'pedir') { const j = await post('/api/entrar/codigo', { email }); ir('digitar'); if (j.codigo_dev) $('#l-codigo', corpo).value = j.codigo_dev; return }
        if (f === 'codigo') {
          await post('/api/entrar', { email, codigo: val('#l-codigo') })
          const s = await fetch('/api/senha').then((r) => r.json()).catch(() => ({ tem_senha: true }))
          return s.tem_senha ? aoEntrar() : ir('criar')
        }
        if (f === 'criar') { await post('/api/senha', { senha: val('#l-nova') }); msg('Senha criada!', 'ok'); return aoEntrar() }
        if (f === 'esqueci') { const j = await post('/api/senha/esqueci', { email }); ir('redefinir'); if (j.codigo_dev) $('#l-codigo', corpo).value = j.codigo_dev; return }
        if (f === 'redefinir') { await post('/api/senha/redefinir', { email, codigo: val('#l-codigo'), senha: val('#l-nova') }); msg('Senha trocada! Abrindo…', 'ok'); return aoEntrar() }
      } catch (err) { msg(err.message) } finally { if (b) b.disabled = false }
    })
    return { ir }
  }

  // ---------------------------------------------------------------- landing
  const modal = document.getElementById('m-entrar')
  if (modal) {
    const m = montar(modal, { aoEntrar: () => (location.href = DESTINO) })
    const abrir = async (passo = 'senha') => {
      try { const r = await fetch(CONTA); if (r.ok) return (location.href = DESTINO) } catch {}
      modal.hidden = false; m.ir(passo)
    }
    document.addEventListener('click', (e) => { const b = e.target.closest('[data-entrar]'); if (b) { e.preventDefault(); abrir(b.dataset.entrar === 'codigo' ? 'codigo' : 'senha') } })
    modal.addEventListener('click', (e) => { if (e.target === modal || e.target.closest('[data-fechar]')) modal.hidden = true })
    addEventListener('keydown', (e) => { if (e.key === 'Escape') modal.hidden = true })
    window.RTLogin = { abrir }
    if (new URLSearchParams(location.search).has('entrar')) abrir()
  }

  // ---------------------------------------------------------------- app: minha senha (obrigatória)
  async function abrirSenha(obrigatoria) {
    let s = {}
    try { s = await fetch('/api/senha').then((r) => r.json()) } catch {}
    if (obrigatoria && (s.tem_senha || s.tem_senha === undefined)) return
    const box = document.createElement('div')
    box.className = 'modal'; box.setAttribute('role', 'dialog'); box.setAttribute('aria-modal', 'true')
    box.innerHTML = `<div class="caixa">${obrigatoria ? '' : '<button class="x" data-fechar aria-label="Fechar">×</button>'}
      <h3>${s.tem_senha ? 'Trocar senha' : 'Crie sua senha'}</h3><p>${s.tem_senha ? 'Digite a atual e a nova.' : 'Para continuar, escolha a senha que você vai usar para entrar.'}</p>
      <form>${s.tem_senha ? campoSenha('s-atual', 'Senha atual', 'current-password') : ''}${campoSenha('s-nova', 'Senha nova (mínimo 8)', 'new-password')}
      <button class="btn btn-pri grande" style="${largo}" type="submit">Salvar</button></form><div class="msg" role="alert"></div></div>`
    document.body.append(box)
    const msg = (t, tipo = 'erro') => { const m = $('.msg', box); m.textContent = t; m.className = 'msg ' + tipo }
    box.addEventListener('click', (ev) => {
      if (!obrigatoria && (ev.target === box || ev.target.closest('[data-fechar]'))) return box.remove()
      const v = ev.target.closest('[data-ver]')
      if (v) { const i = $('#' + v.dataset.ver, box); i.type = i.type === 'password' ? 'text' : 'password'; v.textContent = i.type === 'password' ? 'mostrar' : 'esconder' }
    })
    $('form', box).onsubmit = async (ev) => {
      ev.preventDefault(); const b = ev.submitter; b.disabled = true
      try { await post('/api/senha', { senha: $('#s-nova', box).value, atual: $('#s-atual', box)?.value || '' }); msg('Senha salva.', 'ok'); setTimeout(() => box.remove(), 900) }
      catch (err) { msg(err.message) } finally { b.disabled = false }
    }
    setTimeout(() => $('input', box)?.focus(), 50)
  }
  document.addEventListener('click', (e) => { if (e.target.closest('[data-senha]')) abrirSenha(false) })
  if (!document.getElementById('m-entrar')) abrirSenha(true)  // painel: conta sem senha cria agora
})()
