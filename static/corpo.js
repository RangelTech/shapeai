// Mapa do corpo (frente e costas) em SVG: músculos do treino acesos e zonas de aplicação com rodízio.
// Corpo.musculos(lista, { secundarios }) -> string SVG    Corpo.zonas({ zonas, proxima, ultimas, nomes }) -> string SVG
;(() => {
  // regiões desenhadas sobre uma silhueta estilizada (viewBox 200x420 por vista). x espelhado nas duas metades.
  const F = { // frente
    shoulders: ['M46 92 q14 -16 30 -10 l2 22 q-18 2 -32 10z', 'M154 92 q-14 -16 -30 -10 l-2 22 q18 2 32 10z'],
    chest: ['M78 86 q22 -6 22 6 l0 36 q-16 6 -30 -4 q-6 -20 8 -38z', 'M122 86 q-22 -6 -22 6 l0 36 q16 6 30 -4 q6 -20 -8 -38z'],
    biceps: ['M44 108 q8 -6 14 0 l-2 46 q-8 4 -14 -2z', 'M156 108 q-8 -6 -14 0 l2 46 q8 4 14 -2z'],
    forearms: ['M40 160 q8 -4 14 0 l-4 52 q-7 3 -12 -1z', 'M160 160 q-8 -4 -14 0 l4 52 q7 3 12 -1z'],
    abdominals: ['M86 134 q14 4 28 0 l-2 64 q-12 6 -24 0z'],
    obliques: ['M72 132 q8 2 12 4 l0 58 q-8 -2 -14 -12z', 'M128 132 q-8 2 -12 4 l0 58 q8 -2 14 -12z'],
    quadriceps: ['M70 214 q14 -6 28 4 l-4 92 q-12 6 -22 -2z', 'M130 214 q-14 -6 -28 4 l4 92 q12 6 22 -2z'],
    adductors: ['M96 218 q4 30 2 60 l-6 -2 q-2 -30 -2 -56z', 'M104 218 q-4 30 -2 60 l6 -2 q2 -30 2 -56z'],
    calves: ['M74 322 q10 -4 18 2 l-2 62 q-8 4 -14 -2z', 'M126 322 q-10 -4 -18 2 l2 62 q8 4 14 -2z'],
    neck: ['M90 62 h20 l2 16 h-24z'],
  }
  const C = { // costas
    traps: ['M78 72 q22 -10 44 0 l10 18 q-32 10 -64 0z'],
    shoulders: ['M46 92 q14 -16 30 -10 l2 22 q-18 2 -32 10z', 'M154 92 q-14 -16 -30 -10 l-2 22 q18 2 32 10z'],
    lats: ['M74 108 q12 -4 24 2 l-2 62 q-14 -4 -24 -22z', 'M126 108 q-12 -4 -24 2 l2 62 q14 -4 24 -22z'],
    'middle back': ['M88 92 h24 l2 30 h-28z'],
    'lower back': ['M86 170 q14 4 28 0 l-2 32 q-12 4 -24 0z'],
    triceps: ['M44 108 q8 -6 14 0 l-2 46 q-8 4 -14 -2z', 'M156 108 q-8 -6 -14 0 l2 46 q8 4 14 -2z'],
    forearms: ['M40 160 q8 -4 14 0 l-4 52 q-7 3 -12 -1z', 'M160 160 q-8 -4 -14 0 l4 52 q7 3 12 -1z'],
    glutes: ['M70 204 q16 -8 30 2 l-2 34 q-16 6 -28 -6z', 'M130 204 q-16 -8 -30 2 l2 34 q16 6 28 -6z'],
    abductors: ['M66 214 q4 -2 6 0 l-2 34 q-4 0 -6 -4z', 'M134 214 q-4 -2 -6 0 l2 34 q4 0 6 -4z'],
    hamstrings: ['M72 244 q12 -4 24 2 l-4 66 q-10 4 -18 -2z', 'M128 244 q-12 -4 -24 2 l4 66 q10 4 18 -2z'],
    calves: ['M74 322 q10 -4 18 2 l-2 62 q-8 4 -14 -2z', 'M126 322 q-10 -4 -18 2 l2 62 q8 4 14 -2z'],
  }
  // contorno da silhueta (o mesmo para as duas vistas)
  const SIL = 'M100 18 q16 0 18 20 q2 18 -8 26 l2 12 q22 2 36 12 q14 10 14 30 l4 50 q2 30 -2 58 q-4 6 -10 0 l-2 -48 q-2 -10 -6 -18 l-2 46 q2 14 4 30 q6 40 4 84 q-2 40 -2 70 q0 10 -8 12 q-10 2 -12 -6 l-6 -86 q-2 -20 -6 -40 h-2 q-4 20 -6 40 l-6 86 q-2 8 -12 6 q-8 -2 -8 -12 q0 -30 -2 -70 q-2 -44 4 -84 q2 -16 4 -30 l-2 -46 q-4 8 -6 18 l-2 48 q-6 6 -10 0 q-4 -28 -2 -58 l4 -50 q0 -20 14 -30 q14 -10 36 -12 l2 -12 q-10 -8 -8 -26 q2 -20 18 -20z'
  const ZONA_XY = { // vista, x, y
    abdomen_sd: ['f', 90, 150], abdomen_se: ['f', 110, 150], abdomen_id: ['f', 90, 178], abdomen_ie: ['f', 110, 178],
    coxa_frente_d: ['f', 82, 256], coxa_frente_e: ['f', 118, 256], coxa_d: ['f', 70, 268], coxa_e: ['f', 130, 268],
    deltoide_d: ['c', 50, 104], deltoide_e: ['c', 150, 104], gluteo_d: ['c', 80, 214], gluteo_e: ['c', 120, 214],
  }
  // na vista de frente o lado direito da pessoa fica à esquerda da imagem; nas costas, à direita: espelha as costas
  const espelho = (v, x) => (v === 'c' ? 200 - x : x)

  function vista(regioes, cor, rot, extra = '') {
    return `<svg viewBox="0 0 200 420" class="corpo-svg" role="img" aria-label="${rot}"><path d="${SIL}" class="sil"/>${regioes}${extra}<text x="100" y="412" class="rot">${rot}</text></svg>`
  }
  function musculos(ativos = [], op = {}) {
    const on = new Set(ativos), sec = new Set(op.secundarios || [])
    const pinta = (mapa) => Object.entries(mapa).map(([m, ds]) => ds.map((d) => `<path d="${d}" class="m ${on.has(m) ? 'on' : sec.has(m) ? 'sec' : ''}"><title>${m}</title></path>`).join('')).join('')
    return `<div class="corpo">${vista(pinta(F), '', 'Frente')}${vista(pinta(C), '', 'Costas')}</div>`
  }
  function zonas(z) {
    const lista = z.zonas || [], ult = new Set((z.ultimas || []).slice(0, 2).map((a) => a.zona))
    const pontos = (v) => lista.filter((k) => ZONA_XY[k] && ZONA_XY[k][0] === v).map((k) => {
      const [, x, y] = ZONA_XY[k], cx = espelho(v, x)
      const cls = k === z.proxima ? 'prox' : ult.has(k) ? 'ult' : ''
      return `<g class="zona ${cls}" data-zona="${k}"><circle cx="${cx}" cy="${y}" r="${cls === 'prox' ? 11 : 8}"/><title>${(z.nomes || {})[k] || k}</title></g>`
    }).join('')
    const pinta = (mapa) => Object.values(mapa).map((ds) => ds.map((d) => `<path d="${d}" class="m"/>`).join('')).join('')
    return `<div class="corpo">${vista(pinta(F), '', 'Frente', pontos('f'))}${vista(pinta(C), '', 'Costas', pontos('c'))}</div>`
  }
  window.Corpo = { musculos, zonas }
})()
