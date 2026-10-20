import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { ContractMindmap } from '../src/components/ContractMindmap'

describe('ContractMindmap dossier grounding', () => {
  it('does not render hard-coded sample structure for every dossier', () => {
    const html = renderToStaticMarkup(<ContractMindmap />)

    // This is intentionally red: the current component renders the sample
    // contract instead of receiving the active dossier structure.
    expect(html).not.toContain('9 Điều khoản • 4 Phụ lục')
    expect(html).not.toContain('Điều 9: Luật áp dụng & VIAC')
  })
})
