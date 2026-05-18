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
import CostsPage from './pages/CostsPage'
import UsersPage from './pages/UsersPage'

// Protected Route Component
const ProtectedRoute = ({ children }) => {
    const { isAuthenticated, loading, user } = useAuth()

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-screen">
                <div className="text-xl text-gray-600">Loading...</div>
            </div>
        )
    }

    if (!isAuthenticated) {
        return <Navigate to="/login" replace />
    }

    return children
}

// Public Route Component (redirect to kanban if already authenticated)
const PublicRoute = ({ children }) => {
    const { isAuthenticated, loading, user } = useAuth()

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-screen">
                <div className="text-xl text-gray-600">Loading...</div>
            </div>
        )
    }

    if (isAuthenticated) {
        return <Navigate to="/kanban" replace />
    }

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
                <Route path="costs" element={<CostsPage />} />
                <Route path="users" element={<UsersPage />} />
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
