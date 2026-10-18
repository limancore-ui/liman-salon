import { describe, expect, it } from 'vitest'
import { ruMessages, t } from './index'

describe('i18n t()', () => {
  it('returns Russian defaults for public leftover keys', () => {
    expect(t('common.loading')).toBe('Загрузка…')
    expect(t('common.somethingWentWrong')).toBe('Что-то пошло не так')
    expect(t('public.salonNotFound')).toBe('Салон не найден')
    expect(t('public.servicesSubtitle')).toBe('Услуги')
    expect(t('public.servicesLoading')).toBe('Загрузка услуг…')
    expect(t('public.servicesLoadError')).toBe('Не удалось загрузить услуги')
    expect(t('public.servicesEmpty')).toBe('Пока нет доступных услуг.')
    expect(t('public.confirmation.title')).toBe('Запись успешно оформлена!')
    expect(t('public.confirmation.lead')).toBe(
      'Ваше время зарезервировано. Ждём вас!',
    )
    expect(t('public.confirmation.copyLink')).toBe('Скопировать ссылку')
  })

  it('returns Russian admin shell copy', () => {
    expect(t('admin.nav.bookings')).toBe('Записи')
    expect(t('admin.nav.settings')).toBe('Настройки')
    expect(t('common.logOut')).toBe('Выйти')
    expect(t('admin.layout.openMenu')).toBe('Открыть меню')
    expect(t('admin.login.title')).toBe('Админ салона')
    expect(t('admin.noAccess.title')).toBe('Нет доступа к салону')
    expect(t('admin.workspace.title')).toBe('Выберите салон')
  })

  it('interpolates placeholders', () => {
    expect(
      t('admin.noAccess.leadWithEmail', { email: 'a@example.com' }),
    ).toBe('a@example.com не привязан ни к одному активному салону.')
    expect(t('admin.workspace.lead', { email: 'b@example.com' })).toContain(
      'b@example.com',
    )
  })

  it('covers every dictionary key exactly once', () => {
    const keys = Object.keys(ruMessages) as (keyof typeof ruMessages)[]
    expect(keys.length).toBeGreaterThan(0)
    for (const key of keys) {
      expect(t(key)).toBe(ruMessages[key])
      expect(t(key).trim().length).toBeGreaterThan(0)
    }
  })
})
