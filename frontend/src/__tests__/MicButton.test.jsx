import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import MicButton from '../components/MicButton'

test('renders nothing when speech is unsupported', () => {
  const { container } = render(
    <MicButton supported={false} listening={false} onStart={() => {}} onStop={() => {}} />)
  expect(container).toBeEmptyDOMElement()
})

test('clicking starts dictation', async () => {
  const onStart = vi.fn()
  render(<MicButton supported listening={false} onStart={onStart} onStop={() => {}} />)
  await userEvent.click(screen.getByRole('button', { name: /dictate|speak/i }))
  expect(onStart).toHaveBeenCalled()
})

test('clicking while listening cancels', async () => {
  const onStop = vi.fn()
  render(<MicButton supported listening onStart={() => {}} onStop={onStop} />)
  await userEvent.click(screen.getByRole('button', { name: /stop/i }))
  expect(onStop).toHaveBeenCalled()
})

test('shows the permission hint when blocked', () => {
  render(<MicButton supported listening={false} error="Microphone blocked — check browser settings."
                    onStart={() => {}} onStop={() => {}} />)
  expect(screen.getByText(/microphone blocked/i)).toBeInTheDocument()
})
