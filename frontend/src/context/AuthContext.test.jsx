import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { AuthProvider, useAuth } from './AuthContext'

// Test component that uses the auth context
const TestComponent = () => {
    const { user, isAuthenticated, loading } = useAuth()

    if (loading) return <div>Loading...</div>

    return (
        <div>
            <div data-testid="auth-status">
                {isAuthenticated ? 'Authenticated' : 'Not Authenticated'}
            </div>
            {user && <div data-testid="user-name">{user.username}</div>}
        </div>
    )
}

describe('AuthContext', () => {
    beforeEach(() => {
        localStorage.clear()
        vi.clearAllMocks()
    })

    it('renders children correctly', () => {
        render(
            <AuthProvider>
                <div>Test Child</div>
            </AuthProvider>
        )

        expect(screen.getByText('Test Child')).toBeInTheDocument()
    })

    it('provides authentication state', async () => {
        render(
            <AuthProvider>
                <TestComponent />
            </AuthProvider>
        )

        await waitFor(() => {
            expect(screen.getByTestId('auth-status')).toHaveTextContent('Not Authenticated')
        })
    })

    it('loads user from localStorage on mount', async () => {
        const mockUser = { id: 1, username: 'testuser', email: 'test@example.com' }
        localStorage.setItem('token', 'mock-token')
        localStorage.setItem('user', JSON.stringify(mockUser))

        render(
            <AuthProvider>
                <TestComponent />
            </AuthProvider>
        )

        await waitFor(() => {
            expect(screen.getByTestId('auth-status')).toHaveTextContent('Authenticated')
            expect(screen.getByTestId('user-name')).toHaveTextContent('testuser')
        })
    })

    it('throws error when useAuth is used outside provider', () => {
        // Suppress console.error for this test
        const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => { })

        expect(() => {
            render(<TestComponent />)
        }).toThrow('useAuth must be used within an AuthProvider')

        consoleSpy.mockRestore()
    })
})
