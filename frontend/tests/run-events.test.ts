import { describe, expect, it } from 'vitest'
import {
  createSseParser,
  formatStepProgress,
  parseStepProgress,
  RUN_STEP_GROUPS,
  RUN_STEP_ORDER,
  stepFromEvent,
  stepProgressPercent,
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

describe('step progress (DOC-05b v3.2.0)', () => {
  it('reads progress from a step.changed event', () => {
    const step = stepFromEvent({
      id: '9',
      event: 'step.changed',
      data: {
        step: 'S2',
        status: 'running',
        attempt: 1,
        pages: null,
        duration_ms: null,
        progress: { done: 37, total: 202, unit: 'page' },
      },
    })
    expect(step?.progress).toEqual({ done: 37, total: 202, unit: 'page' })
    expect(formatStepProgress(step!.progress!)).toBe('37/202 trang')
    expect(stepProgressPercent(step!.progress!)).toBe(18)
  })

  it('treats a missing or null progress as no progress (spinner)', () => {
    const base = { step: 'S6', status: 'running' }
    expect(
      stepFromEvent({ id: null, event: 'step.changed', data: base })?.progress,
    ).toBeNull()
    expect(
      stepFromEvent({
        id: null,
        event: 'step.changed',
        data: { ...base, progress: null },
      })?.progress,
    ).toBeNull()
  })

  it('rejects malformed values and unknown units', () => {
    expect(parseStepProgress({ done: 1, total: 0, unit: 'page' })).toBeNull()
    expect(parseStepProgress({ done: 1.5, total: 4, unit: 'page' })).toBeNull()
    expect(parseStepProgress({ done: '1', total: 4, unit: 'page' })).toBeNull()
    expect(parseStepProgress({ done: 1, total: 4, unit: 'row' })).toBeNull()
    expect(
      parseStepProgress({ done: 1, total: 4, unit: 'toString' }),
    ).toBeNull()
  })

  it('clamps done into 0..total and words every unit', () => {
    expect(parseStepProgress({ done: 9, total: 4, unit: 'pair' })).toEqual({
      done: 4,
      total: 4,
      unit: 'pair',
    })
    expect(parseStepProgress({ done: -2, total: 4, unit: 'chunk' })?.done).toBe(
      0,
    )
    const words = (
      ['page', 'document', 'chunk', 'clause', 'pair'] as const
    ).map((unit) => formatStepProgress({ done: 1, total: 3, unit }))
    expect(words).toEqual([
      '1/3 trang',
      '1/3 tài liệu',
      '1/3 đoạn',
      '1/3 điều khoản',
      '1/3 cặp',
    ])
  })

  it('stays under 100% until the step is done', () => {
    expect(stepProgressPercent({ done: 201, total: 202, unit: 'page' })).toBe(
      99,
    )
    expect(stepProgressPercent({ done: 202, total: 202, unit: 'page' })).toBe(
      100,
    )
  })
})
