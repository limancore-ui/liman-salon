type LoadingStateProps = {
  message?: string
}

export function LoadingState({ message = 'Loading…' }: LoadingStateProps) {
  return (
    <div className="state state--loading" role="status" aria-live="polite">
      <div className="state__spinner" aria-hidden="true" />
      <p className="state__message">{message}</p>
    </div>
  )
}
