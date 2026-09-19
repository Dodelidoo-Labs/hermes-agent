import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { execFileSync } from 'node:child_process'
import { afterEach, describe, expect, it } from 'vitest'
import { defaultDesktopUpdateBranch, readDesktopUpdateConfig } from './desktop-update-branch'

const roots: string[] = []
afterEach(() => { for (const root of roots.splice(0)) fs.rmSync(root, { recursive: true, force: true }) })

describe('Desktop update branch authority', () => {
  it.each([
    ['https://github.com/Dodelidoo-Labs/hermes-agent.git', 'opencdx'],
    ['git@github.com:Dodelidoo-Labs/hermes-agent.git', 'opencdx'],
    ['ssh://git@github.com/Dodelidoo-Labs/hermes-agent.git', 'opencdx'],
    ['https://github.com/NousResearch/hermes-agent.git', 'main'],
    ['https://github.com/another-owner/hermes-agent.git', 'main'],
    ['https://example.invalid/Dodelidoo-Labs/hermes-agent.git', 'main'],
    ['', 'main']
  ])('uses actual origin %s for implicit defaults and preserves explicit selection', async (origin, expected) => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'hermes-update-branch-'))
    roots.push(root)
    execFileSync('git', ['init', '-q', root])
    if (origin) execFileSync('git', ['-C', root, 'remote', 'add', 'origin', origin])
    const config = path.join(root, 'updates.json')
    const getOrigin = async () => origin ? execFileSync('git', ['-C', root, 'remote', 'get-url', 'origin'], { encoding: 'utf8' }) : ''
    expect(defaultDesktopUpdateBranch(await getOrigin())).toBe(expected)
    expect(await readDesktopUpdateConfig(config, getOrigin)).toEqual({ branch: expected })
    for (const content of ['{invalid', '{}', '{"branch":"  "}']) {
      fs.writeFileSync(config, content)
      expect(await readDesktopUpdateConfig(config, getOrigin)).toEqual({ branch: expected })
    }
    for (const branch of ['main', 'opencdx', 'feature/test']) {
      fs.writeFileSync(config, JSON.stringify({ branch: ` ${branch} ` }))
      expect(await readDesktopUpdateConfig(config, async () => { throw new Error('unneeded origin probe') })).toEqual({ branch })
    }
  })
})
