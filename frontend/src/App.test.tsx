// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MemoryRouter } from 'react-router'

import App from './App'

describe('App', () => {
  it('renders the SynapseLMS foundation dashboard', () => {
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: /chào mừng đến synapselms/i })).toBeInTheDocument()
    expect(screen.getByText('Multi-tenant')).toBeInTheDocument()
  })
})
