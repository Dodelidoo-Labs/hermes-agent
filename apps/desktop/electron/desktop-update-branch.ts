import fs from 'node:fs'

/** Fork identity, independent of the name of its current customization. */
export function isMaintainedDesktopOrigin(originUrl: string): boolean {
  const origin = originUrl.trim().replace(/\/+$/, '').replace(/\.git$/i, '').toLowerCase()
  const maintainedOrigins = new Set([
    'https://github.com/dodelidoo-labs/hermes-agent',
    'git@github.com:dodelidoo-labs/hermes-agent',
    'ssh://git@github.com/dodelidoo-labs/hermes-agent'
  ])
  return maintainedOrigins.has(origin)
}

/** Explicit Desktop settings win; implicit defaults follow the checkout being updated. */
export async function readDesktopUpdateConfig(
  configPath: string,
  getOriginUrl: () => Promise<string>
): Promise<{ branch: string }> {
  let branch = 'main'
  try {
    const parsed: unknown = JSON.parse(fs.readFileSync(configPath, 'utf8'))
    if (typeof parsed === 'object' && parsed !== null && 'branch' in parsed) {
      const saved = typeof parsed.branch === 'string' ? parsed.branch.trim() : ''
      if (saved) branch = saved
    }
  } catch {
    // Missing or invalid settings use the normal main branch.
  }
  // An unreadable origin must fail the check, not silently retarget another fork.
  if (branch === 'opencdx' && isMaintainedDesktopOrigin(await getOriginUrl())) branch = 'main'
  return { branch }
}
