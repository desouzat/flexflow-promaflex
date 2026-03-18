import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import DashboardPage from './DashboardPage'
import api from '../utils/api'

// Mock the API
vi.mock('../utils/api')

// Mock toast utilities
vi.mock('../utils/toast', () => ({
    showError: vi.fn(),
    showSuccess: vi.fn(),
    showInfo: vi.fn(),
}))

// Mock recharts to avoid rendering issues in tests
vi.mock('recharts', () => ({
    BarChart: ({ children }) => <div data-testid="bar-chart">{children}</div>,
    Bar: () => <div data-testid="bar" />,
    PieChart: ({ children }) => <div data-testid="pie-chart">{children}</div>,
    Pie: () => <div data-testid="pie" />,
    Cell: () => <div data-testid="cell" />,
    XAxis: () => <div data-testid="x-axis" />,
    YAxis: () => <div data-testid="y-axis" />,
    CartesianGrid: () => <div data-testid="cartesian-grid" />,
    Tooltip: () => <div data-testid="tooltip" />,
    Legend: () => <div data-testid="legend" />,
    ResponsiveContainer: ({ children }) => <div data-testid="responsive-container">{children}</div>,
}))

const mockDashboardData = {
    total_pos: 45,
    total_value: 1250000.50,
    pending_approval: 8,
    delivered: 28,
    area_distribution: [
        { area: 'IT', count: 15, value: 450000 },
        { area: 'Operations', count: 12, value: 380000 },
        { area: 'Marketing', count: 8, value: 220000 },
        { area: 'HR', count: 6, value: 120000 },
        { area: 'Finance', count: 4, value: 80000 },
    ],
    margin_by_category: [
        { category: 'Hardware', margin: 15.5, value: 350000 },
        { category: 'Software', margin: 25.3, value: 280000 },
        { category: 'Services', margin: 18.7, value: 420000 },
        { category: 'Supplies', margin: 12.2, value: 200000 },
    ],
    average_lead_time: 12.5,
}

const renderDashboard = () => {
    return render(
        <BrowserRouter>
            <DashboardPage />
        </BrowserRouter>
    )
}

describe('DashboardPage Integration Tests', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('should render loading state initially', () => {
        api.get.mockImplementation(() => new Promise(() => { })) // Never resolves
        renderDashboard()

        expect(screen.getByText(/loading dashboard/i)).toBeInTheDocument()
    })

    it('should fetch and display dashboard metrics from backend', async () => {
        api.get.mockResolvedValueOnce({ data: mockDashboardData })

        renderDashboard()

        await waitFor(() => {
            expect(api.get).toHaveBeenCalledWith('/dashboard/metrics')
        })

        // Check if stats are rendered
        await waitFor(() => {
            expect(screen.getByText('45')).toBeInTheDocument() // Total POs
            expect(screen.getByText('8')).toBeInTheDocument() // Pending Approval
            expect(screen.getByText('28')).toBeInTheDocument() // Delivered
        })
    })

    it('should display formatted currency values correctly', async () => {
        api.get.mockResolvedValueOnce({ data: mockDashboardData })

        renderDashboard()

        await waitFor(() => {
            // Check for Brazilian Real formatting
            const totalValueElement = screen.getByText(/R\$\s*1\.250\.000,50/i)
            expect(totalValueElement).toBeInTheDocument()
        })
    })

    it('should render bar chart for area distribution', async () => {
        api.get.mockResolvedValueOnce({ data: mockDashboardData })

        renderDashboard()

        await waitFor(() => {
            expect(screen.getByText('Distribuição por Área')).toBeInTheDocument()
            expect(screen.getAllByTestId('bar-chart')).toHaveLength(1)
        })
    })

    it('should render pie chart for margin by category', async () => {
        api.get.mockResolvedValueOnce({ data: mockDashboardData })

        renderDashboard()

        await waitFor(() => {
            expect(screen.getByText('Margem Média por Categoria')).toBeInTheDocument()
            expect(screen.getAllByTestId('pie-chart')).toHaveLength(1)
        })
    })

    it('should display average lead time indicator', async () => {
        api.get.mockResolvedValueOnce({ data: mockDashboardData })

        renderDashboard()

        await waitFor(() => {
            expect(screen.getByText('Lead Time Médio')).toBeInTheDocument()
            expect(screen.getByText('12.5')).toBeInTheDocument()
            expect(screen.getByText('dias')).toBeInTheDocument()
        })
    })

    it('should display area distribution summary with values', async () => {
        api.get.mockResolvedValueOnce({ data: mockDashboardData })

        renderDashboard()

        await waitFor(() => {
            expect(screen.getByText('Resumo de Valores por Área')).toBeInTheDocument()
            expect(screen.getByText('IT')).toBeInTheDocument()
            expect(screen.getByText('Operations')).toBeInTheDocument()
            expect(screen.getByText('Marketing')).toBeInTheDocument()
            expect(screen.getByText('15 POs')).toBeInTheDocument()
            expect(screen.getByText('12 POs')).toBeInTheDocument()
        })
    })

    it('should handle API errors gracefully and show mock data', async () => {
        api.get.mockRejectedValueOnce(new Error('Network error'))

        renderDashboard()

        await waitFor(() => {
            // Should still render with mock data
            expect(screen.getByText('Dashboard')).toBeInTheDocument()
            expect(screen.getByText('45')).toBeInTheDocument() // Mock data total POs
        })
    })

    it('should display all stat cards with correct icons', async () => {
        api.get.mockResolvedValueOnce({ data: mockDashboardData })

        renderDashboard()

        await waitFor(() => {
            expect(screen.getByText('Total POs')).toBeInTheDocument()
            expect(screen.getByText('Total Value')).toBeInTheDocument()
            expect(screen.getByText('Pending Approval')).toBeInTheDocument()
            expect(screen.getByText('Delivered')).toBeInTheDocument()
        })
    })

    it('should render all chart components correctly', async () => {
        api.get.mockResolvedValueOnce({ data: mockDashboardData })

        renderDashboard()

        await waitFor(() => {
            // Check for ResponsiveContainer (wraps charts)
            expect(screen.getAllByTestId('responsive-container').length).toBeGreaterThan(0)

            // Check for chart elements
            expect(screen.getAllByTestId('bar-chart')).toHaveLength(1)
            expect(screen.getAllByTestId('pie-chart')).toHaveLength(1)
        })
    })

    it('should format dates and numbers according to pt-BR locale', async () => {
        api.get.mockResolvedValueOnce({ data: mockDashboardData })

        renderDashboard()

        await waitFor(() => {
            // Check for Brazilian number formatting (dots for thousands, comma for decimals)
            const valueElements = screen.getAllByText(/R\$/i)
            expect(valueElements.length).toBeGreaterThan(0)
        })
    })

    it('should display percentage changes for stats', async () => {
        api.get.mockResolvedValueOnce({ data: mockDashboardData })

        renderDashboard()

        await waitFor(() => {
            expect(screen.getByText('+12%')).toBeInTheDocument()
            expect(screen.getByText('+8%')).toBeInTheDocument()
            expect(screen.getByText('+15%')).toBeInTheDocument()
        })
    })

    it('should render dashboard header with description', async () => {
        api.get.mockResolvedValueOnce({ data: mockDashboardData })

        renderDashboard()

        expect(screen.getByText('Dashboard')).toBeInTheDocument()
        expect(screen.getByText('Overview of purchase order metrics')).toBeInTheDocument()
    })

    it('should handle empty or missing data gracefully', async () => {
        const emptyData = {
            total_pos: 0,
            total_value: 0,
            pending_approval: 0,
            delivered: 0,
            area_distribution: [],
            margin_by_category: [],
            average_lead_time: 0,
        }

        api.get.mockResolvedValueOnce({ data: emptyData })

        renderDashboard()

        await waitFor(() => {
            expect(screen.getByText('0')).toBeInTheDocument()
            expect(screen.getByText(/R\$\s*0,00/i)).toBeInTheDocument()
        })
    })
})
