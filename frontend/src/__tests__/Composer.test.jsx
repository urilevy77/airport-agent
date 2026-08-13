import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import Composer from '../components/Composer'

test('sends the typed question and clears the box', async () => {
  const onSend = vi.fn()
  render(<Composer onSend={onSend} disabled={false} status="idle" />)

  const input = screen.getByRole('textbox')
  await userEvent.type(input, 'Is JFK busy?')
  await userEvent.click(screen.getByRole('button', { name: /send/i }))

  expect(onSend).toHaveBeenCalledWith('Is JFK busy?')
  expect(input).toHaveValue('')
})

test('does not send an empty question', async () => {
  const onSend = vi.fn()
  render(<Composer onSend={onSend} disabled={false} status="idle" />)
  await userEvent.click(screen.getByRole('button', { name: /send/i }))
  expect(onSend).not.toHaveBeenCalled()
})

test('input and send are locked while the agent works', () => {
  render(<Composer onSend={() => {}} disabled status="thinking" />)
  expect(screen.getByRole('textbox')).toBeDisabled()
  expect(screen.getByRole('button', { name: /send/i })).toBeDisabled()
})
