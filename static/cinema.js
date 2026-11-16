// Kit cinematográfico: topo que escurece ao rolar, entrada suave das seções, vídeos que só tocam visíveis, planos da API.
;(() => {
  const $ = (q, r = document) => r.querySelector(q)
  const $$ = (q, r = document) => [...r.querySelectorAll(q)]
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c])
  const topo = $('.topo')
  const rolar = () => topo && topo.classList.toggle('rolou', scrollY > 30)
  addEventListener('scroll', rolar, { passive: true }); rolar()

  const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add('vis'); io.unobserve(e.target) } }), { threshold: 0.12 })
  $$('.rev').forEach((el) => io.observe(el))

  // vídeos tocam só quando aparecem (economiza dados no celular)
  const iov = new IntersectionObserver((es) => es.forEach((e) => { const v = e.target; if (e.isIntersecting) v.play().catch(() => {}); else v.pause() }), { threshold: 0.25 })
  $$('video[data-auto]').forEach((v) => { v.muted = true; v.playsInline = true; v.loop = true; iov.observe(v) })

  // conversa que se escreve sozinha e recomeça: <div data-conversa> com .msg-b dentro
  $$('[data-conversa]').forEach((box) => {
    const msgs = $$('.msg-b', box)
    const rodar = () => {
      msgs.forEach((m) => m.classList.remove('on'))
      msgs.forEach((m, i) => setTimeout(() => m.classList.add('on'), 600 + i * 1500))
      setTimeout(rodar, 600 + msgs.length * 1500 + 5000)
    }
    rodar()
  })

  // planos ao vivo: <div class="planos" data-planos="/api/marca" data-destaque="1">
  const alvo = $('[data-planos]')
  if (alvo) {
    fetch(alvo.dataset.planos).then((r) => r.json()).then((j) => {
      const planos = j.planos || []
      const dest = Number(alvo.dataset.destaque ?? 1)
      alvo.innerHTML = planos.map((p, i) => {
        const preco = Number(p.preco).toFixed(2).replace('.', ',')
        const [inteiro, cent] = preco.split(',')
        const depois = p.depois ? `<div class="depois">Preço de lançamento · depois R$ ${Number(p.depois).toFixed(2).replace('.', ',')}</div>` : '<div class="depois">Preço de lançamento</div>'
        const cta = p.checkout ? `<a class="btn ${i === dest ? 'btn-pri pulsa' : 'btn-sec'}" href="${esc(p.checkout)}">Assinar o ${esc(p.nome)}</a>` : '<button class="btn btn-sec" disabled>Em breve</button>'
        return `<div class="plano rev ${i === dest ? 'destaque' : ''}"><h3>${esc(p.nome)}</h3><div class="preco">R$ ${inteiro}<small>,${cent}/mês</small></div>${depois}
          <ul>${(p.itens || []).map((x) => `<li>${esc(x)}</li>`).join('')}</ul>${cta}</div>`
      }).join('')
      $$('.plano.rev', alvo).forEach((el) => io.observe(el))
      if (j.outras && $('#outras')) $('#outras').innerHTML = j.outras.map((o) => `<a href="${esc(o.url)}">${esc(o.nome)}</a>`).join('')
    }).catch(() => {})
  }
})()
