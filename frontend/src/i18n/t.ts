import { ruMessages, type MessageKey } from './ru'

/**
 * Resolve a typed UI message from the default Russian dictionary.
 * Optional `{name}` placeholders are replaced from `vars`.
 */
export function t(
  key: MessageKey,
  vars?: Record<string, string | number>,
): string {
  let message: string = ruMessages[key]
  if (vars) {
    for (const [name, value] of Object.entries(vars)) {
      message = message.replaceAll(`{${name}}`, String(value))
    }
  }
  return message
}
