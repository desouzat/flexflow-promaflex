import { expect, afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'
import '@testing-library/jest-dom'

// Cleanup after each test
afterEach(() => {
    cleanup()
})

// Global mocks for Auth and Notification Contexts to support page testing
vi.mock('../context/NotificationContext', () => ({
    useNotifications: () => ({
        badges: { kanban: 0, import: 0, dashboard: 0 },
        updateBadge: vi.fn(),
        incrementBadge: vi.fn(),
        decrementBadge: vi.fn(),
        clearBadge: vi.fn(),
        refreshNotifications: vi.fn().mockResolvedValue(true),
    }),
    NotificationProvider: ({ children }) => children
}))

vi.mock('../context/AuthContext', () => ({
    useAuth: () => ({
        user: { id: 'test-user-id', tenant_id: 'test-tenant-id', name: 'Test User', role: 'OPERATOR' },
        login: vi.fn().mockResolvedValue(true),
        logout: vi.fn().mockResolvedValue(true),
    }),
    AuthProvider: ({ children }) => children
}))


