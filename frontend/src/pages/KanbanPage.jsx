import React, { useState, useEffect } from 'react'
import KanbanColumn from '../components/kanban/KanbanColumn'
import ErrorBoundary from '../components/ErrorBoundary'
import MetadataVisualizer from '../components/MetadataVisualizer'
import api from '../utils/api'
import { showSuccess, showError } from '../utils/toast'
import { useNotifications } from '../context/NotificationContext'
import {
    RefreshCw, Filter, Search, Maximize2, Minimize2, X,
    Package, DollarSign, Calendar, User, FileText, Globe,
    Star, RefreshCw as RefreshIcon, Zap, AlertCircle
} from 'lucide-react'

const KanbanPage = () => {
    const [boardData, setBoardData] = useState(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const [searchTerm, setSearchTerm] = useState('')
    const [compactView, setCompactView] = useState(false)
    const [selectedPO, setSelectedPO] = useState(null)
    const [showDetailsModal, setShowDetailsModal] = useState(false)
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
        setSelectedPO(po)
        setShowDetailsModal(true)
    }

    const handleCloseModal = () => {
        setShowDetailsModal(false)
        setSelectedPO(null)
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

    const handleMetadataUpdate = async (itemId, newMetadata) => {
        try {
            await api.put(`/kanban/items/${itemId}/metadata`, newMetadata)
            showSuccess('Metadata atualizada com sucesso')
            // Refresh the selected PO data
            fetchBoard()
            // Update the selected PO in the modal
            if (selectedPO) {
                const updatedPO = { ...selectedPO }
                // Update the metadata in the items array
                if (updatedPO.items) {
                    updatedPO.items = updatedPO.items.map(item =>
                        item.id === itemId ? { ...item, extra_metadata: newMetadata } : item
                    )
                }
                setSelectedPO(updatedPO)
            }
        } catch (err) {
            const errorMsg = err.response?.data?.detail || 'Falha ao atualizar metadata'
            showError(errorMsg)
            console.error('Error updating metadata:', err)
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
            'Comercial': 'yellow',
            'PCP': 'blue',
            'Produção/Embalagem': 'purple',
            'Expedição/Faturamento': 'lightblue',
            'Concluído': 'green'
        }
        return colorMap[status] || 'gray'
    }

    const formatCurrency = (value) => {
        return new Intl.NumberFormat('pt-BR', {
            style: 'currency',
            currency: 'BRL',
        }).format(value || 0)
    }

    const formatDate = (dateString) => {
        if (!dateString) return 'N/A'
        return new Date(dateString).toLocaleDateString('pt-BR')
    }

    const getStrategicIndicators = (metadata) => {
        const indicators = []
        if (!metadata) return indicators

        if (metadata.is_export) {
            indicators.push({ icon: Globe, label: 'Exportação', color: 'blue' })
        }
        if (metadata.is_first_order) {
            indicators.push({ icon: Star, label: 'Primeiro Pedido', color: 'yellow' })
        }
        if (metadata.is_replacement) {
            indicators.push({ icon: RefreshIcon, label: 'Reposição', color: 'purple' })
        }
        if (metadata.is_urgent) {
            indicators.push({ icon: Zap, label: 'Urgente', color: 'red' })
        }

        return indicators
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
                                className="btn-primary flex items-center gap-2"
                            >
                                <RefreshCw className="w-5 h-5" />
                                Atualizar
                            </button>
                        </div>
                    </div>
                </div>

                {/* Kanban Board */}
                <div className="flex-1 overflow-x-auto bg-gray-50 p-6">
                    <div className="flex gap-4 h-full min-w-max">
                        {boardData.columns.map((column) => (
                            <KanbanColumn
                                key={column.status}
                                title={column.status}
                                pos={filterPOs(column.pos)}
                                color={getColumnColor(column.status)}
                                count={column.count}
                                onCardClick={handleCardClick}
                                onMoveCard={handleMoveCard}
                                compactView={compactView}
                            />
                        ))}
                    </div>
                </div>

                {/* Details Modal/Drawer */}
                {showDetailsModal && selectedPO && (
                    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
                        <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
                            {/* Modal Header */}
                            <div className="flex items-center justify-between p-6 border-b border-gray-200 bg-gray-50">
                                <div>
                                    <h2 className="text-2xl font-bold text-gray-900">
                                        Pedido #{selectedPO.po_number}
                                    </h2>
                                    <p className="text-sm text-gray-600 mt-1">
                                        {selectedPO.supplier_name || selectedPO.client_name || 'Cliente não especificado'}
                                    </p>
                                </div>
                                <button
                                    onClick={handleCloseModal}
                                    className="p-2 hover:bg-gray-200 rounded-lg transition-colors"
                                >
                                    <X className="w-6 h-6 text-gray-600" />
                                </button>
                            </div>

                            {/* Modal Content */}
                            <div className="flex-1 overflow-y-auto p-6">
                                {/* PO Summary */}
                                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                                    <div className="bg-gray-50 p-4 rounded-lg">
                                        <div className="flex items-center gap-2 text-gray-600 mb-1">
                                            <DollarSign className="w-4 h-4" />
                                            <span className="text-xs font-medium">Valor Total</span>
                                        </div>
                                        <p className="text-lg font-bold text-gray-900">
                                            {formatCurrency(selectedPO.total_value)}
                                        </p>
                                    </div>
                                    <div className="bg-gray-50 p-4 rounded-lg">
                                        <div className="flex items-center gap-2 text-gray-600 mb-1">
                                            <Calendar className="w-4 h-4" />
                                            <span className="text-xs font-medium">Entrega</span>
                                        </div>
                                        <p className="text-lg font-bold text-gray-900">
                                            {formatDate(selectedPO.expected_delivery_date)}
                                        </p>
                                    </div>
                                    <div className="bg-gray-50 p-4 rounded-lg">
                                        <div className="flex items-center gap-2 text-gray-600 mb-1">
                                            <Package className="w-4 h-4" />
                                            <span className="text-xs font-medium">Itens</span>
                                        </div>
                                        <p className="text-lg font-bold text-gray-900">
                                            {selectedPO.items_count || 0}
                                        </p>
                                    </div>
                                    <div className="bg-gray-50 p-4 rounded-lg">
                                        <div className="flex items-center gap-2 text-gray-600 mb-1">
                                            <FileText className="w-4 h-4" />
                                            <span className="text-xs font-medium">Status</span>
                                        </div>
                                        <p className="text-lg font-bold text-gray-900 capitalize">
                                            {selectedPO.status || 'N/A'}
                                        </p>
                                    </div>
                                </div>

                                {/* Strategic Indicators */}
                                {selectedPO.extra_metadata && Object.keys(selectedPO.extra_metadata).length > 0 && (
                                    <div className="mb-6">
                                        <h3 className="text-lg font-semibold text-gray-900 mb-3">Indicadores Estratégicos</h3>
                                        <div className="flex flex-wrap gap-2">
                                            {getStrategicIndicators(selectedPO.extra_metadata).map((indicator, idx) => {
                                                const IconComponent = indicator.icon
                                                return (
                                                    <div
                                                        key={idx}
                                                        className={`flex items-center gap-2 px-3 py-2 rounded-lg bg-${indicator.color}-100 text-${indicator.color}-700 border border-${indicator.color}-200`}
                                                    >
                                                        <IconComponent className="w-4 h-4" />
                                                        <span className="text-sm font-medium">{indicator.label}</span>
                                                    </div>
                                                )
                                            })}
                                        </div>
                                    </div>
                                )}

                                {/* Production Impediment */}
                                {selectedPO.extra_metadata?.production_impediment && (
                                    <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
                                        <div className="flex items-center gap-2 text-red-700 mb-2">
                                            <AlertCircle className="w-5 h-5" />
                                            <h3 className="font-semibold">Impedimento de Produção</h3>
                                        </div>
                                        <p className="text-sm text-red-600">
                                            {selectedPO.extra_metadata.production_impediment}
                                        </p>
                                    </div>
                                )}

                                {/* Items List */}
                                {selectedPO.items && selectedPO.items.length > 0 && (
                                    <div className="mb-6">
                                        <h3 className="text-lg font-semibold text-gray-900 mb-3">Itens do Pedido</h3>
                                        <div className="space-y-4">
                                            {selectedPO.items.map((item, idx) => (
                                                <div key={item.id || idx} className="border border-gray-200 rounded-lg p-4">
                                                    <div className="flex items-start justify-between mb-3">
                                                        <div>
                                                            <h4 className="font-semibold text-gray-900">{item.sku}</h4>
                                                            <p className="text-sm text-gray-600">
                                                                Quantidade: {item.quantity} | Preço: {formatCurrency(item.price)}
                                                            </p>
                                                        </div>
                                                        <span className="px-2 py-1 bg-blue-100 text-blue-700 text-xs font-medium rounded">
                                                            {item.status_item || 'PENDING'}
                                                        </span>
                                                    </div>

                                                    {/* Metadata Visualizer for each item */}
                                                    {item.extra_metadata && Object.keys(item.extra_metadata).length > 0 && (
                                                        <div className="mt-3">
                                                            <MetadataVisualizer
                                                                metadata={item.extra_metadata}
                                                                itemId={item.id}
                                                                onUpdate={handleMetadataUpdate}
                                                                readOnly={false}
                                                            />
                                                        </div>
                                                    )}
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {/* PO-level Metadata */}
                                {selectedPO.extra_metadata && Object.keys(selectedPO.extra_metadata).length > 0 && (
                                    <div>
                                        <h3 className="text-lg font-semibold text-gray-900 mb-3">Metadata do Pedido</h3>
                                        <MetadataVisualizer
                                            metadata={selectedPO.extra_metadata}
                                            itemId={selectedPO.id}
                                            onUpdate={null}
                                            readOnly={true}
                                        />
                                    </div>
                                )}
                            </div>

                            {/* Modal Footer */}
                            <div className="flex items-center justify-end gap-3 p-6 border-t border-gray-200 bg-gray-50">
                                <button
                                    onClick={handleCloseModal}
                                    className="btn-secondary"
                                >
                                    Fechar
                                </button>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </ErrorBoundary>
    )
}

export default KanbanPage
