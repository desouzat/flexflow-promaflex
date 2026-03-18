import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import ImportPage from './ImportPage'

describe('ImportPage', () => {
    it('renders import page header', () => {
        render(<ImportPage />)

        expect(screen.getByText('Import Purchase Orders')).toBeInTheDocument()
        expect(screen.getByText(/upload excel files/i)).toBeInTheDocument()
    })

    it('renders upload area', () => {
        render(<ImportPage />)

        expect(screen.getByText(/drop your excel file here/i)).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /select file/i })).toBeInTheDocument()
    })

    it('renders file requirements section', () => {
        render(<ImportPage />)

        expect(screen.getByText('File Requirements')).toBeInTheDocument()
        expect(screen.getByText(/excel format/i)).toBeInTheDocument()
        expect(screen.getByText(/maximum file size/i)).toBeInTheDocument()
    })

    it('renders important notes section', () => {
        render(<ImportPage />)

        expect(screen.getByText('Important Notes')).toBeInTheDocument()
        expect(screen.getByText(/duplicate po numbers/i)).toBeInTheDocument()
    })
})
