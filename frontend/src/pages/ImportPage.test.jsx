import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import ImportPage from './ImportPage'

describe('ImportPage', () => {
    it('renders import page header', () => {
        render(<ImportPage />)

        expect(screen.getByText('Mesa de Conferência')).toBeInTheDocument()
        expect(screen.getByText(/Importar e validar pedidos/i)).toBeInTheDocument()
    })

    it('renders upload area', () => {
        render(<ImportPage />)

        expect(screen.getByText(/Arraste seu arquivo Excel aqui/i)).toBeInTheDocument()
    })

    it('renders file requirements section', () => {
        render(<ImportPage />)

        expect(screen.getByText('Requisitos do Arquivo (Campos ONET)')).toBeInTheDocument()
        expect(screen.getByText(/Formato Excel/i)).toBeInTheDocument()
        expect(screen.getByText(/Tamanho máximo/i)).toBeInTheDocument()
    })

    it('renders important notes section', () => {
        render(<ImportPage />)

        expect(screen.getByText('Regras de Validação')).toBeInTheDocument()
    })
})
