import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import KanbanCard from './KanbanCard'

const mockPO = {
    id: 1,
    po_number: 'PO-2024-001',
    supplier_name: 'Test Supplier',
    status: 'pending',
    total_value: 1500.50,
    expected_delivery_date: '2024-12-31',
    items_count: 5,
    priority: 'normal',
}

describe('KanbanCard', () => {
    it('renders PO information correctly', () => {
        render(<KanbanCard po={mockPO} />)

        expect(screen.getByText('PO #PO-2024-001')).toBeInTheDocument()
        expect(screen.getByText('Test Supplier')).toBeInTheDocument()
        expect(screen.getByText(/pending/i)).toBeInTheDocument()
        expect(screen.getByText('5 items')).toBeInTheDocument()
    })

    it('formats currency correctly', () => {
        render(<KanbanCard po={mockPO} />)

        // Should format as Brazilian Real
        expect(screen.getByText(/R\$/)).toBeInTheDocument()
    })

    it('formats date correctly', () => {
        render(<KanbanCard po={mockPO} />)

        // Should format date in pt-BR format
        expect(screen.getByText(/31\/12\/2024/)).toBeInTheDocument()
    })

    it('calls onCardClick when clicked', () => {
        const handleClick = vi.fn()
        render(<KanbanCard po={mockPO} onCardClick={handleClick} />)

        const card = screen.getByText('PO #PO-2024-001').closest('div')
        fireEvent.click(card)

        expect(handleClick).toHaveBeenCalledWith(mockPO)
    })

    it('displays high priority indicator', () => {
        const highPriorityPO = { ...mockPO, priority: 'high' }
        render(<KanbanCard po={highPriorityPO} />)

        expect(screen.getByText('High Priority')).toBeInTheDocument()
    })

    it('does not display priority indicator for normal priority', () => {
        render(<KanbanCard po={mockPO} />)

        expect(screen.queryByText('High Priority')).not.toBeInTheDocument()
    })

    it('applies correct status color classes', () => {
        const { rerender } = render(<KanbanCard po={mockPO} />)

        expect(screen.getByText(/pending/i).closest('div')).toHaveClass('bg-yellow-100')

        rerender(<KanbanCard po={{ ...mockPO, status: 'approved' }} />)
        expect(screen.getByText(/approved/i).closest('div')).toHaveClass('bg-green-100')

        rerender(<KanbanCard po={{ ...mockPO, status: 'rejected' }} />)
        expect(screen.getByText(/rejected/i).closest('div')).toHaveClass('bg-red-100')
    })

    it('handles singular item count', () => {
        const singleItemPO = { ...mockPO, items_count: 1 }
        render(<KanbanCard po={singleItemPO} />)

        expect(screen.getByText('1 item')).toBeInTheDocument()
    })

    it('handles missing optional fields', () => {
        const minimalPO = {
            id: 1,
            po_number: 'PO-2024-001',
            supplier_name: 'Test Supplier',
            status: 'pending',
        }

        render(<KanbanCard po={minimalPO} />)

        expect(screen.getByText('PO #PO-2024-001')).toBeInTheDocument()
        expect(screen.getByText('N/A')).toBeInTheDocument() // For missing date
    })
})
