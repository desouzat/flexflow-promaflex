import React from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { AuthProvider, useAuth } from './context/AuthContext'
import { NotificationProvider } from './context/NotificationContext'
import LoginPage from './pages/LoginPage'
import Layout from './components/Layout'
import KanbanPage from './pages/KanbanPage'
import ImportPage from './pages/ImportPage'
import DashboardPage from './pages/DashboardPage'

// Protected Route Component
const ProtectedRoute = ({ children }) => {
    const { isAuthenticated, loading, user } = useAuth()

    console.log('[ProtectedRoute] Checking access - loading:', loading, 'isAuthenticated:', isAuthenticated, 'user:', user?.email)

    if (loading) {
        console.log('[ProtectedRoute] Still loading, showing loading screen')
        return (
            <div className="flex items-center justify-center min-h-screen">
                <div className="text-xl text-gray-600">Loading...</div>
            </div>
        )
    }

    if (!isAuthenticated) {
        console.log('[ProtectedRoute] Not authenticated, redirecting to login')
        return <Navigate to="/login" replace />
    }

    console.log('[ProtectedRoute] Authenticated, rendering protected content')
    return children
}

// Public Route Component (redirect to kanban if already authenticated)
const PublicRoute = ({ children }) => {
    const { isAuthenticated, loading, user } = useAuth()

    console.log('[PublicRoute] Checking access - loading:', loading, 'isAuthenticated:', isAuthenticated, 'user:', user?.email)

    if (loading) {
        console.log('[PublicRoute] Still loading, showing loading screen')
        return (
            <div className="flex items-center justify-center min-h-screen">
                <div className="text-xl text-gray-600">Loading...</div>
            </div>
        )
    }

    if (isAuthenticated) {
        console.log('[PublicRoute] Already authenticated, redirecting to kanban')
        return <Navigate to="/kanban" replace />
    }

    console.log('[PublicRoute] Not authenticated, rendering public content')
    return children
}

function AppRoutes() {
    return (
        <Routes>
            <Route
                path="/login"
                element={
                    <PublicRoute>
                        <LoginPage />
                    </PublicRoute>
                }
            />
            <Route
                path="/"
                element={
                    <ProtectedRoute>
                        <Layout />
                    </ProtectedRoute>
                }
            >
                <Route index element={<Navigate to="/kanban" replace />} />
                <Route path="kanban" element={<KanbanPage />} />
                <Route path="import" element={<ImportPage />} />
                <Route path="dashboard" element={<DashboardPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
    )
}

function App() {
    return (
        <AuthProvider>
            <NotificationProvider>
                <Router>
                    <AppRoutes />
                    <Toaster />
                </Router>
            </NotificationProvider>
        </AuthProvider>
    )
}

export default App
