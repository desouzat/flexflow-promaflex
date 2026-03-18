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
        const token = localStorage.getItem('token')
        const savedUser = localStorage.getItem('user')

        if (token && savedUser) {
            try {
                setUser(JSON.parse(savedUser))
            } catch (err) {
                console.error('Error parsing saved user:', err)
                localStorage.removeItem('user')
                localStorage.removeItem('token')
            }
        }
        setLoading(false)
    }, [])

    const login = async (username, password) => {
        try {
            setError(null)
            setLoading(true)

            // Create form data for OAuth2 password flow
            const formData = new FormData()
            formData.append('username', username)
            formData.append('password', password)

            const response = await api.post('/auth/login', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
            })

            const { access_token, user: userData } = response.data

            // Save token and user data
            localStorage.setItem('token', access_token)
            localStorage.setItem('user', JSON.stringify(userData))

            setUser(userData)
            return { success: true }
        } catch (err) {
            const errorMessage = err.response?.data?.detail || 'Login failed. Please try again.'
            setError(errorMessage)
            return { success: false, error: errorMessage }
        } finally {
            setLoading(false)
        }
    }

    const logout = () => {
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
