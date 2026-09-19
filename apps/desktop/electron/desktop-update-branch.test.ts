import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { execFileSync } from 'node:child_process'
import { afterEach, describe, expect, it } from 'vitest'
import { readDesktopUpdateConfig } from './desktop-update-branch'

const roots: string[] = []
afterEach(() => { for (const root of roots.splice(0)) fs.rmSync(root, { recursive: true, force: true }) })

describe('Desktop update branch authority', () => {
  it.each([
    ['https://github.com/Dodelidoo-Labs/hermes-agent.git', 'main'],
    ['git@github.com:Dodelidoo-Labs/hermes-agent.git', 'main'],
    ['ssh://git@github.com/Dodelidoo-Labs/hermes-agent.git', 'main'],
    ['https://github.com/NousResearch/hermes-agent.git', 'opencdx'],
    ['https://github.com/another-owner/hermes-agent.git', 'opencdx'],
    ['https://example.invalid/Dodelidoo-Labs/hermes-agent.git', 'opencdx'],
    ['', 'opencdx']
  ])('migrates the retired branch only for maintained origin %s', async (origin, retiredTarget) => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'hermes-update-branch-'))
    roots.push(root)
    execFileSync('git', ['init', '-q', root])
    if (origin) execFileSync('git', ['-C', root, 'remote', 'add', 'origin', origin])
    const config = path.join(root, 'updates.json')
    const getOrigin = async () => origin ? execFileSync('git', ['-C', root, 'remote', 'get-url', 'origin'], { encoding: 'utf8' }) : ''
    expect(await readDesktopUpdateConfig(config, getOrigin)).toEqual({ branch: 'main' })
    for (const content of ['{invalid', '{}', '{"branch":"  "}']) {
      fs.writeFileSync(config, content)
      expect(await readDesktopUpdateConfig(config, getOrigin)).toEqual({ branch: 'main' })
    }
    for (const branch of ['main', 'opencdx', 'feature/test']) {
      fs.writeFileSync(config, JSON.stringify({ branch: ` ${branch} ` }))
      expect(await readDesktopUpdateConfig(config, getOrigin)).toEqual({
        branch: branch === 'opencdx' ? retiredTarget : branch
      })
      if (branch === 'opencdx') {
        await expect(readDesktopUpdateConfig(config, async () => { throw new Error('origin unavailable') }))
          .rejects.toThrow('origin unavailable')
      }
    }
  })
})
