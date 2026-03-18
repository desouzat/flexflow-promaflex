import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import KanbanPage from './KanbanPage'
import api from '../utils/api'

vi.mock('../utils/api')

const mockPOs = [
    {
        id: 1,
        po_number: 'PO-2024-001',
        supplier_name: 'Supplier A',
        status: 'pending',
        total_value: 1500.50,
        expected_delivery_date: '2024-12-31',
        items_count: 5,
    },
    {
        id: 2,
        po_number: 'PO-2024-002',
        supplier_name: 'Supplier B',
        status: 'approved',
        total_value: 2500.00,
        expected_delivery_date: '2024-12-25',
        items_count: 3,
    },
]

describe('KanbanPage', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('renders loading state initially', () => {
        api.get.mockImplementation(() => new Promise(() => { })) // Never resolves
        render(<KanbanPage />)

        expect(screen.getByText(/loading purchase orders/i)).toBeInTheDocument()
    })

    it('fetches and displays POs', async () => {
        api.get.mockResolvedValue({ data: mockPOs })
        render(<KanbanPage />)

        await waitFor(() => {
            expect(screen.getByText('Kanban Board')).toBeInTheDocument()
        })

        expect(api.get).toHaveBeenCalledWith('/kanban/pos')
    })

    it('displays error state on fetch failure', async () => {
        api.get.mockRejectedValue({
            response: { data: { detail: 'Network error' } }
        })
        render(<KanbanPage />)

        await waitFor(() => {
            expect(screen.getByText('Error Loading Data')).toBeInTheDocument()
            expect(screen.getByText('Network error')).toBeInTheDocument()
        })
    })

    it('renders all kanban columns', async () => {
        api.get.mockResolvedValue({ data: mockPOs })
        render(<KanbanPage />)

        await waitFor(() => {
            expect(screen.getByText('Pending')).toBeInTheDocument()
            expect(screen.getByText('Approved')).toBeInTheDocument()
            expect(screen.getByText('In Transit')).toBeInTheDocument()
            expect(screen.getByText('Delivered')).toBeInTheDocument()
            expect(screen.getByText('Rejected')).toBeInTheDocument()
        })
    })

    it('renders search input', async () => {
        api.get.mockResolvedValue({ data: mockPOs })
        render(<KanbanPage />)

        await waitFor(() => {
            expect(screen.getByPlaceholderText(/search pos/i)).toBeInTheDocument()
        })
    })

    it('renders refresh button', async () => {
        api.get.mockResolvedValue({ data: mockPOs })
        render(<KanbanPage />)

        await waitFor(() => {
            expect(screen.getByLabelText(/refresh/i)).toBeInTheDocument()
        })
    })
})
