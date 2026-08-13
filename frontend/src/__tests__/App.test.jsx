import { render, screen } from '@testing-library/react'
import App from '../App'

test('renders the app name in the header', () => {
  render(<App />)
  expect(screen.getByText(/Airport Investment Intelligence/i)).toBeInTheDocument()
})
