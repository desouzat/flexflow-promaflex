import React, { useState, useEffect } from 'react'
import KanbanColumn from '../components/kanban/KanbanColumn'
import ErrorBoundary from '../components/ErrorBoundary'
import MetadataVisualizer from '../components/MetadataVisualizer'
import { calculatePOMargins } from '../utils/marginCalculator'
import api from '../utils/api'
import { showSuccess, showError } from '../utils/toast'
import { useNotifications } from '../context/NotificationContext'
import { useAuth } from '../context/AuthContext'
import {
    RefreshCw, Filter, Search, Maximize2, Minimize2, X,
    Package, DollarSign, Calendar, User, FileText, Globe,
    Star, RefreshCw as RefreshIcon, Zap, AlertCircle, Upload,
    CheckCircle, Edit2, Save, XCircle, Truck, Lock, Unlock,
    ArrowUpRight, ShieldAlert
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
    const [handoffHistory, setHandoffHistory] = useState(null)
    const [savingFields, setSavingFields] = useState(false)
    const [localFields, setLocalFields] = useState({})
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

    // Add escape key handler for modals
    useEffect(() => {
        const handleEscape = (e) => {
            if (e.key === 'Escape') {
                if (showDetailsModal) {
                    handleCloseModal();
                } else if (showReturnModal) {
                    setShowReturnModal(false);
                    setReturnReason('');
                } else if (showPartitionModal) {
                    setShowPartitionModal(false);
                    setPartitionReason('');
                }
            }
        };

        document.addEventListener('keydown', handleEscape);
        return () => document.removeEventListener('keydown', handleEscape);
    }, [showDetailsModal, showReturnModal, showPartitionModal]);

    useEffect(() => {
        if (selectedPO) {
            setLocalFields(selectedPO.extra_metadata || {})
        } else {
            setLocalFields({})
        }
    }, [selectedPO])

    const handleChangeLocalField = (key, value) => {
        setLocalFields(prev => ({ ...prev, [key]: value }))
    }

    const handleBlurLocalField = (key) => {
        if (!selectedPO) return
        const originalValue = selectedPO.extra_metadata?.[key] || ''
        const currentValue = localFields[key] || ''
        if (String(originalValue) !== String(currentValue)) {
            handleSaveAreaFields({ [key]: currentValue })
        }
    }

    const handleSelectField = (key, value) => {
        setLocalFields(prev => ({ ...prev, [key]: value }))
        handleSaveAreaFields({ [key]: value })
    }

    const handleCardClick = async (po) => {
        setSelectedPO(po)
        setShowDetailsModal(true)
        setHandoffHistory(null)

        // Load handoff history & SLA data
        try {
            const response = await api.get(`/kanban/pos/${po.id}/handoff-history`)
            setHandoffHistory(response.data)
        } catch (err) {
            console.error('Error loading handoff history:', err)
        }

        // Load logistics checklist if in Expedição/Faturamento or Faturamento/Expedição
        if (po.status === 'Expedição/Faturamento' || po.status === 'Faturamento/Expedição') {
            try {
                const response = await api.get(`/kanban/pos/${po.id}/logistics-checklist`)
                setLogisticsChecklist(response.data.checklist)
            } catch (err) {
                console.error('Error loading logistics checklist:', err)
            }
        }
    }

    const handleSaveAreaFields = async (fieldsToUpdate) => {
        if (!selectedPO) return
        setSavingFields(true)
        try {
            const response = await api.put(`/kanban/pos/${selectedPO.id}/area-fields`, fieldsToUpdate)
            if (response.data.success) {
                // Update selectedPO in local state
                setSelectedPO(prev => ({
                    ...prev,
                    extra_metadata: {
                        ...(prev.extra_metadata || {}),
                        ...response.data.partition_metadata
                    }
                }))
                // Also update in boardData to reflect changes instantly on the cards
                setBoardData(prev => {
                    if (!prev || !prev.columns) return prev
                    const updatedColumns = prev.columns.map(col => {
                        const updatedPos = col.pos.map(po => {
                            if (po.id === selectedPO.id) {
                                return {
                                    ...po,
                                    extra_metadata: {
                                        ...(po.extra_metadata || {}),
                                        ...response.data.partition_metadata
                                    }
                                }
                            }
                            return po
                        })
                        return { ...col, pos: updatedPos }
                    })
                    return { ...prev, columns: updatedColumns }
                })
            }
        } catch (err) {
            console.error('Error saving area fields:', err)
            showError('Falha ao salvar as alterações do setor.')
        } finally {
            setSavingFields(false)
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
            // FIXED: Send po_id as query parameter with proper encoding
            const response = await api.post(`/kanban/advance-status?po_id=${encodeURIComponent(selectedPO.id)}`)
            showSuccess(response.data.message)
            await fetchBoard() // Refresh board data
            refreshNotifications() // Refresh notifications
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
            // FIXED: Send po_id and reason as query parameters with proper encoding
            const response = await api.post(
                `/kanban/return-status?po_id=${encodeURIComponent(selectedPO.id)}&reason=${encodeURIComponent(returnReason)}`
            )
            showSuccess(response.data.message)
            setShowReturnModal(false)
            setReturnReason('')
            await fetchBoard() // Refresh board data
            refreshNotifications() // Refresh notifications
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
            // FIXED: Send po_id and reason as query parameters with proper encoding
            const response = await api.post(
                `/kanban/suggest-partition?po_id=${encodeURIComponent(selectedPO.id)}&reason=${encodeURIComponent(partitionReason)}`
            )
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
            'Produção/Embalagem': 'Faturamento/Expedição',
            'Faturamento/Expedição': 'Financeiro',
            'Financeiro': null
        }
        return statusFlow[currentStatus] || null
    }

    const getPreviousStatus = (currentStatus) => {
        const statusFlow = {
            'PCP': 'Comercial',
            'Produção/Embalagem': 'PCP',
            'Faturamento/Expedição': 'Produção/Embalagem',
            'Financeiro': 'Faturamento/Expedição'
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
            'Faturamento/Expedição': 'lightblue',
            'Financeiro': 'green'
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

    const canAdvanceCurrentArea = () => {
        if (!selectedPO) return false

        const meta = selectedPO.extra_metadata || {}

        if (selectedPO.status === 'Comercial') {
            return true
        }

        if (selectedPO.status === 'PCP') {
            const packaging = meta.packaging_type || ''
            const deliveryDate = meta.data_programada || selectedPO.expected_delivery_date || ''
            return packaging !== '' && deliveryDate !== ''
        }

        if (selectedPO.status === 'Produção/Embalagem') {
            const statusProd = meta.status_producao || ''
            const qReal = parseFloat(meta.qtd_real_produzida)
            const perda = parseFloat(meta.perda_tecnica)
            
            return (
                (statusProd === 'Finalizado' || statusProd === 'FINISH') &&
                !isNaN(qReal) && qReal > 0 &&
                !isNaN(perda) && perda >= 0
            )
        }

        if (selectedPO.status === 'Faturamento/Expedição') {
            const nfe = meta.numero_nfe || ''
            const accessKey = (meta.chave_acesso || '').replace(/\D/g, '')
            const carrier = meta.transportadora || ''
            
            const checklistDone = 
                logisticsChecklist.endereco_conferido &&
                logisticsChecklist.peso_validado &&
                logisticsChecklist.etiquetas_impressas &&
                logisticsChecklist.foto_carga_path &&
                logisticsChecklist.foto_canhoto_path

            const isKeyValid = accessKey.length === 44

            return nfe !== '' && isKeyValid && carrier !== '' && checklistDone
        }

        if (selectedPO.status === 'Financeiro') {
            const comment = meta.audit_comment || ''
            return comment.trim().length > 0
        }

        return true
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
                    <div
                        className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4"
                        onClick={(e) => {
                            if (e.target === e.currentTarget) {
                                handleCloseModal();
                            }
                        }}
                    >
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

                                {/* SLA and Performance Control Dashboard */}
                                {(() => {
                                    const totalSlaHours = handoffHistory?.total_sla_hours || (selectedPO?.extra_metadata?.is_replacement ? 120 : 240);
                                    const totalElapsedHours = handoffHistory?.total_elapsed_hours || 0;
                                    const currentAreaSlaHours = handoffHistory?.current_area_sla_hours || 48;
                                    const currentAreaElapsedHours = handoffHistory?.current_area_elapsed_hours || 0;
                                    const isReplacement = handoffHistory?.is_replacement || selectedPO?.extra_metadata?.is_replacement || false;

                                    const totalPercent = Math.min((totalElapsedHours / totalSlaHours) * 100, 100);
                                    const areaPercent = Math.min((currentAreaElapsedHours / currentAreaSlaHours) * 100, 100);

                                    const getProgressBarColor = (percent) => {
                                        if (percent < 60) return 'bg-emerald-500';
                                        if (percent < 85) return 'bg-amber-500';
                                        if (percent < 100) return 'bg-orange-500';
                                        return 'bg-rose-500 animate-pulse';
                                    };

                                    return (
                                        <div className="mb-6 bg-slate-900 text-slate-100 p-5 rounded-xl border border-slate-700 shadow-lg">
                                            <div className="flex items-center justify-between mb-4 border-b border-slate-800 pb-2">
                                                <h3 className="text-xs font-bold tracking-wide uppercase text-slate-300 flex items-center gap-2">
                                                    <span>⏱️</span> Controle de SLA e Performance
                                                </h3>
                                                {isReplacement && (
                                                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[9px] font-extrabold bg-cyan-950 text-cyan-400 border border-cyan-800 animate-pulse">
                                                        SLA REDUZIDO (50% - TROCA)
                                                    </span>
                                                )}
                                            </div>
                                            
                                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                                {/* Tempo Total */}
                                                <div>
                                                    <div className="flex justify-between text-xs font-semibold mb-1">
                                                        <span>Tempo Total Acumulado</span>
                                                        <span className="font-mono text-slate-300">
                                                            {totalElapsedHours.toFixed(1)}h / {totalSlaHours.toFixed(0)}h ({totalPercent.toFixed(0)}%)
                                                        </span>
                                                    </div>
                                                    <div className="w-full bg-slate-800 rounded-full h-3 overflow-hidden border border-slate-700">
                                                        <div 
                                                            className={`h-full transition-all duration-500 ${getProgressBarColor(totalPercent)}`} 
                                                            style={{ width: `${totalPercent}%` }}
                                                        />
                                                    </div>
                                                    <p className="text-[10px] text-slate-450 mt-1">
                                                        Prazo total contratual para o fluxo completo do pedido.
                                                    </p>
                                                </div>

                                                {/* Tempo na Área Atual */}
                                                <div>
                                                    <div className="flex justify-between text-xs font-semibold mb-1">
                                                        <span>Tempo na Área Atual ({selectedPO.status})</span>
                                                        <span className="font-mono text-slate-300">
                                                            {currentAreaElapsedHours.toFixed(1)}h / {currentAreaSlaHours.toFixed(0)}h ({areaPercent.toFixed(0)}%)
                                                        </span>
                                                    </div>
                                                    <div className="w-full bg-slate-800 rounded-full h-3 overflow-hidden border border-slate-700">
                                                        <div 
                                                            className={`h-full transition-all duration-500 ${getProgressBarColor(areaPercent)}`} 
                                                            style={{ width: `${areaPercent}%` }}
                                                        />
                                                    </div>
                                                    <p className="text-[10px] text-slate-455 mt-1">
                                                        Tempo decorrido neste setor operacional específico.
                                                    </p>
                                                </div>
                                            </div>
                                        </div>
                                    );
                                })()}

                                {/* Sector Flow Stepper */}
                                <div className="space-y-6 mb-6">
                                    <h3 className="text-lg font-bold text-gray-900 border-b border-gray-150 pb-2 flex items-center gap-2">
                                        <span>⚙️</span> Esteira BPMS de Operações (Setores de Produção)
                                    </h3>
                                    
                                    {(() => {
                                        const stages = ['Comercial', 'PCP', 'Produção/Embalagem', 'Faturamento/Expedição', 'Financeiro'];
                                        const currentStageIndex = stages.indexOf(selectedPO.status);

                                        return stages.map((stageName, idx) => {
                                            const isCompleted = idx < currentStageIndex;
                                            const isActive = idx === currentStageIndex;
                                            const isLocked = idx > currentStageIndex;
                                            
                                            let headerColor = 'bg-gray-50 border-gray-200 text-gray-500';
                                            let leftBorder = 'border-l-4 border-l-gray-300';
                                            let iconBadge = <Lock className="w-4 h-4 text-gray-400" />;
                                            let statusLabel = 'Aguardando';
                                            
                                            if (isCompleted) {
                                                headerColor = 'bg-emerald-50 bg-opacity-30 border-emerald-150';
                                                leftBorder = 'border-l-4 border-l-emerald-500';
                                                iconBadge = <CheckCircle className="w-5 h-5 text-emerald-500" />;
                                                statusLabel = 'Concluído';
                                            } else if (isActive) {
                                                headerColor = 'bg-blue-50 bg-opacity-40 border-blue-200 shadow-sm';
                                                leftBorder = 'border-l-4 border-l-blue-500 ring-1 ring-blue-100 rounded-r-lg';
                                                iconBadge = <Unlock className="w-4 h-4 text-blue-600 animate-pulse" />;
                                                statusLabel = 'Em Foco';
                                            }
                                            
                                            const displayNames = {
                                                'Comercial': '1. Mesa Comercial',
                                                'PCP': '2. Planejamento e Controle de Produção (PCP)',
                                                'Produção/Embalagem': '3. Execução Industrial & Embalagem',
                                                'Faturamento/Expedição': '4. Faturamento, Logística & Expedição',
                                                'Financeiro': '5. Auditoria & Liberação Financeira'
                                            };

                                            return (
                                                <div 
                                                    key={stageName}
                                                    className={`border rounded-lg overflow-hidden transition-all duration-300 ${headerColor} ${leftBorder}`}
                                                >
                                                    {/* Stage Header */}
                                                    <div className="px-5 py-3.5 flex items-center justify-between border-b border-gray-150">
                                                        <div className="flex items-center gap-3">
                                                            {iconBadge}
                                                            <div>
                                                                <h4 className="font-bold text-gray-900 text-sm md:text-base">
                                                                    {displayNames[stageName] || stageName}
                                                                </h4>
                                                            </div>
                                                        </div>
                                                        <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${
                                                            isCompleted ? 'bg-emerald-100 text-emerald-800' :
                                                            isActive ? 'bg-blue-100 text-blue-800 animate-pulse' :
                                                            'bg-gray-100 text-gray-400'
                                                        }`}>
                                                            {statusLabel}
                                                        </span>
                                                    </div>

                                                    {/* Stage Body */}
                                                    <div className="p-5 bg-white">
                                                        {isLocked ? (
                                                            <div className="flex items-center gap-2 text-gray-400 text-sm italic py-1">
                                                                <Lock className="w-4 h-4" />
                                                                Este setor está bloqueado. Conclua as etapas anteriores na esteira para liberar.
                                                            </div>
                                                        ) : (
                                                            <div>
                                                                {/* Render Stage Specific Content */}
                                                                {stageName === 'Comercial' && (
                                                                    <div className="space-y-4">
                                                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                                                                            <div>
                                                                                <span className="text-xs text-gray-500 font-semibold uppercase block">Cliente</span>
                                                                                <span className="font-bold text-gray-800">{selectedPO.client_name || 'Não Informado'}</span>
                                                                            </div>
                                                                            <div>
                                                                                <span className="text-xs text-gray-500 font-semibold uppercase block">Fornecedor</span>
                                                                                <span className="font-semibold text-gray-800">{selectedPO.supplier_name || 'Desconhecido'}</span>
                                                                            </div>
                                                                            <div>
                                                                                <span className="text-xs text-gray-500 font-semibold uppercase block">Condição de Pagamento</span>
                                                                                <span className="font-medium text-gray-700">{selectedPO.payment_terms || selectedPO.extra_metadata?.payment_terms || 'À vista'}</span>
                                                                            </div>
                                                                            <div>
                                                                                <span className="text-xs text-gray-500 font-semibold uppercase block">Data Limite de Entrega</span>
                                                                                <span className="font-medium text-gray-700">{formatDate(selectedPO.expected_delivery_date)}</span>
                                                                            </div>
                                                                        </div>
                                                                        
                                                                        <div>
                                                                            <span className="text-xs text-gray-500 font-semibold uppercase block mb-1.5">Regras e Indicadores Estratégicos</span>
                                                                            <div className="flex flex-wrap gap-2">
                                                                                {selectedPO.extra_metadata?.is_export && (
                                                                                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-sky-100 text-sky-800 border border-sky-200">
                                                                                        🌐 Exportação
                                                                                    </span>
                                                                                )}
                                                                                {selectedPO.extra_metadata?.is_first_order && (
                                                                                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-200">
                                                                                        ⭐ Primeiro Pedido
                                                                                    </span>
                                                                                )}
                                                                                {selectedPO.extra_metadata?.is_replacement && (
                                                                                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-extrabold bg-cyan-100 text-cyan-800 border border-cyan-300">
                                                                                        🔄 CRÉDITO PRÉ-APROVADO (TROCA)
                                                                                    </span>
                                                                                )}
                                                                                {selectedPO.extra_metadata?.is_urgent && (
                                                                                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-100 text-rose-800 border border-rose-200">
                                                                                        ⚡ Urgente
                                                                                    </span>
                                                                                )}
                                                                                {!selectedPO.extra_metadata?.is_export && 
                                                                                 !selectedPO.extra_metadata?.is_first_order && 
                                                                                 !selectedPO.extra_metadata?.is_replacement && 
                                                                                 !selectedPO.extra_metadata?.is_urgent && (
                                                                                    <span className="text-xs text-gray-500 italic">Nenhum indicador especial registrado.</span>
                                                                                )}
                                                                            </div>
                                                                        </div>

                                                                        {(() => {
                                                                            const marginInfo = calculatePOMargins(selectedPO);
                                                                            return (
                                                                                <div className="bg-slate-50 border border-gray-200 rounded-lg p-4 mt-2">
                                                                                    <div className="flex justify-between items-center">
                                                                                        <div>
                                                                                            <span className="text-xs text-gray-500 font-semibold uppercase block">Margem de Contribuição Estimada</span>
                                                                                            <div className="mt-1 flex items-center gap-2">
                                                                                                {marginInfo.status === 'PENDENTE_PCP' ? (
                                                                                                    <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-extrabold bg-amber-100 text-amber-800 border border-amber-300 cursor-help" title="Custo ainda não validado pelo PCP">
                                                                                                        PENDENTE PCP
                                                                                                    </span>
                                                                                                ) : (
                                                                                                    <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-extrabold border ${
                                                                                                        marginInfo.badgeColor === 'green' ? 'bg-green-100 text-green-800 border-green-300' :
                                                                                                        marginInfo.badgeColor === 'yellow' ? 'bg-yellow-100 text-yellow-800 border-yellow-300' :
                                                                                                        marginInfo.badgeColor === 'orange' ? 'bg-orange-100 text-orange-800 border-orange-300' :
                                                                                                        'bg-red-100 text-red-800 border-red-300'
                                                                                                    }`}>
                                                                                                        {marginInfo.formattedMargin}
                                                                                                    </span>
                                                                                                )}
                                                                                            </div>
                                                                                        </div>
                                                                                        {marginInfo.status !== 'PENDENTE_PCP' && (
                                                                                            <div className="text-right text-xs text-gray-500 font-mono">
                                                                                                <div>VP: {formatCurrency(marginInfo.breakdown.vp)}</div>
                                                                                                <div>Custos: {formatCurrency(marginInfo.breakdown.costs)}</div>
                                                                                            </div>
                                                                                        )}
                                                                                    </div>
                                                                                    {marginInfo.status === 'PENDENTE_PCP' && (
                                                                                        <div className="mt-2.5 p-3 bg-amber-50 border border-amber-250 rounded-lg text-amber-900 text-xs flex items-start gap-2 leading-relaxed shadow-3xs">
                                                                                            <span className="text-amber-500 font-bold flex-shrink-0 text-sm">💡</span>
                                                                                            <span>
                                                                                                <strong>PENDENTE PCP:</strong> Indica que o custo industrial do SKU ainda não foi validado pelo PCP; a margem será calculada após o vínculo técnico.
                                                                                            </span>
                                                                                        </div>
                                                                                    )}
                                                                                </div>
                                                                            );
                                                                        })()}
                                                                    </div>
                                                                )}

                                                                {stageName === 'PCP' && (
                                                                    <div className="space-y-4">
                                                                        {!isActive ? (
                                                                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                                                                                <div>
                                                                                    <span className="text-xs text-gray-500 font-semibold uppercase block">Embalagem</span>
                                                                                    <span className="font-semibold text-gray-800">{selectedPO.extra_metadata?.packaging_type || 'Não selecionado'}</span>
                                                                                </div>
                                                                                <div>
                                                                                    <span className="text-xs text-gray-500 font-semibold uppercase block">Data Programada</span>
                                                                                    <span className="font-semibold text-gray-800">{selectedPO.extra_metadata?.data_programada ? new Date(selectedPO.extra_metadata.data_programada + 'T00:00:00').toLocaleDateString('pt-BR') : 'Não agendada'}</span>
                                                                                </div>
                                                                                <div>
                                                                                    <span className="text-xs text-gray-500 font-semibold uppercase block">Impedimento de Produção</span>
                                                                                    <span className="font-medium text-gray-700">{selectedPO.extra_metadata?.production_impediment || 'Nenhum impedimento'}</span>
                                                                                </div>
                                                                            </div>
                                                                        ) : (
                                                                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                                                                <div>
                                                                                    <label className="block text-xs font-bold text-gray-700 uppercase mb-1">
                                                                                        Tipo de Embalagem <span className="text-red-500">*</span>
                                                                                    </label>
                                                                                    <select
                                                                                        value={localFields.packaging_type || ''}
                                                                                        onChange={(e) => handleSelectField('packaging_type', e.target.value)}
                                                                                        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-semibold text-gray-800"
                                                                                    >
                                                                                        <option value="">Selecione...</option>
                                                                                        <option value="Palete">Palete</option>
                                                                                        <option value="Caixa de Papelão">Caixa de Papelão</option>
                                                                                        <option value="Fardo Plástico">Fardo Plástico</option>
                                                                                        <option value="Granel">Granel</option>
                                                                                    </select>
                                                                                </div>

                                                                                <div>
                                                                                    <label className="block text-xs font-bold text-gray-700 uppercase mb-1">
                                                                                        Data Programada <span className="text-red-500">*</span>
                                                                                    </label>
                                                                                    <input
                                                                                        type="date"
                                                                                        value={localFields.data_programada || ''}
                                                                                        onChange={(e) => handleChangeLocalField('data_programada', e.target.value)}
                                                                                        onBlur={() => handleBlurLocalField('data_programada')}
                                                                                        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-800 font-medium"
                                                                                    />
                                                                                </div>

                                                                                <div className="md:col-span-2">
                                                                                    <label className="block text-xs font-bold text-gray-700 uppercase mb-1">
                                                                                        Impedimento de Produção (Opcional)
                                                                                    </label>
                                                                                    <textarea
                                                                                        value={localFields.production_impediment || ''}
                                                                                        onChange={(e) => handleChangeLocalField('production_impediment', e.target.value)}
                                                                                        onBlur={() => handleBlurLocalField('production_impediment')}
                                                                                        placeholder="Descreva gargalos de matéria-prima ou maquinário..."
                                                                                        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-850 font-medium"
                                                                                        rows="2"
                                                                                    />
                                                                                </div>

                                                                                {/* Sugerir Partição Button inside PCP Panel */}
                                                                                <div className="md:col-span-2 mt-2 p-3.5 bg-purple-50 border border-purple-150 rounded-lg flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
                                                                                    <div className="text-xs text-purple-950 font-medium">
                                                                                        <strong>Partição Técnica:</strong> Se houver restrições de maquinário ou entrega, proponha o desmembramento técnico deste PO.
                                                                                    </div>
                                                                                    <button
                                                                                        onClick={() => setShowPartitionModal(true)}
                                                                                        className="flex items-center gap-2 px-3 py-1.5 bg-purple-600 text-white rounded-lg hover:bg-purple-700 cursor-pointer transition-colors text-xs font-semibold flex-shrink-0 shadow-sm"
                                                                                    >
                                                                                        <Package className="w-3.5 h-3.5" />
                                                                                        Sugerir Partição
                                                                                    </button>
                                                                                </div>
                                                                            </div>
                                                                        )}
                                                                    </div>
                                                                )}

                                                                {stageName === 'Produção/Embalagem' && (
                                                                    <div className="space-y-4">
                                                                        {!isActive ? (
                                                                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                                                                                <div>
                                                                                    <span className="text-xs text-gray-500 font-semibold uppercase block">Status de Produção</span>
                                                                                    <span className="font-semibold text-gray-850">{selectedPO.extra_metadata?.status_producao === 'FINISH' || selectedPO.extra_metadata?.status_producao === 'Finalizado' ? 'Finalizado (FINISH)' : 'Em andamento (START)'}</span>
                                                                                </div>
                                                                                <div>
                                                                                    <span className="text-xs text-gray-500 font-semibold uppercase block">Quantidade Real Produzida</span>
                                                                                    <span className="font-semibold text-gray-855">{selectedPO.extra_metadata?.qtd_real_produzida || '0'} SKUs</span>
                                                                                </div>
                                                                                <div>
                                                                                    <span className="text-xs text-gray-500 font-semibold uppercase block">Perda Técnica</span>
                                                                                    <span className="font-semibold text-gray-850">{selectedPO.extra_metadata?.perda_tecnica || '0'} unidades</span>
                                                                                </div>
                                                                            </div>
                                                                        ) : (
                                                                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                                                                <div>
                                                                                    <label className="block text-xs font-bold text-gray-700 uppercase mb-1">
                                                                                        Status da Produção <span className="text-red-500">*</span>
                                                                                    </label>
                                                                                    <select
                                                                                        value={localFields.status_producao || ''}
                                                                                        onChange={(e) => handleSelectField('status_producao', e.target.value)}
                                                                                        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-semibold text-gray-800"
                                                                                    >
                                                                                        <option value="">Selecione...</option>
                                                                                        <option value="START">Em Andamento (START)</option>
                                                                                        <option value="FINISH">Finalizado (FINISH)</option>
                                                                                    </select>
                                                                                </div>

                                                                                <div>
                                                                                    <label className="block text-xs font-bold text-gray-700 uppercase mb-1">
                                                                                        Quantidade Real Produzida <span className="text-red-500">*</span>
                                                                                    </label>
                                                                                    <input
                                                                                        type="number"
                                                                                        step="1"
                                                                                        min="1"
                                                                                        value={localFields.qtd_real_produzida || ''}
                                                                                        onChange={(e) => handleChangeLocalField('qtd_real_produzida', e.target.value)}
                                                                                        onBlur={() => handleBlurLocalField('qtd_real_produzida')}
                                                                                        placeholder="Ex: 500"
                                                                                        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-800 font-medium"
                                                                                    />
                                                                                </div>

                                                                                <div>
                                                                                    <label className="block text-xs font-bold text-gray-700 uppercase mb-1">
                                                                                        Perda Técnica (unidades) <span className="text-red-500">*</span>
                                                                                    </label>
                                                                                    <input
                                                                                        type="number"
                                                                                        step="1"
                                                                                        min="0"
                                                                                        value={localFields.perda_tecnica || ''}
                                                                                        onChange={(e) => handleChangeLocalField('perda_tecnica', e.target.value)}
                                                                                        onBlur={() => handleBlurLocalField('perda_tecnica')}
                                                                                        placeholder="Ex: 12"
                                                                                        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-800 font-medium"
                                                                                    />
                                                                                </div>
                                                                            </div>
                                                                        )}
                                                                    </div>
                                                                )}

                                                                {stageName === 'Faturamento/Expedição' && (
                                                                    <div className="space-y-4">
                                                                        {!isActive ? (
                                                                            <div className="space-y-3 text-sm">
                                                                                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 border-b border-gray-150 pb-3">
                                                                                    <div>
                                                                                        <span className="text-xs text-gray-500 font-semibold uppercase block">Número NF-e</span>
                                                                                        <span className="font-semibold text-gray-800">{selectedPO.extra_metadata?.numero_nfe || 'Não informado'}</span>
                                                                                    </div>
                                                                                    <div>
                                                                                        <span className="text-xs text-gray-500 font-semibold uppercase block">Chave de Acesso</span>
                                                                                        <span className="font-mono text-xs text-gray-800">{selectedPO.extra_metadata?.chave_acesso || 'Não informada'}</span>
                                                                                    </div>
                                                                                    <div>
                                                                                        <span className="text-xs text-gray-500 font-semibold uppercase block">Transportadora</span>
                                                                                        <span className="font-semibold text-gray-800">{selectedPO.extra_metadata?.transportadora || 'Não informada'}</span>
                                                                                    </div>
                                                                                </div>
                                                                                <div className="flex gap-4">
                                                                                    {logisticsChecklist.foto_carga_path && (
                                                                                        <a 
                                                                                            href={`/api/uploads/download?path=${encodeURIComponent(logisticsChecklist.foto_carga_path)}`}
                                                                                            target="_blank" 
                                                                                            rel="noreferrer" 
                                                                                            className="text-xs text-blue-600 hover:text-blue-800 flex items-center gap-1 font-semibold underline"
                                                                                        >
                                                                                            Visualizar Foto da Carga
                                                                                        </a>
                                                                                    )}
                                                                                    {logisticsChecklist.foto_canhoto_path && (
                                                                                        <a 
                                                                                            href={`/api/uploads/download?path=${encodeURIComponent(logisticsChecklist.foto_canhoto_path)}`}
                                                                                            target="_blank" 
                                                                                            rel="noreferrer" 
                                                                                            className="text-xs text-blue-600 hover:text-blue-800 flex items-center gap-1 font-semibold underline"
                                                                                        >
                                                                                            Visualizar Foto do Canhoto/NF
                                                                                        </a>
                                                                                    )}
                                                                                </div>
                                                                            </div>
                                                                        ) : (
                                                                            <div className="space-y-4">
                                                                                {/* Checklist de Saída */}
                                                                                <div className="p-4 bg-cyan-50 border border-cyan-100 rounded-lg">
                                                                                    <h5 className="text-xs font-bold uppercase text-cyan-800 mb-3 tracking-wide flex items-center gap-1.5">
                                                                                        <Truck className="w-4 h-4" /> Checklist Operacional de Saída (Obrigatório)
                                                                                    </h5>
                                                                                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                                                                                        <label className="flex items-center gap-3 cursor-pointer bg-white p-2.5 border border-cyan-200 rounded-lg shadow-2xs hover:border-cyan-300 transition-all select-none">
                                                                                            <input
                                                                                                type="checkbox"
                                                                                                checked={logisticsChecklist.endereco_conferido || false}
                                                                                                onChange={(e) => handleChecklistChange('endereco_conferido', e.target.checked)}
                                                                                                className="w-5 h-5 text-cyan-600 rounded focus:ring-cyan-500 cursor-pointer"
                                                                                            />
                                                                                            <span className="text-xs text-gray-700 font-semibold">Endereço Conferido</span>
                                                                                            {logisticsChecklist.endereco_conferido && (
                                                                                                <CheckCircle className="w-4 h-4 text-green-600 ml-auto flex-shrink-0" />
                                                                                            )}
                                                                                        </label>

                                                                                        <label className="flex items-center gap-3 cursor-pointer bg-white p-2.5 border border-cyan-200 rounded-lg shadow-2xs hover:border-cyan-300 transition-all select-none">
                                                                                            <input
                                                                                                type="checkbox"
                                                                                                checked={logisticsChecklist.peso_validado || false}
                                                                                                onChange={(e) => handleChecklistChange('peso_validado', e.target.checked)}
                                                                                                className="w-5 h-5 text-cyan-600 rounded focus:ring-cyan-500 cursor-pointer"
                                                                                            />
                                                                                            <span className="text-xs text-gray-700 font-semibold">Peso Validado</span>
                                                                                            {logisticsChecklist.peso_validado && (
                                                                                                <CheckCircle className="w-4 h-4 text-green-600 ml-auto flex-shrink-0" />
                                                                                            )}
                                                                                        </label>

                                                                                        <label className="flex items-center gap-3 cursor-pointer bg-white p-2.5 border border-cyan-200 rounded-lg shadow-2xs hover:border-cyan-300 transition-all select-none">
                                                                                            <input
                                                                                                type="checkbox"
                                                                                                checked={logisticsChecklist.etiquetas_impressas || false}
                                                                                                onChange={(e) => handleChecklistChange('etiquetas_impressas', e.target.checked)}
                                                                                                className="w-5 h-5 text-cyan-600 rounded focus:ring-cyan-500 cursor-pointer"
                                                                                            />
                                                                                            <span className="text-xs text-gray-700 font-semibold">Etiquetas Impressas</span>
                                                                                            {logisticsChecklist.etiquetas_impressas && (
                                                                                                <CheckCircle className="w-4 h-4 text-green-600 ml-auto flex-shrink-0" />
                                                                                            )}
                                                                                        </label>
                                                                                    </div>
                                                                                </div>

                                                                                {/* NF, Key and Carrier */}
                                                                                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                                                                    <div>
                                                                                        <label className="block text-xs font-bold text-gray-700 uppercase mb-1">
                                                                                            Número da NF-e <span className="text-red-500">*</span>
                                                                                        </label>
                                                                                        <input
                                                                                            type="text"
                                                                                            value={localFields.numero_nfe || ''}
                                                                                            onChange={(e) => handleChangeLocalField('numero_nfe', e.target.value)}
                                                                                            onBlur={() => handleBlurLocalField('numero_nfe')}
                                                                                            placeholder="Ex: 004123"
                                                                                            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-800 font-medium"
                                                                                        />
                                                                                    </div>

                                                                                    <div>
                                                                                        <label className="block text-xs font-bold text-gray-700 uppercase mb-1">
                                                                                            Chave de Acesso NF-e (44 dígitos) <span className="text-red-500">*</span>
                                                                                        </label>
                                                                                        <div className="relative">
                                                                                            <input
                                                                                                type="text"
                                                                                                maxLength={44}
                                                                                                value={localFields.chave_acesso || ''}
                                                                                                onChange={(e) => handleChangeLocalField('chave_acesso', e.target.value.replace(/\D/g, ''))}
                                                                                                onBlur={() => handleBlurLocalField('chave_acesso')}
                                                                                                placeholder="Digite os 44 números..."
                                                                                                className="w-full pr-10 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-800 font-mono font-medium"
                                                                                            />
                                                                                            <div className="absolute right-3 top-1/2 transform -translate-y-1/2 flex items-center">
                                                                                                {(localFields.chave_acesso || '').replace(/\D/g, '').length === 44 ? (
                                                                                                    <CheckCircle className="w-4 h-4 text-emerald-500" />
                                                                                                ) : (
                                                                                                    <span className="text-[10px] text-gray-400 font-semibold font-mono">
                                                                                                        {(localFields.chave_acesso || '').replace(/\D/g, '').length}/44
                                                                                                    </span>
                                                                                                )}
                                                                                            </div>
                                                                                        </div>
                                                                                    </div>

                                                                                    <div>
                                                                                        <label className="block text-xs font-bold text-gray-700 uppercase mb-1">
                                                                                            Transportadora <span className="text-red-500">*</span>
                                                                                        </label>
                                                                                        <input
                                                                                            type="text"
                                                                                            value={localFields.transportadora || ''}
                                                                                            onChange={(e) => handleChangeLocalField('transportadora', e.target.value)}
                                                                                            onBlur={() => handleBlurLocalField('transportadora')}
                                                                                            placeholder="Ex: Braspress"
                                                                                            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-800 font-medium"
                                                                                        />
                                                                                    </div>
                                                                                </div>

                                                                                {/* File Evidence Uploads */}
                                                                                <div className="border-t border-gray-150 pt-4 mt-2">
                                                                                    <h5 className="text-xs font-bold uppercase text-gray-700 mb-3 tracking-wide">
                                                                                        Upload de Evidências Logísticas (Obrigatório)
                                                                                    </h5>
                                                                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                                                                        {/* Foto da Carga */}
                                                                                        <div className="border-2 border-dashed border-cyan-200 bg-cyan-50/10 rounded-lg p-4 transition-colors">
                                                                                            <label className="block text-xs font-bold text-cyan-900 uppercase mb-2">
                                                                                                Foto da Carga Carregada
                                                                                            </label>
                                                                                            {logisticsChecklist.foto_carga_path ? (
                                                                                                <div className="space-y-2">
                                                                                                    <div className="flex items-center gap-2 text-green-600 font-semibold text-sm">
                                                                                                        <CheckCircle className="w-5 h-5 flex-shrink-0" />
                                                                                                        <span>Evidência da Carga Salva!</span>
                                                                                                    </div>
                                                                                                    <a 
                                                                                                        href={`/api/uploads/download?path=${encodeURIComponent(logisticsChecklist.foto_carga_path)}`}
                                                                                                        target="_blank" 
                                                                                                        rel="noreferrer" 
                                                                                                        className="text-xs text-blue-600 hover:text-blue-800 font-semibold underline block"
                                                                                                    >
                                                                                                        Abrir Foto da Carga
                                                                                                    </a>
                                                                                                    <div className="pt-1">
                                                                                                        <input
                                                                                                            type="file"
                                                                                                            accept="image/*"
                                                                                                            onChange={(e) => handleEvidenceUpload('foto_carga_path', e.target.files[0])}
                                                                                                            className="hidden"
                                                                                                            id="foto-carga-reupload"
                                                                                                            disabled={uploadingEvidence}
                                                                                                        />
                                                                                                        <label
                                                                                                            htmlFor="foto-carga-reupload"
                                                                                                            className="inline-flex items-center gap-1 text-[10px] text-gray-500 bg-gray-100 hover:bg-gray-200 border border-gray-305 rounded px-2 py-0.5 cursor-pointer transition-colors"
                                                                                                        >
                                                                                                            Substituir Arquivo
                                                                                                        </label>
                                                                                                    </div>
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
                                                                                                        className="flex items-center justify-center gap-2 px-4 py-2 bg-cyan-600 text-white rounded-lg hover:bg-cyan-700 cursor-pointer transition-colors text-xs font-semibold shadow-xs"
                                                                                                    >
                                                                                                        <Upload className="w-4 h-4" />
                                                                                                        {uploadingEvidence ? 'Enviando...' : 'Enviar Foto da Carga'}
                                                                                                    </label>
                                                                                                </div>
                                                                                            )}
                                                                                        </div>

                                                                                        {/* Foto do Canhoto/NF */}
                                                                                        <div className="border-2 border-dashed border-cyan-200 bg-cyan-50/10 rounded-lg p-4 transition-colors">
                                                                                            <label className="block text-xs font-bold text-cyan-900 uppercase mb-2">
                                                                                                Canhoto Assinado / Comprovante
                                                                                            </label>
                                                                                            {logisticsChecklist.foto_canhoto_path ? (
                                                                                                <div className="space-y-2">
                                                                                                    <div className="flex items-center gap-2 text-green-600 font-semibold text-sm">
                                                                                                        <CheckCircle className="w-5 h-5 flex-shrink-0" />
                                                                                                        <span>Evidência do Canhoto Salva!</span>
                                                                                                    </div>
                                                                                                    <a 
                                                                                                        href={`/api/uploads/download?path=${encodeURIComponent(logisticsChecklist.foto_canhoto_path)}`}
                                                                                                        target="_blank" 
                                                                                                        rel="noreferrer" 
                                                                                                        className="text-xs text-blue-600 hover:text-blue-800 font-semibold underline block"
                                                                                                    >
                                                                                                        Abrir Foto do Canhoto
                                                                                                    </a>
                                                                                                    <div className="pt-1">
                                                                                                        <input
                                                                                                            type="file"
                                                                                                            accept="image/*"
                                                                                                            onChange={(e) => handleEvidenceUpload('foto_canhoto_path', e.target.files[0])}
                                                                                                            className="hidden"
                                                                                                            id="foto-canhoto-reupload"
                                                                                                            disabled={uploadingEvidence}
                                                                                                        />
                                                                                                        <label
                                                                                                            htmlFor="foto-canhoto-reupload"
                                                                                                            className="inline-flex items-center gap-1 text-[10px] text-gray-500 bg-gray-100 hover:bg-gray-200 border border-gray-305 rounded px-2 py-0.5 cursor-pointer transition-colors"
                                                                                                        >
                                                                                                            Substituir Arquivo
                                                                                                        </label>
                                                                                                    </div>
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
                                                                                                        className="flex items-center justify-center gap-2 px-4 py-2 bg-cyan-600 text-white rounded-lg hover:bg-cyan-700 cursor-pointer transition-colors text-xs font-semibold shadow-xs"
                                                                                                    >
                                                                                                        <Upload className="w-4 h-4" />
                                                                                                        {uploadingEvidence ? 'Enviando...' : 'Enviar Foto do Canhoto'}
                                                                                                    </label>
                                                                                                </div>
                                                                                            )}
                                                                                        </div>
                                                                                    </div>
                                                                                </div>
                                                                            </div>
                                                                        )}
                                                                    </div>
                                                                )}

                                                                {stageName === 'Financeiro' && (
                                                                    <div className="space-y-4">
                                                                        {/* Comissão */}
                                                                        <div className="p-4 bg-slate-50 border border-gray-200 rounded-lg">
                                                                            <div className="flex items-center justify-between mb-3 border-b border-gray-200 pb-2">
                                                                                <h5 className="text-xs font-bold text-gray-700 uppercase tracking-wider">
                                                                                    Taxa de Comissão Comercial
                                                                                </h5>
                                                                                {canEditCommission() && !editingCommission && isActive && (
                                                                                    <button
                                                                                        onClick={() => {
                                                                                            setCommissionValue(selectedPO.commission_rate || '')
                                                                                            setEditingCommission(true)
                                                                                        }}
                                                                                        className="flex items-center gap-1 px-2.5 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded text-xs font-semibold transition-colors cursor-pointer shadow-xs"
                                                                                    >
                                                                                        <Edit2 className="w-3.5 h-3.5" />
                                                                                        Ajustar Taxa Manual
                                                                                    </button>
                                                                                )}
                                                                            </div>

                                                                            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-1">
                                                                                <div>
                                                                                    <span className="text-xs text-gray-500 font-semibold block uppercase">Comissão Cadastrada</span>
                                                                                    <p className="text-lg font-bold text-gray-800">
                                                                                        {selectedPO.commission_rate ? `${parseFloat(selectedPO.commission_rate).toFixed(2)}%` : 'N/A'}
                                                                                    </p>
                                                                                </div>
                                                                                <div>
                                                                                    <span className="text-xs text-gray-500 font-semibold block uppercase">Valor Bruto Comissão</span>
                                                                                    <p className="text-lg font-bold text-emerald-700 font-mono">
                                                                                        {formatCurrency(selectedPO.commission_value || 0)}
                                                                                    </p>
                                                                                </div>
                                                                                <div>
                                                                                    <span className="text-xs text-gray-500 font-semibold block uppercase">Margem Operacional CM</span>
                                                                                    <p className="text-lg font-bold text-gray-800">
                                                                                        {(() => {
                                                                                            const marginVal = parseFloat(selectedPO.margin_percentage);
                                                                                            return isNaN(marginVal) ? 'PENDENTE PCP' : (marginVal > 1000 ? '> 1000%' : `${marginVal.toFixed(2)}%`);
                                                                                        })()}
                                                                                    </p>
                                                                                </div>
                                                                            </div>

                                                                            {editingCommission && (
                                                                                <div className="mt-4 p-3 bg-white border border-blue-200 rounded-lg space-y-3 shadow-xs">
                                                                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                                                                        <div>
                                                                                            <label className="block text-xs font-bold text-gray-700 uppercase mb-1">
                                                                                                Nova Alíquota de Comissão (%)
                                                                                            </label>
                                                                                            <input
                                                                                                type="number"
                                                                                                step="0.01"
                                                                                                min="0"
                                                                                                max="100"
                                                                                                value={commissionValue}
                                                                                                onChange={(e) => setCommissionValue(e.target.value)}
                                                                                                placeholder="Taxa em %"
                                                                                                className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm text-gray-800 focus:ring-2 focus:ring-blue-500"
                                                                                            />
                                                                                        </div>
                                                                                        <div>
                                                                                            <label className="block text-xs font-bold text-gray-700 uppercase mb-1">
                                                                                                Justificativa de Ajuste (mín. 10 chars)
                                                                                            </label>
                                                                                            <input
                                                                                                type="text"
                                                                                                value={commissionJustification}
                                                                                                onChange={(e) => setCommissionJustification(e.target.value)}
                                                                                                placeholder="Explique a alteração da taxa..."
                                                                                                className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm text-gray-800 focus:ring-2 focus:ring-blue-500"
                                                                                            />
                                                                                        </div>
                                                                                    </div>
                                                                                    <div className="flex gap-2">
                                                                                        <button
                                                                                            onClick={handleSaveCommission}
                                                                                            className="flex items-center gap-1.5 px-3 py-1.5 bg-green-600 hover:bg-green-700 text-white rounded text-xs font-semibold cursor-pointer"
                                                                                        >
                                                                                            <Save className="w-3.5 h-3.5" />
                                                                                            Gravar Alteração
                                                                                        </button>
                                                                                        <button
                                                                                            onClick={() => {
                                                                                                setEditingCommission(false)
                                                                                                setCommissionValue('')
                                                                                                setCommissionJustification('')
                                                                                            }}
                                                                                            className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-200 hover:bg-gray-350 text-gray-700 rounded text-xs font-semibold cursor-pointer"
                                                                                        >
                                                                                            <XCircle className="w-3.5 h-3.5" />
                                                                                            Cancelar
                                                                                        </button>
                                                                                    </div>
                                                                                </div>
                                                                            )}
                                                                        </div>

                                                                        {/* Comentário de Auditoria Financeira */}
                                                                        <div>
                                                                            <label className="block text-xs font-bold text-gray-700 uppercase mb-1">
                                                                                Comentários e Parecer de Auditoria Financeira <span className="text-red-500">*</span>
                                                                            </label>
                                                                            {!isActive ? (
                                                                                <p className="text-sm text-gray-800 bg-gray-50 p-3 rounded-lg border border-gray-200 font-medium">
                                                                                    {selectedPO.extra_metadata?.audit_comment || 'Nenhum comentário registrado.'}
                                                                                </p>
                                                                            ) : (
                                                                                <textarea
                                                                                    value={localFields.audit_comment || ''}
                                                                                    onChange={(e) => handleChangeLocalField('audit_comment', e.target.value)}
                                                                                    onBlur={() => handleBlurLocalField('audit_comment')}
                                                                                    placeholder="Descreva observações de auditoria, conferência de frete ou margem para liberação..."
                                                                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-850 font-medium"
                                                                                    rows="3"
                                                                                />
                                                                            )}
                                                                        </div>
                                                                    </div>
                                                                )}
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                            );
                                        });
                                    })()}
                                </div>

                                {/* Items List */}
                                {selectedPO.items && selectedPO.items.length > 0 && (
                                    <div className="mb-6">
                                        <h3 className="text-lg font-bold text-gray-900 border-b border-gray-150 pb-2 mb-3 flex items-center gap-2">
                                            <span>📦</span> Itens do Pedido (Itens e Especificações)
                                        </h3>
                                        <div className="space-y-4">
                                            {selectedPO.items.map((item, idx) => (
                                                <div key={item.id || idx} className="border border-gray-200 rounded-lg p-4 bg-white shadow-3xs">
                                                    <div className="flex items-start justify-between mb-3">
                                                        <div>
                                                            <h4 className="font-bold text-gray-900">{item.sku}</h4>
                                                            <p className="text-sm text-gray-600 font-medium">
                                                                Quantidade: {item.quantity} | Preço Unitário: {formatCurrency(item.price_unit || item.price || item.unit_value)}
                                                            </p>
                                                        </div>
                                                        <span className="px-2 py-0.5 bg-blue-50 text-blue-700 text-xs font-semibold rounded-full border border-blue-150 uppercase">
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

                                {/* Chronological Handoff Timeline Table (Task 5) */}
                                <div className="mt-8 border-t border-gray-200 pt-6">
                                    <div className="flex items-center gap-2 mb-4">
                                        <span className="text-xl">⏱️</span>
                                        <h3 className="text-lg font-bold text-gray-900">Histórico de Movimentação (Handoff Timeline)</h3>
                                    </div>
                                    
                                    {!handoffHistory ? (
                                        <div className="flex justify-center items-center py-6 text-gray-500 text-sm gap-2 bg-slate-50 border border-gray-200 rounded-lg">
                                            <RefreshCw className="w-4 h-4 animate-spin text-gray-400" />
                                            Carregando histórico do fluxo...
                                        </div>
                                    ) : (!handoffHistory.handoff_history || handoffHistory.handoff_history.length === 0) ? (
                                        <p className="text-sm text-gray-500 italic py-4 text-center bg-slate-50 border border-gray-200 rounded-lg">Nenhum registro de movimentação disponível para este pedido.</p>
                                    ) : (
                                        <div className="overflow-hidden border border-gray-200 rounded-lg shadow-2xs">
                                            <table className="min-w-full divide-y divide-gray-200 text-sm text-left">
                                                <thead className="bg-slate-50 text-slate-700 font-bold uppercase tracking-wider text-[10px]">
                                                    <tr>
                                                        <th className="px-4 py-3">Área Operacional</th>
                                                        <th className="px-4 py-3">Data de Entrada</th>
                                                        <th className="px-4 py-3">Data de Saída</th>
                                                        <th className="px-4 py-3">Duração</th>
                                                        <th className="px-4 py-3">Responsáveis</th>
                                                    </tr>
                                                </thead>
                                                <tbody className="divide-y divide-gray-100 bg-white text-gray-700 font-medium">
                                                    {handoffHistory.handoff_history.map((record, index) => (
                                                        <tr key={index} className="hover:bg-slate-50 transition-colors">
                                                            <td className="px-4 py-3 font-semibold text-gray-900">
                                                                <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold ${
                                                                    record.area === 'Comercial' ? 'bg-yellow-100 text-yellow-800' :
                                                                    record.area === 'PCP' ? 'bg-blue-100 text-blue-800' :
                                                                    record.area === 'Produção' ? 'bg-purple-100 text-purple-800' :
                                                                    record.area === 'Expedição' ? 'bg-cyan-100 text-cyan-800' :
                                                                    'bg-green-100 text-green-800'
                                                                }`}>
                                                                    {record.area}
                                                                </span>
                                                            </td>
                                                            <td className="px-4 py-3 font-mono text-xs text-gray-650">{record.arrival}</td>
                                                            <td className="px-4 py-3 font-mono text-xs">
                                                                {record.departure === 'Em andamento' ? (
                                                                    <span className="text-blue-600 font-bold flex items-center gap-1">
                                                                        <span className="w-1.5 h-1.5 rounded-full bg-blue-600 animate-ping" />
                                                                        Em andamento
                                                                    </span>
                                                                ) : record.departure}
                                                            </td>
                                                            <td className="px-4 py-3 font-mono text-xs text-gray-900">{record.duration}</td>
                                                            <td className="px-4 py-3 text-xs text-gray-600">{record.user || 'Sistema'}</td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    )}
                                </div>
                            </div>

                            {/* Modal Footer */}
                            <div className="flex items-center justify-between gap-3 p-6 border-t border-gray-200 bg-gray-50">
                                <div className="flex items-center gap-3">
                                    {/* Return Button - visible for PCP and subsequent stages */}
                                    {canReturn(selectedPO) && (
                                        <button
                                            onClick={() => setShowReturnModal(true)}
                                            className="flex items-center gap-2 px-4 py-2 bg-orange-650 text-white rounded-lg hover:bg-orange-700 transition-colors font-semibold text-sm cursor-pointer shadow-sm"
                                        >
                                            <RefreshCw className="w-4 h-4" />
                                            Devolver para {getPreviousStatus(selectedPO.status)}
                                        </button>
                                    )}
                                </div>

                                <div className="flex items-center gap-3">
                                    {/* Advance Button - enabled only if mandatory fields are filled */}
                                    {canAdvance(selectedPO) && (
                                        <button
                                            onClick={handleAdvanceStatus}
                                            disabled={!canAdvanceCurrentArea()}
                                            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-semibold transition-colors shadow-sm text-sm ${
                                                canAdvanceCurrentArea()
                                                    ? 'bg-green-600 text-white hover:bg-green-700 cursor-pointer'
                                                    : 'bg-gray-300 text-gray-500 cursor-not-allowed border border-gray-310'
                                            }`}
                                            title={!canAdvanceCurrentArea() ? "Preencha todos os campos obrigatórios deste setor para avançar" : `Avançar para ${getNextStatus(selectedPO.status)}`}
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
                    <div
                        className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
                        onClick={(e) => {
                            if (e.target === e.currentTarget) {
                                setShowReturnModal(false);
                                setReturnReason('');
                            }
                        }}
                    >
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
                    <div
                        className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
                        onClick={(e) => {
                            if (e.target === e.currentTarget) {
                                setShowPartitionModal(false);
                                setPartitionReason('');
                            }
                        }}
                    >
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
