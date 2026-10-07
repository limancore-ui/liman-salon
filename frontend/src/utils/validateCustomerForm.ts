import type {
  CustomerFormFieldErrors,
  CustomerFormState,
} from '../types/publicBooking'
import { isCompleteKgLocalPhone } from './kyrgyzPhone'

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
  } else if (!isCompleteKgLocalPhone(phone)) {
    errors.phone = 'Введите 9 цифр номера после +996'
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

/** Lookup runs only for a complete 9-digit local number (form state value). */
export function isCustomerPhoneLookupEligible(phone: string): boolean {
  return isCompleteKgLocalPhone(phone.trim())
}
