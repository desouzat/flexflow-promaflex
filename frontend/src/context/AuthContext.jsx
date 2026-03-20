import React, { createContext, useContext, useState, useEffect } from 'react'
import api from '../utils/api'

const AuthContext = createContext(null)

export const useAuth = () => {
    const context = useContext(AuthContext)
    if (!context) {
        throw new Error('useAuth must be used within an AuthProvider')
    }
    return context
}

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)

    useEffect(() => {
        // Check if user is already logged in
        console.log('[AuthContext] Initializing - checking localStorage')
        const token = localStorage.getItem('token')
        const savedUser = localStorage.getItem('user')

        console.log('[AuthContext] Token exists:', !!token)
        console.log('[AuthContext] Saved user exists:', !!savedUser)

        if (token && savedUser) {
            try {
                const parsedUser = JSON.parse(savedUser)
                console.log('[AuthContext] Restoring user session:', parsedUser.email)
                setUser(parsedUser)
            } catch (err) {
                console.error('[AuthContext] Error parsing saved user:', err)
                localStorage.removeItem('user')
                localStorage.removeItem('token')
            }
        }
        setLoading(false)
        console.log('[AuthContext] Initialization complete')
    }, [])

    const login = async (username, password) => {
        try {
            console.log('[AuthContext] Login attempt for:', username)
            setError(null)
            setLoading(true)

            // Send JSON payload with email field (backend expects email, not username)
            const response = await api.post('/auth/login', {
                email: username,
                password: password
            })

            const { access_token, user: userData } = response.data
            console.log('[AuthContext] Login successful, received token and user data')

            // Save token and user data synchronously
            localStorage.setItem('token', access_token)
            localStorage.setItem('user', JSON.stringify(userData))
            console.log('[AuthContext] Token saved to localStorage')
            console.log('[AuthContext] User data saved to localStorage')

            // Verify the save was successful
            const verifyToken = localStorage.getItem('token')
            const verifyUser = localStorage.getItem('user')
            console.log('[AuthContext] Verification - Token in localStorage:', !!verifyToken)
            console.log('[AuthContext] Verification - User in localStorage:', !!verifyUser)

            // Update state - this will trigger re-render
            setUser(userData)
            console.log('[AuthContext] User state updated, isAuthenticated will be true')

            // Wait for state to propagate (React 18 batching)
            await new Promise(resolve => setTimeout(resolve, 0))

            return { success: true, user: userData }
        } catch (err) {
            console.error('[AuthContext] Login failed:', err.response?.data || err.message)
            const errorMessage = err.response?.data?.detail || 'Login failed. Please try again.'
            setError(errorMessage)
            return { success: false, error: errorMessage }
        } finally {
            setLoading(false)
        }
    }

    const logout = () => {
        console.log('[AuthContext] Logging out user')
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        setUser(null)
        setError(null)
    }

    const value = {
        user,
        loading,
        error,
        login,
        logout,
        isAuthenticated: !!user,
    }

    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
