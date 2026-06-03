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
        status: 'Comercial',
        total_value: 1500.50,
        expected_delivery_date: '2024-12-31',
        items_count: 5,
    },
    {
        id: 2,
        po_number: 'PO-2024-002',
        supplier_name: 'Supplier B',
        status: 'PCP',
        total_value: 2500.00,
        expected_delivery_date: '2024-12-25',
        items_count: 3,
    },
]

const mockBoardData = {
    columns: [
        { status: 'Comercial', count: 1, pos: [mockPOs[0]] },
        { status: 'PCP', count: 1, pos: [mockPOs[1]] },
        { status: 'Produção/Embalagem', count: 0, pos: [] },
        { status: 'Faturamento/Expedição', count: 0, pos: [] },
        { status: 'Financeiro', count: 0, pos: [] },
        { status: 'Concluídos', count: 0, pos: [] }
    ],
    total_pos: 2
}

describe('KanbanPage', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('renders loading state initially', () => {
        api.get.mockImplementation(() => new Promise(() => { })) // Never resolves
        render(<KanbanPage />)

        expect(screen.getByText(/Carregando pedidos.../i)).toBeInTheDocument()
    })

    it('fetches and displays POs', async () => {
        api.get.mockResolvedValue({ data: mockBoardData })
        render(<KanbanPage />)

        await waitFor(() => {
            expect(screen.getByText('Quadro Kanban')).toBeInTheDocument()
        })

        expect(api.get).toHaveBeenCalledWith('/kanban/board')
    })

    it('displays error state on fetch failure', async () => {
        api.get.mockRejectedValue({
            response: { data: { detail: 'Network error' } }
        })
        render(<KanbanPage />)

        await waitFor(() => {
            expect(screen.getByText('Erro ao Carregar Dados')).toBeInTheDocument()
            expect(screen.getByText('Network error')).toBeInTheDocument()
        })
    })

    it('renders all kanban columns', async () => {
        api.get.mockResolvedValue({ data: mockBoardData })
        render(<KanbanPage />)

        await waitFor(() => {
            expect(screen.getByRole('heading', { name: 'Comercial' })).toBeInTheDocument()
            expect(screen.getByRole('heading', { name: 'PCP' })).toBeInTheDocument()
            expect(screen.getByRole('heading', { name: 'Produção/Embalagem' })).toBeInTheDocument()
            expect(screen.getByRole('heading', { name: 'Faturamento/Expedição' })).toBeInTheDocument()
            expect(screen.getByRole('heading', { name: 'Financeiro' })).toBeInTheDocument()
            expect(screen.getByRole('heading', { name: 'Concluídos' })).toBeInTheDocument()
        })
    })

    it('renders search input', async () => {
        api.get.mockResolvedValue({ data: mockBoardData })
        render(<KanbanPage />)

        await waitFor(() => {
            expect(screen.getByPlaceholderText(/Buscar pedidos.../i)).toBeInTheDocument()
        })
    })

    it('renders refresh button', async () => {
        api.get.mockResolvedValue({ data: mockBoardData })
        render(<KanbanPage />)

        await waitFor(() => {
            expect(screen.getByText(/Atualizar/i)).toBeInTheDocument()
        })
    })
})
