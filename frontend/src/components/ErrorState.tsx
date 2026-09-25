type ErrorStateProps = {
  title: string
  message?: string
}

export function ErrorState({ title, message }: ErrorStateProps) {
  return (
    <div className="state state--error" role="alert">
      <h1 className="state__title">{title}</h1>
      {message ? <p className="state__message">{message}</p> : null}
    </div>
  )
}
