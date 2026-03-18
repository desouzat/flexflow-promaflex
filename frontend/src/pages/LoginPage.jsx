import React, { useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { LogIn, AlertCircle } from 'lucide-react'

const LoginPage = () => {
    const [username, setUsername] = useState('')
    const [password, setPassword] = useState('')
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [localError, setLocalError] = useState('')
    const { login } = useAuth()

    const handleSubmit = async (e) => {
        e.preventDefault()
        setLocalError('')

        if (!username || !password) {
            setLocalError('Please enter both username and password')
            return
        }

        setIsSubmitting(true)

        try {
            const result = await login(username, password)

            if (!result.success) {
                setLocalError(result.error || 'Login failed')
            }
        } catch (err) {
            setLocalError('An unexpected error occurred')
        } finally {
            setIsSubmitting(false)
        }
    }

    return (
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 to-primary-100">
            <div className="max-w-md w-full mx-4">
                <div className="card">
                    <div className="text-center mb-8">
                        <div className="inline-flex items-center justify-center w-16 h-16 bg-primary-600 rounded-full mb-4">
                            <LogIn className="w-8 h-8 text-white" />
                        </div>
                        <h1 className="text-3xl font-bold text-gray-900">FlexFlow</h1>
                        <p className="text-gray-600 mt-2">Purchase Order Management System</p>
                    </div>

                    {localError && (
                        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3">
                            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                            <p className="text-sm text-red-800">{localError}</p>
                        </div>
                    )}

                    <form onSubmit={handleSubmit} className="space-y-6">
                        <div>
                            <label htmlFor="username" className="block text-sm font-medium text-gray-700 mb-2">
                                Username
                            </label>
                            <input
                                id="username"
                                type="text"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                className="input-field"
                                placeholder="Enter your username"
                                disabled={isSubmitting}
                                autoComplete="username"
                            />
                        </div>

                        <div>
                            <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-2">
                                Password
                            </label>
                            <input
                                id="password"
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="input-field"
                                placeholder="Enter your password"
                                disabled={isSubmitting}
                                autoComplete="current-password"
                            />
                        </div>

                        <button
                            type="submit"
                            disabled={isSubmitting}
                            className="w-full btn-primary disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                        >
                            {isSubmitting ? (
                                <>
                                    <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                                    Signing in...
                                </>
                            ) : (
                                <>
                                    <LogIn className="w-5 h-5" />
                                    Sign In
                                </>
                            )}
                        </button>
                    </form>

                    <div className="mt-6 text-center text-sm text-gray-600">
                        <p>Demo credentials:</p>
                        <p className="font-mono text-xs mt-1">admin / admin123</p>
                    </div>
                </div>
            </div>
        </div>
    )
}

export default LoginPage
