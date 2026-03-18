import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './Layout'
import { AuthProvider } from '../context/AuthContext'

const mockLogout = vi.fn()
const mockNavigate = vi.fn()

vi.mock('../context/AuthContext', async () => {
    const actual = await vi.importActual('../context/AuthContext')
    return {
        ...actual,
        useAuth: () => ({
            user: { username: 'testuser', email: 'test@example.com' },
            logout: mockLogout,
            isAuthenticated: true,
        }),
    }
})

vi.mock('react-router-dom', async () => {
    const actual = await vi.importActual('react-router-dom')
    return {
        ...actual,
        useNavigate: () => mockNavigate,
    }
})

const renderLayout = () => {
    return render(
        <BrowserRouter>
            <AuthProvider>
                <Routes>
                    <Route path="/" element={<Layout />}>
                        <Route index element={<div>Test Content</div>} />
                    </Route>
                </Routes>
            </AuthProvider>
        </BrowserRouter>
    )
}

describe('Layout', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('renders layout with sidebar', () => {
        renderLayout()

        expect(screen.getByText('FlexFlow')).toBeInTheDocument()
        expect(screen.getByText('Kanban Board')).toBeInTheDocument()
        expect(screen.getByText('Import POs')).toBeInTheDocument()
        expect(screen.getByText('Dashboard')).toBeInTheDocument()
    })

    it('displays user information', () => {
        renderLayout()

        expect(screen.getByText('testuser')).toBeInTheDocument()
        expect(screen.getByText('test@example.com')).toBeInTheDocument()
    })

    it('toggles sidebar when menu button is clicked', () => {
        renderLayout()

        const toggleButton = screen.getByLabelText(/close sidebar/i)

        // Sidebar should be open initially
        expect(screen.getByText('Kanban Board')).toBeInTheDocument()

        // Click to close
        fireEvent.click(toggleButton)

        // Button label should change
        expect(screen.getByLabelText(/open sidebar/i)).toBeInTheDocument()
    })

    it('calls logout when logout button is clicked', () => {
        renderLayout()

        const logoutButton = screen.getByRole('button', { name: /logout/i })
        fireEvent.click(logoutButton)

        expect(mockLogout).toHaveBeenCalled()
        expect(mockNavigate).toHaveBeenCalledWith('/login')
    })

    it('renders navigation links', () => {
        renderLayout()

        const kanbanLink = screen.getByRole('link', { name: /kanban board/i })
        const importLink = screen.getByRole('link', { name: /import pos/i })
        const dashboardLink = screen.getByRole('link', { name: /dashboard/i })

        expect(kanbanLink).toHaveAttribute('href', '/kanban')
        expect(importLink).toHaveAttribute('href', '/import')
        expect(dashboardLink).toHaveAttribute('href', '/dashboard')
    })

    it('renders outlet content', () => {
        renderLayout()

        expect(screen.getByText('Test Content')).toBeInTheDocument()
    })
})
