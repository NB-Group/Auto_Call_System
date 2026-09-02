// pywebview js_api 注入的 window.pywebview(app/bridge.py Bridge 的 js 侧形状)。
// 浏览器/开发模式下不存在,调用方一律可选链。
declare global {
  interface Window {
    pywebview?: {
      api?: {
        speak?: (text: string) => void
        fullscreen?: (on: boolean) => void
        set_display_mode?: (mode: 'expand' | 'collapse') => void
        get_role?: () => string
        app_version?: () => string
        quit?: () => void
      }
    }
  }
}

export {}
