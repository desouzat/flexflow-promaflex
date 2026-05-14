import React, { useState, useEffect } from 'react'
import KanbanColumn from '../components/kanban/KanbanColumn'
import ErrorBoundary from '../components/ErrorBoundary'
import MetadataVisualizer from '../components/MetadataVisualizer'
import api from '../utils/api'
import { showSuccess, showError } from '../utils/toast'
import { useNotifications } from '../context/NotificationContext'
import { useAuth } from '../context/AuthContext'
import {
    RefreshCw, Filter, Search, Maximize2, Minimize2, X,
    Package, DollarSign, Calendar, User, FileText, Globe,
    Star, RefreshCw as RefreshIcon, Zap, AlertCircle, Upload,
    CheckCircle, Edit2, Save, XCircle, Truck
} from 'lucide-react'

const KanbanPage = () => {
    const [boardData, setBoardData] = useState(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const [searchTerm, setSearchTerm] = useState('')
    const [compactView, setCompactView] = useState(false)
    const [selectedPO, setSelectedPO] = useState(null)
    const [showDetailsModal, setShowDetailsModal] = useState(false)
    const [editingCommission, setEditingCommission] = useState(false)
    const [commissionValue, setCommissionValue] = useState('')
    const [commissionJustification, setCommissionJustification] = useState('')
    const [logisticsChecklist, setLogisticsChecklist] = useState({
        endereco_conferido: false,
        peso_validado: false,
        etiquetas_impressas: false,
        foto_carga_path: null,
        foto_canhoto_path: null
    })
    const [uploadingEvidence, setUploadingEvidence] = useState(false)
    const [showReturnModal, setShowReturnModal] = useState(false)
    const [returnReason, setReturnReason] = useState('')
    const [showPartitionModal, setShowPartitionModal] = useState(false)
    const [partitionReason, setPartitionReason] = useState('')
    const { refreshNotifications } = useNotifications()
    const { user } = useAuth()

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

    const handleCardClick = async (po) => {
        console.log('PO clicked:', po)
        setSelectedPO(po)
        setShowDetailsModal(true)

        // Load logistics checklist if in Expedição/Faturamento
        if (po.status === 'Expedição/Faturamento') {
            try {
                const response = await api.get(`/kanban/pos/${po.id}/logistics-checklist`)
                setLogisticsChecklist(response.data.checklist)
            } catch (err) {
                console.error('Error loading logistics checklist:', err)
            }
        }
    }

    const handleCloseModal = () => {
        setShowDetailsModal(false)
        setSelectedPO(null)
        setEditingCommission(false)
        setCommissionValue('')
        setCommissionJustification('')
        setLogisticsChecklist({
            endereco_conferido: false,
            peso_validado: false,
            etiquetas_impressas: false,
            foto_carga_path: null,
            foto_canhoto_path: null
        })
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
            fetchBoard()
            if (selectedPO) {
                const updatedPO = { ...selectedPO }
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

    const handleSaveCommission = async () => {
        if (!commissionValue || !commissionJustification) {
            showError('Preencha a taxa de comissão e a justificativa')
            return
        }

        if (commissionJustification.length < 10) {
            showError('A justificativa deve ter pelo menos 10 caracteres')
            return
        }

        try {
            const response = await api.put(`/kanban/pos/${selectedPO.id}/commission`, {
                po_id: selectedPO.id,
                manual_commission_rate: parseFloat(commissionValue),
                justification: commissionJustification
            })

            showSuccess(response.data.message)
            setEditingCommission(false)
            setCommissionValue('')
            setCommissionJustification('')

            // Refresh PO data
            fetchBoard()

            // Update selected PO
            const updatedPO = { ...selectedPO }
            updatedPO.commission_rate = response.data.new_commission_rate
            updatedPO.margin_percentage = response.data.new_margin
            setSelectedPO(updatedPO)
        } catch (err) {
            const errorMsg = err.response?.data?.detail || 'Falha ao atualizar comissão'
            showError(errorMsg)
            console.error('Error updating commission:', err)
        }
    }

    const handleChecklistChange = async (field, value) => {
        const updatedChecklist = { ...logisticsChecklist, [field]: value }
        setLogisticsChecklist(updatedChecklist)

        try {
            const response = await api.put(`/kanban/pos/${selectedPO.id}/logistics-checklist`, {
                po_id: selectedPO.id,
                ...updatedChecklist
            })

            if (response.data.can_dispatch) {
                showSuccess('✅ Checklist completo! Pronto para despacho.')
            }
        } catch (err) {
            const errorMsg = err.response?.data?.detail || 'Falha ao atualizar checklist'
            showError(errorMsg)
            console.error('Error updating checklist:', err)
        }
    }

    const handleEvidenceUpload = async (field, file) => {
        if (!file) return

        setUploadingEvidence(true)
        const formData = new FormData()
        formData.append('file', file)
        formData.append('po_id', selectedPO.id)

        try {
            // Upload file
            const uploadResponse = await api.post('/upload', formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            })

            const filePath = uploadResponse.data.file_path

            // Update checklist with file path
            const updatedChecklist = { ...logisticsChecklist, [field]: filePath }
            setLogisticsChecklist(updatedChecklist)

            const response = await api.put(`/kanban/pos/${selectedPO.id}/logistics-checklist`, {
                po_id: selectedPO.id,
                ...updatedChecklist
            })

            showSuccess(`${field === 'foto_carga_path' ? 'Foto da Carga' : 'Foto do Canhoto/NF'} enviada com sucesso`)

            if (response.data.can_dispatch) {
                showSuccess('✅ Todas as evidências enviadas! Pronto para despacho.')
            }
        } catch (err) {
            const errorMsg = err.response?.data?.detail || 'Falha ao enviar evidência'
            showError(errorMsg)
            console.error('Error uploading evidence:', err)
        } finally {
            setUploadingEvidence(false)
        }
    }

    const handleAdvanceStatus = async () => {
        if (!selectedPO) return

        try {
            const response = await api.post('/kanban/advance-status', null, {
                params: { po_id: selectedPO.id }
            })
            showSuccess(response.data.message)
            fetchBoard()
            handleCloseModal()
        } catch (err) {
            const errorMsg = err.response?.data?.detail?.message || err.response?.data?.detail || 'Falha ao avançar status'
            const errors = err.response?.data?.detail?.errors
            if (errors && Array.isArray(errors)) {
                showError(`${errorMsg}: ${errors.join(', ')}`)
            } else {
                showError(errorMsg)
            }
            console.error('Error advancing status:', err)
        }
    }

    const handleReturnStatus = async () => {
        if (!returnReason || returnReason.trim().length < 10) {
            showError('Motivo da devolução deve ter pelo menos 10 caracteres')
            return
        }

        try {
            const response = await api.post('/kanban/return-status', null, {
                params: {
                    po_id: selectedPO.id,
                    reason: returnReason
                }
            })
            showSuccess(response.data.message)
            setShowReturnModal(false)
            setReturnReason('')
            fetchBoard()
            handleCloseModal()
        } catch (err) {
            const errorMsg = err.response?.data?.detail || 'Falha ao devolver status'
            showError(errorMsg)
            console.error('Error returning status:', err)
        }
    }

    const handleSuggestPartition = async () => {
        if (!partitionReason || partitionReason.trim().length < 10) {
            showError('Motivo da sugestão de partição deve ter pelo menos 10 caracteres')
            return
        }

        try {
            const response = await api.post('/kanban/suggest-partition', null, {
                params: {
                    po_id: selectedPO.id,
                    reason: partitionReason
                }
            })
            showSuccess(response.data.message)
            setShowPartitionModal(false)
            setPartitionReason('')
            fetchBoard()
            handleCloseModal()
        } catch (err) {
            const errorMsg = err.response?.data?.detail || 'Falha ao sugerir partição'
            showError(errorMsg)
            console.error('Error suggesting partition:', err)
        }
    }

    const getNextStatus = (currentStatus) => {
        const statusFlow = {
            'Comercial': 'PCP',
            'PCP': 'Produção/Embalagem',
            'Produção/Embalagem': 'Expedição/Faturamento',
            'Expedição/Faturamento': 'Concluído',
            'Aguardando Partição': 'PCP'
        }
        return statusFlow[currentStatus] || null
    }

    const getPreviousStatus = (currentStatus) => {
        const statusFlow = {
            'PCP': 'Comercial',
            'Produção/Embalagem': 'PCP',
            'Expedição/Faturamento': 'Produção/Embalagem',
            'Concluído': 'Expedição/Faturamento'
        }
        return statusFlow[currentStatus] || null
    }

    const canAdvance = (po) => {
        if (!po) return false
        return getNextStatus(po.status) !== null
    }

    const canReturn = (po) => {
        if (!po) return false
        return getPreviousStatus(po.status) !== null
    }

    const canSuggestPartition = (po) => {
        if (!po) return false
        return po.status === 'PCP'
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

    const canEditCommission = () => {
        return user && (user.role === 'MASTER' || user.role === 'ADMIN')
    }

    const isDispatchReady = () => {
        return (
            logisticsChecklist.endereco_conferido &&
            logisticsChecklist.peso_validado &&
            logisticsChecklist.etiquetas_impressas &&
            logisticsChecklist.foto_carga_path &&
            logisticsChecklist.foto_canhoto_path
        )
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
                        <div className="bg-white rounded-lg shadow-xl max-w-5xl w-full max-h-[90vh] overflow-hidden flex flex-col">
                            {/* Modal Header */}
                            <div className="flex items-center justify-between p-6 border-b border-gray-200 bg-gray-50">
                                <div>
                                    <h2 className="text-2xl font-bold text-gray-900">
                                        Pedido #{selectedPO.po_number}
                                    </h2>
                                    <p className="text-sm text-gray-600 mt-1">
                                        {selectedPO.client_name || 'Cliente não especificado'}
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

                                {/* Financial Section - Editable Commission */}
                                <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                                    <div className="flex items-center justify-between mb-3">
                                        <h3 className="text-lg font-semibold text-gray-900">Dados Financeiros</h3>
                                        {canEditCommission() && !editingCommission && (
                                            <button
                                                onClick={() => setEditingCommission(true)}
                                                className="flex items-center gap-2 px-3 py-1 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm"
                                            >
                                                <Edit2 className="w-4 h-4" />
                                                Editar Comissão
                                            </button>
                                        )}
                                    </div>

                                    <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                                        <div>
                                            <span className="text-xs text-gray-600">Margem (CM)</span>
                                            <p className="text-lg font-bold text-gray-900">
                                                {selectedPO.margin_percentage ? `${parseFloat(selectedPO.margin_percentage).toFixed(2)}%` : 'N/A'}
                                            </p>
                                        </div>
                                        <div>
                                            <span className="text-xs text-gray-600">Comissão</span>
                                            {editingCommission ? (
                                                <input
                                                    type="number"
                                                    step="0.01"
                                                    min="0"
                                                    max="100"
                                                    value={commissionValue}
                                                    onChange={(e) => setCommissionValue(e.target.value)}
                                                    placeholder="Taxa %"
                                                    className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
                                                />
                                            ) : (
                                                <p className="text-lg font-bold text-gray-900">
                                                    {selectedPO.commission_rate ? `${parseFloat(selectedPO.commission_rate).toFixed(2)}%` : 'N/A'}
                                                </p>
                                            )}
                                        </div>
                                        <div>
                                            <span className="text-xs text-gray-600">Valor Comissão</span>
                                            <p className="text-lg font-bold text-gray-900">
                                                {formatCurrency(selectedPO.commission_value || 0)}
                                            </p>
                                        </div>
                                    </div>

                                    {editingCommission && (
                                        <div className="mt-4 space-y-3">
                                            <div>
                                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                                    Justificativa (mínimo 10 caracteres)
                                                </label>
                                                <textarea
                                                    value={commissionJustification}
                                                    onChange={(e) => setCommissionJustification(e.target.value)}
                                                    placeholder="Explique o motivo da alteração manual da comissão..."
                                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                                                    rows="3"
                                                />
                                            </div>
                                            <div className="flex gap-2">
                                                <button
                                                    onClick={handleSaveCommission}
                                                    className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-sm"
                                                >
                                                    <Save className="w-4 h-4" />
                                                    Salvar
                                                </button>
                                                <button
                                                    onClick={() => {
                                                        setEditingCommission(false)
                                                        setCommissionValue('')
                                                        setCommissionJustification('')
                                                    }}
                                                    className="flex items-center gap-2 px-4 py-2 bg-gray-300 text-gray-700 rounded-lg hover:bg-gray-400 transition-colors text-sm"
                                                >
                                                    <XCircle className="w-4 h-4" />
                                                    Cancelar
                                                </button>
                                            </div>
                                        </div>
                                    )}
                                </div>

                                {/* Logistics Checklist - Only for Expedição/Faturamento */}
                                {selectedPO.status === 'Expedição/Faturamento' && (
                                    <div className="mb-6 p-4 bg-cyan-50 border border-cyan-200 rounded-lg">
                                        <div className="flex items-center gap-2 mb-4">
                                            <Truck className="w-5 h-5 text-cyan-700" />
                                            <h3 className="text-lg font-semibold text-gray-900">Checklist de Saída</h3>
                                        </div>

                                        <div className="space-y-3 mb-4">
                                            <label className="flex items-center gap-3 cursor-pointer">
                                                <input
                                                    type="checkbox"
                                                    checked={logisticsChecklist.endereco_conferido}
                                                    onChange={(e) => handleChecklistChange('endereco_conferido', e.target.checked)}
                                                    className="w-5 h-5 text-cyan-600 rounded focus:ring-cyan-500"
                                                />
                                                <span className="text-gray-700 font-medium">Endereço Conferido</span>
                                                {logisticsChecklist.endereco_conferido && (
                                                    <CheckCircle className="w-5 h-5 text-green-600" />
                                                )}
                                            </label>

                                            <label className="flex items-center gap-3 cursor-pointer">
                                                <input
                                                    type="checkbox"
                                                    checked={logisticsChecklist.peso_validado}
                                                    onChange={(e) => handleChecklistChange('peso_validado', e.target.checked)}
                                                    className="w-5 h-5 text-cyan-600 rounded focus:ring-cyan-500"
                                                />
                                                <span className="text-gray-700 font-medium">Peso Validado</span>
                                                {logisticsChecklist.peso_validado && (
                                                    <CheckCircle className="w-5 h-5 text-green-600" />
                                                )}
                                            </label>

                                            <label className="flex items-center gap-3 cursor-pointer">
                                                <input
                                                    type="checkbox"
                                                    checked={logisticsChecklist.etiquetas_impressas}
                                                    onChange={(e) => handleChecklistChange('etiquetas_impressas', e.target.checked)}
                                                    className="w-5 h-5 text-cyan-600 rounded focus:ring-cyan-500"
                                                />
                                                <span className="text-gray-700 font-medium">Etiquetas Impressas</span>
                                                {logisticsChecklist.etiquetas_impressas && (
                                                    <CheckCircle className="w-5 h-5 text-green-600" />
                                                )}
                                            </label>
                                        </div>

                                        <div className="border-t border-cyan-200 pt-4 mt-4">
                                            <h4 className="text-md font-semibold text-gray-900 mb-3">Evidências Fotográficas</h4>

                                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                                {/* Foto da Carga */}
                                                <div className="border-2 border-dashed border-gray-300 rounded-lg p-4">
                                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                                        Foto da Carga
                                                    </label>
                                                    {logisticsChecklist.foto_carga_path ? (
                                                        <div className="flex items-center gap-2 text-green-600">
                                                            <CheckCircle className="w-5 h-5" />
                                                            <span className="text-sm">Enviada</span>
                                                        </div>
                                                    ) : (
                                                        <div>
                                                            <input
                                                                type="file"
                                                                accept="image/*"
                                                                onChange={(e) => handleEvidenceUpload('foto_carga_path', e.target.files[0])}
                                                                className="hidden"
                                                                id="foto-carga-upload"
                                                                disabled={uploadingEvidence}
                                                            />
                                                            <label
                                                                htmlFor="foto-carga-upload"
                                                                className="flex items-center justify-center gap-2 px-4 py-2 bg-cyan-600 text-white rounded-lg hover:bg-cyan-700 cursor-pointer transition-colors"
                                                            >
                                                                <Upload className="w-4 h-4" />
                                                                {uploadingEvidence ? 'Enviando...' : 'Enviar Foto'}
                                                            </label>
                                                        </div>
                                                    )}
                                                </div>

                                                {/* Foto do Canhoto/NF */}
                                                <div className="border-2 border-dashed border-gray-300 rounded-lg p-4">
                                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                                        Foto do Canhoto/NF
                                                    </label>
                                                    {logisticsChecklist.foto_canhoto_path ? (
                                                        <div className="flex items-center gap-2 text-green-600">
                                                            <CheckCircle className="w-5 h-5" />
                                                            <span className="text-sm">Enviada</span>
                                                        </div>
                                                    ) : (
                                                        <div>
                                                            <input
                                                                type="file"
                                                                accept="image/*"
                                                                onChange={(e) => handleEvidenceUpload('foto_canhoto_path', e.target.files[0])}
                                                                className="hidden"
                                                                id="foto-canhoto-upload"
                                                                disabled={uploadingEvidence}
                                                            />
                                                            <label
                                                                htmlFor="foto-canhoto-upload"
                                                                className="flex items-center justify-center gap-2 px-4 py-2 bg-cyan-600 text-white rounded-lg hover:bg-cyan-700 cursor-pointer transition-colors"
                                                            >
                                                                <Upload className="w-4 h-4" />
                                                                {uploadingEvidence ? 'Enviando...' : 'Enviar Foto'}
                                                            </label>
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        </div>

                                        {/* Dispatch Button */}
                                        <div className="mt-4 pt-4 border-t border-cyan-200">
                                            <button
                                                disabled={!isDispatchReady()}
                                                className={`w-full flex items-center justify-center gap-2 px-6 py-3 rounded-lg font-semibold transition-colors ${isDispatchReady()
                                                    ? 'bg-green-600 text-white hover:bg-green-700'
                                                    : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                                                    }`}
                                            >
                                                <Truck className="w-5 h-5" />
                                                {isDispatchReady() ? 'Concluir Despacho' : 'Complete o Checklist e Evidências'}
                                            </button>
                                        </div>
                                    </div>
                                )}

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
                            <div className="flex items-center justify-between gap-3 p-6 border-t border-gray-200 bg-gray-50">
                                <div className="flex items-center gap-3">
                                    {/* Return Button - visible for PCP and subsequent stages */}
                                    {canReturn(selectedPO) && (
                                        <button
                                            onClick={() => setShowReturnModal(true)}
                                            className="flex items-center gap-2 px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 transition-colors"
                                        >
                                            <RefreshCw className="w-4 h-4" />
                                            Devolver para {getPreviousStatus(selectedPO.status)}
                                        </button>
                                    )}

                                    {/* PCP Partition Suggestion Button */}
                                    {canSuggestPartition(selectedPO) && (
                                        <button
                                            onClick={() => setShowPartitionModal(true)}
                                            className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
                                        >
                                            <Package className="w-4 h-4" />
                                            Sugerir Partição
                                        </button>
                                    )}
                                </div>

                                <div className="flex items-center gap-3">
                                    {/* Advance Button - enabled only if mandatory fields are filled */}
                                    {canAdvance(selectedPO) && (
                                        <button
                                            onClick={handleAdvanceStatus}
                                            className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                                        >
                                            Avançar para {getNextStatus(selectedPO.status)}
                                            <Zap className="w-4 h-4" />
                                        </button>
                                    )}

                                    <button
                                        onClick={handleCloseModal}
                                        className="btn-secondary"
                                    >
                                        Fechar
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {/* Return Status Modal */}
                {showReturnModal && (
                    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
                        <div className="bg-white rounded-lg shadow-xl max-w-md w-full">
                            <div className="p-6">
                                <h3 className="text-xl font-bold text-gray-900 mb-4">
                                    Devolver para {getPreviousStatus(selectedPO?.status)}
                                </h3>
                                <p className="text-sm text-gray-600 mb-4">
                                    Informe o motivo da devolução (mínimo 10 caracteres):
                                </p>
                                <textarea
                                    value={returnReason}
                                    onChange={(e) => setReturnReason(e.target.value)}
                                    placeholder="Ex: Falta informação de prazo de entrega..."
                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                                    rows="4"
                                />
                                <div className="flex items-center justify-end gap-3 mt-6">
                                    <button
                                        onClick={() => {
                                            setShowReturnModal(false)
                                            setReturnReason('')
                                        }}
                                        className="px-4 py-2 bg-gray-300 text-gray-700 rounded-lg hover:bg-gray-400 transition-colors"
                                    >
                                        Cancelar
                                    </button>
                                    <button
                                        onClick={handleReturnStatus}
                                        disabled={!returnReason || returnReason.trim().length < 10}
                                        className={`px-4 py-2 rounded-lg transition-colors ${returnReason && returnReason.trim().length >= 10
                                                ? 'bg-orange-600 text-white hover:bg-orange-700'
                                                : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                                            }`}
                                    >
                                        Devolver
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {/* Partition Suggestion Modal */}
                {showPartitionModal && (
                    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
                        <div className="bg-white rounded-lg shadow-xl max-w-md w-full">
                            <div className="p-6">
                                <h3 className="text-xl font-bold text-gray-900 mb-4">
                                    Sugerir Partição do Pedido
                                </h3>
                                <p className="text-sm text-gray-600 mb-4">
                                    Informe o motivo da sugestão de partição (mínimo 10 caracteres):
                                </p>
                                <textarea
                                    value={partitionReason}
                                    onChange={(e) => setPartitionReason(e.target.value)}
                                    placeholder="Ex: Pedido muito grande, sugerir divisão em 2 entregas..."
                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                                    rows="4"
                                />
                                <div className="flex items-center justify-end gap-3 mt-6">
                                    <button
                                        onClick={() => {
                                            setShowPartitionModal(false)
                                            setPartitionReason('')
                                        }}
                                        className="px-4 py-2 bg-gray-300 text-gray-700 rounded-lg hover:bg-gray-400 transition-colors"
                                    >
                                        Cancelar
                                    </button>
                                    <button
                                        onClick={handleSuggestPartition}
                                        disabled={!partitionReason || partitionReason.trim().length < 10}
                                        className={`px-4 py-2 rounded-lg transition-colors ${partitionReason && partitionReason.trim().length >= 10
                                                ? 'bg-purple-600 text-white hover:bg-purple-700'
                                                : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                                            }`}
                                    >
                                        Sugerir Partição
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </ErrorBoundary>
    )
}

export default KanbanPage
