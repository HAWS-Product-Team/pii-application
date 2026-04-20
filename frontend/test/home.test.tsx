import {expect, test} from 'vitest'
import '@testing-library/jest-dom/vitest'
import { render, screen } from '@testing-library/react'
import Homepage from '../src/pages/HomePage'
import { MemoryRouter } from 'react-router-dom'

test("canary", () => expect(true).toBe(true))

test("Home Smoke Test", () => {
    render(<MemoryRouter> <Homepage/> </MemoryRouter>)
})

test("Home Page Title Loads", () => {
    render(
        <MemoryRouter>
            <Homepage/>
        </MemoryRouter>
)

    expect(screen.getByText("Track Your Inflation, Not Theirs")).toBeInTheDocument()
})

test("Calculate Link works as Expected", () => {
    render(<MemoryRouter>
        <Homepage/>
    </MemoryRouter>)

    expect(screen.getByRole("link", {name: "Calculate"})).toHaveAttribute("href", "/upload")
})

test("Learn More appears in Home Page", () => {
    render(<MemoryRouter>
        <Homepage/>
    </MemoryRouter>)

    expect(screen.getByRole("link", {name: "Learn more"})).toHaveAttribute("href", "/")
})

test("Homepage description text renders", () => {
  render(<MemoryRouter><Homepage /></MemoryRouter>)
  expect(screen.getByText(/Official inflation rates don't reflect your life/i)).toBeInTheDocument()
})

test("Homepage has one h1", () => {
  render(<MemoryRouter><Homepage /></MemoryRouter>)
  expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1)
})
