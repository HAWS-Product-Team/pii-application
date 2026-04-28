import { test } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import UploadPage from '../src/pages/UploadPage'

test("UploadPage Smoke Test", () => {
  render(<MemoryRouter> <UploadPage /> </MemoryRouter>)
})


