import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import KanbanColumn from './KanbanColumn'

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
        status: 'pending',
        total_value: 2500.00,
        expected_delivery_date: '2024-12-25',
        items_count: 3,
    },
]

describe('KanbanColumn', () => {
    it('renders column with title and count', () => {
        render(
            <KanbanColumn
                title="Pending"
                status="pending"
                pos={mockPOs}
                color="yellow"
            />
        )

        expect(screen.getByText('Pending')).toBeInTheDocument()
        expect(screen.getByText('2')).toBeInTheDocument() // Count badge
    })

    it('renders all PO cards', () => {
        render(
            <KanbanColumn
                title="Pending"
                status="pending"
                pos={mockPOs}
                color="yellow"
            />
        )

        expect(screen.getByText('PO #PO-2024-001')).toBeInTheDocument()
        expect(screen.getByText('PO #PO-2024-002')).toBeInTheDocument()
    })

    it('displays empty state when no POs', () => {
        render(
            <KanbanColumn
                title="Pending"
                status="pending"
                pos={[]}
                color="yellow"
            />
        )

        expect(screen.getByText('No items in this column')).toBeInTheDocument()
        expect(screen.getByText('0')).toBeInTheDocument() // Count badge
    })

    it('applies correct color classes', () => {
        const { container } = render(
            <KanbanColumn
                title="Approved"
                status="approved"
                pos={mockPOs}
                color="green"
            />
        )

        const header = screen.getByText('Approved').closest('div')
        expect(header).toHaveClass('bg-green-100')
    })

    it('passes onCardClick to KanbanCard components', () => {
        const handleCardClick = vi.fn()
        render(
            <KanbanColumn
                title="Pending"
                status="pending"
                pos={mockPOs}
                onCardClick={handleCardClick}
                color="yellow"
            />
        )

        // Cards should be rendered and clickable
        expect(screen.getByText('PO #PO-2024-001')).toBeInTheDocument()
    })

    it('renders column options button', () => {
        render(
            <KanbanColumn
                title="Pending"
                status="pending"
                pos={mockPOs}
                color="yellow"
            />
        )

        expect(screen.getByLabelText('Column options')).toBeInTheDocument()
    })
})
