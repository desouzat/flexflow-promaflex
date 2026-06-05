import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

// Create axios instance
const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
})

// Request interceptor to add token dynamically
api.interceptors.request.use(
    (config) => {
        // CRITICAL: Fetch token dynamically on each request, not once at module load
        const token = localStorage.getItem('token')

        console.log('[API Interceptor] Request:', config.method?.toUpperCase(), config.url)
        console.log('[API Interceptor] Token in localStorage:', token ? `YES (${token.substring(0, 20)}...)` : 'NO')

        if (token) {
            config.headers.Authorization = `Bearer ${token}`
            console.log('[API Interceptor] Authorization header added')
        } else {
            console.warn('[API Interceptor] NO TOKEN - Request will be sent without Authorization header')
        }

        return config
    },
    (error) => {
        console.error('[API Interceptor] Request error:', error)
        return Promise.reject(error)
    }
)

// Response interceptor to handle errors
api.interceptors.response.use(
    (response) => {
        return response
    },
    (error) => {
        const status = error.response?.status
        const url = error.config?.url
        console.error('[API Interceptor] Response error:', status, url)

        if (status === 403) {
            console.warn('[API Interceptor] 403 Forbidden - Access Denied (Bypassing logout/redirect)')
            return Promise.reject(error)
        }

        if (status === 401) {
            if (window.location.pathname !== '/login') {
                console.warn('[API Interceptor] 401 Unauthorized - clearing localStorage and redirecting to login')
                localStorage.clear()
                window.location.href = '/login'
            } else {
                console.warn('[API Interceptor] 401 Unauthorized on login page - bypassing forced redirect loop')
            }
        }

        return Promise.reject(error)
    }
)

export default api
