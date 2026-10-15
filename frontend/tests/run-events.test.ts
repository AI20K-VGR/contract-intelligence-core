import { describe, expect, it } from 'vitest'
import {
  createSseParser,
  RUN_STEP_GROUPS,
  RUN_STEP_ORDER,
  type RunEvent,
} from '../src/api/runEvents'

function collect() {
  const events: RunEvent[] = []
  return { events, parse: createSseParser((event) => events.push(event)) }
}

describe('createSseParser', () => {
  it('reads id, event and JSON data', () => {
    const { events, parse } = collect()
    parse('id: 7\nevent: step.changed\ndata: {"step":"S1"}\n\n')
    expect(events).toEqual([
      { id: '7', event: 'step.changed', data: { step: 'S1' } },
    ])
  })

  it('joins events split across chunks and handles CRLF', () => {
    const { events, parse } = collect()
    parse('event: run.started\r\ndata: {"a"')
    expect(events).toHaveLength(0)
    parse(':1}\r\n\r\nevent: run.completed\r\ndata: {}\r\n\r\n')
    expect(events.map((event) => event.event)).toEqual([
      'run.started',
      'run.completed',
    ])
  })

  it('ignores heartbeat comments', () => {
    const { events, parse } = collect()
    parse(':heartbeat\n\n')
    expect(events).toHaveLength(0)
  })
})

describe('RUN_STEP_GROUPS', () => {
  it('puts every step in exactly one group', () => {
    const grouped = RUN_STEP_GROUPS.flatMap((group) => [...group.steps])
    expect([...grouped].sort()).toEqual([...RUN_STEP_ORDER].sort())
    expect(new Set(grouped).size).toBe(grouped.length)
  })

  it('follows who marks each step on the backend', () => {
    const owner = (code: string) =>
      RUN_STEP_GROUPS.find((group) =>
        (group.steps as readonly string[]).includes(code),
      )?.id
    expect(owner('S1')).toBe('backend')
    expect(owner('S8')).toBe('ai1')
    expect(owner('S4')).toBe('ai2')
  })
})
