import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import DashboardPage from './DashboardPage'

describe('DashboardPage', () => {
    it('renders dashboard header', () => {
        render(<DashboardPage />)

        expect(screen.getByText('Dashboard')).toBeInTheDocument()
        expect(screen.getByText(/overview of purchase order metrics/i)).toBeInTheDocument()
    })

    it('renders all stat cards', () => {
        render(<DashboardPage />)

        expect(screen.getByText('Total POs')).toBeInTheDocument()
        expect(screen.getByText('Total Value')).toBeInTheDocument()
        expect(screen.getByText('Pending Approval')).toBeInTheDocument()
        expect(screen.getByText('Delivered')).toBeInTheDocument()
    })

    it('renders chart placeholders', () => {
        render(<DashboardPage />)

        expect(screen.getByText('POs by Status')).toBeInTheDocument()
        expect(screen.getByText('Monthly Trends')).toBeInTheDocument()
        expect(screen.getAllByText(/chart coming soon/i)).toHaveLength(2)
    })
})
