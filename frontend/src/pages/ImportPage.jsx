import React, { useState, useRef, useEffect } from 'react'
import { Upload, FileSpreadsheet, AlertCircle, CheckCircle, X, HelpCircle, Paperclip, Trash2, Cloud, ChevronLeft, ChevronRight, Globe, RefreshCw, DollarSign, CheckSquare, Square, Lock, Unlock, Package, Briefcase, Ban } from 'lucide-react'
import api from '../utils/api'
import { showSuccess, showError, showLoading, dismissToast } from '../utils/toast'
import { useNotifications } from '../context/NotificationContext'
import { useAuth } from '../context/AuthContext'
import HelpModal from '../components/HelpModal'
import FinanceApprovalModal from '../components/FinanceApprovalModal'
import { getHelpForStatus } from '../config/helpConfig'
import { calculateDynamicMargin, calculatePOMargins, parsePaymentTermsToDays } from '../utils/marginCalculator'
import { cleanBrazilianNumber } from '../utils/numberUtils'

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

// Robust DD/MM/YYYY date formatter
const formatDate = (dateString) => {
    if (!dateString) return 'N/A'
    if (/^\d{4}-\d{2}-\d{2}$/.test(dateString) || /^\d{4}-\d{2}-\d{2}T.*$/.test(dateString)) {
        const cleanDate = dateString.split('T')[0]
        const [year, month, day] = cleanDate.split('-')
        return `${day}/${month}/${year}`
    }
    if (/^\d{2}\/\d{2}\/\d{4}$/.test(dateString)) {
        return dateString
    }
    try {
        const d = new Date(dateString)
        if (isNaN(d.getTime())) return dateString
        const day = String(d.getDate()).padStart(2, '0')
        const month = String(d.getMonth() + 1).padStart(2, '0')
        const year = d.getFullYear()
        return `${day}/${month}/${year}`
    } catch (e) {
        return dateString
    }
}


// Robust Brazilian/Standard number parser delegated to central utility
const parseBrazilianNumber = (value) => cleanBrazilianNumber(value)

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
    // FF-HARDENING-004: financial override checkbox state
    const [overrideAprovado, setOverrideAprovado] = useState(false)
    const [financeSubmitting, setFinanceSubmitting] = useState(false)
    const [sessionChecked, setSessionChecked] = useState(false) // Race-condition guard for session restoration
    // FF-HARDENING-012.1 [Item 1]: Cancel PO from ImportPage (Mesa de Conferência)
    const [showCancelImportModal, setShowCancelImportModal] = useState(false)
    const [cancelImportJustification, setCancelImportJustification] = useState('')
    const [cancellingImport, setCancellingImport] = useState(false)
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
        if (!sessionChecked) return // Guard: wait until mount restore offer has been settled

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
    }, [stagingData, selectedPOIndex, currentPage, user, sessionChecked])

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
                setSessionChecked(true)
                return
            }

            const parsed = JSON.parse(savedSession)

            // Schema version check: discard old/incompatible sessions silently
            if (!isValidSessionSchema(parsed)) {
                console.warn('⚠️ [Session] Session schema mismatch or invalid — discarding automatically')
                localStorage.removeItem(storageKey)
                setSessionChecked(true)
                return
            }

            // Age check: discard sessions older than 24 hours
            const sessionAge = Date.now() - new Date(parsed.timestamp).getTime()
            const MAX_AGE_MS = 24 * 60 * 60 * 1000
            if (sessionAge >= MAX_AGE_MS) {
                console.log('⏳ [Session] Session expired (', Math.floor(sessionAge / 60000), 'min old) — discarding')
                localStorage.removeItem(storageKey)
                setSessionChecked(true)
                return
            }

            console.log('✅ [Session] Valid session found (' + Math.floor(sessionAge / 60000) + ' min old), showing restore modal')
            setShowRestoreModal(true)
            // Note: we leave sessionChecked=false here because the user is deciding whether to restore or discard
        } catch (error) {
            console.error('❌ [Session] Failed to check for saved session:', error)
            try { localStorage.removeItem(getStorageKey(user)) } catch (_) {}
            setSessionChecked(true)
        }
    }, [user]) // Re-check when user changes (login/logout)

    const handleRestoreSession = () => {
        const storageKey = getStorageKey(user)
        if (!storageKey) { setShowRestoreModal(false); setSessionChecked(true); return }

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
                    setSessionChecked(true)
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
        setSessionChecked(true)
        setShowRestoreModal(false)
    }

    const handleDiscardSession = () => {
        const storageKey = getStorageKey(user)
        console.log('🗑️ [Session] Discarding saved session')
        if (storageKey) {
            try { localStorage.removeItem(storageKey) } catch (_) {}
        }
        setSessionChecked(true)
        setShowRestoreModal(false)
    }

    // FF-HARDENING-004: Reset override checkbox whenever the operator navigates to a different PO
    // Each PO in the batch must start unchecked by default.
    useEffect(() => {
        setOverrideAprovado(false)
    }, [selectedPOIndex])

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
                    { column_name: 'Nº do Pedido', field_type: 'po_number' },
                    { column_name: 'Cliente', field_type: 'client_name' },
                    { column_name: 'Id Produto', field_type: 'sku' },
                    { column_name: 'Qtd', field_type: 'quantity' },
                    // Optional ONET fields — FINAL PRODUCTION SCHEMA (Ewaldo 2026-07-01)
                    // Primary column name changed from 'Descr. Produto' → 'Produto'
                    { column_name: 'Produto', field_type: 'description' },
                    { column_name: 'Unidade', field_type: 'unit' },
                    { column_name: 'Largura', field_type: 'width' },
                    { column_name: 'Comprimento', field_type: 'length' },
                    { column_name: 'Lead Time', field_type: 'lead_time' },
                    // Dt.Entrega  → order entry/receipt date
                    { column_name: 'Dt.Entrega', field_type: 'delivery_date' },
                    // Dt.Faturamento → SLA base / expected_delivery_date [9.1]
                    { column_name: 'Dt.Faturamento', field_type: 'billing_date' },
                    // Data do Pedido → original PO creation date
                    { column_name: 'Data do Pedido', field_type: 'order_date' },
                    { column_name: '% ICMS', field_type: 'icms_percent' },
                    { column_name: 'Bloqueio Faturamento', field_type: 'block_status' },
                    { column_name: 'Saldo', field_type: 'balance' },
                    { column_name: 'Atraso', field_type: 'delay' },
                    { column_name: 'Cond.Pgto', field_type: 'payment_terms' },
                    { column_name: 'Frete', field_type: 'freight' },
                    { column_name: 'Vendedor', field_type: 'salesperson' },
                    { column_name: 'IPI', field_type: 'ipi' },
                    // Financial value fields
                    { column_name: 'VlUnit', field_type: 'unit_value' },
                    { column_name: 'Total Item', field_type: 'item_total_value' },
                    { column_name: 'Vl.Pedido', field_type: 'po_total_value' },
                    // NEW: ONET final production schema — carrier & structured code
                    { column_name: 'Codigo Estruturado', field_type: 'codigo_estruturado' },
                    { column_name: 'Cod. Transportadora', field_type: 'carrier_code' },
                    { column_name: 'Nome Transportadora', field_type: 'carrier_name' }
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
                    const poList = response.data.po_list.map(po => {
                        const sumFreight = po.items.reduce((sum, item) => sum + (parseFloat(item.freight) || 0), 0);
                        return {
                            po_number: po.po_number,
                            client_name: po.client_name,
                            freight_cost: sumFreight,
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
                            unit_value: item.unit_value || null,
                            item_total_value: item.item_total_value || null,
                            // Risk fields from ONET
                            block_status: item.block_status || null,
                            balance: item.balance || null,
                            delay: item.delay || null,
                            payment_terms: item.payment_terms || null,
                            unit: item.unit || null,
                            width: item.width || null,
                            length: item.length || null,
                            lead_time: item.lead_time || null,
                            delivery_date: item.delivery_date || null,
                            billing_date: item.billing_date || null,
                            icms_percent: item.icms_percent || null,
                            freight: item.freight || null,
                            salesperson: item.salesperson || null,
                            ipi: item.ipi || null,
                            // ONET final schema — new fields (2026-07-01)
                            order_date: item.order_date || null,
                            codigo_estruturado: item.codigo_estruturado || null,
                            carrier_code: item.carrier_code || null,
                            carrier_name: item.carrier_name || null,
                            // Metadata flags
                            is_personalized: false,
                            is_new_client: false,
                            is_export: false,
                            is_replacement: false,
                            is_triangular: false,       // FF-HARDENING-015 Item 3
                            is_estoque: false,           // FF-HARDENING-015 Item 3
                            customization_notes: '',
                            attachment_path: null,
                            needs_mapping: false,
                            is_checked: false,
                            extra_metadata: {
                                finance_justification: null
                            }
                        }))
                    }
                })

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
                            freight_cost: response.data.items.reduce((sum, item) => sum + (parseFloat(item.freight) || 0), 0),
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
                                unit: item.unit || null,
                                width: item.width || null,
                                length: item.length || null,
                                lead_time: item.lead_time || null,
                                delivery_date: item.delivery_date || null,
                                billing_date: item.billing_date || null,
                                icms_percent: item.icms_percent || null,
                                freight: item.freight || null,
                                salesperson: item.salesperson || null,
                                ipi: item.ipi || null,
                                // ONET final schema — new fields (2026-07-01)
                                order_date: item.order_date || null,
                                codigo_estruturado: item.codigo_estruturado || null,
                                carrier_code: item.carrier_code || null,
                                carrier_name: item.carrier_name || null,
                                // Metadata flags
                                is_personalized: false,
                                is_new_client: false,
                                is_export: false,
                                is_replacement: false,
                                is_triangular: false,       // FF-HARDENING-015 Item 3
                                is_estoque: false,           // FF-HARDENING-015 Item 3
                                customization_notes: '',
                                attachment_path: null,
                                needs_mapping: false,
                                is_checked: false,
                                extra_metadata: {
                                    finance_justification: null
                                }
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

    // FF-HARDENING-015 Item 3: Triangular/Remessa toggle
    const handleToggleTriangular = (itemId) => {
        setStagingData(prev => {
            if (!prev || !prev.po_list || !Array.isArray(prev.po_list)) return prev
            return {
                ...prev,
                po_list: prev.po_list.map(po => ({
                    ...po,
                    items: Array.isArray(po.items) ? po.items.map(item =>
                        item.id === itemId
                            ? { ...item, is_triangular: !item.is_triangular }
                            : item
                    ) : []
                }))
            }
        })
    }

    // FF-HARDENING-015 Item 3: Material de Estoque toggle
    const handleToggleEstoque = (itemId) => {
        setStagingData(prev => {
            if (!prev || !prev.po_list || !Array.isArray(prev.po_list)) return prev
            return {
                ...prev,
                po_list: prev.po_list.map(po => ({
                    ...po,
                    items: Array.isArray(po.items) ? po.items.map(item =>
                        item.id === itemId
                            ? { ...item, is_estoque: !item.is_estoque }
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

    const handlePOFieldChange = (field, value, e) => {
        setStagingData(prev => {
            if (!prev || !prev.po_list || !Array.isArray(prev.po_list)) return prev

            const updatedPoList = [...prev.po_list]
            let cleanedVal = value;
            if (typeof value === 'string') {
                cleanedVal = value.replace(/^0+(?=\d)/, '');
                if (cleanedVal.startsWith('0') && cleanedVal.length > 1 && cleanedVal[1] !== '.') {
                    cleanedVal = cleanedVal.replace(/^0+/, '');
                }
            }
            
            // Force DOM update to bypass React's type="number" virtual DOM issue
            if (e && e.target) {
                e.target.value = cleanedVal;
            }

            updatedPoList[selectedPOIndex] = {
                ...updatedPoList[selectedPOIndex],
                [field]: cleanedVal
            }

            return {
                ...prev,
                po_list: updatedPoList
            }
        })
    }

    const handleItemFieldChange = (itemId, field, value, e) => {
        setStagingData(prev => {
            if (!prev || !prev.po_list || !Array.isArray(prev.po_list)) return prev

            let cleanedVal = value;
            if ((field === 'freight' || field === 'total_cost') && typeof value === 'string') {
                cleanedVal = value.replace(/^0+(?=\d)/, '');
                if (cleanedVal.startsWith('0') && cleanedVal.length > 1 && cleanedVal[1] !== '.') {
                    cleanedVal = cleanedVal.replace(/^0+/, '');
                }
            }

            // Force DOM update to bypass React's type="number" virtual DOM issue
            if (e && e.target && (field === 'freight' || field === 'total_cost')) {
                e.target.value = cleanedVal;
            }

            return {
                ...prev,
                po_list: prev.po_list.map(po => ({
                    ...po,
                    items: Array.isArray(po.items) ? po.items.map(item =>
                        item.id === itemId
                            ? { ...item, [field]: cleanedVal }
                            : item
                    ) : []
                }))
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
        const rawPrice = item.unit_value !== null && item.unit_value !== undefined ? item.unit_value : item.price_unit
        const parsedPrice = parseBrazilianNumber(rawPrice)

        if (parsedPrice <= 0) {
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

        const parseBRL = parseBrazilianNumber

        return po.items.reduce((sum, item) => {
            const parsedUnit = parseBRL(item.unit_value !== null && item.unit_value !== undefined ? item.unit_value : item.price_unit)
            const parsedTotal = item.item_total_value ? parseBRL(item.item_total_value) : 0

            const itemTotal = parsedTotal > 0 ? parsedTotal : (item.quantity * parsedUnit)
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

        // Check if all POs have selected packaging type
        const allHavePackaging = stagingData?.po_list?.every(po => po.packaging_type && po.packaging_type.trim() !== '') || false

        // Check if all POs have selected business unit
        const allHaveBusinessUnit = stagingData?.po_list?.every(po => po.business_unit && po.business_unit.trim() !== '') || false

        // NOTE (FF-HARDENING-004.1): financial integrity mismatch does NOT block the button.
        // The "Aprovar com Divergência" checkbox controls routing only (financial_override: true/false).
        // Case A (checked): routed to PCP. Case B (unchecked): routed to Concluídos.
        // Both cases write an immutable audit log. The operator always has a path forward.
        return allChecked && noErrors && allHavePackaging && allHaveBusinessUnit
    }

    const handleCommitAll = async () => {
        const toastId = showLoading('Criando pedidos...')

        try {
            // All items must be checked and valid to reach here
            const validPOs = stagingData.po_list.map(po => ({
                ...po,
                items: po.items.filter(item => item.is_checked && validateItem(item).length === 0)
            })).filter(po => po.items.length > 0)

            const parseBRL = parseBrazilianNumber

            // Prepare payload with all 22 fields + metadata
            const payload = {
                financial_override: overrideAprovado,  // FF-HARDENING-004
                pos: validPOs.map(po => ({
                    po_number: po.po_number,
                    client_name: po.client_name,
                    business_unit: po.business_unit,
                    freight_cost: cleanBrazilianNumber(po.freight_cost),
                    additional_costs: cleanBrazilianNumber(po.additional_costs),
                    po_total_value: po.po_total_value !== undefined && po.po_total_value !== null ? cleanBrazilianNumber(po.po_total_value) : null,
                    packaging_type: po.packaging_type || null,
                    items: po.items.map(item => {
                        const parsedPrice = parseBRL(item.unit_value !== null && item.unit_value !== undefined ? item.unit_value : item.price_unit)
                        return {
                            sku: item.sku,
                            quantity: item.quantity,
                            price_unit: parsedPrice,
                            unit_value: item.unit_value !== null && item.unit_value !== undefined ? parseBRL(item.unit_value) : null,
                            item_total_value: item.item_total_value !== null && item.item_total_value !== undefined ? parseBRL(item.item_total_value) : null,
                            block_status: item.block_status || null,
                            balance: item.balance !== null && item.balance !== undefined ? parseBRL(item.balance) : null,
                            delay: item.delay !== null && item.delay !== undefined ? parseInt(item.delay, 10) : null,
                            payment_terms: item.payment_terms || null,
                            description: item.description || null,
                            unit: item.unit || null,
                            width: item.width !== null && item.width !== undefined ? parseBRL(item.width) : null,
                            length: item.length !== null && item.length !== undefined ? parseBRL(item.length) : null,
                            lead_time: item.lead_time !== null && item.lead_time !== undefined ? parseInt(item.lead_time, 10) : null,
                            delivery_date: item.delivery_date || null,
                            billing_date: item.billing_date || null,
                            // ONET final schema — new fields forwarded to backend (2026-07-01)
                            order_date: item.order_date || null,
                            codigo_estruturado: item.codigo_estruturado || null,
                            carrier_code: item.carrier_code || null,
                            carrier_name: item.carrier_name || null,
                            icms_percent: item.icms_percent !== null && item.icms_percent !== undefined ? parseBRL(item.icms_percent) : null,
                            freight: item.freight !== null && item.freight !== undefined ? parseBRL(item.freight) : null,
                            salesperson: item.salesperson || null,
                            ipi: item.ipi !== null && item.ipi !== undefined ? parseBRL(item.ipi) : null,
                            extra_metadata: {
                                is_personalized: item.is_personalized || false,
                                is_new_client: item.is_new_client || false,
                                is_export: item.is_export || false,
                                is_replacement: item.is_replacement || false,
                                is_triangular: item.is_triangular || false,   // FF-HARDENING-015 Item 3
                                is_estoque: item.is_estoque || false,         // FF-HARDENING-015 Item 3
                                customization_notes: item.customization_notes || '',
                                attachment_path: item.attachment_path || null,
                                attachment_filename: item.attachment_filename || null,
                                apply_sla_reduction: item.is_replacement || false,
                                finance_justification: item.extra_metadata?.finance_justification || null
                            }
                        }
                    })
                }))
            }

            // Call actual backend endpoint
            const response = await api.post('/import/confirm-staging', payload)

            // Only proceed if we got a successful response (200 OK)
            if (response.status === 200) {
                dismissToast(toastId)
                showSuccess(`${validPOs.length} pedido(s) criado(s) com sucesso! Atualizando Kanban...`)

                // Clear session storage dynamically using tenant-scoped key
                const storageKey = getStorageKey(user)
                if (storageKey) {
                    try {
                        localStorage.removeItem(storageKey)
                    } catch (_) {}
                }

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

                // Trigger a clean redirect to the Kanban page with a full hard refresh
                // This ensures the Kanban board fetches and displays the new POs immediately
                setTimeout(() => {
                    window.location.href = '/kanban'
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

    const [showS3Modal, setShowS3Modal] = useState(false)
    const [s3Files, setS3Files] = useState([])
    const [selectedS3Files, setSelectedS3Files] = useState([])
    const [fetchingS3Files, setFetchingS3Files] = useState(false)

    const handleOpenSyncModal = async () => {
        setShowS3Modal(true)
        setFetchingS3Files(true)
        setS3Files([])
        setSelectedS3Files([])
        try {
            const response = await api.get('/import/pending-s3-files')
            setS3Files(response.data)
            // Pre-select all files on load
            setSelectedS3Files(response.data.map(f => f.filename))
        } catch (error) {
            console.error('Error fetching S3 files:', error)
            showError('Erro ao buscar arquivos pendentes no S3.')
        } finally {
            setFetchingS3Files(false)
        }
    }

    const handleConfirmS3Import = async () => {
        if (selectedS3Files.length === 0) return
        setSyncing(true)
        const toastId = showLoading('Sincronizando com ONET (Nuvem)...')

        try {
            const response = await api.post('/import/sync-s3', {
                filenames: selectedS3Files
            })

            dismissToast(toastId)

            if (response.data.success) {
                const { files_processed, pos_imported, errors } = response.data

                if (files_processed > 0) {
                    showSuccess(
                        `✅ Sincronização concluída! ${files_processed} arquivo(s) processado(s).`
                    )
                    if (pos_imported && pos_imported.length > 0) {
                        showSuccess(`POs importados: ${pos_imported.join(', ')}`)
                    }
                    if (errors && errors.length > 0) {
                        showError(`Divergências: ${errors.join('; ')}`)
                    }
                    await refreshNotifications()
                } else {
                    showSuccess('✅ Sincronização concluída. Nenhum arquivo novo importado.')
                }
                setShowS3Modal(false)
            } else {
                showError(response.data.message || 'Falha na sincronização')
            }
        } catch (error) {
            dismissToast(toastId)
            console.error('S3 sync error:', error)
            showError(error.response?.data?.detail || 'Erro ao sincronizar com ONET.')
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
        if (currentPO && (!currentPO.packaging_type || currentPO.packaging_type.trim() === '')) {
            showError('⚠️ Atenção: Este pedido não possui tipo de embalagem selecionado!')
        }
        if (currentPO && (!currentPO.business_unit || currentPO.business_unit.trim() === '')) {
            showError('⚠️ Atenção: Este pedido não possui a Unidade de Negócio selecionada!')
        }
        setSelectedPOIndex(prev => Math.max(0, prev - 1))
        setCurrentPage(1) // Reset to first page when switching POs
    }

    const handleNextPO = () => {
        if (currentPO && (!currentPO.packaging_type || currentPO.packaging_type.trim() === '')) {
            showError('⚠️ Atenção: Este pedido não possui tipo de embalagem selecionado!')
        }
        if (currentPO && (!currentPO.business_unit || currentPO.business_unit.trim() === '')) {
            showError('⚠️ Atenção: Este pedido não possui a Unidade de Negócio selecionada!')
        }
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
                        <div className="flex items-center gap-2">
                            <h1 className="text-2xl font-bold text-gray-900">Mesa de Conferência</h1>
                            <button
                                onClick={() => setShowHelp(true)}
                                className="p-1 text-gray-400 hover:text-gray-600 rounded-full hover:bg-gray-100 transition-colors"
                                title="Ver regras de negócio de Staging"
                            >
                                <HelpCircle className="w-5 h-5" />
                            </button>
                        </div>
                        <p className="text-sm text-gray-600 mt-1">
                            Importar e validar pedidos de compra (campos ONET)
                        </p>
                    </div>
                    <div className="flex items-center gap-3">
                        <button
                            onClick={handleOpenSyncModal}
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
                                ) : null}
                                <input
                                    ref={fileInputRef}
                                    type="file"
                                    accept=".xlsx,.xls"
                                    onChange={handleFileSelect}
                                    className="hidden"
                                />
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
                                <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
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
                                    {['admin', 'master'].includes((user?.role || '').toLowerCase()) ? (
                                        <div>
                                            <label className="text-sm font-medium text-gray-700">📊 Margem Global PO</label>
                                            {(() => {
                                                const poMarginInfo = calculatePOMargins(currentPO);
                                                if (poMarginInfo.status === 'PENDENTE_PCP') {
                                                    return (
                                                        <div>
                                                            <p className="text-xs font-bold text-gray-500 mt-1 uppercase bg-gray-100 border border-gray-300 px-2.5 py-0.5 rounded-full inline-block">
                                                                PENDENTE PCP
                                                            </p>
                                                        </div>
                                                    );
                                                }
                                                return (
                                                    <div className="mt-1">
                                                         <span className={`inline-flex items-center px-3 py-0.5 rounded-full text-sm font-bold border shadow-sm ${
                                                             poMarginInfo.badgeColor === 'green' ? 'bg-green-100 text-green-800 border-green-300' :
                                                             poMarginInfo.badgeColor === 'yellow' ? 'bg-yellow-100 text-yellow-800 border-yellow-300' :
                                                             poMarginInfo.badgeColor === 'orange' ? 'bg-orange-100 text-orange-800 border-orange-300' :
                                                             'bg-red-100 text-red-800 border-red-300'
                                                         }`}>
                                                             {poMarginInfo.formattedMargin}
                                                         </span>
                                                    </div>
                                                );
                                            })()}
                                        </div>
                                    ) : (
                                        <div />
                                    )}
                                </div>

                                {/* Integrity Check Warning Banner */}
                                {/* HOMOLOGATION OVERRIDE (FF-HARDENING-004-BYPASS): has_integrity_error forced to false.
                                    Restore: replace `false` below with `currentPO.has_integrity_error` to re-enable. */}
                                {false && (
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
                                                    <strong>Ação necessária:</strong> Marque a opção abaixo para desbloquear a confirmação.
                                                </p>
                                                {/* FF-HARDENING-004: Override checkbox — only shown when mismatch exists */}
                                                <label
                                                    id="override-aprovado-label"
                                                    className="flex items-start gap-2 mt-3 cursor-pointer select-none"
                                                >
                                                    <input
                                                        id="checkbox-override-aprovado"
                                                        type="checkbox"
                                                        checked={overrideAprovado}
                                                        onChange={e => setOverrideAprovado(e.target.checked)}
                                                        className="w-4 h-4 mt-0.5 accent-orange-500 rounded flex-shrink-0"
                                                    />
                                                    <span className="text-sm font-semibold text-orange-900">
                                                        Aprovar com Divergência (marcado: envia ao PCP; desmarcado: arquiva em Concluídos. Ambas as opções registram log de auditoria imutável)
                                                    </span>
                                                </label>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {/* PO-Level Cost Fields */}
                                <div className="grid grid-cols-4 gap-4 p-4 bg-green-50 border border-green-200 rounded-lg">
                                    <div>
                                        <label className="block text-sm font-medium text-gray-700 mb-2">
                                            <DollarSign className="w-4 h-4 inline mr-1" />
                                            Frete (R$)
                                        </label>
                                        <input
                                            type="number"
                                            step="0.01"
                                            min="0"
                                            value={currentPO.freight_cost !== undefined && currentPO.freight_cost !== null ? currentPO.freight_cost : 0}
                                            onChange={(e) => handlePOFieldChange('freight_cost', e.target.value, e)}
                                            onFocus={(e) => e.target.select()}
                                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent animate-fade-in"
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
                                            value={currentPO.additional_costs !== undefined && currentPO.additional_costs !== null ? currentPO.additional_costs : 0}
                                            onChange={(e) => handlePOFieldChange('additional_costs', e.target.value, e)}
                                            onFocus={(e) => e.target.select()}
                                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent animate-fade-in"
                                            placeholder="0.00"
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-sm font-medium text-gray-700 mb-2 text-cyan-905">
                                            <Package className="w-4 h-4 inline mr-1 text-cyan-700" />
                                            Tipo de Embalagem <span className="text-red-500 font-bold">*</span>
                                        </label>
                                        <select
                                            value={currentPO.packaging_type || ''}
                                            onChange={(e) => handlePOFieldChange('packaging_type', e.target.value)}
                                            className="w-full px-3 py-2 border border-gray-305 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent text-gray-800 font-medium"
                                        >
                                            <option value="">Selecione...</option>
                                            <option value="Padrão">Padrão</option>
                                            <option value="Palete">Palete</option>
                                            <option value="Caixa de Papelão">Caixa de Papelão</option>
                                            <option value="Fardo Plástico">Fardo Plástico</option>
                                            <option value="Granel">Granel</option>
                                            <option value="Filme">Filme</option>
                                        </select>
                                    </div>
                                    <div>
                                        <label className="block text-sm font-medium text-gray-700 mb-2 text-cyan-905">
                                            <Briefcase className="w-4 h-4 inline mr-1 text-cyan-700" />
                                            Unidade de Negócio <span className="text-red-500 font-bold">*</span>
                                        </label>
                                        <select
                                            value={currentPO.business_unit || ''}
                                            onChange={(e) => handlePOFieldChange('business_unit', e.target.value)}
                                            className="w-full px-3 py-2 border border-gray-305 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent text-gray-800 font-medium"
                                        >
                                            <option value="">Selecione...</option>
                                            <option value="Indústria">Indústria</option>
                                            <option value="Construção Civil">Construção Civil</option>
                                            <option value="Varejo">Varejo</option>
                                            <option value="Outros">Outros</option>
                                        </select>
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
                                                className={`border rounded-lg p-4 transition-all duration-300 ${hasError
                                                    ? 'border-red-300 bg-red-50'
                                                    : (item.block_status === 'BLOQUEADO' && item.is_replacement)
                                                        ? 'border-cyan-300 bg-cyan-50 shadow-md'
                                                        : item.is_checked
                                                            ? item.is_replacement
                                                                ? 'border-cyan-300 bg-cyan-50 shadow-md'
                                                                : 'border-green-300 bg-green-50 shadow-md'
                                                            : 'border-gray-300 bg-gray-50'
                                                    }`}
                                            >
                                                {/* Item Header with Conferido Status */}
                                                {(() => {
                                                    const priceVal = parseBrazilianNumber(item.unit_value !== null && item.unit_value !== undefined ? item.unit_value : item.price_unit);
                                                    const itemGross = priceVal * item.quantity;
                                                    const paymentDays = parsePaymentTermsToDays(item.payment_terms || currentPO.payment_terms);
                                                    const itemCost = parseFloat(item.total_cost) || parseFloat(item.cost_mp) || 0;
                                                    const itemFreight = parseFloat(item.freight) || 0;
                                                    const commRate = parseFloat(item.manual_commission_rate) || parseFloat(currentPO.commission_rate) || 0;

                                                    // Proportional rate apportionment
                                                    const poTotalGross = (currentPO.items || []).reduce((sum, it) => {
                                                        const pVal = parseBrazilianNumber(it.unit_value !== null && it.unit_value !== undefined ? it.unit_value : it.price_unit);
                                                        return sum + (pVal * (parseFloat(it.quantity) || 0));
                                                    }, 0);
                                                    const itemProportion = poTotalGross > 0 ? (itemGross / poTotalGross) : 0;

                                                    const headerFreightCost = parseFloat(currentPO.freight_cost) || 0;
                                                    const proportionalFreight = itemProportion * headerFreightCost;

                                                    const headerAdditionalCostsVal = parseFloat(currentPO.additional_costs) || 0;
                                                    const proportionalAdditional = itemProportion * headerAdditionalCostsVal;

                                                    const marginResult = calculateDynamicMargin({
                                                        gross: itemGross,
                                                        freight: itemFreight + proportionalFreight,
                                                        commissionRate: commRate,
                                                        costs: (itemCost * item.quantity) + proportionalAdditional,
                                                        paymentDays: paymentDays,
                                                        taxRate: 9.25  // FF-HARDENING-015: PIS/COFINS unified rate (was 22.25)
                                                    });

                                                    return (
                                                        <div className="grid grid-cols-7 gap-4 mb-4 items-start">
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
                                                                {/* ONET 2026-07-01: Código Estruturado — primary product code reference */}
                                                                {item.codigo_estruturado && (
                                                                    <span className="inline-flex items-center mt-0.5 px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-50 text-indigo-700 border border-indigo-200 font-mono tracking-wide">
                                                                        🔖 {item.codigo_estruturado}
                                                                    </span>
                                                                )}
                                                                {/* FF-HARDENING-015 Item 3: Dimensions */}
                                                                {(item.width != null && item.length != null) && (
                                                                    <span className="inline-flex items-center mt-0.5 ml-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                                                                        📐 Largura: {parseFloat(item.width)} mm × Comprimento: {parseFloat(item.length)} mm
                                                                    </span>
                                                                )}
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
                                                            {['admin', 'master'].includes((user?.role || '').toLowerCase()) && (
                                                                <div>
                                                                    <label className="text-xs font-medium text-gray-600 block">Margem</label>
                                                                    {marginResult.status === 'PENDENTE_PCP' ? (
                                                                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-gray-100 text-gray-800 border border-gray-300">
                                                                            PENDENTE PCP
                                                                        </span>
                                                                    ) : (
                                                                        <div className="relative group inline-block">
                                                                            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold border cursor-help shadow-sm transition-all duration-250 hover:scale-105 ${
                                                                                marginResult.badgeColor === 'green' ? 'bg-green-100 text-green-800 border-green-300' :
                                                                                marginResult.badgeColor === 'yellow' ? 'bg-yellow-100 text-yellow-800 border-yellow-300' :
                                                                                marginResult.badgeColor === 'orange' ? 'bg-orange-100 text-orange-800 border-orange-300' :
                                                                                'bg-red-100 text-red-800 border-red-300'
                                                                            }`}>
                                                                                {marginResult.formattedMargin}
                                                                            </span>
                                                                            
                                                                            {/* Tooltip Popover "O Extrato" */}
                                                                            <div className="absolute z-[9999] hidden group-hover:block bg-slate-900 text-slate-100 p-4 rounded-xl shadow-2xl min-w-[320px] w-80 text-xs border border-slate-700 -top-2 left-full ml-3 pointer-events-none animate-fade-in">
                                                                                <h4 className="font-bold text-white mb-2 border-b border-slate-700 pb-1 flex items-center justify-between">
                                                                                    <span>📊 Extrato de Margem</span>
                                                                                </h4>
                                                                                <div className="space-y-1 font-sans font-medium">
                                                                                    <div className="flex justify-between py-1">
                                                                                        <span className="text-slate-400">(+) Valor Bruto:</span>
                                                                                        <span className="font-mono text-white">{formatCurrency(marginResult.breakdown.gross)}</span>
                                                                                    </div>
                                                                                    <div className="flex justify-between text-amber-400 py-1">
                                                                                        <span className="text-slate-400">(-) Ajuste VP (Prazo):</span>
                                                                                        <span className="font-mono">-{formatCurrency(marginResult.breakdown.vpDiscount)}</span>
                                                                                    </div>
                                                                                    <div className="flex justify-between border-t border-slate-800 pt-1 pb-1">
                                                                                        <span className="text-slate-400 font-semibold">(=) Valor Presente (VP):</span>
                                                                                        <span className="font-semibold font-mono text-white">{formatCurrency(marginResult.breakdown.vp)}</span>
                                                                                    </div>
                                                                                    <div className="flex justify-between text-red-400 py-1">
                                                                                        <span className="text-slate-400">(-) Impostos (22.25%):</span>
                                                                                        <span className="font-mono">-{formatCurrency(marginResult.breakdown.taxes)}</span>
                                                                                    </div>
                                                                                    {marginResult.breakdown.commission > 0 && (
                                                                                        <div className="flex justify-between text-red-400 py-1">
                                                                                            <span className="text-slate-400">(-) Comissão ({commRate}%):</span>
                                                                                            <span className="font-mono">-{formatCurrency(marginResult.breakdown.commission)}</span>
                                                                                        </div>
                                                                                    )}
                                                                                    {marginResult.breakdown.freight > 0 && (
                                                                                        <div className="flex justify-between text-red-400 py-1">
                                                                                            <span className="text-slate-400">(-) Frete:</span>
                                                                                            <span className="font-mono">-{formatCurrency(marginResult.breakdown.freight)}</span>
                                                                                        </div>
                                                                                    )}
                                                                                    <div className="border-t border-slate-800 my-1"></div>
                                                                                    <div className="flex justify-between text-emerald-400 font-bold py-1">
                                                                                        <span className="text-slate-300">(=) Margem Absoluta:</span>
                                                                                        <span className="font-mono text-white">{formatCurrency(marginResult.breakdown.absoluteMargin)}</span>
                                                                                    </div>
                                                                                    <div className="flex justify-between text-slate-300 py-1">
                                                                                        <span className="text-slate-400">(/) Custo Industrial:</span>
                                                                                        <span className="font-mono text-white">{formatCurrency(marginResult.breakdown.costs)}</span>
                                                                                    </div>
                                                                                    <div className="border-t border-slate-700 pt-1.5 flex justify-between items-center">
                                                                                        <span className="font-bold text-white">Margem Final (%):</span>
                                                                                        <span className={`font-mono text-sm font-bold ${
                                                                                            marginResult.badgeColor === 'green' ? 'text-green-400' :
                                                                                            marginResult.badgeColor === 'yellow' ? 'text-yellow-400' :
                                                                                            marginResult.badgeColor === 'orange' ? 'text-orange-400' :
                                                                                            'text-red-400'
                                                                                        }`}>
                                                                                            {marginResult.formattedMargin}
                                                                                        </span>
                                                                                    </div>
                                                                                </div>
                                                                            </div>
                                                                        </div>
                                                                    )}
                                                                </div>
                                                            )}
                                                        </div>
                                                    );
                                                })()}

                                                {/* Risk Panel (Painel de Risco) - Credit & Terms Gate */}
                                                {(item.block_status || item.balance !== null || item.delay !== null || item.payment_terms) && (
                                                    <div className="mb-4 p-4 bg-yellow-50 border-2 border-yellow-300 rounded-lg">
                                                        <h4 className="text-sm font-bold text-yellow-900 mb-3 flex items-center gap-2">
                                                            <AlertCircle className="w-5 h-5" />
                                                            🚨 Painel de Risco - Gate Financeiro
                                                        </h4>
                                                        <div className="grid grid-cols-2 gap-3">
                                                            {item.block_status && (
                                                                <div className={`p-3 rounded-lg ${
                                                                    item.block_status === 'BLOQUEADO' 
                                                                        ? item.is_replacement
                                                                            ? 'bg-cyan-50 border-2 border-cyan-300'
                                                                            : 'bg-red-100 border-2 border-red-400' 
                                                                        : 'bg-green-100 border border-green-300'
                                                                }`}>
                                                                    <label className="text-xs font-medium text-gray-700">Bloqueio</label>
                                                                    <p className={`text-sm font-bold ${
                                                                        item.block_status === 'BLOQUEADO' 
                                                                            ? item.is_replacement
                                                                                ? 'text-cyan-700'
                                                                                : 'text-red-700' 
                                                                            : 'text-green-700'
                                                                    }`}>
                                                                        {item.block_status === 'BLOQUEADO' && item.is_replacement ? 'LIBERADO (TROCA)' : item.block_status}
                                                                    </p>
                                                                    {item.block_status === 'BLOQUEADO' && (
                                                                        <p className={`text-xs mt-1 ${item.is_replacement ? 'text-cyan-600 font-semibold' : 'text-red-600'}`}>
                                                                            {item.is_replacement ? '✓ Crédito Pré-Aprovado (Troca)' : '⚠️ Intervenção do Financeiro necessária'}
                                                                        </p>
                                                                    )}
                                                                </div>
                                                            )}
                                                            {item.delay !== null && (
                                                                <div className={`p-3 rounded-lg ${item.delay > 0 ? 'bg-orange-100 border-2 border-orange-400' : 'bg-green-100 border border-green-300'}`}>
                                                                    <label className="text-xs font-medium text-gray-700">Dias Atraso</label>
                                                                    <p className={`text-sm font-bold ${item.delay > 0 ? 'text-orange-700' : 'text-green-700'}`}>
                                                                        {item.delay} dias
                                                                    </p>
                                                                </div>
                                                            )}
                                                            {item.payment_terms && (
                                                                <div className="p-3 bg-purple-50 border border-purple-200 rounded-lg">
                                                                    <label className="text-xs font-medium text-gray-700">Condição Pagamento</label>
                                                                    <p className="text-sm font-bold text-purple-700">
                                                                        {String(item.payment_terms || '').replace(/\s*-\s*$/, '')}
                                                                    </p>
                                                                </div>
                                                            )}
                                                        </div>
                                                        {item.block_status === 'BLOQUEADO' && (
                                                            <div className={`mt-3 p-2 border rounded ${item.is_replacement ? 'bg-cyan-50 border-cyan-300' : 'bg-red-50 border-red-300'}`}>
                                                                <p className={`text-xs ${item.is_replacement ? 'text-cyan-800' : 'text-red-800'}`}>
                                                                    {item.is_replacement ? (
                                                                        <>
                                                                            <strong>🔄 BYPASS ATIVO:</strong> Este item foi marcado como Troca/Reposição, liberando o crédito pré-aprovado automaticamente.
                                                                        </>
                                                                    ) : (
                                                                        <>
                                                                            <strong>🔒 GATE ATIVO:</strong> Este pedido está bloqueado e requer aprovação do Financeiro antes de prosseguir.
                                                                        </>
                                                                    )}
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
                                                        ) : (item.block_status === 'BLOQUEADO' && item.is_replacement) ? (
                                                            <div className="flex items-center gap-2 text-cyan-700 bg-cyan-100 px-2 py-0.5 rounded-full font-bold border border-cyan-300">
                                                                <CheckCircle className="w-4 h-4 text-cyan-600 animate-pulse" />
                                                                <span className="text-[10px]">CRÉDITO PRÉ-APROVADO (TROCA)</span>
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

                                                {/* Toggles - 5 flags: Personalizado, Cliente Novo, Exportação, Triangular/Remessa, Mat. Estoque (FF-HARDENING-015) */}
                                                <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
                                                    <label className="flex items-center gap-2 cursor-pointer">
                                                        <input
                                                            type="checkbox"
                                                            checked={item.is_personalized}
                                                            onChange={() => handleTogglePersonalized(item.id)}
                                                            className="w-4 h-4 text-primary-600 rounded focus:ring-primary-500"
                                                        />
                                                        <span className="text-sm font-medium text-gray-700">
                                                            Personalizado?
                                                        </span>
                                                    </label>
                                                    <label className="flex items-center gap-2 cursor-pointer">
                                                        <input
                                                            type="checkbox"
                                                            checked={item.is_new_client}
                                                            onChange={() => handleToggleNewClient(item.id)}
                                                            className="w-4 h-4 text-primary-600 rounded focus:ring-primary-500"
                                                        />
                                                        <span className="text-sm font-medium text-gray-700">
                                                            Cliente Novo?
                                                        </span>
                                                    </label>
                                                    <label className="flex items-center gap-2 cursor-pointer">
                                                        <input
                                                            type="checkbox"
                                                            checked={item.is_export}
                                                            onChange={() => handleToggleExport(item.id)}
                                                            className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                                                        />
                                                        <span className="text-sm font-medium text-gray-700 flex items-center gap-1">
                                                            <Globe className="w-3.5 h-3.5" />
                                                            Exportação?
                                                        </span>
                                                    </label>
                                                    {/* FF-HARDENING-015 Item 3: Triangular/Remessa → routes to BILLING */}
                                                    <label className="flex items-center gap-2 cursor-pointer">
                                                        <input
                                                            type="checkbox"
                                                            checked={item.is_triangular || false}
                                                            onChange={() => handleToggleTriangular(item.id)}
                                                            className="w-4 h-4 text-orange-600 rounded focus:ring-orange-500"
                                                        />
                                                        <span className="text-sm font-medium text-orange-700">
                                                            🔺 Triangular/Remessa
                                                        </span>
                                                    </label>
                                                    {/* FF-HARDENING-015 Item 3: Material de Estoque (e-com) → routes to BILLING */}
                                                    <label className="flex items-center gap-2 cursor-pointer">
                                                        <input
                                                            type="checkbox"
                                                            checked={item.is_estoque || false}
                                                            onChange={() => handleToggleEstoque(item.id)}
                                                            className="w-4 h-4 text-teal-600 rounded focus:ring-teal-500"
                                                        />
                                                        <span className="text-sm font-medium text-teal-700">
                                                            🏭 Mat. Estoque (e-com)
                                                        </span>
                                                    </label>
                                                    {/* UAT-FIX-4: Troca/Reposição checkbox removed — exchange cards are created via Kanban manual card flow */}
                                                </div>

                                                {/* UAT-FIX-4: SLA notice removed with checkbox */}

                                                {/* Detalhes do Item: Vl.Frete, % ICMS, Dt.Faturamento, Vendedor, Vl. IPI, Data do Pedido */}
                                                {/* Dt. Entrega hidden per FF-HARDENING-015 Item 3 */}
                                                <div className="mb-4 p-3.5 bg-gray-50 border border-gray-200 rounded-lg grid grid-cols-2 md:grid-cols-6 gap-4 shadow-3xs animate-fade-in">
                                                    <div>
                                                        <label className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block mb-0.5">Vl. Frete</label>
                                                        <p className="text-xs font-bold text-green-700 font-mono">
                                                            {item.freight !== null && item.freight !== undefined 
                                                                ? formatCurrency(item.freight) 
                                                                : 'R$ 0,00'}
                                                        </p>
                                                    </div>
                                                    <div>
                                                        <label className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block mb-0.5">% ICMS</label>
                                                        <p className="text-xs font-semibold text-gray-800 font-sans">
                                                            {item.icms_percent !== null && item.icms_percent !== undefined 
                                                                ? `${parseFloat(item.icms_percent).toFixed(2)}%` 
                                                                : '0.00%'}
                                                        </p>
                                                    </div>
                                                    <div>
                                                        <label className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block mb-0.5">Dt. Faturamento</label>
                                                        <p className="text-xs font-semibold text-gray-850 font-sans">{formatDate(item.billing_date)}</p>
                                                    </div>
                                                    <div>
                                                        <label className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block mb-0.5">Vendedor</label>
                                                        <p className="text-xs font-semibold text-gray-850 truncate" title={item.salesperson || 'N/A'}>
                                                            {item.salesperson || 'N/A'}
                                                        </p>
                                                    </div>
                                                    <div>
                                                        <label className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block mb-0.5">Vl. IPI</label>
                                                        <p className="text-xs font-bold text-green-700 font-mono">
                                                            {item.ipi !== null && item.ipi !== undefined 
                                                                ? formatCurrency(item.ipi) 
                                                                : 'R$ 0,00'}
                                                        </p>
                                                    </div>
                                                    {/* ONET 2026-07-01: Data do Pedido */}
                                                    {item.order_date && (
                                                        <div>
                                                            <label className="text-[10px] font-bold text-blue-500 uppercase tracking-wider block mb-0.5">Data do Pedido</label>
                                                            <p className="text-xs font-semibold text-blue-800 font-sans">{formatDate(item.order_date)}</p>
                                                        </div>
                                                    )}
                                                </div>

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
                                                    {item.block_status === 'BLOQUEADO' && !item.is_replacement ? (
                                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                                            {/* Twin Action 1: Manter Bloqueio */}
                                                            <button
                                                                type="button"
                                                                onClick={() => {
                                                                    setStagingData(prev => {
                                                                        if (!prev || !prev.po_list || !Array.isArray(prev.po_list)) return prev;
                                                                        return {
                                                                            ...prev,
                                                                            po_list: prev.po_list.map(po => ({
                                                                                ...po,
                                                                                items: Array.isArray(po.items) ? po.items.map(it => {
                                                                                    if (it.id === item.id) {
                                                                                        return {
                                                                                            ...it,
                                                                                            is_checked: !it.is_checked,
                                                                                            extra_metadata: {
                                                                                                ...(it.extra_metadata || {}),
                                                                                                finance_justification: null
                                                                                            }
                                                                                        };
                                                                                    }
                                                                                    return it;
                                                                                }) : []
                                                                            }))
                                                                        };
                                                                    });
                                                                }}
                                                                disabled={hasError}
                                                                className={`flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-semibold transition-all ${
                                                                    hasError
                                                                        ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                                                                        : item.is_checked && !item.extra_metadata?.finance_justification
                                                                            ? 'bg-red-200 text-red-800 border border-red-400 hover:bg-red-300'
                                                                            : 'bg-red-50 text-red-700 border border-red-350 hover:bg-red-100'
                                                                }`}
                                                            >
                                                                {hasError ? (
                                                                    <>
                                                                        <X className="w-4 h-4" />
                                                                        <span>Erros Pendentes</span>
                                                                    </>
                                                                ) : item.is_checked && !item.extra_metadata?.finance_justification ? (
                                                                    <>
                                                                        <Lock className="w-4 h-4" />
                                                                        <span>✓ Bloqueio Mantido</span>
                                                                    </>
                                                                ) : (
                                                                    <>
                                                                        <Lock className="w-4 h-4 text-red-600" />
                                                                        <span>Manter Bloqueio</span>
                                                                    </>
                                                                )}
                                                            </button>

                                                            {/* Twin Action 2: Solicitar Liberação Financeira */}
                                                            <button
                                                                type="button"
                                                                onClick={() => {
                                                                    if (item.is_checked && item.extra_metadata?.finance_justification) {
                                                                        // Desmarcar / clique para desfazer
                                                                        setStagingData(prev => {
                                                                            if (!prev || !prev.po_list || !Array.isArray(prev.po_list)) return prev;
                                                                            return {
                                                                                ...prev,
                                                                                po_list: prev.po_list.map(po => ({
                                                                                    ...po,
                                                                                    items: Array.isArray(po.items) ? po.items.map(it => {
                                                                                        if (it.id === item.id) {
                                                                                            return {
                                                                                                ...it,
                                                                                                is_checked: false,
                                                                                                extra_metadata: {
                                                                                                    ...(it.extra_metadata || {}),
                                                                                                    finance_justification: null
                                                                                                }
                                                                                            };
                                                                                        }
                                                                                        return it;
                                                                                    }) : []
                                                                                }))
                                                                            };
                                                                        });
                                                                    } else {
                                                                        // Solicitar liberação
                                                                        setSelectedFinanceItem(item);
                                                                        setShowFinanceModal(true);
                                                                    }
                                                                }}
                                                                disabled={hasError}
                                                                className={`flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-semibold transition-all ${
                                                                    hasError
                                                                        ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                                                                        : item.is_checked && item.extra_metadata?.finance_justification
                                                                            ? 'bg-emerald-600 text-white hover:bg-emerald-700'
                                                                            : 'bg-amber-500 text-white hover:bg-amber-600'
                                                                }`}
                                                            >
                                                                {hasError ? (
                                                                    <>
                                                                        <X className="w-4 h-4" />
                                                                        <span>Erros Pendentes</span>
                                                                    </>
                                                                ) : item.is_checked && item.extra_metadata?.finance_justification ? (
                                                                    <>
                                                                        <Unlock className="w-4 h-4 text-white" />
                                                                        <span>✓ Liberação Solicitada</span>
                                                                    </>
                                                                ) : (
                                                                    <>
                                                                        <DollarSign className="w-4 h-4 text-white" />
                                                                        <span>Solicitar Liberação</span>
                                                                    </>
                                                                )}
                                                            </button>
                                                        </div>
                                                    ) : (
                                                        <button
                                                            onClick={() => handleToggleChecked(item.id)}
                                                            disabled={hasError}
                                                            className={`w-full flex items-center justify-center gap-3 px-4 py-3 rounded-lg font-semibold transition-all ${hasError
                                                                ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                                                                : item.is_checked
                                                                    ? item.is_replacement
                                                                        ? 'bg-cyan-600 text-white hover:bg-cyan-700 shadow-md'
                                                                        : 'bg-green-600 text-white hover:bg-green-700 shadow-md'
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
                                                    )}
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
                                    onClick={() =>
                                        setCancelImportJustification('') || setShowCancelImportModal(true)
                                    }
                                    disabled={!stagingData}
                                    className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-semibold transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                                    title="Cancelar o pedido atual e removê-lo da fila de conferência"
                                >
                                    <Ban className="w-4 h-4" />
                                    Cancelar PO
                                </button>
                                <button
                                    onClick={handleConfirmPO}
                                    disabled={!canCommit()}
                                    className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
                                    title={!canCommit() ? 'Confira todos os itens, selecione embalagem e unidade de negócio antes de confirmar' : 'Confirmar todos os pedidos'}
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
                    status="Staging"
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
                    submitting={financeSubmitting}
                    onApprove={(justification) => {
                        // In staging/local mode, we don't call the API.
                        // Perform a purely local state update:
                        setStagingData(prev => {
                            if (!prev || !prev.po_list || !Array.isArray(prev.po_list)) return prev;
                            const updatedPoList = prev.po_list.map((po, idx) => {
                                if (idx !== selectedPOIndex) return po;
                                return {
                                    ...po,
                                    items: (po.items || []).map(it =>
                                        it.id === selectedFinanceItem.id
                                            ? {
                                                  ...it,
                                                  is_checked: true,
                                                  extra_metadata: {
                                                      ...(it.extra_metadata || {}),
                                                      finance_justification: justification
                                                  }
                                              }
                                            : it
                                    )
                                };
                            });
                            return { ...prev, po_list: updatedPoList };
                        });
                        showSuccess(`✅ Liberação financeira registrada localmente para o item ${selectedFinanceItem.sku || ''}`);
                        setShowFinanceModal(false);
                        setSelectedFinanceItem(null);
                        setFinanceJustification('');
                    }}
                    onReject={(justification) => {
                        // In staging/local mode, reject clears justification and sets is_checked = false
                        setStagingData(prev => {
                            if (!prev || !prev.po_list || !Array.isArray(prev.po_list)) return prev;
                            const updatedPoList = prev.po_list.map((po, idx) => {
                                if (idx !== selectedPOIndex) return po;
                                return {
                                    ...po,
                                    items: (po.items || []).map(it =>
                                        it.id === selectedFinanceItem.id
                                            ? {
                                                  ...it,
                                                  is_checked: false,
                                                  extra_metadata: {
                                                      ...(it.extra_metadata || {}),
                                                      finance_justification: null
                                                  }
                                              }
                                            : it
                                    )
                                };
                            });
                            return { ...prev, po_list: updatedPoList };
                        });
                        showSuccess(`❌ Liberação financeira rejeitada localmente.`);
                        setShowFinanceModal(false);
                        setSelectedFinanceItem(null);
                        setFinanceJustification('');
                    }}
                    onClose={() => {
                        setShowFinanceModal(false);
                        setSelectedFinanceItem(null);
                        setFinanceJustification('');
                    }}
                />
            )}

            {/* FF-HARDENING-012.1 [Item 1]: Cancel PO Confirmation Modal (Mesa de Conferência) */}
            {showCancelImportModal && currentPO && (
                <div className="fixed inset-0 bg-black bg-opacity-60 flex items-center justify-center z-50 p-4">
                    <div className="bg-white rounded-xl shadow-2xl max-w-md w-full mx-4 overflow-hidden">
                        {/* Header */}
                        <div className="bg-red-600 px-6 py-4 flex items-center gap-3">
                            <span className="text-2xl">🚫</span>
                            <div>
                                <h3 className="text-lg font-bold text-white">Cancelar Pedido</h3>
                                <p className="text-red-200 text-xs font-medium">PO: {currentPO.po_number}</p>
                            </div>
                        </div>

                        {/* Body */}
                        <div className="p-6">
                            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
                                <p className="text-xs text-red-800 font-semibold">
                                    ⚠️ <strong>Atenção:</strong> O pedido será removido da fila de conferência e marcado como <strong>CANCELADO</strong>. Essa ação é irreversível.
                                </p>
                            </div>

                            <label className="block text-xs font-bold text-gray-700 uppercase mb-2">
                                Justificativa de Cancelamento <span className="text-red-500">*</span>
                                <span className="text-gray-400 font-normal lowercase ml-1">(mínimo 10 caracteres)</span>
                            </label>
                            <textarea
                                value={cancelImportJustification}
                                onChange={(e) => setCancelImportJustification(e.target.value)}
                                placeholder="Ex: Pedido duplicado, cliente solicitou cancelamento, erro de importação..."
                                rows={4}
                                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-red-500 focus:outline-none text-gray-800 font-medium resize-none"
                                autoFocus
                            />
                            {cancelImportJustification.trim().length > 0 && cancelImportJustification.trim().length < 10 && (
                                <p className="text-xs text-red-600 mt-1 font-semibold">
                                    {10 - cancelImportJustification.trim().length} caractere(s) restante(s)
                                </p>
                            )}
                        </div>

                        {/* Footer */}
                        <div className="bg-gray-50 px-6 py-4 flex justify-end gap-3 border-t border-gray-200">
                            <button
                                onClick={() => {
                                    setShowCancelImportModal(false);
                                    setCancelImportJustification('');
                                }}
                                disabled={cancellingImport}
                                className="px-4 py-2 bg-gray-300 text-gray-700 text-sm font-semibold rounded-lg hover:bg-gray-400 transition-colors disabled:opacity-50"
                            >
                                Voltar
                            </button>
                            <button
                                onClick={async () => {
                                    if (cancelImportJustification.trim().length < 10) return;
                                    setCancellingImport(true);
                                    try {
                                        // If the PO already has a DB id, call the Kanban cancel endpoint
                                        if (currentPO.id) {
                                            await api.post(`/kanban/pos/${currentPO.id}/cancel`, {
                                                justification: cancelImportJustification.trim()
                                            });
                                        } else {
                                            // Bug 2 fix: PO exists only in staging memory (not yet in DB).
                                            // Persist it as CANCELLED so it appears in the cancellations report.
                                            await api.post('/import/cancel-staging', {
                                                po_number: currentPO.po_number,
                                                client_name: currentPO.client_name || null,
                                                po_total_value: currentPO.po_total_value != null
                                                    ? Number(currentPO.po_total_value) : null,
                                                justification: cancelImportJustification.trim(),
                                                items: (currentPO.items || []).map(item => ({
                                                    sku: item.sku || 'N/A',
                                                    quantity: Number(item.quantity) || 1,
                                                    price: Number(item.unit_value ?? item.price_unit) || 0,
                                                    codigo_estruturado: item.codigo_estruturado || null,
                                                    largura: item.width ?? item.largura ?? null,
                                                    comprimento: item.length ?? item.comprimento ?? null,
                                                }))
                                            });
                                        }
                                        // Remove this PO from the staging list regardless
                                        setStagingData(prev => {
                                            if (!prev || !prev.po_list) return prev;
                                            const updatedList = prev.po_list.filter((_, idx) => idx !== selectedPOIndex);
                                            if (updatedList.length === 0) return null; // All POs cancelled — clear staging
                                            return {
                                                ...prev,
                                                po_list: updatedList,
                                                total_pos: updatedList.length
                                            };
                                        });
                                        // Adjust selected index
                                        setSelectedPOIndex(prev => Math.max(0, prev > 0 ? prev - 1 : 0));
                                        setCurrentPage(1);
                                        showSuccess(`✅ Pedido ${currentPO.po_number} cancelado e removido da fila.`);
                                        setShowCancelImportModal(false);
                                        setCancelImportJustification('');
                                    } catch (err) {
                                        showError(err.response?.data?.detail || 'Erro ao cancelar pedido');
                                    } finally {
                                        setCancellingImport(false);
                                    }
                                }}
                                disabled={cancelImportJustification.trim().length < 10 || cancellingImport}
                                className={`px-4 py-2 text-sm font-bold rounded-lg transition-colors ${
                                    cancelImportJustification.trim().length >= 10 && !cancellingImport
                                        ? 'bg-red-600 hover:bg-red-700 text-white'
                                        : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                                }`}
                            >
                                {cancellingImport ? 'Cancelando...' : '🚫 Confirmar Cancelamento'}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* S3 Sync Modal */}
            {showS3Modal && (
                <div className="fixed inset-0 bg-slate-900 bg-opacity-50 backdrop-blur-xs flex items-center justify-center z-[9999] p-4 animate-fade-in">
                    <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl overflow-hidden flex flex-col max-h-[85vh] border border-slate-200">
                        {/* Header */}
                        <div className="bg-slate-50 px-6 py-4 border-b border-slate-200 flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <Cloud className="w-5 h-5 text-blue-600 animate-pulse" />
                                <h3 className="text-lg font-bold text-slate-800">Sincronizar com ONET (Nuvem)</h3>
                            </div>
                            <button 
                                onClick={() => setShowS3Modal(false)}
                                className="text-slate-400 hover:text-slate-600 hover:bg-slate-100 p-1.5 rounded-lg transition-all"
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>
                        
                        {/* Body */}
                        <div className="p-6 overflow-y-auto flex-1">
                            {fetchingS3Files ? (
                                <div className="flex flex-col items-center justify-center py-12 gap-3">
                                    <div className="w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
                                    <span className="text-sm font-medium text-slate-600">Buscando arquivos pendentes no S3...</span>
                                </div>
                            ) : s3Files.length === 0 ? (
                                <div className="text-center py-12">
                                    <Package className="w-12 h-12 text-slate-400 mx-auto mb-3" />
                                    <h4 className="font-semibold text-slate-700 mb-1">Nenhum arquivo novo encontrado</h4>
                                    <p className="text-sm text-slate-500">O bucket do ONET está atualizado.</p>
                                </div>
                            ) : (
                                <div className="space-y-4">
                                    <div className="flex items-center justify-between bg-slate-50 p-3 rounded-lg border border-slate-200">
                                        <label className="flex items-center gap-2 cursor-pointer text-slate-700 font-semibold text-sm">
                                            <input 
                                                type="checkbox"
                                                checked={selectedS3Files.length === s3Files.length}
                                                onChange={(e) => {
                                                    if (e.target.checked) {
                                                        setSelectedS3Files(s3Files.map(f => f.filename))
                                                    } else {
                                                        setSelectedS3Files([])
                                                    }
                                                }}
                                                className="w-4 h-4 rounded text-blue-600 border-slate-300 focus:ring-blue-500"
                                            />
                                            Selecionar Todos ({s3Files.length})
                                        </label>
                                        <span className="text-xs text-slate-500 font-medium">
                                            {selectedS3Files.length} selecionado(s)
                                        </span>
                                    </div>
                                    
                                    <div className="border border-slate-200 rounded-lg overflow-hidden">
                                        <table className="w-full text-left text-sm border-collapse">
                                            <thead>
                                                <tr className="bg-slate-50 text-slate-600 uppercase font-semibold text-xs border-b border-slate-200">
                                                    <th className="px-4 py-3 w-10">Select</th>
                                                    <th className="px-4 py-3">Arquivo</th>
                                                    <th className="px-4 py-3">Data Ref</th>
                                                    <th className="px-4 py-3">Tamanho</th>
                                                    <th className="px-4 py-3">Status</th>
                                                </tr>
                                            </thead>
                                            <tbody className="divide-y divide-slate-100 text-slate-700 font-medium">
                                                {s3Files.map((file) => (
                                                    <tr 
                                                        key={file.filename}
                                                        className={`hover:bg-slate-50 transition-colors ${file.is_empty_template ? 'bg-slate-50/50' : ''}`}
                                                    >
                                                        <td className="px-4 py-3">
                                                            <input 
                                                                type="checkbox"
                                                                checked={selectedS3Files.includes(file.filename)}
                                                                onChange={(e) => {
                                                                    if (e.target.checked) {
                                                                        setSelectedS3Files(prev => [...prev, file.filename])
                                                                    } else {
                                                                        setSelectedS3Files(prev => prev.filter(name => name !== file.filename))
                                                                    }
                                                                }}
                                                                className="w-4 h-4 rounded text-blue-600 border-slate-300 focus:ring-blue-500"
                                                            />
                                                        </td>
                                                        <td className="px-4 py-3 font-mono text-xs max-w-[200px] truncate" title={file.filename}>
                                                            {file.filename}
                                                        </td>
                                                        <td className="px-4 py-3 text-slate-600">
                                                            {file.parsed_date}
                                                        </td>
                                                        <td className="px-4 py-3 text-slate-500">
                                                            {(file.size_bytes / 1024).toFixed(1)} KB
                                                        </td>
                                                        <td className="px-4 py-3">
                                                            {file.is_empty_template ? (
                                                                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-gray-100 text-gray-700 border border-gray-300">
                                                                    Vazio - Final de Semana
                                                                </span>
                                                            ) : (
                                                                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-green-100 text-green-700 border border-green-200">
                                                                    Possui Dados
                                                                </span>
                                                            )}
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            )}
                        </div>
                        
                        {/* Footer */}
                        <div className="bg-slate-50 px-6 py-4 border-t border-slate-200 flex justify-end gap-3">
                            <button 
                                onClick={() => setShowS3Modal(false)}
                                className="px-4 py-2 border border-slate-300 text-slate-700 rounded-lg hover:bg-slate-100 font-semibold transition-colors"
                                disabled={syncing}
                            >
                                Cancelar
                            </button>
                            <button 
                                onClick={handleConfirmS3Import}
                                disabled={syncing || selectedS3Files.length === 0 || fetchingS3Files}
                                className="flex items-center gap-2 px-5 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed font-semibold"
                            >
                                {syncing ? (
                                    <>
                                        <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                                        <span>Importando...</span>
                                    </>
                                ) : (
                                    <>
                                        <Cloud className="w-5 h-5" />
                                        <span>Confirmar e Importar</span>
                                    </>
                                )}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}

export default ImportPage
