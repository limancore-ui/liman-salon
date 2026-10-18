import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { ServiceList } from './ServiceList'

describe('ServiceList', () => {
  it('shows Russian loading copy', () => {
    const html = renderToStaticMarkup(
      <ServiceList state={{ status: 'loading' }} />,
    )
    expect(html).toContain('Загрузка услуг…')
    expect(html).not.toContain('Loading services')
  })

  it('shows Russian error title and keeps provided message', () => {
    const html = renderToStaticMarkup(
      <ServiceList
        state={{ status: 'error', message: 'Что-то пошло не так' }}
      />,
    )
    expect(html).toContain('Не удалось загрузить услуги')
    expect(html).toContain('Что-то пошло не так')
    expect(html).not.toContain('Could not load services')
  })

  it('shows Russian empty copy', () => {
    const html = renderToStaticMarkup(
      <ServiceList state={{ status: 'success', services: [] }} />,
    )
    expect(html).toContain('Пока нет доступных услуг.')
    expect(html).not.toContain('No services available')
  })
})
