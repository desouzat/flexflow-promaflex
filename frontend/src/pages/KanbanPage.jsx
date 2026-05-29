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
    ArrowUpRight, ShieldAlert, ChevronLeft, ChevronRight, Split, Paperclip
} from 'lucide-react'

const KanbanPage = () => {
    const getRobustName = (val) => {
        if (!val || val === 'null' || val === 'None' || String(val).trim() === '') {
            return 'Desconhecido';
        }
        return val;
    };

    const getDownloadUrl = (path) => {
        const cleanPath = (path || '').replace(/^\//, '');
        const baseUrl = (import.meta.env.VITE_API_URL || 'http://localhost:8000/api').replace(/\/api$/, '');
        const generated = `${baseUrl}/api/uploads/download?path=${encodeURIComponent(cleanPath)}`;
        console.log("[FlexFlow Download Link] Generated path for download:", generated);
        return generated;
    };

    const [boardData, setBoardData] = useState(null)
    const [openSKUs, setOpenSKUs] = useState({})
    const toggleSKU = (skuId) => {
        setOpenSKUs(prev => ({ ...prev, [skuId]: !prev[skuId] }));
    }
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const [searchTerm, setSearchTerm] = useState('')
    const [compactView, setCompactView] = useState(false)
    const [selectedPO, setSelectedPO] = useState(null)
    const [isDetailsOpen, setIsDetailsOpen] = useState(false)
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
    const [checklistFinanceiro, setChecklistFinanceiro] = useState({
        margem_comissoes_validadas: false,
        nfe_chave_conferidas: false,
        evidencias_fotograficas_verificadas: false
    })

    const isPOBlocked = selectedPO ? (
        selectedPO.block_status === 'BLOQUEADO' || 
        selectedPO.extra_metadata?.block_status === 'BLOQUEADO' || 
        selectedPO.status_macro === 'ANALISE_CREDITO' || 
        (selectedPO.items && selectedPO.items.some(item => 
            item.block_status === 'BLOQUEADO' || 
            item.extra_metadata?.block_status === 'BLOQUEADO'
        ))
    ) : false;
    
    const handleFinanceiroChecklistChange = (field, checked) => {
        setChecklistFinanceiro(prev => ({
            ...prev,
            [field]: checked
        }))
    }

    const getRobustImpediment = () => {
        if (!selectedPO) return '';
        const meta = selectedPO.extra_metadata || {};
        const impediment = meta.production_impediment || '';
        if (!impediment && meta.priority_note) {
            return typeof meta.priority_note === 'string' ? meta.priority_note : (meta.priority_note.text || '');
        }
        return impediment;
    }

    const getFinanceiroMissingFieldsTooltip = () => {
        const missing = [];
        if (!checklistFinanceiro.margem_comissoes_validadas) missing.push('validar margem e comissões');
        if (!checklistFinanceiro.nfe_chave_conferidas) missing.push('conferir NF-e');
        if (!checklistFinanceiro.evidencias_fotograficas_verificadas) missing.push('verificar evidências fotográficas');
        
        const commentLen = (localFields.audit_comment || '').trim().length;
        if (commentLen < 20) {
            missing.push(`faltam ${20 - commentLen} caracteres no parecer`);
        }
        
        if (missing.length === 0) return '';
        const joined = missing.join(', ');
        return joined.charAt(0).toUpperCase() + joined.slice(1);
    }

    const [showReturnModal, setShowReturnModal] = useState(false)
    const [returnLabel, setReturnLabel] = useState('')
    const [returnReasonText, setReturnReasonText] = useState('')
    const [returnReason, setReturnReason] = useState('')
    const [showPartitionModal, setShowPartitionModal] = useState(false)
    const [partitionReason, setPartitionReason] = useState('')
    const [newDeliveryDate, setNewDeliveryDate] = useState('')
    const [qtySplits, setQtySplits] = useState({})
    const [showFreightModal, setShowFreightModal] = useState(false)
    const [freightC1, setFreightC1] = useState('')
    const [freightC2, setFreightC2] = useState('')
    const [pauseTicks, setPauseTicks] = useState(0)
    const [handoffHistory, setHandoffHistory] = useState(null)
    const [showLinkCostModal, setShowLinkCostModal] = useState(false)
    const [linkingItem, setLinkingItem] = useState(null)
    const [searchQuery, setSearchQuery] = useState('')
    const [searchResults, setSearchResults] = useState([])
    const [costForm, setCostForm] = useState({
        sku: '',
        nome: '',
        custo_mp_kg: '',
        rendimento: '',
        indice_impostos: '22.25'
    })
    const [loadingSearchResults, setLoadingSearchResults] = useState(false)
    const [savingCost, setSavingCost] = useState(false)

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
            
            // Auto-refresh active selectedPO to instantly update item link states/margins
            if (selectedPO) {
                let foundPO = null;
                if (response.data && Array.isArray(response.data.columns)) {
                    for (const col of response.data.columns) {
                        if (Array.isArray(col.pos)) {
                            const match = col.pos.find(p => p.id === selectedPO.id);
                            if (match) {
                                foundPO = match;
                                break;
                            }
                        }
                    }
                }
                if (foundPO) {
                    setSelectedPO(foundPO);
                }
            }
        } catch (err) {
            const errorMsg = err.response?.data?.detail || 'Falha ao carregar o quadro Kanban'
            setError(errorMsg)
            showError(errorMsg)
            console.error('Error fetching board:', err)
        } finally {
            setLoading(false)
        }
    }

    const handleOpenLinkCost = async (item) => {
        setLinkingItem(item)
        setShowLinkCostModal(true)
        setSearchQuery('')
        setSearchResults([])
        
        // Default form values
        const defaultName = item.product_description || item.description || item.extra_metadata?.description || item.nome || '';
        setCostForm({
            sku: item.sku || '',
            nome: defaultName,
            custo_mp_kg: '',
            rendimento: '',
            indice_impostos: '22.25'
        })
        
        // Auto-fetch if this SKU already has material costs configured
        try {
            setLoadingSearchResults(true)
            const checkRes = await api.get(`/costs/materials?sku=${encodeURIComponent(item.sku)}`)
            const exactMatch = (checkRes.data?.items || []).find(it => it.sku.toLowerCase() === item.sku.toLowerCase())
            if (exactMatch) {
                setCostForm({
                    sku: exactMatch.sku,
                    nome: exactMatch.nome,
                    custo_mp_kg: exactMatch.custo_mp_kg.toString(),
                    rendimento: exactMatch.rendimento.toString(),
                    indice_impostos: exactMatch.indice_impostos.toString()
                })
            }
        } catch (err) {
            console.error("Error auto-fetching material cost:", err)
        } finally {
            setLoadingSearchResults(false)
        }
    }

    const handleSearchMaterials = async (query) => {
        setSearchQuery(query)
        if (!query.trim()) {
            setSearchResults([])
            return
        }
        try {
            setLoadingSearchResults(true)
            const response = await api.get(`/costs/materials?sku=${encodeURIComponent(query)}`)
            setSearchResults(response.data?.items || [])
        } catch (err) {
            console.error('Error searching materials:', err)
        } finally {
            setLoadingSearchResults(false)
        }
    }

    const handleSelectMaterial = (mat) => {
        setCostForm({
            sku: mat.sku,
            nome: mat.nome,
            custo_mp_kg: mat.custo_mp_kg.toString(),
            rendimento: mat.rendimento.toString(),
            indice_impostos: mat.indice_impostos.toString()
        })
        setSearchResults([])
        setSearchQuery('')
    }

    const handleCostFormChange = (field, val) => {
        let cleaned = val ? val.replace(',', '.') : ''
        if (['custo_mp_kg', 'rendimento', 'indice_impostos'].includes(field)) {
            // Allow decimals (e.g. "0.", "0.05") but prevent "05", "00" etc.
            if (cleaned.startsWith('0') && cleaned.length > 1 && cleaned[1] !== '.') {
                cleaned = cleaned.replace(/^0+/, '')
                if (cleaned === '') cleaned = '0'
            }
        }
        setCostForm(prev => ({ ...prev, [field]: cleaned }))
    }

    const handleSaveCostLink = async (e) => {
        e.preventDefault()
        if (!costForm.sku || !costForm.nome || !costForm.custo_mp_kg || !costForm.rendimento) {
            showError('Por favor, preencha todos os campos obrigatórios.')
            return
        }
        
        try {
            setSavingCost(true)
            
            // Check if SKU exists to determine if we should POST (create) or PUT (update)
            let exists = false
            try {
                const checkRes = await api.get(`/costs/materials?sku=${encodeURIComponent(costForm.sku)}`)
                exists = (checkRes.data?.items || []).some(item => item.sku.toLowerCase() === costForm.sku.toLowerCase())
            } catch (err) {
                console.log("SKU check failed, assuming create", err)
            }
            
            const payload = {
                sku: costForm.sku,
                nome: costForm.nome,
                custo_mp_kg: parseFloat(String(costForm.custo_mp_kg).replace(',', '.')),
                rendimento: parseFloat(String(costForm.rendimento).replace(',', '.')),
                indice_impostos: parseFloat(String(costForm.indice_impostos || '22.25').replace(',', '.'))
            }
            
            if (exists) {
                await api.put(`/costs/materials/${encodeURIComponent(costForm.sku)}`, payload)
                showSuccess('Custo do material atualizado com sucesso!')
            } else {
                await api.post(`/costs/materials`, payload)
                showSuccess('Custo do material vinculado com sucesso!')
            }
            
            // Auto refresh
            await fetchBoard()
            
            if (selectedPO) {
                try {
                    const poRes = await api.get(`/kanban/pos/${selectedPO.id}`)
                    setSelectedPO(poRes.data)
                } catch (e) {
                    console.error("Failed to refresh selected PO", e)
                }
            }
            
            setShowLinkCostModal(false)
            setLinkingItem(null)
        } catch (err) {
            const errorMsg = err.response?.data?.detail || 'Falha ao salvar custo de material'
            showError(errorMsg)
            console.error('Error saving material cost:', err)
        } finally {
            setSavingCost(false)
        }
    }

    const handleNukeTenantData = async () => {
        if (!window.confirm("ATENÇÃO: Isso apagará TODOS os pedidos deste cliente permanentemente. Deseja continuar?")) {
            return;
        }

        try {
            setLoading(true);
            const response = await api.post('/kanban/admin/nuke-tenant-data');
            if (response.data.success) {
                showSuccess("Banco de dados higienizado com sucesso!");
                setBoardData({
                    columns: (boardData?.columns || []).map(col => ({
                        ...col,
                        pos: [],
                        count: 0
                    })),
                    total_pos: 0,
                    total_items: 0,
                    margin_global: 0,
                    margin_percentage: 0
                });
                refreshNotifications();
            } else {
                showError("Erro inesperado ao higienizar banco.");
            }
        } catch (err) {
            console.error('Error nuking tenant data:', err);
            const errorMsg = err.response?.data?.detail || 'Erro ao higienizar banco de dados.';
            showError(errorMsg);
        } finally {
            setLoading(false);
        }
    }

    useEffect(() => {
        fetchBoard()
        
        // Auto-sync: Trigger a re-fetch of the board when the window recovers focus
        const handleFocus = () => {
            console.log('Window focused, triggering auto-sync...');
            fetchBoard();
        };
        window.addEventListener('focus', handleFocus);
        return () => {
            window.removeEventListener('focus', handleFocus);
        };
    }, [])

    // Ticking interval for live pause counter
    useEffect(() => {
        if (!selectedPO?.sla_paused_at) return;
        const interval = setInterval(() => {
            setPauseTicks(prev => prev + 1);
        }, 1000);
        return () => clearInterval(interval);
    }, [selectedPO?.sla_paused_at]);

    // Add escape key handler for modals
    useEffect(() => {
        const handleEscape = (e) => {
            if (e.key === 'Escape') {
                if (showDetailsModal) {
                    handleCloseModal();
                } else if (showReturnModal) {
                    setShowReturnModal(false);
                    setReturnLabel('');
                    setReturnReasonText('');
                    setReturnReason('');
                } else if (showPartitionModal) {
                    setShowPartitionModal(false);
                    setPartitionReason('');
                    setQtySplits({});
                } else if (showFreightModal) {
                    setShowFreightModal(false);
                    setFreightC1('');
                    setFreightC2('');
                }
            }
        };

        document.addEventListener('keydown', handleEscape);
        return () => document.removeEventListener('keydown', handleEscape);
    }, [showDetailsModal, showReturnModal, showPartitionModal, showFreightModal]);

    useEffect(() => {
        if (selectedPO) {
            const meta = selectedPO.extra_metadata || {}
            let impediment = meta.production_impediment || ''
            if (!impediment && meta.priority_note) {
                impediment = typeof meta.priority_note === 'string' ? meta.priority_note : (meta.priority_note.text || '')
            }
            setLocalFields({
                ...meta,
                production_impediment: impediment
            })
            if (meta.logistics_checklist) {
                setLogisticsChecklist(meta.logistics_checklist)
            } else {
                setLogisticsChecklist({
                    endereco_conferido: false,
                    peso_validado: false,
                    etiquetas_impressas: false,
                    foto_carga_path: null,
                    foto_canhoto_path: null
                })
            }
        } else {
            setLocalFields({})
            setLogisticsChecklist({
                endereco_conferido: false,
                peso_validado: false,
                etiquetas_impressas: false,
                foto_carga_path: null,
                foto_canhoto_path: null
            })
        }
    }, [selectedPO])

    const handleChangeLocalField = (key, value) => {
        let processedValue = value;
        if (typeof value === 'string' && /^0\d+/.test(value)) {
            processedValue = value.replace(/^0+/, '');
        }
        setLocalFields(prev => ({ ...prev, [key]: processedValue }))
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
        setIsDetailsOpen(false) // Accordion state: Ensure the 'Detalhe do Pedido' accordion defaults to CLOSED so the modal looks clean upon opening.
        setShowDetailsModal(true)
        setHandoffHistory(null)

        // Fetch up-to-date PO details from database to ensure fresh fields (like shipping_cost) are loaded
        try {
            const poResponse = await api.get(`/kanban/pos/${po.id}`)
            setSelectedPO(poResponse.data)
        } catch (err) {
            console.error('Error fetching PO details:', err)
        }

        // Reset Financeiro checklist
        setChecklistFinanceiro({
            margem_comissoes_validadas: false,
            nfe_chave_conferidas: false,
            evidencias_fotograficas_verificadas: false
        })

        // Load handoff history & SLA data
        try {
            const response = await api.get(`/kanban/pos/${po.id}/handoff-history`)
            setHandoffHistory(response.data)
        } catch (err) {
            console.error('Error loading handoff history:', err)
            setHandoffHistory({ handoff_history: [], transitions: [] })
        }

        // Load logistics checklist (always query to make it available for Financeiro audit)
        try {
            const response = await api.get(`/kanban/pos/${po.id}/logistics-checklist`)
            setLogisticsChecklist(response.data.checklist)
        } catch (err) {
            console.error('Error loading logistics checklist:', err)
            setLogisticsChecklist({
                endereco_conferido: false,
                peso_validado: false,
                etiquetas_impressas: false,
                foto_carga_path: null,
                foto_canhoto_path: null
            })
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

            setSelectedPO(prev => {
                if (!prev) return prev;
                return {
                    ...prev,
                    partition_metadata: {
                        ...(prev.partition_metadata || {}),
                        logistics_checklist: updatedChecklist
                    }
                };
            });
            fetchBoard();

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
            const uploadResponse = await api.post('/import/upload-attachment', formData, {
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

            setSelectedPO(prev => {
                if (!prev) return prev;
                return {
                    ...prev,
                    partition_metadata: {
                        ...(prev.partition_metadata || {}),
                        logistics_checklist: updatedChecklist
                    }
                };
            });
            fetchBoard();

            showSuccess(`${field === 'foto_carga_path' ? 'Foto da Carga' : 'Nota Fiscal com Canhoto Assinado'} enviada com sucesso`)

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

    const handleArchivePO = async () => {
        if (!selectedPO) return

        try {
            setSavingFields(true)
            const response = await api.post(`/kanban/pos/${selectedPO.id}/archive`, {
                audit_comment: (localFields.audit_comment || '').trim()
            })
            showSuccess(response.data.message)
            await fetchBoard() // Refresh board data
            refreshNotifications() // Refresh notifications
            handleCloseModal()
        } catch (err) {
            const errorMsg = err.response?.data?.detail?.message || err.response?.data?.detail || 'Falha ao finalizar e arquivar pedido'
            showError(errorMsg)
            console.error('Error archiving PO:', err)
        } finally {
            setSavingFields(false)
        }
    }

    const handleReturnStatus = async () => {
        if (!returnLabel) {
            showError('Selecione um motivo de devolução da lista')
            return
        }
        if (!returnReasonText || returnReasonText.trim().length < 10) {
            showError('A explicação adicional deve ter pelo menos 10 caracteres')
            return
        }

        const fullReason = `${returnLabel} ${returnReasonText.trim()}`

        try {
            // FIXED: Send po_id and reason as query parameters with proper encoding
            const response = await api.post(
                `/kanban/return-status?po_id=${encodeURIComponent(selectedPO.id)}&reason=${encodeURIComponent(fullReason)}`
            )
            showSuccess(response.data.message)
            setShowReturnModal(false)
            setReturnLabel('')
            setReturnReasonText('')
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

        if (!newDeliveryDate) {
            showError('Nova data de entrega prevista é obrigatória')
            return
        }

        // Validate splits sum up to parent quantity exactly for each item
        const payloadQtySplits = {};
        for (const item of selectedPO.items || []) {
            const split = qtySplits[item.id] || [Math.ceil(item.quantity / 2), item.quantity - Math.ceil(item.quantity / 2)];
            if (split[0] + split[1] !== item.quantity) {
                showError(`A soma das partições do item ${item.sku} deve ser igual a ${item.quantity}`);
                return;
            }
            payloadQtySplits[item.id] = split;
        }

        try {
            const response = await api.post(
                `/kanban/suggest-partition`,
                {
                    po_id: selectedPO.id,
                    reason: partitionReason,
                    qty_splits: payloadQtySplits,
                    new_delivery_date: newDeliveryDate
                }
            )
            showSuccess(`Sugestão enviada. Se aprovado, o C1 manterá a data original e o C2 assumirá a data ${formatDate(newDeliveryDate)}.`)
            setShowPartitionModal(false)
            setPartitionReason('')
            setNewDeliveryDate('')
            setQtySplits({})
            fetchBoard()
            handleCloseModal()
        } catch (err) {
            const errorMsg = err.response?.data?.detail || 'Falha ao sugerir partição'
            showError(errorMsg)
            console.error('Error suggesting partition:', err)
        }
    }

    const mapStatusToStageName = (status) => {
        if (!status) return 'Comercial';
        const statusMap = {
            'Comercial': 'Comercial',
            'PCP': 'PCP',
            'Produção/Embalagem': 'Produção/Embalagem',
            'Faturamento/Expedição': 'Faturamento/Expedição',
            'Financeiro': 'Financeiro',
            'Concluídos': 'Concluídos',
            'SUBMITTED': 'Comercial',
            'APPROVED': 'PCP',
            'MANUFACTURING': 'Produção/Embalagem',
            'SHIPPING': 'Faturamento/Expedição',
            'FINANCE': 'Financeiro',
            'DRAFT': 'Comercial',
            'WAITING_COMMERCIAL_PARTITION': 'Comercial',
            'PARTITION_REQUESTED': 'Comercial',
            'WAITING_MATERIAL': 'PCP',
            'ARCHIVED_PARTITIONED': 'Concluídos',
            'ARCHIVED': 'Concluídos',
            'COMPLETED': 'Concluídos'
        };
        const upper = String(status).toUpperCase();
        return statusMap[status] || statusMap[upper] || status || 'Comercial';
    };

    const getNextStatus = (currentStatus) => {
        const mapped = mapStatusToStageName(currentStatus)
        const statusFlow = {
            'Comercial': 'PCP',
            'PCP': 'Produção/Embalagem',
            'Produção/Embalagem': 'Faturamento/Expedição',
            'Faturamento/Expedição': 'Concluídos',
            'Financeiro': 'Concluídos',
            'Concluídos': null
        }
        return statusFlow[mapped] || null
    }

    const getPreviousStatus = (currentStatus) => {
        const mapped = mapStatusToStageName(currentStatus)
        const statusFlow = {
            'PCP': 'Comercial',
            'Produção/Embalagem': 'PCP',
            'Faturamento/Expedição': 'Produção/Embalagem',
            'Financeiro': 'Faturamento/Expedição',
            'Concluídos': 'Faturamento/Expedição'
        }
        return statusFlow[mapped] || null
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
        return ['admin', 'master'].includes((user?.role || '').toLowerCase())
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
            
            return (
                (statusProd === 'Finalizado' || statusProd === 'FINISH' || statusProd === 'Concluído') &&
                !isNaN(qReal) && qReal > 0
            )
        }

        if (selectedPO.status === 'Faturamento/Expedição') {
            const nfe = meta.numero_nfe || ''
            const carrier = meta.transportadora || ''
            
            const checklistDone = 
                logisticsChecklist.endereco_conferido &&
                logisticsChecklist.peso_validado &&
                logisticsChecklist.etiquetas_impressas &&
                logisticsChecklist.foto_carga_path &&
                logisticsChecklist.foto_canhoto_path

            return nfe !== '' && carrier !== '' && checklistDone
        }

        if (selectedPO.status === 'Financeiro') {
            const comment = meta.audit_comment || ''
            return comment.trim().length > 0
        }

        return true
    }

    const getMissingFieldsTooltip = () => {
        if (!selectedPO) return '';
        const meta = selectedPO.extra_metadata || {};
        const missing = [];

        if (selectedPO.status === 'PCP') {
            const packaging = meta.packaging_type || '';
            const deliveryDate = meta.data_programada || selectedPO.expected_delivery_date || '';
            if (packaging === '') missing.push('Tipo de Embalagem');
            if (deliveryDate === '') missing.push('Data Programada');
        }

        if (selectedPO.status === 'Produção/Embalagem') {
            const statusProd = meta.status_producao || '';
            const qReal = parseFloat(meta.qtd_real_produzida);
            
            if (statusProd !== 'Finalizado' && statusProd !== 'FINISH' && statusProd !== 'Concluído') missing.push('Status de Produção (Concluído)');
            if (isNaN(qReal) || qReal <= 0) missing.push('Quantidade Real Produzida (>0)');
        }

        if (selectedPO.status === 'Faturamento/Expedição') {
            const nfe = meta.numero_nfe || '';
            const carrier = meta.transportadora || '';
            
            if (nfe === '') missing.push('Número NF-e');
            if (carrier === '') missing.push('Transportadora');
            
            const checklistMissing = [];
            if (!logisticsChecklist.endereco_conferido) checklistMissing.push('Endereço');
            if (!logisticsChecklist.peso_validado) checklistMissing.push('Peso');
            if (!logisticsChecklist.etiquetas_impressas) checklistMissing.push('Etiquetas');
            if (!logisticsChecklist.foto_carga_path) checklistMissing.push('Foto da Carga');
            if (!logisticsChecklist.foto_canhoto_path) checklistMissing.push('Nota Fiscal com Canhoto Assinado');
            
            if (checklistMissing.length > 0) {
                missing.push(`Checklist pendente: ${checklistMissing.join(', ')}`);
            }
        }

        if (selectedPO.status === 'Financeiro') {
            const comment = meta.audit_comment || '';
            if (comment.trim().length === 0) missing.push('Comentário de Auditoria');
        }

        if (missing.length > 0) {
            return `Campos pendentes: ${missing.join('; ')}`;
        }
        return '';
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

    const isArchived = selectedPO ? (['ARCHIVED', 'ARCHIVED_PARTITIONED', 'COMPLETED'].includes(selectedPO.status_macro) || selectedPO.status === 'Concluídos') : false;

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
                            {(user?.role || '').toLowerCase() === 'admin' && (
                                <button
                                    onClick={handleNukeTenantData}
                                    className="border border-red-600 hover:bg-red-50 text-red-600 font-semibold px-4 py-2 rounded-lg flex items-center gap-2 transition-colors cursor-pointer"
                                >
                                    🧹 Higienizar Banco (Testes)
                                </button>
                            )}
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
                            {(() => {
                                const activeColumn = boardData?.columns?.find?.(col => col?.status === selectedPO?.status);
                                const columnPOs = activeColumn ? filterPOs(activeColumn.pos) : [];
                                const currentPOIndex = columnPOs?.findIndex?.(po => po?.id === selectedPO?.id);
                                const hasPrevPO = currentPOIndex > 0;
                                const hasNextPO = currentPOIndex >= 0 && currentPOIndex < columnPOs.length - 1;

                                const handlePrevPO = () => {
                                    if (hasPrevPO) {
                                        handleCardClick(columnPOs[currentPOIndex - 1]);
                                    }
                                };

                                const handleNextPO = () => {
                                    if (hasNextPO) {
                                        handleCardClick(columnPOs[currentPOIndex + 1]);
                                    }
                                };

                                const salesperson = selectedPO.vendedor || selectedPO.extra_metadata?.salesperson || selectedPO.extra_metadata?.vendedor;

                                return (
                                    <div className="flex items-center justify-between p-6 border-b border-gray-200 bg-gray-50">
                                        <div>
                                            <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-3 flex-wrap">
                                                <span>Pedido #{selectedPO.po_number}</span>
                                                {/* Navigation Arrows */}
                                                {columnPOs.length > 1 && (
                                                    <div className="flex items-center gap-1.5 ml-4">
                                                        <button
                                                            onClick={handlePrevPO}
                                                            disabled={!hasPrevPO}
                                                            className={`p-1.5 rounded-lg border transition-all ${
                                                                hasPrevPO 
                                                                    ? 'border-gray-300 bg-white text-gray-700 hover:bg-gray-100 cursor-pointer shadow-3xs' 
                                                                    : 'border-gray-200 bg-gray-50 text-gray-400 cursor-not-allowed opacity-50'
                                                            }`}
                                                            title="Pedido Anterior"
                                                        >
                                                            <ChevronLeft className="w-4 h-4" />
                                                        </button>
                                                        <span className="text-xs font-semibold text-gray-500 font-mono">
                                                            {currentPOIndex + 1} de {columnPOs.length}
                                                        </span>
                                                        <button
                                                            onClick={handleNextPO}
                                                            disabled={!hasNextPO}
                                                            className={`p-1.5 rounded-lg border transition-all ${
                                                                hasNextPO 
                                                                    ? 'border-gray-300 bg-white text-gray-700 hover:bg-gray-100 cursor-pointer shadow-3xs' 
                                                                    : 'border-gray-200 bg-gray-50 text-gray-400 cursor-not-allowed opacity-50'
                                                            }`}
                                                            title="Próximo Pedido"
                                                        >
                                                            <ChevronRight className="w-4 h-4" />
                                                        </button>
                                                    </div>
                                                )}
                                            </h2>
                                            <p className="text-sm text-gray-650 mt-1 flex flex-wrap gap-x-4">
                                                <span><strong>Cliente:</strong> {getRobustName(selectedPO.client_name || selectedPO.supplier_name)}</span>
                                                {salesperson && (
                                                    <span><strong>Vendedor:</strong> {getRobustName(salesperson)}</span>
                                                )}
                                            </p>
                                        </div>
                                        <button
                                            onClick={handleCloseModal}
                                            className="p-2 hover:bg-gray-200 rounded-lg transition-colors cursor-pointer"
                                        >
                                            <X className="w-6 h-6 text-gray-600" />
                                        </button>
                                    </div>
                                );
                            })()}

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
                                    const calculateSlaPercent = (po) => {
                                        if (!po?.created_at || (!po?.expected_delivery_date && !po?.data_limite)) return 0;
                                        const start = new Date(po.created_at).getTime();
                                        const originalEnd = new Date(po.expected_delivery_date || po.data_limite).getTime();
                                        const now = new Date().getTime();
                                        
                                        if (originalEnd <= start) return 100;
                                        
                                        let totalSlaDuration = originalEnd - start;
                                        const isRep = po.is_replacement || po.extra_metadata?.is_replacement || false;
                                        if (isRep) {
                                            totalSlaDuration = totalSlaDuration * 0.5;
                                        }
                                        
                                        const elapsed = now - start;
                                        const percent = (elapsed / totalSlaDuration) * 100;
                                        return Math.max(0, Math.min(100, percent));
                                    };

                                    const isReplacement = selectedPO?.is_replacement || selectedPO?.extra_metadata?.is_replacement || false;
                                    const totalPercent = calculateSlaPercent(selectedPO);
                                    
                                    const totalSlaHours = handoffHistory?.total_sla_hours || (isReplacement ? 120 : 240);
                                    const totalElapsedHours = handoffHistory?.total_elapsed_hours || 0;
                                    const currentAreaSlaHours = handoffHistory?.current_area_sla_hours || 48;
                                    const currentAreaElapsedHours = handoffHistory?.current_area_elapsed_hours || 0;

                                    const areaPercent = Math.min((currentAreaElapsedHours / currentAreaSlaHours) * 100, 100);

                                    const getProgressBarColor = (percent) => {
                                        if (isReplacement) return 'bg-cyan-500';
                                        if (percent < 60) return 'bg-emerald-500';
                                        if (percent < 85) return 'bg-amber-500';
                                        if (percent < 100) return 'bg-orange-500';
                                        return 'bg-rose-500 animate-pulse';
                                    };

                                    return (
                                        <div className="mb-6 bg-slate-50 text-slate-700 p-5 rounded-xl border border-slate-200 shadow-sm">
                                            <div className="flex items-center justify-between mb-4 border-b border-slate-200 pb-2">
                                                <h3 className="text-xs font-bold tracking-wide uppercase text-slate-700 flex items-center gap-2">
                                                    <span>⏱️</span> Controle de SLA e Performance
                                                </h3>
                                                <div className="flex items-center gap-2">
                                                    {selectedPO?.sla_paused_at && (
                                                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-gray-200 text-gray-700 border border-gray-300">
                                                            ⏸️ Pausa: {(() => {
                                                                const pausedAt = new Date(selectedPO.sla_paused_at).getTime();
                                                                const now = new Date().getTime();
                                                                const diffSecs = Math.max(0, Math.floor((now - pausedAt) / 1000));
                                                                const hrs = Math.floor(diffSecs / 3600);
                                                                const mins = Math.floor((diffSecs % 3600) / 60);
                                                                const secs = diffSecs % 60;
                                                                
                                                                let str = '';
                                                                if (hrs > 0) str += `${hrs}h `;
                                                                if (mins > 0 || hrs > 0) str += `${mins}m `;
                                                                str += `${secs}s`;
                                                                return str;
                                                            })()}
                                                        </span>
                                                    )}
                                                    {isReplacement && (
                                                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[9px] font-extrabold bg-cyan-100 text-cyan-800 border border-cyan-300 animate-pulse">
                                                            SLA REDUZIDO (50% - TROCA)
                                                        </span>
                                                    )}
                                                </div>
                                            </div>
                                            
                                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                                {/* Tempo Total */}
                                                <div>
                                                    <div className="flex justify-between text-xs font-semibold mb-1">
                                                        <span>{handoffHistory?.is_archived ? 'Total Lead Time' : 'Tempo Total Acumulado'}</span>
                                                        <span className="font-mono text-slate-650 font-bold">
                                                            {totalElapsedHours.toFixed(1)}h / {totalSlaHours.toFixed(0)}h ({totalPercent.toFixed(0)}%)
                                                        </span>
                                                    </div>
                                                    <div 
                                                        className="w-full bg-slate-200 rounded-full h-3 overflow-hidden border border-slate-300"
                                                        title={isReplacement ? "SLA Prioritário (Troca)" : "Progresso de SLA"}
                                                    >
                                                        <div 
                                                            className={`h-full transition-all duration-500 ${getProgressBarColor(totalPercent)}`} 
                                                            style={{ width: `${totalPercent}%` }}
                                                        />
                                                    </div>
                                                    <p className="text-[10px] text-slate-500 mt-1">
                                                        Prazo total contratual para o fluxo completo do pedido.
                                                    </p>
                                                </div>

                                                {/* Tempo na Área Atual */}
                                                <div>
                                                    <div className="flex justify-between text-xs font-semibold mb-1">
                                                        <span>{handoffHistory?.is_archived ? 'Tempo na Área Atual (Arquivado)' : `Tempo na Área Atual (${selectedPO.status})`}</span>
                                                        <span className="font-mono text-slate-650 font-bold">
                                                            {handoffHistory?.is_archived ? 'Finalizado' : `${currentAreaElapsedHours.toFixed(1)}h / ${currentAreaSlaHours.toFixed(0)}h (${areaPercent.toFixed(0)}%)`}
                                                        </span>
                                                    </div>
                                                    <div className="w-full bg-slate-200 rounded-full h-3 overflow-hidden border border-slate-300">
                                                        <div 
                                                            className={`h-full transition-all duration-500 ${getProgressBarColor(areaPercent)}`} 
                                                            style={{ width: `${areaPercent}%` }}
                                                        />
                                                    </div>
                                                    <p className="text-[10px] text-slate-500 mt-1">
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
                                        <span>⚙️</span> Esteira de Operações (Setores de Produção)
                                    </h3>
                                    
                                    {(() => {
                                        const isPOBlocked = 
                                            selectedPO.block_status === 'BLOQUEADO' || 
                                            selectedPO.extra_metadata?.block_status === 'BLOQUEADO' || 
                                            selectedPO.status_macro === 'ANALISE_CREDITO' || 
                                            (selectedPO.items && selectedPO.items.some(item => 
                                                item.block_status === 'BLOQUEADO' || 
                                                item.extra_metadata?.block_status === 'BLOQUEADO'
                                            ));

                                        const finance_justification = 
                                            selectedPO.finance_justification || 
                                            selectedPO.extra_metadata?.finance_justification || 
                                            (selectedPO.items && selectedPO.items.find(item => item.extra_metadata?.finance_justification)?.extra_metadata?.finance_justification) ||
                                            (selectedPO.items && selectedPO.items.find(item => item.finance_justification)?.finance_justification) ||
                                            'Sem justificativa comercial registrada.';

                                        const stages = ['Comercial', 'PCP', 'Produção/Embalagem', 'Faturamento/Expedição', 'Financeiro', 'Concluídos'];
                                        const currentStageIndex = stages.indexOf(mapStatusToStageName(selectedPO.status));

                                        return stages.map((stageName, idx) => {
                                            const isCompleted = idx < currentStageIndex;
                                            const isActive = idx === currentStageIndex;
                                            const isLocked = idx > currentStageIndex;
                                            
                                            if (isLocked) return null;

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
                                                'Comercial': 'Comercial',
                                                'PCP': 'PCP',
                                                'Produção/Embalagem': 'Produção/Embalagem',
                                                'Faturamento/Expedição': 'Faturamento/Expedição',
                                                'Financeiro': 'Financeiro'
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
                                                                {/* Return Priority Banner */}
                                                                {selectedPO.extra_metadata?.priority_note && selectedPO.extra_metadata.priority_note.target_area === stageName && (
                                                                    <div className="mb-5 p-4 bg-amber-50 border-l-4 border-amber-500 rounded-r-lg shadow-2xs">
                                                                        <div className="flex items-center gap-2 mb-1.5">
                                                                            <span className="text-base">⚠️</span>
                                                                            <span className="font-extrabold text-amber-800 text-xs uppercase tracking-wider">Nota de Devolução Prioritária</span>
                                                                        </div>
                                                                        <p className="text-sm text-amber-950 font-bold italic leading-relaxed">
                                                                            "{selectedPO.extra_metadata.priority_note.text}"
                                                                        </p>
                                                                        <p className="text-[10px] text-amber-700 mt-2 font-medium">
                                                                            Devolvido de <strong className="text-amber-850">{selectedPO.extra_metadata.priority_note.from_area}</strong> por <strong>{selectedPO.extra_metadata.priority_note.user}</strong> em {new Date(selectedPO.extra_metadata.priority_note.timestamp).toLocaleString()}
                                                                        </p>
                                                                    </div>
                                                                )}

                                                                {/* Render Stage Specific Content */}
                                                                {stageName === 'Comercial' && (
                                                                    <div className="space-y-4">
                                                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                                                                            <div>
                                                                                <span className="text-xs text-gray-500 font-semibold uppercase block">Cliente</span>
                                                                                <span className="font-bold text-gray-800">{getRobustName(selectedPO.client_name || selectedPO.supplier_name)}</span>
                                                                            </div>
                                                                            <div>
                                                                                <span className="text-xs text-gray-500 font-semibold uppercase block">Fornecedor</span>
                                                                                <span className="font-semibold text-gray-800">{getRobustName(selectedPO.supplier_name || selectedPO.vendor_name || selectedPO.client_name)}</span>
                                                                            </div>
                                                                            <div>
                                                                                <span className="text-xs text-gray-500 font-semibold uppercase block">Condição de Pagamento</span>
                                                                                <span className="font-medium text-gray-700">{selectedPO.payment_terms || selectedPO.extra_metadata?.payment_terms || 'À vista'}</span>
                                                                            </div>
                                                                            <div>
                                                                                <span className="text-xs text-gray-500 font-semibold uppercase block">Data de Entrega (Excel)</span>
                                                                                <span className="font-medium text-gray-700">{formatDate(selectedPO.delivery_date)}</span>
                                                                            </div>
                                                                            <div>
                                                                                <span className="text-xs text-gray-500 font-semibold uppercase block">Data Limite de Entrega</span>
                                                                                <span className="font-medium text-gray-700">{formatDate(selectedPO.data_limite || selectedPO.expected_delivery_date)}</span>
                                                                            </div>
                                                                        </div>
                                                                        
                                                                        <div>
                                                                            <span className="text-xs text-gray-500 font-semibold uppercase block mb-2">Regras e Indicadores Estratégicos</span>
                                                                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-gray-50 p-3 rounded-lg border border-gray-200">
                                                                                {/* 1. Personalizado */}
                                                                                <label className="flex items-center gap-2 cursor-not-allowed">
                                                                                    <input
                                                                                        type="checkbox"
                                                                                        checked={selectedPO.extra_metadata?.is_personalized || selectedPO.extra_metadata?.is_urgent || false}
                                                                                        disabled
                                                                                        className="rounded border-gray-300 text-rose-600 focus:ring-rose-500 disabled:opacity-80"
                                                                                    />
                                                                                    <span className="text-xs font-semibold text-gray-700">
                                                                                        Personalizado: {(selectedPO.extra_metadata?.is_personalized || selectedPO.extra_metadata?.is_urgent) ? 'Sim' : 'Não'}
                                                                                    </span>
                                                                                </label>

                                                                                {/* 2. Cliente Novo */}
                                                                                <label className="flex items-center gap-2 cursor-not-allowed">
                                                                                    <input
                                                                                        type="checkbox"
                                                                                        checked={selectedPO.extra_metadata?.is_new_client || selectedPO.extra_metadata?.is_first_order || false}
                                                                                        disabled
                                                                                        className="rounded border-gray-300 text-amber-600 focus:ring-amber-500 disabled:opacity-80"
                                                                                    />
                                                                                    <span className="text-xs font-semibold text-gray-700">
                                                                                        Cliente Novo: {(selectedPO.extra_metadata?.is_new_client || selectedPO.extra_metadata?.is_first_order) ? 'Sim' : 'Não'}
                                                                                    </span>
                                                                                </label>

                                                                                {/* 3. Exportação */}
                                                                                <label className="flex items-center gap-2 cursor-not-allowed">
                                                                                    <input
                                                                                        type="checkbox"
                                                                                        checked={selectedPO.extra_metadata?.is_export || false}
                                                                                        disabled
                                                                                        className="rounded border-gray-300 text-blue-600 focus:ring-blue-500 disabled:opacity-80"
                                                                                    />
                                                                                    <span className="text-xs font-semibold text-gray-700">
                                                                                        Exportação: {selectedPO.extra_metadata?.is_export ? 'Sim' : 'Não'}
                                                                                    </span>
                                                                                </label>

                                                                                {/* 4. Troca/Reposição */}
                                                                                <label className="flex items-center gap-2 cursor-not-allowed">
                                                                                    <input
                                                                                        type="checkbox"
                                                                                        checked={selectedPO.extra_metadata?.is_replacement || false}
                                                                                        disabled
                                                                                        className="rounded border-gray-300 text-cyan-600 focus:ring-cyan-500 disabled:opacity-80"
                                                                                    />
                                                                                    <span className="text-xs font-semibold text-gray-700">
                                                                                        Troca/Reposição: {selectedPO.extra_metadata?.is_replacement ? 'Sim' : 'Não'}
                                                                                    </span>
                                                                                </label>
                                                                            </div>
                                                                        </div>

                                                                        {['admin', 'master'].includes((user?.role || '').toLowerCase()) && (() => {
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

                                                                        {/* Commercial Partition Approval or Material Pause Panel */}
                                                                        {((selectedPO.status_macro === 'WAITING_COMMERCIAL_PARTITION') || (['DRAFT', 'SUBMITTED'].includes(selectedPO.status_macro) && (selectedPO.partition_reason || selectedPO.extra_metadata?.partition_reason))) && (
                                                                            <div className="mt-4 p-4 bg-purple-50 border border-purple-200 rounded-lg shadow-2xs">
                                                                                <h4 className="text-sm font-bold text-purple-900 mb-2 flex items-center gap-1.5">
                                                                                    <Split className="w-4 h-4" />
                                                                                    <span>Sugestão de Partição Pendente (PCP)</span>
                                                                                </h4>
                                                                                <p className="text-xs text-purple-950 font-semibold mb-3">
                                                                                    <strong>Justificativa Técnica:</strong> "{selectedPO.partition_reason || selectedPO.extra_metadata?.partition_reason || 'Sem justificativa técnica registrada.'}"
                                                                                </p>
                                                                                {selectedPO.status_macro === 'WAITING_COMMERCIAL_PARTITION' && (
                                                                                    <div className="flex flex-wrap gap-2.5">
                                                                                        <button
                                                                                            onClick={() => {
                                                                                                let originalFreight = parseFloat(selectedPO.shipping_cost) || 0;
                                                                                                if (originalFreight === 0 && selectedPO.items && selectedPO.items.length > 0) {
                                                                                                    const firstItem = selectedPO.items[0];
                                                                                                    if (firstItem.extra_metadata) {
                                                                                                        const metaFreight = firstItem.extra_metadata.freight || firstItem.extra_metadata.Freight;
                                                                                                        originalFreight = parseFloat(metaFreight) || 0;
                                                                                                    }
                                                                                                }
                                                                                                setFreightC1((originalFreight / 2).toFixed(4));
                                                                                                setFreightC2((originalFreight - originalFreight / 2).toFixed(4));
                                                                                                setShowFreightModal(true);
                                                                                            }}
                                                                                            className="inline-flex items-center justify-center px-3.5 py-1.5 bg-purple-600 hover:bg-purple-700 text-white text-xs font-bold rounded-lg cursor-pointer transition-colors shadow-2xs"
                                                                                        >
                                                                                            Aprovar Partição e Ratear Frete
                                                                                        </button>
                                                                                        <button
                                                                                            onClick={async () => {
                                                                                                try {
                                                                                                    const response = await api.post(`/kanban/pos/${selectedPO.id}/pause-material`);
                                                                                                    showSuccess(response.data.message);
                                                                                                    await fetchBoard();
                                                                                                    handleCloseModal();
                                                                                                } catch (err) {
                                                                                                    showError(err.response?.data?.detail || 'Erro ao aguardar insumo');
                                                                                                }
                                                                                            }}
                                                                                            className="inline-flex items-center justify-center px-3.5 py-1.5 bg-gray-600 hover:bg-gray-700 text-white text-xs font-bold rounded-lg cursor-pointer transition-colors shadow-2xs"
                                                                                        >
                                                                                            Aguardar Insumo (Pausar SLA)
                                                                                        </button>
                                                                                    </div>
                                                                                )}
                                                                            </div>
                                                                        )}
                                                                    </div>
                                                                )}

                                                                {stageName === 'PCP' && (
                                                                    <div className="space-y-4">
                                                                        {selectedPO.status_macro === 'WAITING_MATERIAL' && (
                                                                            <div className="p-4 bg-gray-50 border border-gray-300 rounded-lg shadow-3xs mb-4">
                                                                                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                                                                                    <div className="flex items-center gap-2">
                                                                                        <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-extrabold bg-gray-200 text-gray-800 border border-gray-350">
                                                                                            SLA PAUSADO (AGUARDANDO INSUMO)
                                                                                        </span>
                                                                                        <span className="text-xs text-gray-750 font-semibold">
                                                                                            Retome o cronômetro assim que os materiais forem recebidos.
                                                                                        </span>
                                                                                    </div>
                                                                                    <button
                                                                                        onClick={async () => {
                                                                                            try {
                                                                                                const response = await api.post(`/kanban/pos/${selectedPO.id}/resume-material`);
                                                                                                showSuccess(response.data.message);
                                                                                                await fetchBoard();
                                                                                                handleCloseModal();
                                                                                            } catch (err) {
                                                                                                showError(err.response?.data?.detail || 'Falha ao retomar SLA');
                                                                                            }
                                                                                        }}
                                                                                        className="flex items-center justify-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-lg cursor-pointer transition-colors shadow-2xs flex-shrink-0"
                                                                                    >
                                                                                        📦 Insumo Recebido - Retomar SLA
                                                                                    </button>
                                                                                </div>
                                                                            </div>
                                                                        )}

                                                                        {(['APPROVED', 'approved', 'PCP', 'pcp', 'WAITING_MATERIAL'].includes(selectedPO.status_macro) || selectedPO.status === 'PCP') && (
                                                                            <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg shadow-3xs mb-4">
                                                                                <div className="flex items-center justify-between mb-3 border-b border-amber-200 pb-2">
                                                                                    <div className="flex items-center gap-2">
                                                                                        <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-extrabold bg-amber-100 text-amber-800 border border-amber-300">
                                                                                            GRADE DE ITENS E CUSTOS (PCP)
                                                                                        </span>
                                                                                    </div>
                                                                                    <span className="text-xs text-amber-900 font-semibold">
                                                                                        Vincule o custo de cada SKU para calcular a margem.
                                                                                    </span>
                                                                                </div>
                                                                                
                                                                                <div className="overflow-x-auto">
                                                                                    <table className="w-full text-xs text-left text-gray-500 border border-gray-200 rounded-lg overflow-hidden">
                                                                                        <thead className="text-[10px] text-gray-700 uppercase bg-gray-100 border-b border-gray-200">
                                                                                            <tr>
                                                                                                <th scope="col" className="px-3 py-2 font-bold">SKU</th>
                                                                                                <th scope="col" className="px-3 py-2 font-bold text-center">Quantidade</th>
                                                                                                <th scope="col" className="px-3 py-2 font-bold text-center">Status de Custo</th>
                                                                                                <th scope="col" className="px-3 py-2 font-bold text-center">Ações</th>
                                                                                            </tr>
                                                                                        </thead>
                                                                                        <tbody className="divide-y divide-gray-200 bg-white">
                                                                                            {selectedPO.items && selectedPO.items.length > 0 ? (
                                                                                                selectedPO.items.map((item) => {
                                                                                                    const unitCost = parseFloat(item.total_cost) || parseFloat(item.cost_mp) || parseFloat(item.extra_metadata?.total_cost) || parseFloat(item.extra_metadata?.cost_mp) || 0;
                                                                                                    const hasCost = unitCost > 0;
                                                                                                    const costDateStr = (() => {
                                                                                                        const iso = item.extra_metadata?.cost_updated_at;
                                                                                                        if (!iso) return 'Recente';
                                                                                                        try {
                                                                                                            const d = new Date(iso);
                                                                                                            const day = String(d.getDate()).padStart(2, '0');
                                                                                                            const month = String(d.getMonth() + 1).padStart(2, '0');
                                                                                                            const year = d.getFullYear();
                                                                                                            const hours = String(d.getHours()).padStart(2, '0');
                                                                                                            const minutes = String(d.getMinutes()).padStart(2, '0');
                                                                                                            return `${day}/${month}/${year} ${hours}:${minutes}`;
                                                                                                        } catch (e) {
                                                                                                            return 'Recente';
                                                                                                        }
                                                                                                    })();
                                                                                                    return (
                                                                                                        <tr key={item.id || item.sku} className="hover:bg-gray-50">
                                                                                                            <td className="px-3 py-2 font-semibold text-gray-900">
                                                                                                                {item.sku}
                                                                                                                {(item.product_description || item.description || item.extra_metadata?.description || item.nome) && (
                                                                                                                    <span className="text-[10px] font-normal text-gray-500 ml-1.5">
                                                                                                                        - {item.product_description || item.description || item.extra_metadata?.description || item.nome}
                                                                                                                    </span>
                                                                                                                )}
                                                                                                            </td>
                                                                                                            <td className="px-3 py-2 text-center text-gray-700 font-medium">{item.quantity}</td>
                                                                                                            <td className="px-3 py-2 text-center">
                                                                                                                {hasCost ? (
                                                                                                                    <div className="flex flex-col items-center gap-1">
                                                                                                                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 shadow-3xs uppercase tracking-wider">
                                                                                                                            <span className="text-[10px]">✅</span> Vinculado
                                                                                                                        </span>
                                                                                                                        <span className="text-[9px] text-gray-500 font-semibold block leading-tight text-center">
                                                                                                                            por {item.extra_metadata?.cost_updated_by || 'Sistema'} em {costDateStr}
                                                                                                                        </span>
                                                                                                                    </div>
                                                                                                                ) : (
                                                                                                                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-200">
                                                                                                                        ⚠️ Sem Custo
                                                                                                                    </span>
                                                                                                                )}
                                                                                                            </td>
                                                                                                            <td className="px-3 py-2 text-center">
                                                                                                                <button
                                                                                                                    onClick={() => handleOpenLinkCost(item)}
                                                                                                                    className="inline-flex items-center justify-center gap-1 px-2.5 py-1 bg-amber-600 hover:bg-amber-700 text-white text-[10px] font-bold rounded cursor-pointer transition-colors shadow-2xs"
                                                                                                                >
                                                                                                                    🔍 Vincular
                                                                                                                </button>
                                                                                                            </td>
                                                                                                        </tr>
                                                                                                    );
                                                                                                })
                                                                                            ) : (
                                                                                                <tr>
                                                                                                    <td colSpan="4" className="px-3 py-4 text-center text-gray-400 italic">
                                                                                                        Nenhum item cadastrado neste pedido
                                                                                                    </td>
                                                                                                </tr>
                                                                                            )}
                                                                                        </tbody>
                                                                                    </table>
                                                                                </div>
                                                                            </div>
                                                                        )}
                                                                        {!isActive ? (
                                                                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                                                                                <div>
                                                                                    <span className="text-xs text-gray-500 font-semibold uppercase block">Embalagem</span>
                                                                                    <span className="font-semibold text-gray-800">{selectedPO.extra_metadata?.packaging_type || 'Não selecionado'}</span>
                                                                                </div>
                                                                                <div>
                                                                                    <span className="text-xs text-gray-500 font-semibold uppercase block">Data Programada</span>
                                                                                    <span className="font-semibold text-gray-800">{selectedPO.extra_metadata?.data_programada ? new Date(selectedPO.extra_metadata.data_programada + 'T00:00:00').toLocaleDateString('pt-BR') : 'Não agendada'}</span>
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
                                                                                        <option value="Padrão">Padrão</option>
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
                                                                                        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-850 font-medium"
                                                                                    />
                                                                                </div>



                                                                                {/* Sugerir Partição Button inside PCP Panel */}
                                                                                <div className="md:col-span-2 mt-2 p-3.5 bg-purple-50 border border-purple-150 rounded-lg flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
                                                                                    <div className="text-xs text-purple-950 font-medium">
                                                                                        <strong>Partição Técnica:</strong> Se houver restrições de maquinário ou entrega, proponha o desmembramento técnico deste PO.
                                                                                    </div>
                                                                                    <button
                                                                                        onClick={() => {
                                                                                            const initialSplits = {};
                                                                                            selectedPO.items?.forEach(item => {
                                                                                                initialSplits[item.id] = [Math.ceil(item.quantity / 2), item.quantity - Math.ceil(item.quantity / 2)];
                                                                                            });
                                                                                            setQtySplits(initialSplits);
                                                                                            setShowPartitionModal(true);
                                                                                        }}
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
                                                                                    <span className="font-semibold text-gray-850">
                                                                                        {['FINISH', 'Finalizado', 'Concluído'].includes(selectedPO.extra_metadata?.status_producao) ? 'Concluído (FINISH)' : 'Em andamento (START)'}
                                                                                    </span>
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
                                                                                        <option value="Concluído">Concluído (FINISH)</option>
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
                                                                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 border-b border-gray-150 pb-3">
                                                                                    <div>
                                                                                        <span className="text-xs text-gray-500 font-semibold uppercase block">Número NF-e</span>
                                                                                        <span className="font-semibold text-gray-800">{selectedPO.extra_metadata?.numero_nfe || 'Não informado'}</span>
                                                                                    </div>
                                                                                    <div>
                                                                                        <span className="text-xs text-gray-500 font-semibold uppercase block">Transportadora</span>
                                                                                        <span className="font-semibold text-gray-800">{selectedPO.extra_metadata?.transportadora || 'Não informada'}</span>
                                                                                    </div>
                                                                                </div>
                                                                                <div className="flex gap-4">
                                                                                    {logisticsChecklist.foto_carga_path && (
                                                                                        <a 
                                                                                            href={getDownloadUrl(logisticsChecklist.foto_carga_path)}
                                                                                            target="_blank" 
                                                                                            rel="noreferrer" 
                                                                                            className="text-xs text-blue-600 hover:text-blue-800 flex items-center gap-1 font-semibold underline"
                                                                                        >
                                                                                            Visualizar Foto da Carga
                                                                                        </a>
                                                                                    )}
                                                                                    {logisticsChecklist.foto_canhoto_path && (
                                                                                        <a 
                                                                                            href={getDownloadUrl(logisticsChecklist.foto_canhoto_path)}
                                                                                            target="_blank" 
                                                                                            rel="noreferrer" 
                                                                                            className="text-xs text-blue-600 hover:text-blue-800 flex items-center gap-1 font-semibold underline"
                                                                                        >
                                                                                            Visualizar Nota Fiscal com Canhoto Assinado
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

                                                                                {/* NF and Carrier */}
                                                                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
                                                                                                        href={getDownloadUrl(logisticsChecklist.foto_carga_path)}
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
                                                                                                Nota Fiscal com Canhoto Assinado
                                                                                            </label>
                                                                                            {logisticsChecklist.foto_canhoto_path ? (
                                                                                                <div className="space-y-2">
                                                                                                    <div className="flex items-center gap-2 text-green-600 font-semibold text-sm">
                                                                                                        <CheckCircle className="w-5 h-5 flex-shrink-0" />
                                                                                                        <span>Nota Fiscal com Canhoto Assinado Salva!</span>
                                                                                                    </div>
                                                                                                    <a 
                                                                                                        href={getDownloadUrl(logisticsChecklist.foto_canhoto_path)}
                                                                                                        target="_blank" 
                                                                                                        rel="noreferrer" 
                                                                                                        className="text-xs text-blue-600 hover:text-blue-800 font-semibold underline block"
                                                                                                    >
                                                                                                        Abrir Nota Fiscal com Canhoto Assinado
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
                                                                                                        {uploadingEvidence ? 'Enviando...' : 'Enviar Nota Fiscal com Canhoto Assinado'}
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
                                                                        {isPOBlocked ? (
                                                                            <div className="space-y-4">
                                                                                {/* Painel de Liberação de Crédito */}
                                                                                <div className="p-4 bg-red-50 border border-red-200 rounded-lg space-y-3 shadow-2xs animate-fade-in">
                                                                                    <h5 className="text-sm font-bold text-red-900 uppercase tracking-wider flex items-center gap-1.5">
                                                                                        <span>🛡️</span> Painel de Liberação de Crédito
                                                                                    </h5>
                                                                                    <div className="p-3 bg-white border border-red-200 rounded-lg shadow-3xs">
                                                                                        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wide block mb-1">Justificativa Comercial</span>
                                                                                        <p className="text-xs font-semibold text-slate-800 italic leading-relaxed">
                                                                                            "{finance_justification}"
                                                                                        </p>
                                                                                    </div>
                                                                                </div>

                                                                                {/* Parecer do Financeiro */}
                                                                                <div>
                                                                                    <label className="block text-xs font-bold text-gray-700 uppercase mb-1">
                                                                                        Parecer do Financeiro <span className="text-red-500">*</span>
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

                                                                                {/* Two Buttons inside the Panel */}
                                                                                {isActive && (
                                                                                    <div className="flex gap-3 mt-4">
                                                                                        <button
                                                                                            onClick={async () => {
                                                                                                const comment = (localFields.audit_comment || '').trim();
                                                                                                if (comment.length < 10) {
                                                                                                    showError("Por favor, preencha o Parecer do Financeiro com pelo menos 10 caracteres.");
                                                                                                    return;
                                                                                                }
                                                                                                try {
                                                                                                    const response = await api.post(`/kanban/pos/${selectedPO.id}/approve-credit`, {
                                                                                                        audit_comment: comment
                                                                                                    });
                                                                                                    showSuccess(response.data.message);
                                                                                                    await fetchBoard();
                                                                                                    handleCloseModal();
                                                                                                } catch (err) {
                                                                                                    showError(err.response?.data?.detail || "Erro ao aprovar crédito");
                                                                                                }
                                                                                            }}
                                                                                            className="flex-1 py-2.5 px-4 bg-green-600 hover:bg-green-700 text-white rounded-lg font-bold text-xs uppercase tracking-wider transition-colors shadow-md cursor-pointer text-center border-0"
                                                                                        >
                                                                                            [Aprovar Crédito]
                                                                                        </button>
                                                                                        <button
                                                                                            onClick={async () => {
                                                                                                const comment = (localFields.audit_comment || '').trim();
                                                                                                if (comment.length < 10) {
                                                                                                    showError("Por favor, preencha o Parecer do Financeiro com pelo menos 10 caracteres.");
                                                                                                    return;
                                                                                                }
                                                                                                try {
                                                                                                    const response = await api.post(`/kanban/pos/${selectedPO.id}/maintain-block`, {
                                                                                                        audit_comment: comment
                                                                                                    });
                                                                                                    showSuccess(response.data.message);
                                                                                                    await fetchBoard();
                                                                                                    handleCloseModal();
                                                                                                } catch (err) {
                                                                                                    showError(err.response?.data?.detail || "Erro ao manter bloqueio");
                                                                                                }
                                                                                            }}
                                                                                            className="flex-1 py-2.5 px-4 bg-orange-600 hover:bg-orange-700 text-white rounded-lg font-bold text-xs uppercase tracking-wider transition-colors shadow-md cursor-pointer text-center border-0"
                                                                                        >
                                                                                            [Manter Bloqueio]
                                                                                        </button>
                                                                                    </div>
                                                                                )}
                                                                            </div>
                                                                        ) : (
                                                                            <div className="space-y-4">
                                                                                {/* Painel de Evidências da Expedição (Visual 360º) */}
                                                                                <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg space-y-3">
                                                                                    <h5 className="text-xs font-bold text-slate-800 uppercase tracking-wider border-b border-slate-200 pb-2 flex items-center gap-1.5">
                                                                                        <span>📋</span> Evidências Físicas & Fiscais (Expedição)
                                                                                    </h5>
                                                                                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                                                                                        {/* NF-e */}
                                                                                        <div className="bg-white p-3 rounded-lg border border-slate-200 shadow-2xs space-y-1">
                                                                                            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wide block">NF-e</span>
                                                                                            <div className="text-xs font-semibold text-slate-800">
                                                                                                Número NF-e: <span className="font-mono text-blue-600 font-bold">{selectedPO.extra_metadata?.numero_nfe || 'Não informado'}</span>
                                                                                            </div>
                                                                                        </div>

                                                                                        {/* Foto da Carga */}
                                                                                        <div className="bg-white p-3 rounded-lg border border-slate-200 shadow-2xs space-y-1 flex flex-col justify-between">
                                                                                            <div>
                                                                                                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wide block">Foto da Carga Carregada</span>
                                                                                                {logisticsChecklist.foto_carga_path ? (
                                                                                                    <div className="text-xs text-green-700 font-semibold flex items-center gap-1 mt-1">
                                                                                                        <span className="text-emerald-500">✓</span> Foto Salva com Sucesso!
                                                                                                    </div>
                                                                                                ) : (
                                                                                                    <div className="text-xs text-amber-700 font-medium flex items-center gap-1 mt-1">
                                                                                                        <span>⚠</span> Nenhuma foto anexada
                                                                                                    </div>
                                                                                                )}
                                                                                            </div>
                                                                                            {logisticsChecklist.foto_carga_path && (
                                                                                                <a 
                                                                                                    href={getDownloadUrl(logisticsChecklist.foto_carga_path)}
                                                                                                    target="_blank" 
                                                                                                    rel="noreferrer" 
                                                                                                    className="text-xs text-blue-600 hover:text-blue-850 font-bold hover:underline block mt-2"
                                                                                                >
                                                                                                    🔍 Visualizar Foto da Carga
                                                                                                </a>
                                                                                            )}
                                                                                        </div>

                                                                                        {/* Nota Fiscal com Canhoto Assinado */}
                                                                                        <div className="bg-white p-3 rounded-lg border border-slate-200 shadow-2xs space-y-1 flex flex-col justify-between">
                                                                                            <div>
                                                                                                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wide block">Nota Fiscal com Canhoto Assinado</span>
                                                                                                {logisticsChecklist.foto_canhoto_path ? (
                                                                                                    <div className="text-xs text-green-700 font-semibold flex items-center gap-1 mt-1">
                                                                                                        <span className="text-emerald-500">✓</span> Evidência Salva com Sucesso!
                                                                                                    </div>
                                                                                                ) : (
                                                                                                    <div className="text-xs text-amber-700 font-medium flex items-center gap-1 mt-1">
                                                                                                        <span>⚠</span> Nenhum arquivo anexado
                                                                                                    </div>
                                                                                                )}
                                                                                            </div>
                                                                                            {logisticsChecklist.foto_canhoto_path && (
                                                                                                <a 
                                                                                                    href={getDownloadUrl(logisticsChecklist.foto_canhoto_path)}
                                                                                                    target="_blank" 
                                                                                                    rel="noreferrer" 
                                                                                                    className="text-xs text-blue-600 hover:text-blue-850 font-bold hover:underline block mt-2"
                                                                                                >
                                                                                                    📄 Abrir Nota Fiscal com Canhoto Assinado
                                                                                                </a>
                                                                                            )}
                                                                                        </div>
                                                                                    </div>
                                                                                </div>

                                                                                {/* Checklist de Auditoria Financeira */}
                                                                                <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg space-y-3">
                                                                                    <h5 className="text-xs font-bold text-slate-800 uppercase tracking-wider border-b border-slate-200 pb-2">
                                                                                        Checklist de Auditoria Financeira
                                                                                    </h5>
                                                                                    <div className="flex flex-col gap-2.5">
                                                                                        <label className="flex items-center gap-2.5 text-xs text-slate-700 font-semibold cursor-pointer">
                                                                                            <input
                                                                                                type="checkbox"
                                                                                                checked={checklistFinanceiro.margem_comissoes_validadas}
                                                                                                onChange={(e) => handleFinanceiroChecklistChange('margem_comissoes_validadas', e.target.checked)}
                                                                                                className="w-4 h-4 text-emerald-600 border-gray-300 rounded focus:ring-emerald-500 cursor-pointer"
                                                                                                disabled={!isActive}
                                                                                            />
                                                                                            <span>Margem e Comissões Validadas</span>
                                                                                        </label>
                                                                                        <label className="flex items-center gap-2.5 text-xs text-slate-700 font-semibold cursor-pointer">
                                                                                            <input
                                                                                                type="checkbox"
                                                                                                checked={checklistFinanceiro.nfe_chave_conferidas}
                                                                                                onChange={(e) => handleFinanceiroChecklistChange('nfe_chave_conferidas', e.target.checked)}
                                                                                                className="w-4 h-4 text-emerald-600 border-gray-300 rounded focus:ring-emerald-500 cursor-pointer"
                                                                                                disabled={!isActive}
                                                                                            />
                                                                                            <span>NF-e Conferida</span>
                                                                                        </label>
                                                                                        <label className="flex items-center gap-2.5 text-xs text-slate-700 font-semibold cursor-pointer">
                                                                                            <input
                                                                                                type="checkbox"
                                                                                                checked={checklistFinanceiro.evidencias_fotograficas_verificadas}
                                                                                                onChange={(e) => handleFinanceiroChecklistChange('evidencias_fotograficas_verificadas', e.target.checked)}
                                                                                                className="w-4 h-4 text-emerald-600 border-gray-300 rounded focus:ring-emerald-500 cursor-pointer"
                                                                                                disabled={!isActive}
                                                                                            />
                                                                                            <span>Evidências Fotográficas Verificadas</span>
                                                                                        </label>
                                                                                    </div>
                                                                                </div>

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
                                                                                        {['admin', 'master'].includes((user?.role || '').toLowerCase()) && (
                                                                                            <div>
                                                                                                <span className="text-xs text-gray-500 font-semibold block uppercase">Margem Operacional CM</span>
                                                                                                <p className="text-lg font-bold text-gray-800">
                                                                                                    {(() => {
                                                                                                        const marginVal = parseFloat(selectedPO.margin_percentage);
                                                                                                        return isNaN(marginVal) ? 'PENDENTE PCP' : (marginVal > 1000 ? '> 1000%' : `${marginVal.toFixed(2)}%`);
                                                                                                    })()}
                                                                                                </p>
                                                                                            </div>
                                                                                        )}
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
                                                            <h4 className="font-bold text-gray-900 flex items-center gap-1.5">
                                                                {item.sku}
                                                                {(item.attachment_path || item.extra_metadata?.attachment_path) && (
                                                                    <a 
                                                                        href={getDownloadUrl(item.attachment_path || item.extra_metadata?.attachment_path)}
                                                                        target="_blank"
                                                                        rel="noopener noreferrer"
                                                                        className="inline-flex items-center text-blue-600 hover:text-blue-800"
                                                                        title="Visualizar anexo de personalização"
                                                                    >
                                                                        <Paperclip className="w-3.5 h-3.5" />
                                                                    </a>
                                                                )}
                                                            </h4>
                                                            <p className="text-sm text-gray-600 font-medium">
                                                                Quantidade: {item.quantity} | Preço Unitário: {formatCurrency(item.price_unit || item.price || item.unit_value)}
                                                            </p>
                                                        </div>
                                                        <span className="px-2 py-0.5 bg-blue-50 text-blue-700 text-xs font-semibold rounded-full border border-blue-150 uppercase">
                                                            {item.status_item || 'PENDING'}
                                                        </span>
                                                    </div>

                                                    {/* Collapsible Accordion at SKU Level */}
                                                    {item.extra_metadata && Object.keys(item.extra_metadata).length > 0 && (() => {
                                                        const isOpen = !!openSKUs[item.id || idx];
                                                        return (
                                                            <div className="mt-3 border border-gray-150 rounded-lg overflow-hidden bg-slate-50">
                                                                <button
                                                                    onClick={() => toggleSKU(item.id || idx)}
                                                                    className="w-full flex items-center justify-between p-2.5 hover:bg-slate-100 transition-colors text-left font-bold text-gray-800 text-xs cursor-pointer select-none"
                                                                >
                                                                    <span className="flex items-center gap-1.5 text-gray-700">
                                                                        <span>📋</span> Detalhe do Pedido
                                                                    </span>
                                                                    <span className="text-gray-500 font-mono font-bold text-sm leading-none select-none">
                                                                        {isOpen ? '−' : '+'}
                                                                    </span>
                                                                </button>
                                                                {isOpen && (
                                                                    <div className="p-3 bg-white border-t border-gray-150">
                                                                        <MetadataVisualizer
                                                                            metadata={item.extra_metadata}
                                                                            itemId={item.id}
                                                                            onUpdate={handleMetadataUpdate}
                                                                            readOnly={true}
                                                                        />
                                                                    </div>
                                                                )}
                                                            </div>
                                                        );
                                                    })()}
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
                                    ) : (!handoffHistory.transitions || handoffHistory.transitions.length === 0) ? (
                                        <p className="text-sm text-gray-500 italic py-4 text-center bg-slate-50 border border-gray-200 rounded-lg">Nenhum registro de movimentação disponível para este pedido.</p>
                                    ) : (
                                        <div className="overflow-hidden border border-gray-200 rounded-lg shadow-2xs">
                                            <table className="min-w-full divide-y divide-gray-200 text-sm text-left">
                                                <thead className="bg-slate-50 text-slate-700 font-bold uppercase tracking-wider text-[10px]">
                                                    <tr>
                                                        <th className="px-4 py-3">Data</th>
                                                        <th className="px-4 py-3">Responsável</th>
                                                        <th className="px-4 py-3">De ➔ Para</th>
                                                        <th className="px-4 py-3">Motivo/Justificativa</th>
                                                    </tr>
                                                </thead>
                                                <tbody className="divide-y divide-gray-100 bg-white text-gray-700 font-medium">
                                                    {handoffHistory.transitions.map((record, index) => (
                                                        <tr key={index} className="hover:bg-slate-50 transition-colors">
                                                            <td className="px-4 py-3 font-mono text-xs text-gray-650">{record.date}</td>
                                                            <td className="px-4 py-3 text-xs text-gray-600 font-semibold">{record.user}</td>
                                                            <td className="px-4 py-3 text-xs font-bold text-gray-900">{record.from_to}</td>
                                                            <td className="px-4 py-3 text-xs text-gray-650 italic font-normal max-w-xs truncate" title={record.reason || 'Sem justificativa'}>
                                                                {record.reason || 'Sem justificativa'}
                                                            </td>
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
                                    {canReturn(selectedPO) && !isArchived && !isPOBlocked && (
                                        <button
                                            onClick={() => setShowReturnModal(true)}
                                            className="flex items-center gap-2 px-4 py-2 bg-orange-600 border border-orange-500 text-white rounded-lg hover:bg-orange-700 transition-colors font-bold text-sm cursor-pointer shadow-md"
                                        >
                                            <RefreshCw className="w-4 h-4" />
                                            Devolver para {getPreviousStatus(selectedPO.status)}
                                        </button>
                                    )}
                                </div>

                                <div className="flex items-center gap-3">
                                    {/* Final Action: Finalizar Auditoria e Arquivar */}
                                    {selectedPO.status === 'Financeiro' && !isArchived && !isPOBlocked && (
                                        <button
                                            onClick={handleArchivePO}
                                            disabled={
                                                !checklistFinanceiro.margem_comissoes_validadas ||
                                                !checklistFinanceiro.nfe_chave_conferidas ||
                                                !checklistFinanceiro.evidencias_fotograficas_verificadas ||
                                                (localFields.audit_comment || '').trim().length < 20
                                            }
                                            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-semibold transition-colors shadow-sm text-sm ${
                                                (checklistFinanceiro.margem_comissoes_validadas &&
                                                checklistFinanceiro.nfe_chave_conferidas &&
                                                checklistFinanceiro.evidencias_fotograficas_verificadas &&
                                                (localFields.audit_comment || '').trim().length >= 20)
                                                    ? 'bg-emerald-600 text-white hover:bg-emerald-700 cursor-pointer animate-pulse'
                                                    : 'bg-gray-300 text-gray-500 cursor-not-allowed border border-gray-310'
                                            }`}
                                            title={
                                                !(checklistFinanceiro.margem_comissoes_validadas &&
                                                checklistFinanceiro.nfe_chave_conferidas &&
                                                checklistFinanceiro.evidencias_fotograficas_verificadas &&
                                                (localFields.audit_comment || '').trim().length >= 20)
                                                    ? `Não é possível finalizar. ${getFinanceiroMissingFieldsTooltip()}`
                                                    : 'Finalizar Auditoria e Arquivar Definitivamente'
                                            }
                                        >
                                            ✅ Finalizar Auditoria e Arquivar
                                        </button>
                                    )}

                                    {/* Advance Button - enabled only if mandatory fields are filled */}
                                    {canAdvance(selectedPO) && !isArchived && !isPOBlocked && (
                                        <button
                                            onClick={handleAdvanceStatus}
                                            disabled={!canAdvanceCurrentArea()}
                                            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-semibold transition-colors shadow-sm text-sm ${
                                                canAdvanceCurrentArea()
                                                    ? 'bg-green-600 text-white hover:bg-green-700 cursor-pointer'
                                                    : 'bg-gray-300 text-gray-500 cursor-not-allowed border border-gray-310'
                                            }`}
                                            title={!canAdvanceCurrentArea() ? `Não é possível avançar. ${getMissingFieldsTooltip()}` : `Avançar para ${getNextStatus(selectedPO.status)}`}
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

                {/* Return Modal */}
                {showReturnModal && (
                    <div
                        className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
                        onClick={(e) => {
                            if (e.target === e.currentTarget) {
                                setShowReturnModal(false);
                                setReturnLabel('');
                                setReturnReasonText('');
                                setReturnReason('');
                            }
                        }}
                    >
                        <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
                            <h3 className="text-xl font-bold text-gray-900 mb-4">
                                Devolver para {getPreviousStatus(selectedPO?.status)}
                            </h3>
                            
                            <div className="mb-4">
                                <label className="block text-xs font-bold text-gray-700 uppercase mb-1">
                                    Motivo da Devolução <span className="text-red-500">*</span>
                                </label>
                                <select
                                    value={returnLabel}
                                    onChange={(e) => setReturnLabel(e.target.value)}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white font-semibold text-gray-800"
                                >
                                    <option value="">Selecione um motivo...</option>
                                    <option value="[Particionamento]">[Particionamento]</option>
                                    <option value="[Ajuste de Personalização]">[Ajuste de Personalização]</option>
                                    <option value="[Erro de Dados ONET]">[Erro de Dados ONET]</option>
                                    <option value="[Outros]">[Outros]</option>
                                </select>
                            </div>

                            <div className="mb-4">
                                <label className="block text-xs font-bold text-gray-700 uppercase mb-1">
                                    Explicação Adicional (mínimo 10 caracteres) <span className="text-red-500">*</span>
                                </label>
                                <textarea
                                    value={returnReasonText}
                                    onChange={(e) => setReturnReasonText(e.target.value)}
                                    placeholder="Ex: Detalhe o motivo da devolução para a área anterior..."
                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                                    rows="3"
                                />
                            </div>

                            <div className="flex items-center justify-end gap-3 mt-6">
                                <button
                                    onClick={() => {
                                        setShowReturnModal(false)
                                        setReturnLabel('')
                                        setReturnReasonText('')
                                        setReturnReason('')
                                    }}
                                    className="px-4 py-2 bg-gray-300 text-gray-700 text-sm font-semibold rounded-lg hover:bg-gray-400 transition-colors"
                                >
                                    Cancelar
                                </button>
                                <button
                                    onClick={handleReturnStatus}
                                    disabled={!returnLabel || !returnReasonText || returnReasonText.trim().length < 10}
                                    className={`px-4 py-2 rounded-lg text-sm font-bold transition-colors ${returnLabel && returnReasonText && returnReasonText.trim().length >= 10
                                        ? 'bg-orange-600 text-white hover:bg-orange-700 font-bold shadow-md cursor-pointer'
                                        : 'bg-gray-300 text-gray-500 cursor-not-allowed border border-gray-310'
                                        }`}
                                >
                                    Devolver
                                </button>
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
                                setNewDeliveryDate('');
                                setQtySplits({});
                            }
                        }}
                    >
                        <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-hidden flex flex-col mx-4">
                            <div className="p-6 overflow-y-auto flex-1">
                                <h3 className="text-xl font-bold text-gray-900 mb-2">
                                    Sugerir Partição do Pedido
                                </h3>
                                <p className="text-xs text-gray-500 mb-4">
                                    Proponha o desmembramento técnico deste pedido em dois pedidos filhos (C1 e C2).
                                </p>
                                
                                <div className="mb-4">
                                    <label className="block text-xs font-bold text-gray-700 uppercase mb-1">
                                        Motivo da Sugestão (mínimo 10 caracteres) <span className="text-red-500">*</span>
                                    </label>
                                    <textarea
                                        value={partitionReason}
                                        onChange={(e) => setPartitionReason(e.target.value)}
                                        placeholder="Ex: Pedido muito grande, sugerir divisão em 2 entregas devido a capacidade produtiva..."
                                        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-purple-500 focus:outline-none text-gray-800 font-medium"
                                        rows="3"
                                    />
                                </div>

                                <div className="mb-4">
                                    <label className="block text-xs font-bold text-gray-700 uppercase mb-1">
                                        Nova Data de Entrega Prevista (C2) <span className="text-red-500">*</span>
                                    </label>
                                    <input
                                        type="date"
                                        value={newDeliveryDate}
                                        onChange={(e) => setNewDeliveryDate(e.target.value)}
                                        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-purple-500 focus:outline-none text-gray-800 font-medium"
                                        required
                                    />
                                </div>

                                <div className="mb-4">
                                    <label className="block text-xs font-bold text-gray-700 uppercase mb-2">
                                        Divisão de Quantidades dos Itens <span className="text-red-500">*</span>
                                    </label>
                                    <div className="border border-gray-200 rounded-lg overflow-hidden max-h-60 overflow-y-auto">
                                        <table className="w-full text-xs text-left text-gray-500">
                                            <thead className="text-[10px] text-gray-700 uppercase bg-gray-50 border-b border-gray-200 sticky top-0">
                                                <tr>
                                                    <th className="px-3 py-2">Item/SKU</th>
                                                    <th className="px-3 py-2 text-center">Original</th>
                                                    <th className="px-3 py-2 text-center">Qtd Filho 1 (C1)</th>
                                                    <th className="px-3 py-2 text-center">Qtd Filho 2 (C2)</th>
                                                    <th className="px-3 py-2 text-center">Status</th>
                                                </tr>
                                            </thead>
                                            <tbody className="divide-y divide-gray-200 bg-white">
                                                {selectedPO.items?.map((item) => {
                                                    const split = qtySplits[item.id] || [Math.ceil(item.quantity / 2), item.quantity - Math.ceil(item.quantity / 2)];
                                                    const q1 = split[0];
                                                    const q2 = split[1];
                                                    const sum = q1 + q2;
                                                    const isValid = sum === item.quantity;
                                                    
                                                    return (
                                                        <tr key={item.id} className="hover:bg-gray-50">
                                                            <td className="px-3 py-2 font-semibold text-gray-900">{item.sku}</td>
                                                            <td className="px-3 py-2 text-center font-bold text-gray-700">{item.quantity}</td>
                                                            <td className="px-3 py-2 text-center">
                                                                <input
                                                                    type="number"
                                                                    min="0"
                                                                    max={item.quantity}
                                                                    value={q1}
                                                                    onChange={(e) => {
                                                                        const val = parseInt(e.target.value) || 0;
                                                                        setQtySplits(prev => ({
                                                                            ...prev,
                                                                            [item.id]: [val, item.quantity - val]
                                                                        }));
                                                                    }}
                                                                    className="w-16 px-1.5 py-1 border border-gray-300 rounded text-center text-xs font-bold"
                                                                />
                                                            </td>
                                                            <td className="px-3 py-2 text-center">
                                                                <input
                                                                    type="number"
                                                                    min="0"
                                                                    max={item.quantity}
                                                                    value={q2}
                                                                    onChange={(e) => {
                                                                        const val = parseInt(e.target.value) || 0;
                                                                        setQtySplits(prev => ({
                                                                            ...prev,
                                                                            [item.id]: [item.quantity - val, val]
                                                                        }));
                                                                    }}
                                                                    className="w-16 px-1.5 py-1 border border-gray-300 rounded text-center text-xs font-bold"
                                                                />
                                                            </td>
                                                            <td className="px-3 py-2 text-center">
                                                                {isValid ? (
                                                                    <span className="text-green-650 font-bold">✓ Ok</span>
                                                                ) : (
                                                                    <span className="text-red-650 font-bold">⚠️ Erro</span>
                                                                )}
                                                            </td>
                                                        </tr>
                                                    );
                                                })}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            </div>

                            <div className="bg-gray-50 px-6 py-4 flex justify-end gap-3 border-t border-gray-200">
                                <button
                                    onClick={() => {
                                        setShowPartitionModal(false);
                                        setPartitionReason('');
                                        setNewDeliveryDate('');
                                        setQtySplits({});
                                    }}
                                    className="px-4 py-2 bg-gray-300 text-gray-700 text-sm font-semibold rounded-lg hover:bg-gray-400 transition-colors"
                                >
                                    Cancelar
                                </button>
                                <button
                                    onClick={handleSuggestPartition}
                                    disabled={!partitionReason || partitionReason.trim().length < 10 || !newDeliveryDate}
                                    className={`px-4 py-2 rounded-lg text-sm font-bold transition-colors ${partitionReason && partitionReason.trim().length >= 10 && newDeliveryDate
                                        ? 'bg-purple-600 text-white hover:bg-purple-700'
                                        : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                                        }`}
                                >
                                    Sugerir Partição
                                </button>
                            </div>
                        </div>
                    </div>
                )}

                {/* Freight Split Approval Modal */}
                {showFreightModal && (() => {
                    let rawFreight = selectedPO.shipping_cost;
                    if (rawFreight === 0 || rawFreight === null || rawFreight === undefined) {
                        if (selectedPO.items && selectedPO.items.length > 0) {
                            const firstItem = selectedPO.items[0];
                            if (firstItem.extra_metadata) {
                                rawFreight = firstItem.extra_metadata.freight ?? firstItem.extra_metadata.Freight;
                            }
                        }
                    }
                    let parentFreight = parseFloat(rawFreight) || 0;
                    return (
                        <div
                            className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
                            onClick={(e) => {
                                if (e.target === e.currentTarget) {
                                    setShowFreightModal(false);
                                    setFreightC1('');
                                    setFreightC2('');
                                }
                            }}
                        >
                            <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
                                <h3 className="text-xl font-bold text-gray-900 mb-2">
                                    Aprovar Partição - Rateio de Frete
                                </h3>
                                <p className="text-xs text-gray-500 mb-4">
                                    Rateie o valor do frete original do pedido pai entre os pedidos filhos (C1 e C2).
                                </p>
                                
                                <div className="bg-gray-50 p-3 rounded-lg border border-gray-200 mb-4 text-xs">
                                    <div className="flex justify-between font-semibold text-gray-700">
                                        <span>Frete Original (Pai):</span>
                                        <span>{formatCurrency(parentFreight)}</span>
                                    </div>
                                </div>

                                <div className="space-y-4 mb-6">
                                    <div>
                                        <label className="block text-xs font-bold text-gray-700 uppercase mb-1">
                                            Frete do Pedido Filho 1 (C1) <span className="text-red-500">*</span>
                                        </label>
                                        <input
                                            type="number"
                                            step="0.0001"
                                            value={freightC1}
                                            onChange={(e) => setFreightC1(e.target.value)}
                                            placeholder="Ex: 50.0000"
                                            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm text-gray-800 font-semibold focus:ring-2 focus:ring-purple-500 focus:outline-none"
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-xs font-bold text-gray-700 uppercase mb-1">
                                            Frete do Pedido Filho 2 (C2) <span className="text-red-500">*</span>
                                        </label>
                                        <input
                                            type="number"
                                            step="0.0001"
                                            value={freightC2}
                                            onChange={(e) => setFreightC2(e.target.value)}
                                            placeholder="Ex: 50.0000"
                                            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm text-gray-800 font-semibold focus:ring-2 focus:ring-purple-500 focus:outline-none"
                                        />
                                    </div>

                                    {(() => {
                                        const f1 = parseFloat(freightC1) || 0;
                                        const f2 = parseFloat(freightC2) || 0;
                                        const sum = f1 + f2;
                                        const diff = Math.abs(sum - parentFreight);
                                        const isValid = diff <= 0.01;
                                        
                                        return (
                                            <div className={`p-3 rounded-lg border text-xs font-semibold ${isValid ? 'bg-green-50 border-green-200 text-green-700' : 'bg-red-50 border-red-200 text-red-700'}`}>
                                                <div className="flex justify-between">
                                                    <span>Soma Alocada:</span>
                                                    <span>{formatCurrency(sum)}</span>
                                                </div>
                                                <div className="flex justify-between mt-1 text-[10px]">
                                                    <span>Status:</span>
                                                    <span>{isValid ? '✓ Valor bate exatamente!' : `⚠️ Falta R$ ${(parentFreight - sum).toFixed(4)}`}</span>
                                                </div>
                                            </div>
                                        );
                                    })()}
                                </div>

                                <div className="flex gap-3 justify-end">
                                    <button
                                        onClick={() => {
                                            setShowFreightModal(false);
                                            setFreightC1('');
                                            setFreightC2('');
                                        }}
                                        className="px-4 py-2 bg-gray-300 text-gray-700 text-sm font-semibold rounded-lg hover:bg-gray-400 transition-colors"
                                    >
                                        Cancelar
                                    </button>
                                    <button
                                        onClick={async () => {
                                            const f1 = parseFloat(freightC1) || 0;
                                            const f2 = parseFloat(freightC2) || 0;
                                            if (Math.abs(f1 + f2 - parentFreight) > 0.01) {
                                                showError(`A soma do frete dos filhos (${formatCurrency(f1 + f2)}) deve ser exatamente igual ao frete original do pai (${formatCurrency(parentFreight)})`);
                                                return;
                                            }
                                            
                                            try {
                                                const response = await api.post(`/kanban/pos/${selectedPO.id}/approve-partition`, {
                                                    freight_c1: f1,
                                                    freight_c2: f2
                                                });
                                                showSuccess(response.data.message);
                                                setShowFreightModal(false);
                                                setFreightC1('');
                                                setFreightC2('');
                                                await fetchBoard();
                                                handleCloseModal();
                                            } catch (err) {
                                                showError(err.response?.data?.detail || 'Erro ao aprovar rateio');
                                            }
                                        }}
                                        className="px-4 py-2 bg-purple-600 text-white text-sm font-semibold rounded-lg hover:bg-purple-700 transition-colors"
                                    >
                                        Aprovar Rateio e Liberar Filhos
                                    </button>
                                </div>
                            </div>
                        </div>
                    );
                })()}

                {/* Nested Link Cost Modal */}
                {showLinkCostModal && (
                    <div
                        className="fixed inset-0 bg-black bg-opacity-60 flex items-center justify-center z-[60] p-4"
                        onClick={(e) => {
                            if (e.target === e.currentTarget) {
                                setShowLinkCostModal(false);
                                setLinkingItem(null);
                            }
                        }}
                    >
                        <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full mx-4 overflow-hidden border border-gray-150 animate-scale-up">
                            {/* Modal Header */}
                            <div className="bg-slate-900 text-white px-6 py-4 flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <span className="text-xl">💰</span>
                                    <div>
                                        <h3 className="font-bold text-base md:text-lg">
                                            Vincular Custo do Material
                                        </h3>
                                        <p className="text-[10px] text-slate-350 font-medium">
                                            Item SKU: <span className="font-mono bg-slate-800 px-1 py-0.5 rounded font-bold">{linkingItem?.sku}</span>
                                        </p>
                                    </div>
                                </div>
                                <button
                                    onClick={() => {
                                        setShowLinkCostModal(false);
                                        setLinkingItem(null);
                                    }}
                                    className="text-slate-400 hover:text-white transition-colors cursor-pointer"
                                >
                                    <X className="w-5 h-5" />
                                </button>
                            </div>

                            {/* Search bar for existing materials */}
                            <div className="p-6 pb-2 border-b border-gray-100 bg-slate-50 relative">
                                <label className="block text-xs font-bold text-slate-700 uppercase mb-1.5">
                                    🔍 Buscar outro material existente
                                </label>
                                <div className="relative">
                                    <input
                                        type="text"
                                        value={searchQuery}
                                        onChange={(e) => handleSearchMaterials(e.target.value)}
                                        placeholder="Digite parte do SKU ou Nome para buscar..."
                                        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-xs font-semibold text-gray-800 focus:ring-2 focus:ring-slate-500 focus:outline-none"
                                    />
                                    {loadingSearchResults && (
                                        <span className="absolute right-3 top-2.5 text-[10px] text-gray-400 animate-pulse font-medium">Buscando...</span>
                                    )}
                                </div>

                                {/* Floating search results list */}
                                {searchResults.length > 0 && (
                                    <div className="absolute left-6 right-6 z-70 bg-white border border-gray-200 rounded-lg shadow-xl mt-1 max-h-48 overflow-y-auto">
                                        <ul className="divide-y divide-gray-100">
                                            {searchResults.map((mat) => (
                                                <li
                                                    key={mat.id || mat.sku}
                                                    onClick={() => handleSelectMaterial(mat)}
                                                    className="px-4 py-2 hover:bg-slate-100 cursor-pointer text-xs flex flex-col gap-0.5 font-medium"
                                                >
                                                    <span className="font-bold text-slate-900">{mat.sku}</span>
                                                    <span className="text-gray-500 text-[10px]">{mat.nome}</span>
                                                    <span className="text-[10px] text-slate-700">MP: R$ {parseFloat(mat.custo_mp_kg).toFixed(2)}/kg | Rend: {parseFloat(mat.rendimento).toFixed(2)} kg/un</span>
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}
                            </div>

                            {/* Cost form */}
                            <form onSubmit={handleSaveCostLink} className="p-6 space-y-4">
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <div>
                                        <label className="block text-xs font-bold text-gray-700 uppercase mb-1">
                                            SKU do Material <span className="text-red-500">*</span>
                                        </label>
                                        <input
                                            type="text"
                                            value={costForm.sku}
                                            onChange={(e) => handleCostFormChange('sku', e.target.value)}
                                            required
                                            disabled
                                            className="w-full px-3 py-2 bg-gray-100 border border-gray-300 rounded-lg text-xs font-bold text-gray-500 cursor-not-allowed"
                                        />
                                    </div>

                                    <div>
                                        <label className="block text-xs font-bold text-gray-700 uppercase mb-1">
                                            Nome / Descrição <span className="text-red-500">*</span>
                                        </label>
                                        <input
                                            type="text"
                                            value={costForm.nome}
                                            onChange={(e) => handleCostFormChange('nome', e.target.value)}
                                            required
                                            placeholder="Ex: Filme Termoencolhível Promaflex"
                                            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-xs font-semibold text-gray-800 focus:ring-2 focus:ring-slate-500 focus:outline-none"
                                        />
                                    </div>

                                    <div>
                                        <label className="block text-xs font-bold text-gray-700 uppercase mb-1">
                                            Custo MP por kg (R$) <span className="text-red-500">*</span>
                                        </label>
                                        <input
                                            type="text"
                                            value={costForm.custo_mp_kg}
                                            onChange={(e) => handleCostFormChange('custo_mp_kg', e.target.value)}
                                            required
                                            placeholder="Ex: 14.50"
                                            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-xs font-bold text-gray-800 focus:ring-2 focus:ring-slate-500 focus:outline-none"
                                        />
                                    </div>

                                    <div>
                                        <label className="block text-xs font-bold text-gray-700 uppercase mb-1">
                                            Rendimento (kg / un) <span className="text-red-500">*</span>
                                        </label>
                                        <input
                                            type="text"
                                            value={costForm.rendimento}
                                            onChange={(e) => handleCostFormChange('rendimento', e.target.value)}
                                            required
                                            placeholder="Ex: 0.1250"
                                            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-xs font-bold text-gray-800 focus:ring-2 focus:ring-slate-500 focus:outline-none"
                                        />
                                    </div>

                                    <div className="md:col-span-2">
                                        <label className="block text-xs font-bold text-gray-700 uppercase mb-1">
                                            Índice de Impostos (%) <span className="text-red-500">*</span>
                                        </label>
                                        <input
                                            type="text"
                                            value={costForm.indice_impostos}
                                            onChange={(e) => handleCostFormChange('indice_impostos', e.target.value)}
                                            required
                                            placeholder="Ex: 22.25"
                                            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-xs font-bold text-gray-800 focus:ring-2 focus:ring-slate-500 focus:outline-none"
                                        />
                                    </div>
                                </div>

                                {/* Modal Footer Actions */}
                                <div className="flex gap-3 justify-end pt-4 border-t border-gray-150">
                                    <button
                                        type="button"
                                        onClick={() => {
                                            setShowLinkCostModal(false);
                                            setLinkingItem(null);
                                        }}
                                        className="px-4 py-2 bg-gray-200 text-gray-700 text-xs font-bold rounded-lg hover:bg-gray-300 transition-colors cursor-pointer"
                                    >
                                        Cancelar
                                    </button>
                                    <button
                                        type="submit"
                                        disabled={savingCost}
                                        className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold rounded-lg transition-colors cursor-pointer flex items-center gap-1.5 shadow-md"
                                    >
                                        {savingCost ? 'Salvando...' : 'Confirmar Vínculo'}
                                    </button>
                                </div>
                            </form>
                        </div>
                    </div>
                )}
            </div>
        </ErrorBoundary>
    )
}

export default KanbanPage
