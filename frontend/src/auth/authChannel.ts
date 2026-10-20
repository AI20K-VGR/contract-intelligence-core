// Báo giữa các tab cùng trình duyệt: phiên nằm trong bộ nhớ từng tab (#130),
// nên không còn sự kiện `storage` để biết tab khác đăng nhập hay đăng xuất.
export const AUTH_CHANNEL_NAME = 'lexis-auth'

export type AuthMessage = 'login' | 'logout'

type ChannelLike = Pick<BroadcastChannel, 'postMessage' | 'close'> & {
  onmessage: ((event: MessageEvent) => void) | null
}

export type AuthChannel = {
  post: (message: AuthMessage) => void
  close: () => void
}

function defaultChannel(name: string): ChannelLike | null {
  return typeof BroadcastChannel === 'undefined'
    ? null
    : new BroadcastChannel(name)
}

/**
 * Mở kênh `lexis-auth`. Trình duyệt không có BroadcastChannel thì kênh không
 * làm gì: tab khác vẫn tự về màn đăng nhập khi gia hạn phiên bị từ chối.
 */
export function openAuthChannel(
  onMessage: (message: AuthMessage) => void,
  create: (name: string) => ChannelLike | null = defaultChannel,
): AuthChannel {
  const channel = create(AUTH_CHANNEL_NAME)
  if (!channel) return { post: () => {}, close: () => {} }
  channel.onmessage = (event) => {
    if (event.data === 'login' || event.data === 'logout') onMessage(event.data)
  }
  return {
    post: (message) => channel.postMessage(message),
    close: () => {
      channel.onmessage = null
      channel.close()
    },
  }
}
