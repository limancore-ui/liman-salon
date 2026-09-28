import type { MediaAttachmentIndexItem } from '../types/media'

export function groupAttachmentsByMediaId(
  items: MediaAttachmentIndexItem[],
): Map<string, MediaAttachmentIndexItem[]> {
  const map = new Map<string, MediaAttachmentIndexItem[]>()
  for (const item of items) {
    const list = map.get(item.media_id)
    if (list) {
      list.push(item)
    } else {
      map.set(item.media_id, [item])
    }
  }
  return map
}
