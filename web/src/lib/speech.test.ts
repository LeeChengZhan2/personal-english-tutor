import { afterEach, describe, expect, it, vi } from 'vitest'
import { fakeSpeech, voice } from '@/test/speech'
import { canSpeak, englishVoices, pickVoice, setChosenVoice, speak, voiceLabel } from './speech'

const david = voice('Microsoft David - English (United States)')
const zira = voice('Microsoft Zira - English (United States)')
const ana = voice('Microsoft Ana Online (Natural) - English (United States)', 'en-US', false)
const ava = voice('Microsoft Ava Online (Natural) - English (United States)', 'en-US', false)
const sonia = voice('Microsoft Sonia Online (Natural) - English (United Kingdom)', 'en-GB', false)
const google = voice('Google US English', 'en-US', false)
const huihui = voice('Microsoft Huihui - Chinese (Simplified, PRC)', 'zh-CN')

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('englishVoices', () => {
  it('puts natural voices first, the clearest US ones first among them, and Windows voices last', () => {
    expect(englishVoices([david, huihui, sonia, ana, google, ava])).toEqual([ava, ana, sonia, google, david])
  })

  it('leaves out other languages', () => {
    expect(englishVoices([huihui])).toEqual([])
  })
})

describe('pickVoice', () => {
  it('uses the voice chosen in Settings while the browser has it', () => {
    expect(pickVoice([david, zira, ava], zira.voiceURI)).toBe(zira)
  })

  it('uses the best voice otherwise', () => {
    expect(pickVoice([david, ava], '')).toBe(ava)
    expect(pickVoice([david, ava], 'a voice that is gone')).toBe(ava)
    expect(pickVoice([huihui], '')).toBeUndefined()
  })
})

describe('voiceLabel', () => {
  it('drops the words every Edge voice has', () => {
    expect(voiceLabel(ava)).toBe('Ava (Natural) - English (United States)')
    expect(voiceLabel(david)).toBe('David - English (United States)')
    expect(voiceLabel(google)).toBe('Google US English')
  })
})

describe('speak', () => {
  it('reads with the best voice, a little slower than normal speech', () => {
    const { spoken } = fakeSpeech()
    speak('rationale', [david, ava])
    expect(spoken).toHaveLength(1)
    expect(spoken[0]).toMatchObject({ text: 'rationale', voice: ava, lang: 'en-US', rate: 0.9 })
  })

  it('reads slowly with the voice chosen in Settings', () => {
    const { spoken } = fakeSpeech()
    setChosenVoice(zira.voiceURI)
    speak('rationale', [david, zira, ava], { slow: true })
    expect(spoken[0]).toMatchObject({ voice: zira, rate: 0.6 })
  })

  it('still reads in English before the voices have loaded', () => {
    const { spoken } = fakeSpeech()
    speak('rationale', [])
    expect(spoken[0]).toMatchObject({ voice: null, lang: 'en-US' })
  })

  it('cuts off what is still being read, which then reports its end', () => {
    const { synth, spoken } = fakeSpeech()
    const onEnd = vi.fn<() => void>()
    speak('first', [], { onEnd })
    expect(synth.cancel).not.toHaveBeenCalled()
    synth.speaking = true
    speak('second', [])
    expect(synth.cancel).toHaveBeenCalledOnce()
    spoken[0]?.finish('error') // the browser reports the cut-off one as interrupted
    expect(onEnd).toHaveBeenCalledOnce()
  })

  it('does nothing in a browser that cannot speak', () => {
    expect(canSpeak()).toBe(false)
    expect(() => speak('rationale', [])).not.toThrow()
  })
})
