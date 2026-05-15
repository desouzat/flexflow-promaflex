import React, { useState, useRef } from 'react'
import { Upload, FileSpreadsheet, AlertCircle, CheckCircle, X, HelpCircle, Paperclip, Trash2, Cloud, ChevronLeft, ChevronRight, Globe, RefreshCw, DollarSign } from 'lucide-react'
import api from '../utils/api'
import { showSuccess, showError, showLoading, dismissToast } from '../utils/toast'
import { useNotifications } from '../context/NotificationContext'
import HelpModal from '../components/HelpModal'
import { getHelpForStatus } from '../config/helpConfig'

const ITEMS_PER_PAGE = 10

const ImportPage = () => {
    const [selectedFile, setSelectedFile] = useState(null)
    const [uploading, setUploading] = useState(false)
    const [stagingData, setStagingData] = useState(null) // Can be single PO or multi-PO with po_list
    const [showHelp, setShowHelp] = useState(false)
    const [syncing, setSyncing] = useState(false)
    const [currentPage, setCurrentPage] = useState(1)
    const [selectedPOIndex, setSelectedPOIndex] = useState(0) // For multi-PO navigation
    const [showSummaryModal, setShowSummaryModal] = useState(false)
    const [commitSummary, setCommitSummary] = useState({ valid: 0, errors: 0 })
    const fileInputRef = useRef(null)
    const { refreshNotifications } = useNotifications()

    const handleFileSelect = (e) => {
        const file = e.target.files?.[0]
        if (file) {
            // Validate file type
            const validTypes = [
                'application/vnd.ms-excel',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            ]
            if (!validTypes.includes(file.type) && !file.name.match(/\.(xlsx|xls)$/)) {
                showError('Selecione um arquivo Excel válido (.xlsx ou .xls)')
                return
            }

            // Validate file size (10MB)
            if (file.size > 10 * 1024 * 1024) {
                showError('O arquivo deve ter menos de 10MB')
                return
            }

            setSelectedFile(file)
            setStagingData(null)
            setCurrentPage(1)
        }
    }

    const handleUploadToStaging = async () => {
        if (!selectedFile) {
            showError('Selecione um arquivo primeiro')
            return
        }

        setUploading(true)
        const toastId = showLoading('Processando arquivo...')

        try {
            // Create FormData for file upload
            const formData = new FormData()
            formData.append('file', selectedFile)

            // Default mapping for 19-field ONET structure
            const defaultMapping = {
                mappings: [
                    // Core required fields
                    { column_name: 'Pedido', field_type: 'po_number' },
                    { column_name: 'Cliente', field_type: 'client_name' },
                    { column_name: 'SKU', field_type: 'sku' },
                    { column_name: 'Qtd', field_type: 'quantity' },
                    // Optional ONET fields (19-field structure)
                    { column_name: 'Descrição', field_type: 'description' },
                    { column_name: 'Unidade', field_type: 'unit' },
                    { column_name: 'Largura', field_type: 'width' },
                    { column_name: 'Comprimento', field_type: 'length' },
                    { column_name: 'Lead Time', field_type: 'lead_time' },
                    { column_name: 'Data Entrega', field_type: 'delivery_date' },
                    { column_name: 'Data Faturamento', field_type: 'billing_date' },
                    { column_name: '% ICMS', field_type: 'icms_percent' },
                    { column_name: 'Bloqueio', field_type: 'block_status' },
                    { column_name: 'Saldo', field_type: 'balance' },
                    { column_name: 'Atraso', field_type: 'delay' },
                    { column_name: 'Condição Pagamento', field_type: 'payment_terms' },
                    { column_name: 'Frete', field_type: 'freight' },
                    { column_name: 'Vendedor', field_type: 'salesperson' },
                    { column_name: 'IPI', field_type: 'ipi' }
                ]
            }
            formData.append('mapping_json', JSON.stringify(defaultMapping))

            // Call the backend API
            const response = await api.post('/import/upload', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
            })

            dismissToast(toastId)

            // Handle both single PO and multi-PO responses
            if (response.data.success) {
                // Check if multi-PO (po_list exists and has multiple POs)
                if (response.data.po_list && response.data.po_list.length > 0) {
                    // Multi-PO support
                    const poList = response.data.po_list.map(po => ({
                        po_number: po.po_number,
                        client_name: po.client_name,
                        freight_cost: 0,
                        additional_costs: 0,
                        items: po.items.map((item, index) => ({
                            id: `${po.po_number}-${index + 1}`,
                            sku: item.sku,
                            quantity: item.quantity,
                            price_unit: item.price_unit || 0,
                            is_personalized: false,
                            is_new_client: false,
                            is_export: false,
                            is_replacement: false,
                            customization_notes: '',
                            attachment_path: null,
                            needs_mapping: false
                        }))
                    }))

                    setStagingData({
                        isMultiPO: poList.length > 1,
                        po_list: poList,
                        total_pos: poList.length
                    })
                    setSelectedPOIndex(0)
                    setCurrentPage(1)

                    const totalItems = poList.reduce((sum, po) => sum + po.items.length, 0)
                    if (poList.length > 1) {
                        showSuccess(`Arquivo processado! ${poList.length} POs encontrados com ${totalItems} itens no total.`)
                    } else {
                        showSuccess(`Arquivo processado! ${totalItems} itens carregados.`)
                    }
                } else if (response.data.items) {
                    // Legacy single PO support
                    setStagingData({
                        isMultiPO: false,
                        po_list: [{
                            po_number: response.data.po_number,
                            client_name: response.data.client_name,
                            freight_cost: 0,
                            additional_costs: 0,
                            items: response.data.items.map((item, index) => ({
                                id: index + 1,
                                sku: item.sku,
                                quantity: item.quantity,
                                price_unit: item.price_unit || 0,
                                is_personalized: false,
                                is_new_client: false,
                                is_export: false,
                                is_replacement: false,
                                customization_notes: '',
                                attachment_path: null,
                                needs_mapping: false
                            }))
                        }],
                        total_pos: 1
                    })
                    setSelectedPOIndex(0)
                    setCurrentPage(1)
                    showSuccess(`Arquivo processado! ${response.data.items.length} itens carregados.`)
                } else {
                    throw new Error('Resposta inválida do servidor')
                }
            } else {
                throw new Error('Resposta inválida do servidor')
            }
        } catch (error) {
            dismissToast(toastId)
            console.error('Upload error:', error)
            showError(
                error.response?.data?.detail || 'Falha ao processar arquivo. Tente novamente.'
            )
        } finally {
            setUploading(false)
        }
    }

    const handleTogglePersonalized = (itemId) => {
        setStagingData(prev => {
            if (!prev || !prev.po_list || !Array.isArray(prev.po_list)) return prev

            return {
                ...prev,
                po_list: prev.po_list.map(po => ({
                    ...po,
                    items: Array.isArray(po.items) ? po.items.map(item =>
                        item.id === itemId
                            ? { ...item, is_personalized: !item.is_personalized }
                            : item
                    ) : []
                }))
            }
        })
    }

    const handleToggleNewClient = (itemId) => {
        setStagingData(prev => {
            if (!prev || !prev.po_list || !Array.isArray(prev.po_list)) return prev

            return {
                ...prev,
                po_list: prev.po_list.map(po => ({
                    ...po,
                    items: Array.isArray(po.items) ? po.items.map(item =>
                        item.id === itemId
                            ? { ...item, is_new_client: !item.is_new_client }
                            : item
                    ) : []
                }))
            }
        })
    }

    const handleToggleExport = (itemId) => {
        setStagingData(prev => {
            if (!prev || !prev.po_list || !Array.isArray(prev.po_list)) return prev

            return {
                ...prev,
                po_list: prev.po_list.map(po => ({
                    ...po,
                    items: Array.isArray(po.items) ? po.items.map(item =>
                        item.id === itemId
                            ? { ...item, is_export: !item.is_export }
                            : item
                    ) : []
                }))
            }
        })
    }

    const handleToggleReplacement = (itemId) => {
        setStagingData(prev => {
            if (!prev || !prev.po_list || !Array.isArray(prev.po_list)) return prev

            return {
                ...prev,
                po_list: prev.po_list.map(po => ({
                    ...po,
                    items: Array.isArray(po.items) ? po.items.map(item =>
                        item.id === itemId
                            ? { ...item, is_replacement: !item.is_replacement }
                            : item
                    ) : []
                }))
            }
        })
    }

    const handleNotesChange = (itemId, notes) => {
        setStagingData(prev => {
            if (!prev || !prev.po_list || !Array.isArray(prev.po_list)) return prev

            return {
                ...prev,
                po_list: prev.po_list.map(po => ({
                    ...po,
                    items: Array.isArray(po.items) ? po.items.map(item =>
                        item.id === itemId
                            ? { ...item, customization_notes: notes }
                            : item
                    ) : []
                }))
            }
        })
    }

    const handlePOFieldChange = (field, value) => {
        setStagingData(prev => {
            if (!prev || !prev.po_list || !Array.isArray(prev.po_list)) return prev

            const updatedPoList = [...prev.po_list]
            updatedPoList[selectedPOIndex] = {
                ...updatedPoList[selectedPOIndex],
                [field]: parseFloat(value) || 0
            }

            return {
                ...prev,
                po_list: updatedPoList
            }
        })
    }

    const handleFileUpload = async (itemId, file) => {
        // Validate file
        const validTypes = ['application/pdf', 'image/jpeg', 'image/png']
        if (!validTypes.includes(file.type)) {
            showError('Formato inválido. Use PDF, JPG ou PNG')
            return
        }

        // Validate size (5MB)
        if (file.size > 5 * 1024 * 1024) {
            showError('Arquivo deve ter menos de 5MB')
            return
        }

        const toastId = showLoading('Enviando arquivo...')

        try {
            const formData = new FormData()
            formData.append('file', file)

            const response = await api.post('/import/upload-attachment', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
            })

            dismissToast(toastId)

            if (response.data.success) {
                setStagingData(prev => {
                    if (!prev || !prev.po_list || !Array.isArray(prev.po_list)) return prev

                    return {
                        ...prev,
                        po_list: prev.po_list.map(po => ({
                            ...po,
                            items: Array.isArray(po.items) ? po.items.map(item =>
                                item.id === itemId
                                    ? {
                                        ...item,
                                        attachment_path: response.data.file_path,
                                        attachment_filename: response.data.original_filename
                                    }
                                    : item
                            ) : []
                        }))
                    }
                })
                showSuccess('Arquivo enviado com sucesso!')
            }
        } catch (error) {
            dismissToast(toastId)
            showError(error.response?.data?.detail || 'Erro ao enviar arquivo')
        }
    }

    const handleRemoveAttachment = (itemId) => {
        setStagingData(prev => {
            if (!prev || !prev.po_list || !Array.isArray(prev.po_list)) return prev

            return {
                ...prev,
                po_list: prev.po_list.map(po => ({
                    ...po,
                    items: Array.isArray(po.items) ? po.items.map(item =>
                        item.id === itemId
                            ? { ...item, attachment_path: null, attachment_filename: null }
                            : item
                    ) : []
                }))
            }
        })
    }

    const validateItem = (item) => {
        const errors = []

        // Rule 1: Personalized items require notes
        if (item.is_personalized && (!item.customization_notes || !item.customization_notes.trim())) {
            errors.push('Descrição da customização é obrigatória')
        }

        // Rule 2: Personalized + New Client requires attachment
        if (item.is_personalized && item.is_new_client && !item.attachment_path) {
            errors.push('Anexo é obrigatório para clientes novos')
        }

        return errors
    }

    const hasErrors = () => {
        if (!stagingData || !stagingData.po_list || !Array.isArray(stagingData.po_list)) return false

        // Check all items across all POs
        return stagingData.po_list.some(po =>
            Array.isArray(po.items) && po.items.some(item => validateItem(item).length > 0)
        )
    }

    const calculateSummary = () => {
        if (!stagingData || !stagingData.po_list) return { valid: 0, errors: 0 }

        let validCount = 0
        let errorCount = 0

        stagingData.po_list.forEach(po => {
            if (Array.isArray(po.items)) {
                po.items.forEach(item => {
                    if (validateItem(item).length === 0) {
                        validCount++
                    } else {
                        errorCount++
                    }
                })
            }
        })

        return { valid: validCount, errors: errorCount }
    }

    const handleConfirmPO = async () => {
        const summary = calculateSummary()
        setCommitSummary(summary)
        setShowSummaryModal(true)
    }

    const handleCommitValidOnly = async () => {
        const toastId = showLoading('Criando pedidos válidos...')

        try {
            // Filter only valid items
            const validPOs = stagingData.po_list.map(po => ({
                ...po,
                items: po.items.filter(item => validateItem(item).length === 0)
            })).filter(po => po.items.length > 0)

            // Prepare payload with all 19 fields + metadata
            const payload = {
                pos: validPOs.map(po => ({
                    po_number: po.po_number,
                    client_name: po.client_name,
                    freight_cost: po.freight_cost || 0,
                    additional_costs: po.additional_costs || 0,
                    items: po.items.map(item => ({
                        sku: item.sku,
                        quantity: item.quantity,
                        price_unit: item.price_unit,
                        extra_metadata: {
                            is_personalized: item.is_personalized,
                            is_new_client: item.is_new_client,
                            is_export: item.is_export,
                            is_replacement: item.is_replacement,
                            customization_notes: item.customization_notes,
                            attachment_path: item.attachment_path,
                            attachment_filename: item.attachment_filename,
                            // SLA reduction flag for backend
                            apply_sla_reduction: item.is_replacement
                        }
                    }))
                }))
            }

            // TODO: Call actual backend endpoint when ready
            // const response = await api.post('/import/confirm-staging', payload)

            dismissToast(toastId)
            showSuccess(`${validPOs.length} pedido(s) criado(s) com sucesso!`)
            refreshNotifications()

            // Reset form
            setSelectedFile(null)
            setStagingData(null)
            setCurrentPage(1)
            setShowSummaryModal(false)
            if (fileInputRef.current) {
                fileInputRef.current.value = ''
            }
        } catch (error) {
            dismissToast(toastId)
            showError(error.response?.data?.detail || 'Erro ao criar pedidos')
        }
    }

    const handleSyncS3 = async () => {
        setSyncing(true)
        const toastId = showLoading('Sincronizando com ONET (Nuvem)...')

        try {
            const response = await api.post('/import/sync-s3')

            dismissToast(toastId)

            if (response.data.success) {
                const { files_processed, pos_imported } = response.data

                if (files_processed > 0) {
                    showSuccess(
                        `✅ ${files_processed} arquivo(s) processado(s)! ` +
                        `POs importados: ${pos_imported.join(', ')}`
                    )
                    refreshNotifications()
                } else {
                    showSuccess('✅ Sincronização concluída. Nenhum arquivo novo encontrado.')
                }
            } else {
                showError(response.data.message || 'Falha na sincronização')
            }
        } catch (error) {
            dismissToast(toastId)
            console.error('S3 sync error:', error)

            // Don't block manual upload if S3 fails
            if (error.response?.status === 503) {
                showError('⚠️ Serviço S3 não disponível. Use upload manual abaixo.')
            } else {
                showError('⚠️ Erro ao sincronizar com ONET. Use upload manual abaixo.')
            }
        } finally {
            setSyncing(false)
        }
    }

    const handleDragOver = (e) => {
        e.preventDefault()
        e.stopPropagation()
    }

    const handleDrop = (e) => {
        e.preventDefault()
        e.stopPropagation()

        const file = e.dataTransfer.files?.[0]
        if (file) {
            const syntheticEvent = {
                target: {
                    files: [file]
                }
            }
            handleFileSelect(syntheticEvent)
        }
    }

    // Pagination logic for current PO
    const getPaginatedItems = () => {
        if (!stagingData || !stagingData.po_list || !Array.isArray(stagingData.po_list)) return []
        if (!stagingData.po_list[selectedPOIndex]) return []

        const currentPO = stagingData.po_list[selectedPOIndex]
        if (!currentPO.items || !Array.isArray(currentPO.items)) return []

        const startIndex = (currentPage - 1) * ITEMS_PER_PAGE
        const endIndex = startIndex + ITEMS_PER_PAGE
        return currentPO.items.slice(startIndex, endIndex)
    }

    const getCurrentPO = () => {
        if (!stagingData || !stagingData.po_list || !Array.isArray(stagingData.po_list)) return null
        return stagingData.po_list[selectedPOIndex] || null
    }

    const currentPO = getCurrentPO()
    const totalPages = currentPO && Array.isArray(currentPO.items) ? Math.ceil(currentPO.items.length / ITEMS_PER_PAGE) : 0

    const handlePreviousPage = () => {
        setCurrentPage(prev => Math.max(1, prev - 1))
    }

    const handleNextPage = () => {
        setCurrentPage(prev => Math.min(totalPages, prev + 1))
    }

    const handlePreviousPO = () => {
        setSelectedPOIndex(prev => Math.max(0, prev - 1))
        setCurrentPage(1) // Reset to first page when switching POs
    }

    const handleNextPO = () => {
        if (stagingData && stagingData.po_list && Array.isArray(stagingData.po_list)) {
            setSelectedPOIndex(prev => Math.min(stagingData.po_list.length - 1, prev + 1))
            setCurrentPage(1) // Reset to first page when switching POs
        }
    }

    const helpContent = getHelpForStatus('Staging')

    return (
        <div className="h-full flex flex-col">
            {/* Header */}
            <div className="bg-white border-b border-gray-200 px-6 py-4">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold text-gray-900">Mesa de Conferência</h1>
                        <p className="text-sm text-gray-600 mt-1">
                            Importar e validar pedidos de compra (campos ONET)
                        </p>
                    </div>
                    <div className="flex items-center gap-3">
                        <button
                            onClick={handleSyncS3}
                            disabled={syncing}
                            title="Buscar automaticamente novos arquivos Excel da nuvem ONET e importá-los para o sistema"
                            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {syncing ? (
                                <>
                                    <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                                    <span className="font-medium">Sincronizando...</span>
                                </>
                            ) : (
                                <>
                                    <Cloud className="w-5 h-5" />
                                    <span className="font-medium">Sincronizar com ONET (Nuvem)</span>
                                </>
                            )}
                        </button>
                        <button
                            onClick={() => setShowHelp(true)}
                            className="flex items-center gap-2 px-4 py-2 text-primary-600 hover:bg-primary-50 rounded-lg transition-colors"
                        >
                            <HelpCircle className="w-5 h-5" />
                            <span className="font-medium">Ajuda</span>
                        </button>
                    </div>
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 p-6 overflow-auto">
                <div className="max-w-6xl mx-auto">
                    {/* Upload Area - ALWAYS VISIBLE for manual contingency */}
                    {!stagingData && (
                        <div className="card mb-6">
                            <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                                <p className="text-sm text-blue-800">
                                    <strong>💡 Upload Manual:</strong> Sempre disponível como contingência, mesmo com S3 configurado.
                                </p>
                            </div>
                            <div
                                onDragOver={handleDragOver}
                                onDrop={handleDrop}
                                onClick={() => fileInputRef.current?.click()}
                                className="border-2 border-dashed border-gray-300 rounded-lg p-12 text-center hover:border-primary-500 transition-colors cursor-pointer"
                            >
                                <Upload className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                                <h3 className="text-lg font-semibold text-gray-900 mb-2">
                                    Arraste seu arquivo Excel aqui
                                </h3>
                                <p className="text-sm text-gray-600 mb-4">
                                    ou clique para selecionar (campos ONET)
                                </p>
                                <input
                                    ref={fileInputRef}
                                    type="file"
                                    accept=".xlsx,.xls"
                                    onChange={handleFileSelect}
                                    className="hidden"
                                />
                                {selectedFile ? (
                                    <div className="inline-flex items-center gap-2 px-4 py-2 bg-primary-50 text-primary-700 rounded-lg">
                                        <FileSpreadsheet className="w-5 h-5" />
                                        <span className="font-medium">{selectedFile.name}</span>
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation()
                                                setSelectedFile(null)
                                                if (fileInputRef.current) {
                                                    fileInputRef.current.value = ''
                                                }
                                            }}
                                            className="ml-2 text-primary-600 hover:text-primary-800"
                                        >
                                            <X className="w-4 h-4" />
                                        </button>
                                    </div>
                                ) : (
                                    <button className="btn-primary" onClick={(e) => e.stopPropagation()}>
                                        Selecionar Arquivo
                                    </button>
                                )}
                            </div>

                            {selectedFile && (
                                <div className="mt-4 flex justify-end">
                                    <button
                                        onClick={handleUploadToStaging}
                                        disabled={uploading}
                                        className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                        {uploading ? (
                                            <>
                                                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin mr-2" />
                                                Processando...
                                            </>
                                        ) : (
                                            <>
                                                <Upload className="w-5 h-5 mr-2" />
                                                Processar Arquivo
                                            </>
                                        )}
                                    </button>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Staging Area Grid with Pagination */}
                    {stagingData && currentPO && (
                        <div className="space-y-6">
                            {/* Multi-PO Navigation */}
                            {stagingData.isMultiPO && (
                                <div className="card bg-blue-50 border-blue-200">
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <h3 className="text-lg font-semibold text-blue-900 mb-1">
                                                📦 Múltiplos Pedidos Detectados
                                            </h3>
                                            <p className="text-sm text-blue-700">
                                                {stagingData.total_pos} POs encontrados no arquivo. Navegue entre eles abaixo.
                                            </p>
                                        </div>
                                        <div className="flex items-center gap-3">
                                            <button
                                                onClick={handlePreviousPO}
                                                disabled={selectedPOIndex === 0}
                                                className="p-2 border border-blue-300 rounded-lg hover:bg-blue-100 disabled:opacity-50 disabled:cursor-not-allowed"
                                                title="PO Anterior"
                                            >
                                                <ChevronLeft className="w-5 h-5 text-blue-700" />
                                            </button>
                                            <span className="text-sm font-medium text-blue-900">
                                                PO {selectedPOIndex + 1} de {stagingData.total_pos}
                                            </span>
                                            <button
                                                onClick={handleNextPO}
                                                disabled={selectedPOIndex === stagingData.total_pos - 1}
                                                className="p-2 border border-blue-300 rounded-lg hover:bg-blue-100 disabled:opacity-50 disabled:cursor-not-allowed"
                                                title="Próximo PO"
                                            >
                                                <ChevronRight className="w-5 h-5 text-blue-700" />
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            )}

                            {/* PO Header with PO-level fields */}
                            <div className="card">
                                <h3 className="text-lg font-semibold text-gray-900 mb-4">
                                    Informações do Pedido {stagingData.isMultiPO ? `(${selectedPOIndex + 1}/${stagingData.total_pos})` : ''}
                                </h3>
                                <div className="grid grid-cols-2 gap-4 mb-4">
                                    <div>
                                        <label className="text-sm font-medium text-gray-700">Número PO</label>
                                        <p className="text-lg font-semibold text-gray-900">{currentPO.po_number}</p>
                                    </div>
                                    <div>
                                        <label className="text-sm font-medium text-gray-700">Cliente</label>
                                        <p className="text-lg font-semibold text-gray-900">{currentPO.client_name}</p>
                                    </div>
                                </div>

                                {/* PO-Level Cost Fields */}
                                <div className="grid grid-cols-2 gap-4 p-4 bg-green-50 border border-green-200 rounded-lg">
                                    <div>
                                        <label className="block text-sm font-medium text-gray-700 mb-2">
                                            <DollarSign className="w-4 h-4 inline mr-1" />
                                            Frete (R$)
                                        </label>
                                        <input
                                            type="number"
                                            step="0.01"
                                            min="0"
                                            value={currentPO.freight_cost || 0}
                                            onChange={(e) => handlePOFieldChange('freight_cost', e.target.value)}
                                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                                            placeholder="0.00"
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-sm font-medium text-gray-700 mb-2">
                                            <DollarSign className="w-4 h-4 inline mr-1" />
                                            Custos Adicionais (R$)
                                        </label>
                                        <input
                                            type="number"
                                            step="0.01"
                                            min="0"
                                            value={currentPO.additional_costs || 0}
                                            onChange={(e) => handlePOFieldChange('additional_costs', e.target.value)}
                                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                                            placeholder="0.00"
                                        />
                                    </div>
                                </div>
                            </div>

                            {/* Items Grid with Pagination */}
                            <div className="card">
                                <div className="flex items-center justify-between mb-4">
                                    <h3 className="text-lg font-semibold text-gray-900">
                                        Itens do Pedido ({currentPO && Array.isArray(currentPO.items) ? currentPO.items.length : 0} total)
                                    </h3>
                                    {hasErrors() && (
                                        <div className="flex items-center gap-2 text-red-600">
                                            <AlertCircle className="w-5 h-5" />
                                            <span className="text-sm font-medium">Corrija os erros para continuar</span>
                                        </div>
                                    )}
                                </div>

                                {/* Pagination Controls - Top */}
                                {totalPages > 1 && (
                                    <div className="flex items-center justify-between mb-4 p-3 bg-gray-50 rounded-lg">
                                        <span className="text-sm text-gray-600">
                                            Página {currentPage} de {totalPages} ({ITEMS_PER_PAGE} itens por página)
                                        </span>
                                        <div className="flex items-center gap-2">
                                            <button
                                                onClick={handlePreviousPage}
                                                disabled={currentPage === 1}
                                                className="p-2 border border-gray-300 rounded-lg hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                                            >
                                                <ChevronLeft className="w-5 h-5" />
                                            </button>
                                            <button
                                                onClick={handleNextPage}
                                                disabled={currentPage === totalPages}
                                                className="p-2 border border-gray-300 rounded-lg hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                                            >
                                                <ChevronRight className="w-5 h-5" />
                                            </button>
                                        </div>
                                    </div>
                                )}

                                <div className="space-y-4">
                                    {getPaginatedItems().map((item) => {
                                        const errors = validateItem(item)
                                        const hasError = errors.length > 0

                                        return (
                                            <div
                                                key={item.id}
                                                className={`border rounded-lg p-4 ${hasError ? 'border-red-300 bg-red-50' : 'border-gray-200'
                                                    }`}
                                            >
                                                {/* Item Header */}
                                                <div className="grid grid-cols-4 gap-4 mb-4">
                                                    <div>
                                                        <label className="text-xs font-medium text-gray-600">SKU</label>
                                                        <p className="font-semibold text-gray-900">{item.sku}</p>
                                                        {item.needs_mapping && (
                                                            <span className="inline-block mt-1 px-2 py-1 text-xs bg-yellow-100 text-yellow-800 rounded">
                                                                Precisa mapeamento
                                                            </span>
                                                        )}
                                                    </div>
                                                    <div>
                                                        <label className="text-xs font-medium text-gray-600">Quantidade</label>
                                                        <p className="font-semibold text-gray-900">{item.quantity}</p>
                                                    </div>
                                                    <div>
                                                        <label className="text-xs font-medium text-gray-600">Preço Unit.</label>
                                                        <p className="font-semibold text-gray-900">R$ {item.price_unit.toFixed(2)}</p>
                                                    </div>
                                                    <div>
                                                        <label className="text-xs font-medium text-gray-600">Total</label>
                                                        <p className="font-semibold text-gray-900">
                                                            R$ {(item.quantity * item.price_unit).toFixed(2)}
                                                        </p>
                                                    </div>
                                                </div>

                                                {/* Toggles - Now with 4 flags */}
                                                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                                                    <label className="flex items-center gap-3 cursor-pointer">
                                                        <input
                                                            type="checkbox"
                                                            checked={item.is_personalized}
                                                            onChange={() => handleTogglePersonalized(item.id)}
                                                            className="w-5 h-5 text-primary-600 rounded focus:ring-primary-500"
                                                        />
                                                        <span className="text-sm font-medium text-gray-700">
                                                            Personalizado?
                                                        </span>
                                                    </label>
                                                    <label className="flex items-center gap-3 cursor-pointer">
                                                        <input
                                                            type="checkbox"
                                                            checked={item.is_new_client}
                                                            onChange={() => handleToggleNewClient(item.id)}
                                                            className="w-5 h-5 text-primary-600 rounded focus:ring-primary-500"
                                                        />
                                                        <span className="text-sm font-medium text-gray-700">
                                                            Cliente Novo?
                                                        </span>
                                                    </label>
                                                    <label className="flex items-center gap-3 cursor-pointer">
                                                        <input
                                                            type="checkbox"
                                                            checked={item.is_export}
                                                            onChange={() => handleToggleExport(item.id)}
                                                            className="w-5 h-5 text-blue-600 rounded focus:ring-blue-500"
                                                        />
                                                        <span className="text-sm font-medium text-gray-700 flex items-center gap-1">
                                                            <Globe className="w-4 h-4" />
                                                            Exportação?
                                                        </span>
                                                    </label>
                                                    <label className="flex items-center gap-3 cursor-pointer">
                                                        <input
                                                            type="checkbox"
                                                            checked={item.is_replacement}
                                                            onChange={() => handleToggleReplacement(item.id)}
                                                            className="w-5 h-5 text-purple-600 rounded focus:ring-purple-500"
                                                        />
                                                        <span className="text-sm font-medium text-gray-700 flex items-center gap-1">
                                                            <RefreshCw className="w-4 h-4" />
                                                            Troca/Reposição?
                                                        </span>
                                                    </label>
                                                </div>

                                                {/* SLA Reduction Notice */}
                                                {item.is_replacement && (
                                                    <div className="mb-4 p-3 bg-purple-50 border border-purple-200 rounded-lg">
                                                        <p className="text-sm text-purple-800">
                                                            <strong>⚡ SLA Reduzido:</strong> Este item terá o prazo de entrega reduzido em 50% (Troca/Reposição)
                                                        </p>
                                                    </div>
                                                )}

                                                {/* Customization Notes */}
                                                {item.is_personalized && (
                                                    <div className="mb-4">
                                                        <label className="block text-sm font-medium text-gray-700 mb-2">
                                                            Descrição da Customização *
                                                        </label>
                                                        <textarea
                                                            value={item.customization_notes}
                                                            onChange={(e) => handleNotesChange(item.id, e.target.value)}
                                                            placeholder="Descreva as especificações da customização..."
                                                            rows={3}
                                                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                                                        />
                                                    </div>
                                                )}

                                                {/* File Upload - Shows when Cliente Novo is checked */}
                                                {item.is_new_client && (
                                                    <div className="mb-4">
                                                        <label className="block text-sm font-medium text-gray-700 mb-2">
                                                            Anexo (PDF, JPG, PNG - Max 5MB) {item.is_personalized ? '*' : ''}
                                                        </label>
                                                        {item.attachment_path ? (
                                                            <div className="flex items-center gap-2 p-3 bg-green-50 border border-green-200 rounded-lg">
                                                                <Paperclip className="w-5 h-5 text-green-600" />
                                                                <span className="flex-1 text-sm text-green-900">
                                                                    {item.attachment_filename || 'Arquivo anexado'}
                                                                </span>
                                                                <button
                                                                    onClick={() => handleRemoveAttachment(item.id)}
                                                                    className="text-red-600 hover:text-red-800"
                                                                >
                                                                    <Trash2 className="w-4 h-4" />
                                                                </button>
                                                            </div>
                                                        ) : (
                                                            <input
                                                                type="file"
                                                                accept=".pdf,.jpg,.jpeg,.png"
                                                                onChange={(e) => {
                                                                    const file = e.target.files?.[0]
                                                                    if (file) {
                                                                        handleFileUpload(item.id, file)
                                                                    }
                                                                }}
                                                                className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-primary-50 file:text-primary-700 hover:file:bg-primary-100"
                                                            />
                                                        )}
                                                    </div>
                                                )}

                                                {/* Error Messages */}
                                                {hasError && (
                                                    <div className="flex items-start gap-2 p-3 bg-red-100 border border-red-300 rounded-lg">
                                                        <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                                                        <div className="flex-1">
                                                            {errors.map((error, idx) => (
                                                                <p key={idx} className="text-sm text-red-800">
                                                                    {error}
                                                                </p>
                                                            ))}
                                                        </div>
                                                    </div>
                                                )}
                                            </div>
                                        )
                                    })}
                                </div>

                                {/* Pagination Controls - Bottom */}
                                {totalPages > 1 && (
                                    <div className="flex items-center justify-between mt-4 p-3 bg-gray-50 rounded-lg">
                                        <span className="text-sm text-gray-600">
                                            Página {currentPage} de {totalPages}
                                        </span>
                                        <div className="flex items-center gap-2">
                                            <button
                                                onClick={handlePreviousPage}
                                                disabled={currentPage === 1}
                                                className="p-2 border border-gray-300 rounded-lg hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                                            >
                                                <ChevronLeft className="w-5 h-5" />
                                            </button>
                                            <span className="text-sm font-medium text-gray-700">
                                                {currentPage} / {totalPages}
                                            </span>
                                            <button
                                                onClick={handleNextPage}
                                                disabled={currentPage === totalPages}
                                                className="p-2 border border-gray-300 rounded-lg hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                                            >
                                                <ChevronRight className="w-5 h-5" />
                                            </button>
                                        </div>
                                    </div>
                                )}
                            </div>

                            {/* Action Buttons */}
                            <div className="flex justify-between">
                                <button
                                    onClick={() => {
                                        setStagingData(null)
                                        setSelectedFile(null)
                                        setCurrentPage(1)
                                        if (fileInputRef.current) {
                                            fileInputRef.current.value = ''
                                        }
                                    }}
                                    className="px-6 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
                                >
                                    Cancelar
                                </button>
                                <button
                                    onClick={handleConfirmPO}
                                    className="btn-primary"
                                >
                                    <CheckCircle className="w-5 h-5 mr-2" />
                                    Confirmar Pedido
                                </button>
                            </div>
                        </div>
                    )}

                    {/* Instructions */}
                    {!stagingData && (
                        <div className="card">
                            <div className="flex items-start gap-3 mb-4">
                                <FileSpreadsheet className="w-6 h-6 text-primary-600 flex-shrink-0" />
                                <div>
                                    <h3 className="font-semibold text-gray-900 mb-2">
                                        Requisitos do Arquivo (Campos ONET)
                                    </h3>
                                    <ul className="text-sm text-gray-600 space-y-1 list-disc list-inside">
                                        <li>Formato Excel (.xlsx, .xls)</li>
                                        <li>Tamanho máximo: 10MB</li>
                                        <li>Campos obrigatórios: Pedido, Cliente, SKU, Descrição, Qtd, Unidade, Largura, Comprimento, Lead Time, Data Entrega, Data Faturamento, % ICMS, Bloqueio, Saldo, Atraso, Condição Pagamento, Frete, Vendedor, IPI</li>
                                    </ul>
                                </div>
                            </div>

                            <div className="flex items-start gap-3 pt-4 border-t border-gray-200">
                                <AlertCircle className="w-6 h-6 text-yellow-600 flex-shrink-0" />
                                <div>
                                    <h3 className="font-semibold text-gray-900 mb-2">
                                        Regras de Validação
                                    </h3>
                                    <ul className="text-sm text-gray-600 space-y-1 list-disc list-inside">
                                        <li>Anexos são obrigatórios apenas para Clientes Novos em pedidos Personalizados</li>
                                        <li>Descrição da customização é obrigatória para qualquer pedido Personalizado</li>
                                        <li>Limite de arquivo: 5MB (PDF, JPG, PNG)</li>
                                        <li>Paginação automática para mais de 10 itens</li>
                                        <li><strong>Troca/Reposição:</strong> Reduz o SLA em 50% automaticamente</li>
                                    </ul>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* Summary Modal */}
            {showSummaryModal && (
                <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
                    <div className="bg-white rounded-lg shadow-xl max-w-md w-full">
                        <div className="p-6">
                            <h3 className="text-xl font-bold text-gray-900 mb-4">
                                Resumo do Pedido
                            </h3>
                            <div className="space-y-3 mb-6">
                                <div className="flex items-center justify-between p-3 bg-green-50 border border-green-200 rounded-lg">
                                    <span className="text-sm font-medium text-green-900">Itens Válidos</span>
                                    <span className="text-2xl font-bold text-green-600">{commitSummary.valid}</span>
                                </div>
                                {commitSummary.errors > 0 && (
                                    <div className="flex items-center justify-between p-3 bg-red-50 border border-red-200 rounded-lg">
                                        <span className="text-sm font-medium text-red-900">Itens com Erros</span>
                                        <span className="text-2xl font-bold text-red-600">{commitSummary.errors}</span>
                                    </div>
                                )}
                            </div>

                            {commitSummary.errors > 0 ? (
                                <div className="mb-6 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                                    <p className="text-sm text-yellow-800">
                                        <strong>⚠️ Atenção:</strong> Alguns itens possuem erros. Você pode confirmar apenas os itens válidos ou corrigir os erros primeiro.
                                    </p>
                                </div>
                            ) : (
                                <div className="mb-6 p-3 bg-green-50 border border-green-200 rounded-lg">
                                    <p className="text-sm text-green-800">
                                        <strong>✅ Tudo certo!</strong> Todos os itens estão válidos e prontos para serem confirmados.
                                    </p>
                                </div>
                            )}

                            <div className="flex items-center justify-end gap-3">
                                <button
                                    onClick={() => setShowSummaryModal(false)}
                                    className="px-4 py-2 bg-gray-300 text-gray-700 rounded-lg hover:bg-gray-400 transition-colors"
                                >
                                    Voltar e Corrigir
                                </button>
                                {commitSummary.valid > 0 && (
                                    <button
                                        onClick={handleCommitValidOnly}
                                        className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                                    >
                                        Confirmar {commitSummary.errors > 0 ? 'Apenas Válidos' : 'Todos'}
                                    </button>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Help Modal */}
            {showHelp && (
                <HelpModal
                    isOpen={showHelp}
                    onClose={() => setShowHelp(false)}
                    title={helpContent.title}
                    description={helpContent.description}
                    rules={helpContent.rules}
                    nextSteps={helpContent.nextSteps}
                    requiredFields={helpContent.requiredFields}
                />
            )}
        </div>
    )
}

export default ImportPage
