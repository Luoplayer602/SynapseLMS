// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, expect, it } from 'vitest'
import { AIHub } from './AIHub'

afterEach(cleanup)

it('links the learner to existing AI tasks without presenting a free chat input', () => {
  render(<MemoryRouter><AIHub language="vi" /></MemoryRouter>)
  expect(screen.getByRole('link', { name: 'Mở bài luyện AI' })).toHaveAttribute('href', '/practice')
  expect(screen.getByRole('link', { name: /Nhận xét & bước tiếp/ })).toHaveAttribute('href', '/ai-progress')
  expect(screen.getByRole('link', { name: /Khám phá khóa học/ })).toHaveAttribute('href', '/course-catalog')
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
})
