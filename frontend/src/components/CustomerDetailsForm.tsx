import type {
  CustomerFormFieldErrors,
  CustomerFormState,
} from '../types/publicBooking'

type CustomerDetailsFormProps = {
  form: CustomerFormState
  fieldErrors: CustomerFormFieldErrors
  disabled: boolean
  onChange: (field: keyof CustomerFormState, value: string) => void
}

export function CustomerDetailsForm({
  form,
  fieldErrors,
  disabled,
  onChange,
}: CustomerDetailsFormProps) {
  return (
    <form
      className="customer-form"
      aria-label="Контактные данные"
      onSubmit={(event) => event.preventDefault()}
    >
      <h2 className="booking-step__heading">Ваши данные</h2>

      <div className="form-field">
        <label className="form-field__label" htmlFor="customer-full-name">
          Имя <span className="form-field__required">*</span>
        </label>
        <input
          id="customer-full-name"
          className={`form-field__input${fieldErrors.full_name ? ' form-field__input--invalid' : ''}`}
          type="text"
          name="full_name"
          autoComplete="name"
          maxLength={200}
          value={form.full_name}
          disabled={disabled}
          onChange={(event) => onChange('full_name', event.target.value)}
        />
        {fieldErrors.full_name ? (
          <p className="form-field__error" role="alert">
            {fieldErrors.full_name}
          </p>
        ) : null}
      </div>

      <div className="form-field">
        <label className="form-field__label" htmlFor="customer-phone">
          Телефон <span className="form-field__required">*</span>
        </label>
        <input
          id="customer-phone"
          className={`form-field__input${fieldErrors.phone ? ' form-field__input--invalid' : ''}`}
          type="tel"
          name="phone"
          autoComplete="tel"
          maxLength={32}
          value={form.phone}
          disabled={disabled}
          onChange={(event) => onChange('phone', event.target.value)}
        />
        {fieldErrors.phone ? (
          <p className="form-field__error" role="alert">
            {fieldErrors.phone}
          </p>
        ) : null}
      </div>

      <div className="form-field">
        <label className="form-field__label" htmlFor="customer-email">
          Email
        </label>
        <input
          id="customer-email"
          className={`form-field__input${fieldErrors.email ? ' form-field__input--invalid' : ''}`}
          type="email"
          name="email"
          autoComplete="email"
          maxLength={320}
          value={form.email}
          disabled={disabled}
          onChange={(event) => onChange('email', event.target.value)}
        />
        {fieldErrors.email ? (
          <p className="form-field__error" role="alert">
            {fieldErrors.email}
          </p>
        ) : null}
      </div>

      <div className="form-field">
        <label className="form-field__label" htmlFor="customer-notes">
          Комментарий
        </label>
        <textarea
          id="customer-notes"
          className={`form-field__input form-field__textarea${fieldErrors.customer_notes ? ' form-field__input--invalid' : ''}`}
          name="customer_notes"
          rows={3}
          maxLength={2000}
          value={form.customer_notes}
          disabled={disabled}
          onChange={(event) => onChange('customer_notes', event.target.value)}
        />
        {fieldErrors.customer_notes ? (
          <p className="form-field__error" role="alert">
            {fieldErrors.customer_notes}
          </p>
        ) : null}
      </div>
    </form>
  )
}
