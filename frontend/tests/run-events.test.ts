import { describe, expect, it } from 'vitest'
import { createSseParser, type RunEvent } from '../src/api/runEvents'

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
