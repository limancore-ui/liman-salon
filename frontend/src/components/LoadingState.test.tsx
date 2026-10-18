import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { LoadingState } from './LoadingState'

describe('LoadingState', () => {
  it('defaults to Russian loading copy', () => {
    const html = renderToStaticMarkup(<LoadingState />)
    expect(html).toContain('Загрузка…')
    expect(html).not.toContain('Loading…')
  })

  it('keeps an explicit message override', () => {
    const html = renderToStaticMarkup(
      <LoadingState message="Загрузка салона…" />,
    )
    expect(html).toContain('>Загрузка салона…<')
  })
})

