// Login comum dos produtos Rangel Tech (spec 57, §5A). Fonte única: produtos-core/produtos_core/static/login.js
// (cada produto serve uma cópia em /s/login.js; não editar a cópia, editar aqui e copiar).
// Entrar: e-mail + senha. Criar conta: e-mail + senha (entra na hora). Esqueci a senha e "Entrar por link no e-mail":
// link por e-mail, sem código para copiar. Captcha invisível (Cloudflare Turnstile) em todos os formulários.
// Na landing: <script src="/s/login.js" data-conta="/api/conta" data-destino="/app"></script> + <div class="modal" id="m-entrar"><div class="caixa">…
// No app: qualquer elemento [data-senha] abre "Minha senha" (criar ou trocar).
;(() => {
  const tag = document.currentScript
  const CONTA = tag?.dataset.conta || '/api/conta'
  const DESTINO = tag?.dataset.destino || '/app'
  const $ = (s, r = document) => r.querySelector(s)
  const post = async (url, corpo) => {
    const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corpo) })
    let j = {}
    try { j = await r.json() } catch {}
    if (!r.ok) throw new Error(typeof j.detail === 'string' ? j.detail : 'Não deu certo. Tente de novo.')
    return j
  }

  // ------------------------------------------------------------ captcha invisível (Turnstile)
  let SITE = null, wid = null, pend = null, carregando = null, caixaTs = null
  const config = fetch('/api/acesso/config').then((r) => r.json()).then((j) => (SITE = j.turnstile || '')).catch(() => (SITE = ''))
  const carregar = () => carregando || (carregando = new Promise((ok, falha) => {
    const s = document.createElement('script')
    s.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit'
    s.async = true; s.onload = ok; s.onerror = falha
    document.head.append(s)
  }))
  const entregar = (t) => { const f = pend; pend = null; if (f) f(t) }
  let voando = null  // um pedido de token por vez (o widget é um só)
  function captcha() {
    if (!voando) voando = gerar().finally(() => { voando = null })
    return voando
  }
  async function gerar() {
    await config
    if (!SITE) return ''
    try {
      await carregar()
      if (!caixaTs) { caixaTs = document.createElement('div'); caixaTs.style.cssText = 'position:fixed;bottom:8px;right:8px;z-index:99999'; document.body.append(caixaTs) }
      return await new Promise((ok) => {
        pend = ok
        if (wid === null) {
          wid = window.turnstile.render(caixaTs, { sitekey: SITE, execution: 'execute', appearance: 'interaction-only',
            callback: entregar, 'error-callback': () => entregar(''), 'timeout-callback': () => entregar('') })
        } else window.turnstile.reset(wid)
        window.turnstile.execute(wid)
        setTimeout(() => { if (pend === ok) entregar('') }, 15000)
      })
    } catch { return '' }
  }
  // O token é gerado assim que o formulário abre (leva alguns segundos), para estar pronto no clique. Vale ~5 min.
  let pronto = null
  const preparar = () => { pronto = { quando: Date.now(), token: captcha() } }
  const pegarToken = async () => {
    const p = pronto && Date.now() - pronto.quando < 240000 ? pronto.token : captcha()
    pronto = null
    const t = await p
    setTimeout(preparar, 500)  // já deixa o próximo pronto (se o envio der erro, a pessoa tenta de novo sem esperar)
    return t
  }
  const postH = async (url, corpo) => post(url, { ...corpo, captcha: await pegarToken() })

  const largo = 'width:100%;margin-top:16px'
  const campoSenha = (id, rotulo, auto) => `<label for="${id}" style="margin-top:12px">${rotulo}</label>
    <div style="position:relative"><input id="${id}" type="password" autocomplete="${auto}" required minlength="${auto === 'current-password' ? 1 : 8}" style="padding-right:64px">
    <button type="button" data-ver="${id}" style="position:absolute;right:8px;top:50%;transform:translateY(-50%);background:none;border:0;color:inherit;opacity:.7;font-size:13px;cursor:pointer">mostrar</button></div>`
  const campoEmail = (auto) => `<label for="l-email">E-mail</label><input id="l-email" type="email" autocomplete="${auto}" required placeholder="voce@email.com">`

  const PASSOS = {
    senha: () => `<h3 id="m-tit">Entrar</h3><p>Use seu e-mail e sua senha.</p>
      <form data-f="senha">${campoEmail('username')}
      ${campoSenha('l-senha', 'Senha', 'current-password')}
      <button class="btn btn-pri grande" style="${largo}" type="submit">Entrar</button></form>
      <button class="btn btn-sec" style="width:100%;margin-top:10px" type="button" data-ir="cadastro">Primeira vez? Criar conta</button>
      <button class="link-demo" type="button" data-ir="esqueci">Esqueci minha senha</button>
      <button class="link-demo" type="button" data-ir="link" style="font-size:13px;opacity:.8">Entrar por link no e-mail</button>`,
    cadastro: () => `<h3 id="m-tit">Criar conta</h3><p>Seu e-mail e uma senha. Você já entra em seguida.</p>
      <form data-f="cadastro">${campoEmail('email')}
      ${campoSenha('l-nova', 'Senha (mínimo 8)', 'new-password')}
      <button class="btn btn-pri grande" style="${largo}" type="submit">Criar conta e entrar</button></form>
      <button class="link-demo" type="button" data-ir="senha">Já tenho conta</button>`,
    link: () => `<h3 id="m-tit">Entrar por link</h3><p>Mandamos um link para o seu e-mail. Um clique e você entra, sem senha.</p>
      <form data-f="link">${campoEmail('email')}
      <button class="btn btn-pri grande" style="${largo}" type="submit">Mandar link</button></form>
      <button class="link-demo" type="button" data-ir="senha">Voltar para a senha</button>`,
    esqueci: () => `<h3 id="m-tit">Esqueci minha senha</h3><p>Mandamos um link para o seu e-mail e você cria uma senha nova.</p>
      <form data-f="esqueci">${campoEmail('email')}
      <button class="btn btn-pri grande" style="${largo}" type="submit">Mandar link</button></form>
      <button class="link-demo" type="button" data-ir="senha">Lembrei, voltar</button>`,
    redefinir: () => `<h3 id="m-tit">Senha nova</h3><p>Escolha a senha que você vai usar para entrar.</p>
      <form data-f="redefinir">${campoSenha('l-nova', 'Senha nova (mínimo 8)', 'new-password')}
      <button class="btn btn-pri grande" style="${largo}" type="submit">Salvar e entrar</button></form>`,
  }

  function montar(modal, { aoEntrar }) {
    const caixa = $('.caixa', modal)
    const fechar = $('[data-fechar]', caixa)?.outerHTML || '<button class="x" data-fechar aria-label="Fechar">×</button>'
    let email = '', token = ''
    const corpo = document.createElement('div')
    const msgEl = document.createElement('div')
    msgEl.className = 'msg'; msgEl.setAttribute('role', 'alert')
    caixa.innerHTML = fechar; caixa.append(corpo, msgEl)
    const msg = (t, tipo = 'erro') => { msgEl.textContent = t || ''; msgEl.className = 'msg ' + tipo }
    const ir = (p, extra) => {
      if (extra?.token) token = extra.token
      corpo.innerHTML = PASSOS[p](); msg(extra?.msg || '', extra?.tipo || 'erro')
      if (p !== 'redefinir' && !pronto) preparar()
      const ce = $('#l-email', corpo); if (ce && email) ce.value = email
      setTimeout(() => ((ce && !ce.value ? ce : null) || $('input[type=password]', corpo) || ce)?.focus(), 50)
    }
    caixa.addEventListener('click', (e) => {
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
        if (f === 'senha') { await postH('/api/entrar/senha', { email, senha: val('#l-senha') }); msg('Tudo certo! Abrindo…', 'ok'); return aoEntrar() }
        if (f === 'cadastro') { await postH('/api/cadastro', { email, senha: val('#l-nova') }); msg('Conta criada! Abrindo…', 'ok'); return aoEntrar() }
        if (f === 'link' || f === 'esqueci') {
          const j = await postH(f === 'link' ? '/api/entrar/link' : '/api/senha/esqueci', { email })
          return msg(j.mensagem || 'Se esse e-mail tiver cadastro, enviamos o link. Confira também o spam.', 'ok')
        }
        if (f === 'redefinir') { await post('/api/senha/redefinir', { token, senha: val('#l-nova') }); msg('Senha salva! Abrindo…', 'ok'); return aoEntrar() }
      } catch (err) { msg(err.message) } finally { if (b) b.disabled = false }
    })
    return { ir }
  }

  // ---------------------------------------------------------------- landing
  const modal = document.getElementById('m-entrar')
  if (modal) {
    const m = montar(modal, { aoEntrar: () => (location.href = DESTINO) })
    const abrir = async (passo = 'senha', extra) => {
      if (passo !== 'redefinir') { try { const r = await fetch(CONTA); if (r.ok) return (location.href = DESTINO) } catch {} }
      modal.hidden = false; m.ir(passo, extra)
    }
    document.addEventListener('click', (e) => {
      const b = e.target.closest('[data-entrar]')
      if (b) { e.preventDefault(); abrir({ codigo: 'cadastro', cadastro: 'cadastro', link: 'link' }[b.dataset.entrar] || 'senha') }
    })
    modal.addEventListener('click', (e) => { if (e.target === modal || e.target.closest('[data-fechar]')) modal.hidden = true })
    addEventListener('keydown', (e) => { if (e.key === 'Escape') modal.hidden = true })
    window.RTLogin = { abrir }
    const q = new URLSearchParams(location.search)
    if (q.get('redefinir')) { abrir('redefinir', { token: q.get('redefinir') }); history.replaceState(null, '', location.pathname) }
    else if (q.get('link') === 'invalido') abrir('link', { msg: 'Esse link venceu ou já foi usado. Peça outro.' })
    else if (q.has('entrar')) abrir()
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
