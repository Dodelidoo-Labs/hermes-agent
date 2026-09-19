import fs from 'node:fs'

/** The maintained fork publishes reviewed updates on opencdx, not its upstream main. */
export function defaultDesktopUpdateBranch(originUrl: string): string {
  const origin = originUrl.trim().replace(/\/+$/, '').replace(/\.git$/i, '').toLowerCase()
  const maintainedOrigins = new Set([
    'https://github.com/dodelidoo-labs/hermes-agent',
    'git@github.com:dodelidoo-labs/hermes-agent',
    'ssh://git@github.com/dodelidoo-labs/hermes-agent'
  ])
  return maintainedOrigins.has(origin) ? 'opencdx' : 'main'
}

/** Explicit Desktop settings win; implicit defaults follow the checkout being updated. */
export async function readDesktopUpdateConfig(
  configPath: string,
  getOriginUrl: () => Promise<string>
): Promise<{ branch: string }> {
  try {
    const parsed: unknown = JSON.parse(fs.readFileSync(configPath, 'utf8'))
    if (typeof parsed === 'object' && parsed !== null && 'branch' in parsed) {
      const branch = typeof parsed.branch === 'string' ? parsed.branch.trim() : ''
      if (branch) return { branch }
    }
  } catch {
    // Missing or invalid settings use the same origin-aware default.
  }
  return { branch: defaultDesktopUpdateBranch(await getOriginUrl()) }
}
