import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import App from './App'

describe('App', () => {
    it('renders without crashing', () => {
        render(<App />)
        // Should render the login page initially (not authenticated)
        expect(screen.getByText(/loading/i)).toBeInTheDocument()
    })
})
