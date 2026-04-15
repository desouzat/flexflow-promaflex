import React from 'react'
import { AlertTriangle } from 'lucide-react'

class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props)
        this.state = { hasError: false, error: null, errorInfo: null }
    }

    static getDerivedStateFromError(error) {
        return { hasError: true }
    }

    componentDidCatch(error, errorInfo) {
        console.error('ErrorBoundary caught an error:', error, errorInfo)
        this.setState({
            error: error,
            errorInfo: errorInfo
        })
    }

    render() {
        if (this.state.hasError) {
            return (
                <div className="flex items-center justify-center h-full bg-gray-50">
                    <div className="text-center max-w-md p-6">
                        <AlertTriangle className="w-16 h-16 text-red-600 mx-auto mb-4" />
                        <h2 className="text-xl font-semibold text-gray-900 mb-2">
                            Algo deu errado
                        </h2>
                        <p className="text-gray-600 mb-4">
                            Ocorreu um erro ao carregar esta página. Por favor, tente atualizar.
                        </p>
                        {this.state.error && (
                            <details className="text-left bg-gray-100 p-4 rounded-lg mb-4">
                                <summary className="cursor-pointer font-medium text-gray-700 mb-2">
                                    Detalhes do erro
                                </summary>
                                <pre className="text-xs text-red-600 overflow-auto">
                                    {this.state.error.toString()}
                                    {this.state.errorInfo && this.state.errorInfo.componentStack}
                                </pre>
                            </details>
                        )}
                        <button
                            onClick={() => window.location.reload()}
                            className="btn-primary"
                        >
                            Recarregar Página
                        </button>
                    </div>
                </div>
            )
        }

        return this.props.children
    }
}

export default ErrorBoundary
