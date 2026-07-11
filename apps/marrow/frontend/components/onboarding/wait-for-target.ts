export function routeMatches(pathname: string, route: string): boolean {
  if (route === '/checkin') {
    return pathname === '/checkin' || pathname.startsWith('/checkin/')
  }
  return pathname === route || pathname.startsWith(`${route}/`)
}

export function waitForSelector(selector: string, timeoutMs = 2000): Promise<void> {
  if (selector === 'body') {
    return Promise.resolve()
  }

  return new Promise((resolve) => {
    const started = Date.now()

    const check = () => {
      if (document.querySelector(selector)) {
        resolve()
        return
      }
      if (Date.now() - started >= timeoutMs) {
        resolve()
        return
      }
      requestAnimationFrame(check)
    }

    check()
  })
}
