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

        if (status === 401) {
            const token = localStorage.getItem('token')
            const isAuthRequest = url && (url.includes('/auth/me') || url.includes('/auth/login'))
            if (token && !isAuthRequest && !error.config?._retry) {
                console.warn('[API Interceptor] 401 Unauthorized but token exists - attempting state validation before logout')
                error.config._retry = true
                return api.get('/auth/me')
                    .then(() => {
                        console.log('[API Interceptor] Token verification successful - retrying original request')
                        return api(error.config)
                    })
                    .catch((err) => {
                        console.error('[API Interceptor] Token verification failed - clearing session and redirecting')
                        localStorage.removeItem('token')
                        localStorage.removeItem('user')
                        window.location.href = '/login'
                        return Promise.reject(err)
                    })
            } else {
                console.warn('[API Interceptor] 401 Unauthorized - clearing auth and redirecting to login')
                localStorage.removeItem('token')
                localStorage.removeItem('user')
                window.location.href = '/login'
            }
        } else if (status === 403) {
            console.error('[API Interceptor] 403 Forbidden - token exists but access denied')
            console.error('[API Interceptor] This may indicate a token/state sync issue')
        }
        return Promise.reject(error)
    }
)

export default api
