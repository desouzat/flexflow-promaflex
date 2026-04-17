import React, { useState, useRef } from 'react'
import { Upload, FileSpreadsheet, AlertCircle, CheckCircle, X, HelpCircle, Paperclip, Trash2 } from 'lucide-react'
import api from '../utils/api'
import { showSuccess, showError, showLoading, dismissToast } from '../utils/toast'
import { useNotifications } from '../context/NotificationContext'
import HelpModal from '../components/HelpModal'
import { getHelpForStatus } from '../config/helpConfig'

const ImportPage = () => {
    const [selectedFile, setSelectedFile] = useState(null)
    const [uploading, setUploading] = useState(false)
    const [stagingData, setStagingData] = useState(null)
    const [showHelp, setShowHelp] = useState(false)
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
            // For now, simulate staging data extraction
            // In production, this would call an API endpoint to parse the Excel
            // and return the data for staging

            // Simulated staging data
            const mockStagingData = {
                po_number: 'PO-2026-001',
                client_name: 'Cliente Exemplo',
                items: [
                    {
                        id: 1,
                        sku: 'SKU-001',
                        quantity: 100,
                        price_unit: 25.50,
                        is_personalized: false,
                        is_new_client: false,
                        customization_notes: '',
                        attachment_path: null,
                        needs_mapping: false
                    },
                    {
                        id: 2,
                        sku: 'SKU-002',
                        quantity: 50,
                        price_unit: 45.00,
                        is_personalized: false,
                        is_new_client: false,
                        customization_notes: '',
                        attachment_path: null,
                        needs_mapping: true // SKU not found in material_costs
                    }
                ]
            }

            dismissToast(toastId)
            setStagingData(mockStagingData)
            showSuccess('Arquivo processado! Revise os dados abaixo.')
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
        setStagingData(prev => ({
            ...prev,
            items: prev.items.map(item =>
                item.id === itemId
                    ? { ...item, is_personalized: !item.is_personalized }
                    : item
            )
        }))
    }

    const handleToggleNewClient = (itemId) => {
        setStagingData(prev => ({
            ...prev,
            items: prev.items.map(item =>
                item.id === itemId
                    ? { ...item, is_new_client: !item.is_new_client }
                    : item
            )
        }))
    }

    const handleNotesChange = (itemId, notes) => {
        setStagingData(prev => ({
            ...prev,
            items: prev.items.map(item =>
                item.id === itemId
                    ? { ...item, customization_notes: notes }
                    : item
            )
        }))
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
                setStagingData(prev => ({
                    ...prev,
                    items: prev.items.map(item =>
                        item.id === itemId
                            ? {
                                ...item,
                                attachment_path: response.data.file_path,
                                attachment_filename: response.data.original_filename
                            }
                            : item
                    )
                }))
                showSuccess('Arquivo enviado com sucesso!')
            }
        } catch (error) {
            dismissToast(toastId)
            showError(error.response?.data?.detail || 'Erro ao enviar arquivo')
        }
    }

    const handleRemoveAttachment = (itemId) => {
        setStagingData(prev => ({
            ...prev,
            items: prev.items.map(item =>
                item.id === itemId
                    ? { ...item, attachment_path: null, attachment_filename: null }
                    : item
            )
        }))
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
        if (!stagingData) return false
        return stagingData.items.some(item => validateItem(item).length > 0)
    }

    const handleConfirmPO = async () => {
        if (hasErrors()) {
            showError('Corrija todos os erros antes de confirmar')
            return
        }

        const toastId = showLoading('Criando pedido...')

        try {
            // Here you would call the API to create the PO with staging data
            // const response = await api.post('/import/confirm-staging', stagingData)

            dismissToast(toastId)
            showSuccess('Pedido criado com sucesso!')
            refreshNotifications()

            // Reset form
            setSelectedFile(null)
            setStagingData(null)
            if (fileInputRef.current) {
                fileInputRef.current.value = ''
            }
        } catch (error) {
            dismissToast(toastId)
            showError(error.response?.data?.detail || 'Erro ao criar pedido')
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

    const helpContent = getHelpForStatus('Staging')

    return (
        <div className="h-full flex flex-col">
            {/* Header */}
            <div className="bg-white border-b border-gray-200 px-6 py-4">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold text-gray-900">Mesa de Conferência</h1>
                        <p className="text-sm text-gray-600 mt-1">
                            Importar e validar pedidos de compra
                        </p>
                    </div>
                    <button
                        onClick={() => setShowHelp(true)}
                        className="flex items-center gap-2 px-4 py-2 text-primary-600 hover:bg-primary-50 rounded-lg transition-colors"
                    >
                        <HelpCircle className="w-5 h-5" />
                        <span className="font-medium">Ajuda</span>
                    </button>
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 p-6 overflow-auto">
                <div className="max-w-6xl mx-auto">
                    {/* Upload Area */}
                    {!stagingData && (
                        <div className="card mb-6">
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
                                    ou clique para selecionar
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

                    {/* Staging Area Grid */}
                    {stagingData && (
                        <div className="space-y-6">
                            {/* PO Header */}
                            <div className="card">
                                <h3 className="text-lg font-semibold text-gray-900 mb-4">
                                    Informações do Pedido
                                </h3>
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <label className="text-sm font-medium text-gray-700">Número PO</label>
                                        <p className="text-lg font-semibold text-gray-900">{stagingData.po_number}</p>
                                    </div>
                                    <div>
                                        <label className="text-sm font-medium text-gray-700">Cliente</label>
                                        <p className="text-lg font-semibold text-gray-900">{stagingData.client_name}</p>
                                    </div>
                                </div>
                            </div>

                            {/* Items Grid */}
                            <div className="card">
                                <div className="flex items-center justify-between mb-4">
                                    <h3 className="text-lg font-semibold text-gray-900">
                                        Itens do Pedido ({stagingData.items.length})
                                    </h3>
                                    {hasErrors() && (
                                        <div className="flex items-center gap-2 text-red-600">
                                            <AlertCircle className="w-5 h-5" />
                                            <span className="text-sm font-medium">Corrija os erros para continuar</span>
                                        </div>
                                    )}
                                </div>

                                <div className="space-y-4">
                                    {stagingData.items.map((item) => {
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

                                                {/* Toggles */}
                                                <div className="grid grid-cols-2 gap-4 mb-4">
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
                                                </div>

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

                                                {/* File Upload */}
                                                {item.is_personalized && item.is_new_client && (
                                                    <div className="mb-4">
                                                        <label className="block text-sm font-medium text-gray-700 mb-2">
                                                            Anexo (PDF, JPG, PNG - Max 5MB) *
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
                            </div>

                            {/* Action Buttons */}
                            <div className="flex justify-between">
                                <button
                                    onClick={() => {
                                        setStagingData(null)
                                        setSelectedFile(null)
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
                                    disabled={hasErrors()}
                                    className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
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
                                        Requisitos do Arquivo
                                    </h3>
                                    <ul className="text-sm text-gray-600 space-y-1 list-disc list-inside">
                                        <li>Formato Excel (.xlsx, .xls)</li>
                                        <li>Tamanho máximo: 10MB</li>
                                        <li>Colunas obrigatórias: PO Number, Cliente, SKU, Quantidade, Preço</li>
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
                                    </ul>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>

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
