import {expect, test} from 'vitest'
import '@testing-library/jest-dom/vitest'
import { render, screen } from '@testing-library/react'
import Homepage from '../src/pages/HomePage'
import { MemoryRouter } from 'react-router-dom'

test("canary", () => expect(true).toBe(true))

test("Home Page Title Loads", () => {
    render(
        <MemoryRouter>
            <Homepage/>
        </MemoryRouter>
)

    expect(screen.getByText("Track Your Inflation, Not Theirs")).toBeInTheDocument()
})
