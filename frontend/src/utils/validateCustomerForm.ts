import type {
  CustomerFormFieldErrors,
  CustomerFormState,
} from '../types/publicBooking'

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export function validateCustomerForm(
  form: CustomerFormState,
): CustomerFormFieldErrors {
  const errors: CustomerFormFieldErrors = {}
  const fullName = form.full_name.trim()
  const phone = form.phone.trim()
  const email = form.email.trim()
  const notes = form.customer_notes.trim()

  if (fullName.length === 0) {
    errors.full_name = 'Укажите имя'
  } else if (fullName.length > 200) {
    errors.full_name = 'Слишком длинное имя'
  }

  if (phone.length === 0) {
    errors.phone = 'Укажите телефон'
  } else if (phone.length > 32) {
    errors.phone = 'Слишком длинный номер'
  }

  if (email.length > 0) {
    if (email.length > 320) {
      errors.email = 'Слишком длинный адрес'
    } else if (!EMAIL_PATTERN.test(email)) {
      errors.email = 'Некорректный email'
    }
  }

  if (notes.length > 2000) {
    errors.customer_notes = 'Слишком длинный комментарий'
  }

  return errors
}

export function customerFormHasErrors(
  errors: CustomerFormFieldErrors,
): boolean {
  return Object.keys(errors).length > 0
}
