import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import LoginPage from './LoginPage'
import { AuthProvider } from '../context/AuthContext'

// Mock the auth context
const mockLogin = vi.fn()

vi.mock('../context/AuthContext', async () => {
    const actual = await vi.importActual('../context/AuthContext')
    return {
        ...actual,
        useAuth: () => ({
            login: mockLogin,
            loading: false,
            error: null,
        }),
    }
})

const renderLoginPage = () => {
    return render(
        <BrowserRouter>
            <AuthProvider>
                <LoginPage />
            </AuthProvider>
        </BrowserRouter>
    )
}

describe('LoginPage', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('renders login form correctly', () => {
        renderLoginPage()

        expect(screen.getByText('FlexFlow')).toBeInTheDocument()
        expect(screen.getByText('Purchase Order Management System')).toBeInTheDocument()
        expect(screen.getByLabelText(/username/i)).toBeInTheDocument()
        expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument()
    })

    it('shows validation error when fields are empty', async () => {
        renderLoginPage()

        const submitButton = screen.getByRole('button', { name: /sign in/i })
        fireEvent.click(submitButton)

        await waitFor(() => {
            expect(screen.getByText(/please enter both username and password/i)).toBeInTheDocument()
        })

        expect(mockLogin).not.toHaveBeenCalled()
    })

    it('calls login function with correct credentials', async () => {
        mockLogin.mockResolvedValue({ success: true })
        renderLoginPage()

        const usernameInput = screen.getByLabelText(/username/i)
        const passwordInput = screen.getByLabelText(/password/i)
        const submitButton = screen.getByRole('button', { name: /sign in/i })

        fireEvent.change(usernameInput, { target: { value: 'testuser' } })
        fireEvent.change(passwordInput, { target: { value: 'password123' } })
        fireEvent.click(submitButton)

        await waitFor(() => {
            expect(mockLogin).toHaveBeenCalledWith('testuser', 'password123')
        })
    })

    it('displays error message on login failure', async () => {
        mockLogin.mockResolvedValue({ success: false, error: 'Invalid credentials' })
        renderLoginPage()

        const usernameInput = screen.getByLabelText(/username/i)
        const passwordInput = screen.getByLabelText(/password/i)
        const submitButton = screen.getByRole('button', { name: /sign in/i })

        fireEvent.change(usernameInput, { target: { value: 'testuser' } })
        fireEvent.change(passwordInput, { target: { value: 'wrongpassword' } })
        fireEvent.click(submitButton)

        await waitFor(() => {
            expect(screen.getByText('Invalid credentials')).toBeInTheDocument()
        })
    })

    it('disables form during submission', async () => {
        mockLogin.mockImplementation(() => new Promise(resolve => setTimeout(() => resolve({ success: true }), 100)))
        renderLoginPage()

        const usernameInput = screen.getByLabelText(/username/i)
        const passwordInput = screen.getByLabelText(/password/i)
        const submitButton = screen.getByRole('button', { name: /sign in/i })

        fireEvent.change(usernameInput, { target: { value: 'testuser' } })
        fireEvent.change(passwordInput, { target: { value: 'password123' } })
        fireEvent.click(submitButton)

        expect(submitButton).toBeDisabled()
        expect(usernameInput).toBeDisabled()
        expect(passwordInput).toBeDisabled()
    })
})
