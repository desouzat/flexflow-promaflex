import React, { useState, useEffect } from 'react'
import KanbanColumn from '../components/kanban/KanbanColumn'
import ErrorBoundary from '../components/ErrorBoundary'
import api from '../utils/api'
import { showSuccess, showError } from '../utils/toast'
import { useNotifications } from '../context/NotificationContext'
import { RefreshCw, Filter, Search, Maximize2, Minimize2 } from 'lucide-react'

const KanbanPage = () => {
    const [boardData, setBoardData] = useState(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const [searchTerm, setSearchTerm] = useState('')
    const [compactView, setCompactView] = useState(false)
    const { refreshNotifications } = useNotifications()

    const fetchBoard = async () => {
        try {
            setLoading(true)
            setError(null)
            const response = await api.get('/kanban/board')
            setBoardData(response.data)
            refreshNotifications()
        } catch (err) {
            const errorMsg = err.response?.data?.detail || 'Falha ao carregar o quadro Kanban'
            setError(errorMsg)
            showError(errorMsg)
            console.error('Error fetching board:', err)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchBoard()
    }, [])

    const handleCardClick = (po) => {
        console.log('PO clicked:', po)
        // TODO: Open modal with PO details
    }

    const handleMoveCard = async (poId, newStatus) => {
        try {
            await api.post('/kanban/move-status', {
                po_id: poId,
                to_status: newStatus
            })
            showSuccess(`Pedido movido para ${newStatus}`)
            fetchBoard()
        } catch (err) {
            const errorMsg = err.response?.data?.detail || 'Falha ao mover o card'
            showError(errorMsg)
            console.error('Error moving card:', err)
        }
    }

    const filterPOs = (pos) => {
        if (!pos || !Array.isArray(pos)) return []
        if (!searchTerm) return pos

        return pos.filter((po) => {
            const poNumber = po.po_number || ''
            const clientName = po.client_name || ''
            return poNumber.toLowerCase().includes(searchTerm.toLowerCase()) ||
                clientName.toLowerCase().includes(searchTerm.toLowerCase())
        })
    }

    const getColumnColor = (status) => {
        const colorMap = {
            'Pendente': 'yellow',
            'PCP': 'blue',
            'Produção': 'purple',
            'Expedição': 'orange',
            'Concluído': 'green'
        }
        return colorMap[status] || 'gray'
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center h-full">
                <div className="text-center">
                    <div className="w-16 h-16 border-4 border-primary-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                    <p className="text-gray-600">Carregando pedidos...</p>
                </div>
            </div>
        )
    }

    if (error) {
        return (
            <div className="flex items-center justify-center h-full">
                <div className="text-center max-w-md">
                    <div className="text-red-600 text-5xl mb-4">⚠️</div>
                    <h2 className="text-xl font-semibold text-gray-900 mb-2">Erro ao Carregar Dados</h2>
                    <p className="text-gray-600 mb-4">{error}</p>
                    <button onClick={fetchBoard} className="btn-primary">
                        Tentar Novamente
                    </button>
                </div>
            </div>
        )
    }

    if (!boardData || !boardData.columns || !Array.isArray(boardData.columns)) {
        return (
            <div className="flex items-center justify-center h-full">
                <div className="text-center">
                    <p className="text-gray-600">Nenhum dado disponível</p>
                    <button onClick={fetchBoard} className="btn-primary mt-4">
                        Carregar Dados
                    </button>
                </div>
            </div>
        )
    }

    return (
        <ErrorBoundary>
            <div className="h-full flex flex-col">
                {/* Header */}
                <div className="bg-white border-b border-gray-200 px-6 py-4">
                    <div className="flex items-center justify-between">
                        <div>
                            <h1 className="text-2xl font-bold text-gray-900">Quadro Kanban</h1>
                            <p className="text-sm text-gray-600 mt-1">
                                {boardData.total_pos} {boardData.total_pos === 1 ? 'pedido' : 'pedidos'} no total
                            </p>
                        </div>
                        <div className="flex items-center gap-3">
                            <div className="relative">
                                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                                <input
                                    type="text"
                                    placeholder="Buscar pedidos..."
                                    value={searchTerm}
                                    onChange={(e) => setSearchTerm(e.target.value)}
                                    className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                                />
                            </div>
                            <button
                                onClick={() => setCompactView(!compactView)}
                                className="btn-secondary flex items-center gap-2"
                                title={compactView ? 'Expandir visualização' : 'Visualização compacta'}
                            >
                                {compactView ? (
                                    <Maximize2 className="w-5 h-5" />
                                ) : (
                                    <Minimize2 className="w-5 h-5" />
                                )}
                            </button>
                            <button
                                onClick={fetchBoard}
                                className="btn-secondary flex items-center gap-2"
                                aria-label="Atualizar"
                            >
                                <RefreshCw className="w-5 h-5" />
                                Atualizar
                            </button>
                            <button className="btn-secondary flex items-center gap-2">
                                <Filter className="w-5 h-5" />
                                Filtrar
                            </button>
                        </div>
                    </div>
                </div>

                {/* Kanban Board */}
                <div className="flex-1 overflow-x-auto overflow-y-hidden p-6">
                    <div className="flex gap-4 h-full">
                        {boardData.columns.map((column) => (
                            <KanbanColumn
                                key={column.status}
                                title={column.status}
                                status={column.status}
                                pos={filterPOs(column.pos)}
                                onCardClick={handleCardClick}
                                onMoveCard={handleMoveCard}
                                color={getColumnColor(column.status)}
                                compactView={compactView}
                            />
                        ))}
                    </div>
                </div>
            </div>
        </ErrorBoundary>
    )
}

export default KanbanPage
