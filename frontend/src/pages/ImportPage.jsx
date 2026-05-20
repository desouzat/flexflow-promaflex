import React, { useState, useRef, useEffect } from 'react'
import { Upload, FileSpreadsheet, AlertCircle, CheckCircle, X, HelpCircle, Paperclip, Trash2, Cloud, ChevronLeft, ChevronRight, Globe, RefreshCw, DollarSign, CheckSquare, Square, Lock, Unlock } from 'lucide-react'
import api from '../utils/api'
import { showSuccess, showError, showLoading, dismissToast } from '../utils/toast'
import { useNotifications } from '../context/NotificationContext'
import { useAuth } from '../context/AuthContext'
import HelpModal from '../components/HelpModal'
import FinanceApprovalModal from '../components/FinanceApprovalModal'
import { getHelpForStatus } from '../config/helpConfig'

const ITEMS_PER_PAGE = 10

// ─── Session Persistence Configuration ───────────────────────────────────────────────────────
// Increment SESSION_SCHEMA_VERSION any time the stagingData shape changes in a breaking way.
// Stored sessions from older versions will be automatically discarded on restore,
// preventing silent data corruption from shape mismatches.
const SESSION_SCHEMA_VERSION = 2

/**
 * Generates a tenant-scoped storage key so two users on the same machine
 * (or the same user across different tenants) never share session data.
 *
 * @param {object|null} user - The current auth user (from useAuth)
 * @returns {string} A unique localStorage key for this user's staging session
 */
const getStorageKey = (user) => {
    if (!user?.tenant_id || !user?.id) return null
    return `flexflow_staging_v${SESSION_SCHEMA_VERSION}_${user.tenant_id}_${user.id}`
}

/**
 * Validate that a restored session object has the expected schema shape.
 * Returns true only if the session is structurally sound and matches the current version.
 *
 * @param {object} parsed - The parsed JSON object from localStorage
 * @returns {boolean}
 */
const isValidSessionSchema = (parsed) => {
    if (!parsed || typeof parsed !== 'object') return false
    if (parsed.schema_version !== SESSION_SCHEMA_VERSION) return false
    if (!parsed.stagingData || typeof parsed.stagingData !== 'object') return false
    // Validate multi-PO structure
    if (!Array.isArray(parsed.stagingData.po_list)) return false
    if (typeof parsed.timestamp !== 'string') return false
    return true
}

// Mock function to send finance notification
const sendFinanceNotification = (poNumber, itemSku) => {
    console.log(`📧 EMAIL SENT TO FINANCE: PO [${poNumber}] - Item [${itemSku}] needs approval`)
    return true
}

// Brazilian currency formatter
const formatCurrency = (value) => {
    if (value === null || value === undefined) return 'N/A'
    const numValue = typeof value === 'string' ? parseFloat(value) : value
    if (isNaN(numValue)) return 'N/A'
    return new Intl.NumberFormat('pt-BR', {
        style: 'currency',
        currency: 'BRL',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(numValue)
}

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
    const [showRestoreModal, setShowRestoreModal] = useState(false)
    const [showFinanceModal, setShowFinanceModal] = useState(false)
    const [selectedFinanceItem, setSelectedFinanceItem] = useState(null)
    const [financeJustification, setFinanceJustification] = useState('')
    const fileInputRef = useRef(null)
    const { refreshNotifications } = useNotifications()
    const { user } = useAuth()

    // ─── Session Save Effect (debounced 300ms) ──────────────────────────────────────────────
    // Saves current staging state to tenant-scoped localStorage after a 300ms debounce.
    // Debouncing prevents excessive writes when the user rapidly changes pages or PO tabs.
    // Falls back gracefully on QuotaExceededError (localStorage full).
    useEffect(() => {
        const storageKey = getStorageKey(user)
        if (!storageKey) return // Can't persist without a valid user identity

        const timer = setTimeout(() => {
            if (stagingData) {
                try {
                    const sessionPayload = JSON.stringify({
                        schema_version: SESSION_SCHEMA_VERSION,
                        stagingData,
                        selectedPOIndex,
                        currentPage,
                        timestamp: new Date().toISOString()
                    })
                    localStorage.setItem(storageKey, sessionPayload)
                    console.log('💾 [Session] Saved (v' + SESSION_SCHEMA_VERSION + ', tenant-scoped):', {
                        key: storageKey.slice(-20) + '...', // Log suffix only, not full key
                        totalPOs: stagingData.po_list?.length || 0,
                        selectedPOIndex,
                        currentPage
                    })
                } catch (error) {
                    if (error instanceof DOMException && error.name === 'QuotaExceededError') {
                        console.warn('⚠️ [Session] localStorage quota exceeded — session not saved. Consider clearing old data.')
                        // Do NOT remove the existing session on quota error — it may be partially valid.
                        // Show a non-blocking warning so user is aware.
                        import('../utils/toast').then(({ showError }) =>
                            showError('Aviso: sessão não salva (armazenamento local cheio). Libere espaço ou faça commit agora.')
                        ).catch(() => {})
                    } else {
                        console.error('❌ [Session] Failed to save session:', error)
                    }
                }
            } else {
                // stagingData cleared — remove the stored session
                try {
                    localStorage.removeItem(storageKey)
                    console.log('🗑️ [Session] Session removed from localStorage')
                } catch (_) { /* ignore removal errors */ }
            }
        }, 300) // 300ms debounce

        return () => clearTimeout(timer)
    }, [stagingData, selectedPOIndex, currentPage, user])

    // ─── Session Restore Effect (on mount) ──────────────────────────────────────────────
    // Checks for a saved session in tenant-scoped localStorage on component mount.
    // Validates schema version and data shape before offering restore.
    // Silently discards sessions that are: expired (>24h), wrong schema version, or corrupt.
    useEffect(() => {
        const storageKey = getStorageKey(user)
        if (!storageKey) return // Wait for user to be available

        console.log('🔍 [Session] Checking for saved session on mount...')
        try {
            const savedSession = localStorage.getItem(storageKey)
            if (!savedSession) {
                console.log('ℹ️ [Session] No saved session found')
                return
            }

            const parsed = JSON.parse(savedSession)

            // Schema version check: discard old/incompatible sessions silently
            if (!isValidSessionSchema(parsed)) {
                console.warn('⚠️ [Session] Session schema mismatch or invalid — discarding automatically')
                localStorage.removeItem(storageKey)
                return
            }

            // Age check: discard sessions older than 24 hours
            const sessionAge = Date.now() - new Date(parsed.timestamp).getTime()
            const MAX_AGE_MS = 24 * 60 * 60 * 1000
            if (sessionAge >= MAX_AGE_MS) {
                console.log('⏳ [Session] Session expired (', Math.floor(sessionAge / 60000), 'min old) — discarding')
                localStorage.removeItem(storageKey)
                return
            }

            console.log('✅ [Session] Valid session found (' + Math.floor(sessionAge / 60000) + ' min old), showing restore modal')
            setShowRestoreModal(true)
        } catch (error) {
            console.error('❌ [Session] Failed to check for saved session:', error)
            try { localStorage.removeItem(getStorageKey(user)) } catch (_) {}
        }
    }, [user]) // Re-check when user changes (login/logout)

    const handleRestoreSession = () => {
        const storageKey = getStorageKey(user)
        if (!storageKey) { setShowRestoreModal(false); return }

        console.log('🔄 [Session] Restoring session...')
        try {
            const savedSession = localStorage.getItem(storageKey)
            if (savedSession) {
                const parsed = JSON.parse(savedSession)

                // Re-validate on restore (session could have been modified externally)
                if (!isValidSessionSchema(parsed)) {
                    console.warn('⚠️ [Session] Session schema invalid on restore — discarding')
                    localStorage.removeItem(storageKey)
                    setShowRestoreModal(false)
                    return
                }

                console.log('📥 [Session] Loaded session data:', {
                    totalPOs: parsed.stagingData?.po_list?.length || 0,
                    selectedPOIndex: parsed.selectedPOIndex,
                    currentPage: parsed.currentPage
                })
                setStagingData(parsed.stagingData)
                setSelectedPOIndex(parsed.selectedPOIndex || 0)
                setCurrentPage(parsed.currentPage || 1)
                console.log('✅ [Session] Session restored successfully')
                showSuccess('Sessão restaurada com sucesso!')
            }
        } catch (error) {
            console.error('❌ [Session] Failed to restore session:', error)
            showError('Erro ao restaurar sessão')
            try { localStorage.removeItem(storageKey) } catch (_) {}
        }
        setShowRestoreModal(false)
    }

    const handleDiscardSession = () => {
        const storageKey = getStorageKey(user)
        console.log('🗑️ [Session] Discarding saved session')
        if (storageKey) {
            try { localStorage.removeItem(storageKey) } catch (_) {}
        }
        setShowRestoreModal(false)
    }

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

            // Default mapping for 22-field ONET structure
            const defaultMapping = {
                mappings: [
                    // Core required fields
                    { column_name: 'Pedido', field_type: 'po_number' },
                    { column_name: 'Cliente', field_type: 'client_name' },
                    { column_name: 'SKU', field_type: 'sku' },
                    { column_name: 'Qtd', field_type: 'quantity' },
                    // Optional ONET fields (22-field structure)
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
                    { column_name: 'IPI', field_type: 'ipi' },
                    // NEW: Financial value fields
                    { column_name: 'Vl.Unit', field_type: 'unit_value' },
                    { column_name: 'Total Item', field_type: 'item_total_value' },
                    { column_name: 'Valor Total do Pedido', field_type: 'po_total_value' }
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
                        po_total_value: po.po_total_value || null,  // PO-level total from ONET
                        has_integrity_error: po.has_integrity_error || false,
                        integrity_error_message: po.integrity_error_message || null,
                        items: po.items.map((item, index) => ({
                            id: `${po.po_number}-${index + 1}`,
                            sku: item.sku,
                            description: item.description || null,
                            quantity: item.quantity,
                            price_unit: item.price_unit || 0,
                            unit_value: item.unit_value || null,  // Vl.Unit from ONET
                            item_total_value: item.item_total_value || null,  // Total Item from ONET
                            // Risk fields from ONET
                            block_status: item.block_status || null,
                            balance: item.balance || null,
                            delay: item.delay || null,
                            payment_terms: item.payment_terms || null,
                            // Metadata flags
                            is_personalized: false,
                            is_new_client: false,
                            is_export: false,
                            is_replacement: false,
                            customization_notes: '',
                            attachment_path: null,
                            needs_mapping: false,
                            is_checked: false  // Human review flag
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
                            po_total_value: response.data.po_total_value || null,
                            has_integrity_error: response.data.has_integrity_error || false,
                            integrity_error_message: response.data.integrity_error_message || null,
                            items: response.data.items.map((item, index) => ({
                                id: index + 1,
                                sku: item.sku,
                                description: item.description || null,
                                quantity: item.quantity,
                                price_unit: item.price_unit || 0,
                                unit_value: item.unit_value || null,
                                item_total_value: item.item_total_value || null,
                                // Risk fields
                                block_status: item.block_status || null,
                                balance: item.balance || null,
                                delay: item.delay || null,
                                payment_terms: item.payment_terms || null,
                                // Metadata flags
                                is_personalized: false,
                                is_new_client: false,
                                is_export: false,
                                is_replacement: false,
                                customization_notes: '',
                                attachment_path: null,
                                needs_mapping: false,
                                is_checked: false  // Human review flag
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

    const handleToggleChecked = (itemId) => {
        setStagingData(prev => {
            if (!prev || !prev.po_list || !Array.isArray(prev.po_list)) return prev

            return {
                ...prev,
                po_list: prev.po_list.map(po => ({
                    ...po,
                    items: Array.isArray(po.items) ? po.items.map(item => {
                        if (item.id === itemId) {
                            // Only allow checking if item has no errors
                            const errors = validateItem(item)
                            if (errors.length === 0) {
                                return { ...item, is_checked: !item.is_checked }
                            }
                        }
                        return item
                    }) : []
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

        // Rule 0: Core data integrity - SKU must exist and have valid dimensions
        if (!item.sku || !item.sku.trim()) {
            errors.push('SKU é obrigatório')
        }

        // Rule 0.1: Quantity must be positive
        if (!item.quantity || item.quantity <= 0) {
            errors.push('Quantidade deve ser maior que zero')
        }

        // Rule 0.2: Price must be positive
        if (!item.price_unit || item.price_unit <= 0) {
            errors.push('Preço unitário deve ser maior que zero')
        }

        // Rule 1: Personalized items require notes
        if (item.is_personalized && (!item.customization_notes || !item.customization_notes.trim())) {
            errors.push('Descrição da customização é obrigatória')
        }

        // Rule 2: Personalized items require attachment
        if (item.is_personalized && !item.attachment_path) {
            errors.push('Anexo é obrigatório para itens personalizados')
        }

        return errors
    }

    const calculatePOTotal = (po) => {
        if (!po || !Array.isArray(po.items)) return 0

        return po.items.reduce((sum, item) => {
            const itemTotal = item.item_total_value
                ? parseFloat(item.item_total_value)
                : (item.quantity * item.price_unit)
            return sum + itemTotal
        }, 0)
    }

    const allItemsChecked = () => {
        if (!stagingData || !stagingData.po_list || !Array.isArray(stagingData.po_list)) return false

        // Check if ALL items across ALL POs are checked
        for (const po of stagingData.po_list) {
            if (Array.isArray(po.items)) {
                for (const item of po.items) {
                    if (!item.is_checked) {
                        return false  // Found an unchecked item
                    }
                }
            }
        }
        return true  // All items are checked
    }

    const calculateSummary = () => {
        if (!stagingData || !stagingData.po_list) return { total: 0, checked: 0, unchecked: 0, withErrors: 0 }

        let totalCount = 0
        let checkedCount = 0
        let uncheckedCount = 0
        let errorCount = 0

        stagingData.po_list.forEach(po => {
            if (Array.isArray(po.items)) {
                po.items.forEach(item => {
                    totalCount++
                    if (item.is_checked) {
                        checkedCount++
                    } else {
                        uncheckedCount++
                    }
                    if (validateItem(item).length > 0) {
                        errorCount++
                    }
                })
            }
        })

        return { total: totalCount, checked: checkedCount, unchecked: uncheckedCount, withErrors: errorCount }
    }

    const handleConfirmPO = async () => {
        const summary = calculateSummary()
        setCommitSummary(summary)
        setShowSummaryModal(true)
    }

    const canCommit = () => {
        // Check if all items are checked and have no errors
        const allChecked = allItemsChecked()
        const noErrors = calculateSummary().withErrors === 0

        // Check if any PO has integrity errors
        const hasIntegrityErrors = stagingData?.po_list?.some(po => po.has_integrity_error) || false

        return allChecked && noErrors && !hasIntegrityErrors
    }

    const handleCommitAll = async () => {
        const toastId = showLoading('Criando pedidos...')

        try {
            // All items must be checked and valid to reach here
            const validPOs = stagingData.po_list.map(po => ({
                ...po,
                items: po.items.filter(item => item.is_checked && validateItem(item).length === 0)
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

            // Call actual backend endpoint
            const response = await api.post('/import/confirm-staging', payload)

            // Only proceed if we got a successful response (200 OK)
            if (response.status === 200) {
                dismissToast(toastId)
                showSuccess(`${validPOs.length} pedido(s) criado(s) com sucesso! Atualizando Kanban...`)

                // Clear session storage
                localStorage.removeItem(STORAGE_KEY)

                // Reset form first
                setSelectedFile(null)
                setStagingData(null)
                setCurrentPage(1)
                setShowSummaryModal(false)
                if (fileInputRef.current) {
                    fileInputRef.current.value = ''
                }

                // Refresh notifications
                await refreshNotifications()

                // Trigger a hard refresh by reloading the window after a short delay
                // This ensures the Kanban board shows the new POs
                setTimeout(() => {
                    window.location.reload()
                }, 1500)
            } else {
                dismissToast(toastId)
                showError('Resposta inesperada do servidor')
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
                                <div className="grid grid-cols-3 gap-4 mb-4">
                                    <div>
                                        <label className="text-sm font-medium text-gray-700">Número PO</label>
                                        <p className="text-lg font-semibold text-gray-900">{currentPO.po_number}</p>
                                    </div>
                                    <div>
                                        <label className="text-sm font-medium text-gray-700">Cliente</label>
                                        <p className="text-lg font-semibold text-gray-900">{currentPO.client_name}</p>
                                    </div>
                                    <div>
                                        <label className="text-sm font-medium text-gray-700">💰 Valor Total do Pedido</label>
                                        <p className="text-lg font-semibold text-green-600">
                                            {formatCurrency(currentPO.po_total_value || calculatePOTotal(currentPO))}
                                        </p>
                                    </div>
                                </div>

                                {/* Integrity Check Warning Banner */}
                                {currentPO.has_integrity_error && (
                                    <div className="mb-4 p-4 bg-red-50 border-2 border-red-300 rounded-lg">
                                        <div className="flex items-start gap-3">
                                            <AlertCircle className="w-6 h-6 text-red-600 flex-shrink-0 mt-0.5" />
                                            <div className="flex-1">
                                                <h4 className="text-sm font-bold text-red-900 mb-1">
                                                    ⚠️ Divergência de Valores Detectada
                                                </h4>
                                                <p className="text-sm text-red-800">
                                                    {currentPO.integrity_error_message || 'A soma dos itens não confere com o total do pedido.'}
                                                </p>
                                                <p className="text-xs text-red-700 mt-2">
                                                    <strong>Ação necessária:</strong> Verifique os valores antes de marcar os itens como conferidos.
                                                </p>
                                            </div>
                                        </div>
                                    </div>
                                )}

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
                                    <div>
                                        <h3 className="text-lg font-semibold text-gray-900">
                                            Itens do Pedido ({currentPO && Array.isArray(currentPO.items) ? currentPO.items.length : 0} total)
                                        </h3>
                                        <p className="text-sm text-gray-600 mt-1">
                                            {(() => {
                                                const summary = calculateSummary()
                                                return `Conferidos: ${summary.checked} / ${summary.total}`
                                            })()}
                                        </p>
                                    </div>
                                    {!allItemsChecked() && (
                                        <div className="flex items-center gap-2 text-yellow-600">
                                            <AlertCircle className="w-5 h-5" />
                                            <span className="text-sm font-medium">Confira todos os itens para continuar</span>
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
                                                className={`border rounded-lg p-4 ${hasError
                                                    ? 'border-red-300 bg-red-50'
                                                    : item.is_checked
                                                        ? 'border-green-300 bg-green-50'
                                                        : 'border-gray-300 bg-gray-50'
                                                    }`}
                                            >
                                                {/* Item Header with Conferido Status */}
                                                <div className="grid grid-cols-6 gap-4 mb-4">
                                                    <div>
                                                        <label className="text-xs font-medium text-gray-600">SKU</label>
                                                        <p className="font-semibold text-gray-900">{item.sku}</p>
                                                        {item.needs_mapping && (
                                                            <span className="inline-block mt-1 px-2 py-1 text-xs bg-yellow-100 text-yellow-800 rounded">
                                                                Precisa mapeamento
                                                            </span>
                                                        )}
                                                    </div>
                                                    <div className="col-span-2">
                                                        <label className="text-xs font-medium text-gray-600">Descrição do Produto</label>
                                                        <p className="font-semibold text-gray-900 text-sm truncate" title={item.description || 'N/A'}>
                                                            {item.description || 'N/A'}
                                                        </p>
                                                    </div>
                                                    <div>
                                                        <label className="text-xs font-medium text-gray-600">Quantidade</label>
                                                        <p className="font-semibold text-gray-900">{item.quantity}</p>
                                                    </div>
                                                    <div>
                                                        <label className="text-xs font-medium text-gray-600">Vl.Unit</label>
                                                        <p className="font-semibold text-gray-900">
                                                            {formatCurrency(item.unit_value || item.price_unit)}
                                                        </p>
                                                    </div>
                                                    <div>
                                                        <label className="text-xs font-medium text-gray-600">Total Item</label>
                                                        <p className="font-semibold text-green-600">
                                                            {formatCurrency(item.item_total_value || (item.quantity * item.price_unit))}
                                                        </p>
                                                    </div>
                                                </div>

                                                {/* Risk Panel (Painel de Risco) - Credit & Terms Gate */}
                                                {(item.block_status || item.balance !== null || item.delay !== null || item.payment_terms) && (
                                                    <div className="mb-4 p-4 bg-yellow-50 border-2 border-yellow-300 rounded-lg">
                                                        <h4 className="text-sm font-bold text-yellow-900 mb-3 flex items-center gap-2">
                                                            <AlertCircle className="w-5 h-5" />
                                                            🚨 Painel de Risco - Gate Financeiro
                                                        </h4>
                                                        <div className="grid grid-cols-2 gap-3">
                                                            {item.block_status && (
                                                                <div className={`p-3 rounded-lg ${item.block_status === 'BLOQUEADO' ? 'bg-red-100 border-2 border-red-400' : 'bg-green-100 border border-green-300'}`}>
                                                                    <label className="text-xs font-medium text-gray-700">Bloqueio</label>
                                                                    <p className={`text-sm font-bold ${item.block_status === 'BLOQUEADO' ? 'text-red-700' : 'text-green-700'}`}>
                                                                        {item.block_status}
                                                                    </p>
                                                                    {item.block_status === 'BLOQUEADO' && (
                                                                        <p className="text-xs text-red-600 mt-1">
                                                                            ⚠️ Intervenção do Financeiro necessária
                                                                        </p>
                                                                    )}
                                                                </div>
                                                            )}
                                                            {item.balance !== null && (
                                                                <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
                                                                    <label className="text-xs font-medium text-gray-700">Saldo</label>
                                                                    <p className="text-sm font-bold text-blue-700">
                                                                        R$ {parseFloat(item.balance).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                                                    </p>
                                                                </div>
                                                            )}
                                                            {item.delay !== null && (
                                                                <div className={`p-3 rounded-lg ${item.delay > 0 ? 'bg-orange-100 border-2 border-orange-400' : 'bg-green-100 border border-green-300'}`}>
                                                                    <label className="text-xs font-medium text-gray-700">Atraso</label>
                                                                    <p className={`text-sm font-bold ${item.delay > 0 ? 'text-orange-700' : 'text-green-700'}`}>
                                                                        {item.delay > 0 ? `${item.delay} dias` : 'Em dia'}
                                                                    </p>
                                                                </div>
                                                            )}
                                                            {item.payment_terms && (
                                                                <div className="p-3 bg-purple-50 border border-purple-200 rounded-lg">
                                                                    <label className="text-xs font-medium text-gray-700">Condição Pagamento</label>
                                                                    <p className="text-sm font-bold text-purple-700">
                                                                        {item.payment_terms}
                                                                    </p>
                                                                </div>
                                                            )}
                                                        </div>
                                                        {item.block_status === 'BLOQUEADO' && (
                                                            <div className="mt-3 p-2 bg-red-50 border border-red-300 rounded">
                                                                <p className="text-xs text-red-800">
                                                                    <strong>🔒 GATE ATIVO:</strong> Este pedido está bloqueado e requer aprovação do Financeiro antes de prosseguir.
                                                                </p>
                                                            </div>
                                                        )}
                                                    </div>
                                                )}

                                                {/* Status Row */}
                                                <div className="flex items-center justify-between mb-4 pb-3 border-b border-gray-200">
                                                    <div>
                                                        <label className="text-xs font-medium text-gray-600">Status de Conferência</label>
                                                        {hasError ? (
                                                            <div className="flex items-center gap-2 text-red-600">
                                                                <AlertCircle className="w-4 h-4" />
                                                                <span className="text-xs font-medium">Com Erros</span>
                                                            </div>
                                                        ) : item.is_checked ? (
                                                            <div className="flex items-center gap-2 text-green-600">
                                                                <CheckCircle className="w-4 h-4" />
                                                                <span className="text-xs font-medium">✓ Conferido</span>
                                                            </div>
                                                        ) : (
                                                            <div className="flex items-center gap-2 text-gray-500">
                                                                <AlertCircle className="w-4 h-4" />
                                                                <span className="text-xs font-medium">Aguardando Conferência</span>
                                                            </div>
                                                        )}
                                                    </div>
                                                    {currentPO.has_integrity_error && (
                                                        <div className="text-xs text-red-600 font-medium">
                                                            ⚠️ Verifique os valores antes de conferir
                                                        </div>
                                                    )}
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

                                                {/* Personalizado: Shows BOTH textarea AND upload */}
                                                {item.is_personalized && (
                                                    <div className="mb-4 space-y-4">
                                                        {/* Customization Notes */}
                                                        <div>
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

                                                        {/* File Upload for Personalized Items */}
                                                        <div>
                                                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                                                Upload de Anexo (PDF, JPG, PNG - Max 5MB) *
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
                                                    </div>
                                                )}

                                                {/* Error Messages */}
                                                {hasError && (
                                                    <div className="flex items-start gap-2 p-3 bg-red-100 border border-red-300 rounded-lg mb-4">
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

                                                {/* Conferido Checkbox - PROMINENT at the end */}
                                                <div className="pt-4 border-t border-gray-300">
                                                    <button
                                                        onClick={() => handleToggleChecked(item.id)}
                                                        disabled={hasError}
                                                        className={`w-full flex items-center justify-center gap-3 px-4 py-3 rounded-lg font-semibold transition-all ${hasError
                                                            ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                                                            : item.is_checked
                                                                ? 'bg-green-600 text-white hover:bg-green-700'
                                                                : 'bg-blue-600 text-white hover:bg-blue-700'
                                                            }`}
                                                    >
                                                        {hasError ? (
                                                            <>
                                                                <X className="w-5 h-5" />
                                                                <span>Corrija os erros para conferir</span>
                                                            </>
                                                        ) : item.is_checked ? (
                                                            <>
                                                                <CheckSquare className="w-5 h-5" />
                                                                <span>✓ CONFERIDO - Clique para desmarcar</span>
                                                            </>
                                                        ) : (
                                                            <>
                                                                <Square className="w-5 h-5" />
                                                                <span>Marcar como CONFERIDO</span>
                                                            </>
                                                        )}
                                                    </button>
                                                </div>
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

                            {/* Multi-PO Navigation - Bottom (Duplicate) */}
                            {stagingData.isMultiPO && (
                                <div className="card bg-blue-50 border-blue-200">
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <p className="text-sm font-medium text-blue-900">
                                                Navegando: PO {selectedPOIndex + 1} de {stagingData.total_pos}
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
                                                PO {selectedPOIndex + 1} / {stagingData.total_pos}
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
                                    disabled={!canCommit()}
                                    className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
                                    title={!canCommit() ? 'Confira todos os itens e corrija erros antes de confirmar' : 'Confirmar todos os pedidos'}
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
                                📋 Resumo da Conferência
                            </h3>
                            <div className="space-y-3 mb-6">
                                <div className="flex items-center justify-between p-3 bg-blue-50 border border-blue-200 rounded-lg">
                                    <span className="text-sm font-medium text-blue-900">Total de Itens</span>
                                    <span className="text-2xl font-bold text-blue-600">{commitSummary.total}</span>
                                </div>
                                <div className="flex items-center justify-between p-3 bg-green-50 border border-green-200 rounded-lg">
                                    <span className="text-sm font-medium text-green-900">✓ Itens Conferidos</span>
                                    <span className="text-2xl font-bold text-green-600">{commitSummary.checked}</span>
                                </div>
                                {commitSummary.unchecked > 0 && (
                                    <div className="flex items-center justify-between p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                                        <span className="text-sm font-medium text-yellow-900">Aguardando Conferência</span>
                                        <span className="text-2xl font-bold text-yellow-600">{commitSummary.unchecked}</span>
                                    </div>
                                )}
                                {commitSummary.withErrors > 0 && (
                                    <div className="flex items-center justify-between p-3 bg-red-50 border border-red-200 rounded-lg">
                                        <span className="text-sm font-medium text-red-900">Com Erros</span>
                                        <span className="text-2xl font-bold text-red-600">{commitSummary.withErrors}</span>
                                    </div>
                                )}
                            </div>

                            {commitSummary.checked === commitSummary.total && commitSummary.withErrors === 0 ? (
                                <div className="mb-6 p-4 bg-green-50 border-2 border-green-300 rounded-lg">
                                    <p className="text-sm text-green-900 font-semibold">
                                        <strong>✅ Conferência Completa!</strong>
                                    </p>
                                    <p className="text-sm text-green-800 mt-1">
                                        Todos os {commitSummary.total} itens foram conferidos e estão prontos para envio à fábrica.
                                    </p>
                                </div>
                            ) : (
                                <div className="mb-6 p-4 bg-red-50 border-2 border-red-300 rounded-lg">
                                    <p className="text-sm text-red-900 font-semibold">
                                        <strong>❌ Conferência Incompleta</strong>
                                    </p>
                                    <p className="text-sm text-red-800 mt-1">
                                        {commitSummary.unchecked > 0 && `${commitSummary.unchecked} item(ns) ainda não conferido(s). `}
                                        {commitSummary.withErrors > 0 && `${commitSummary.withErrors} item(ns) com erros. `}
                                        Você deve conferir TODOS os itens antes de enviar à fábrica.
                                    </p>
                                </div>
                            )}

                            <div className="flex items-center justify-end gap-3">
                                <button
                                    onClick={() => setShowSummaryModal(false)}
                                    className="px-4 py-2 bg-gray-300 text-gray-700 rounded-lg hover:bg-gray-400 transition-colors"
                                >
                                    Voltar
                                </button>
                                {commitSummary.checked === commitSummary.total && commitSummary.withErrors === 0 && (
                                    <button
                                        onClick={handleCommitAll}
                                        className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-semibold"
                                    >
                                        ✓ Confirmar Todos ({commitSummary.total} itens)
                                    </button>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Session Restore Modal */}
            {showRestoreModal && (
                <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
                    <div className="bg-white rounded-lg shadow-xl max-w-md w-full">
                        <div className="p-6">
                            <h3 className="text-xl font-bold text-gray-900 mb-4">
                                💾 Sessão Anterior Detectada
                            </h3>
                            <p className="text-sm text-gray-700 mb-6">
                                Encontramos uma sessão de conferência não finalizada. Deseja restaurar e continuar de onde parou?
                            </p>
                            <div className="flex items-center justify-end gap-3">
                                <button
                                    onClick={handleDiscardSession}
                                    className="px-4 py-2 bg-gray-300 text-gray-700 rounded-lg hover:bg-gray-400 transition-colors"
                                >
                                    Descartar
                                </button>
                                <button
                                    onClick={handleRestoreSession}
                                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-semibold"
                                >
                                    ✓ Restaurar Sessão
                                </button>
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

            {/* Finance Approval Modal */}
            {showFinanceModal && selectedFinanceItem && (
                <FinanceApprovalModal
                    item={selectedFinanceItem}
                    poNumber={
                        stagingData?.po_list?.[selectedPOIndex]?.po_number ||
                        stagingData?.po_number ||
                        'N/A'
                    }
                    onApprove={(justification) => {
                        // Mark item as finance-approved in staging state (UI-only, Step 2)
                        // Full API call will be wired in Hardening Step 3
                        console.log('✅ [Finance] APPROVED:', {
                            sku: selectedFinanceItem.sku,
                            justification
                        })
                        showSuccess(`Item ${selectedFinanceItem.sku || ''} aprovado financeiramente.`)
                        setShowFinanceModal(false)
                        setSelectedFinanceItem(null)
                        setFinanceJustification('')
                    }}
                    onReject={(justification) => {
                        // Mark item as finance-rejected in staging state (UI-only, Step 2)
                        console.log('❌ [Finance] REJECTED:', {
                            sku: selectedFinanceItem.sku,
                            justification
                        })
                        showError(`Item ${selectedFinanceItem.sku || ''} rejeitado pelo financeiro.`)
                        setShowFinanceModal(false)
                        setSelectedFinanceItem(null)
                        setFinanceJustification('')
                    }}
                    onClose={() => {
                        setShowFinanceModal(false)
                        setSelectedFinanceItem(null)
                        setFinanceJustification('')
                    }}
                />
            )}
        </div>
    )
}

export default ImportPage
