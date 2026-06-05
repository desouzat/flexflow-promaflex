import React, { createContext, useContext, useState, useEffect } from 'react'
import api from '../utils/api'
import { useAuth } from './AuthContext'

const NotificationContext = createContext()

export const useNotifications = () => {
    const context = useContext(NotificationContext)
    if (!context) {
        throw new Error('useNotifications must be used within NotificationProvider')
    }
    return context
}

export const NotificationProvider = ({ children }) => {
    const { user } = useAuth()
    const [badges, setBadges] = useState({
        kanban: 0,
        import: 0,
        dashboard: 0,
    })

    const fetchNotifications = async () => {
        const token = localStorage.getItem('token')
        if (!token) return

        try {
            // FIXED: Remove /api prefix - api.js baseURL already includes /api
            // So /kanban/pos becomes http://localhost:8000/api/kanban/pos
            const kanbanResponse = await api.get('/kanban/pos')
            const pendingCount = kanbanResponse.data.filter(
                po => po.status === 'pending'
            ).length

            setBadges(prev => ({
                ...prev,
                kanban: pendingCount,
            }))
        } catch (error) {
            console.error('Error fetching notifications:', error)
        }
    }

    useEffect(() => {
        const token = localStorage.getItem('token')
        if (token && user && user.id) {
            fetchNotifications()
            // Refresh every 30 seconds
            const interval = setInterval(fetchNotifications, 30000)
            return () => clearInterval(interval)
        }
    }, [user])

    const updateBadge = (key, value) => {
        setBadges(prev => ({
            ...prev,
            [key]: value,
        }))
    }

    const incrementBadge = (key) => {
        setBadges(prev => ({
            ...prev,
            [key]: prev[key] + 1,
        }))
    }

    const decrementBadge = (key) => {
        setBadges(prev => ({
            ...prev,
            [key]: Math.max(0, prev[key] - 1),
        }))
    }

    const clearBadge = (key) => {
        setBadges(prev => ({
            ...prev,
            [key]: 0,
        }))
    }

    return (
        <NotificationContext.Provider
            value={{
                badges,
                updateBadge,
                incrementBadge,
                decrementBadge,
                clearBadge,
                refreshNotifications: fetchNotifications,
            }}
        >
            {children}
        </NotificationContext.Provider>
    )
}
