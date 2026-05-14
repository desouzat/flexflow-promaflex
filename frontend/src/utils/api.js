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

        if (token) {
            config.headers.Authorization = `Bearer ${token}`
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

        if (status === 401) {
            console.warn('[API Interceptor] 401 Unauthorized - clearing auth and redirecting to login')
            // Token expired or invalid
            localStorage.removeItem('token')
            localStorage.removeItem('user')
            window.location.href = '/login'
        } else if (status === 403) {
            console.error('[API Interceptor] 403 Forbidden - token exists but access denied')
            console.error('[API Interceptor] This may indicate a token/state sync issue')
        }
        return Promise.reject(error)
    }
)

export default api
