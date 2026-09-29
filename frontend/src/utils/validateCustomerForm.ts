import type {
  CustomerFormFieldErrors,
  CustomerFormState,
} from '../types/publicBooking'

export function validateCustomerForm(
  form: CustomerFormState,
): CustomerFormFieldErrors {
  const errors: CustomerFormFieldErrors = {}
  const fullName = form.full_name.trim()
  const phone = form.phone.trim()
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

/** Same trim/length rules as phone validation; used before public lookup. */
export function isCustomerPhoneLookupEligible(phone: string): boolean {
  const trimmed = phone.trim()
  return trimmed.length > 0 && trimmed.length <= 32
}
