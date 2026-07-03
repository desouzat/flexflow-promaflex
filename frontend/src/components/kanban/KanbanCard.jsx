import React, { useMemo, useState, useRef } from 'react'
import {
    Calendar,
    DollarSign,
    Package,
    AlertCircle,
    CheckCircle,
    Clock,
    Globe,
    Star,
    RefreshCw,
    Zap,
    Split,
    Tag,
    Truck
} from 'lucide-react'
import { STRATEGIC_INDICATORS } from '../../config/helpConfig'
import { calculatePOMargins } from '../../utils/marginCalculator'
import { useAuth } from '../../context/AuthContext'

const KanbanCard = ({ po, onCardClick, compactView = false }) => {
    const { user } = useAuth()
    const isPrivileged = ['admin', 'master'].includes((user?.role || '').toLowerCase())
    
    const [showTooltip, setShowTooltip] = useState(false)
    const [tooltipCoords, setTooltipCoords] = useState({ top: 0, left: 0 })
    const badgeRef = useRef(null)

    const handleMouseEnter = () => {
        if (badgeRef.current) {
            const rect = badgeRef.current.getBoundingClientRect()
            let left = rect.left - 330 // default: popover to the left of the badge
            if (left < 10) {
                // If it goes off-screen to the left, align it to the right of the badge
                left = rect.right + 10
            }
            
            // Adjust top to make sure it doesn't go off the bottom of the screen
            let top = rect.top - 8
            const popoverHeight = 285 // estimated height of the popover
            if (top + popoverHeight > window.innerHeight) {
                top = window.innerHeight - popoverHeight - 10
            }
            // Ensure top is not negative
            top = Math.max(10, top)

            setTooltipCoords({ top, left })
            setShowTooltip(true)
        }
    }

    const handleMouseLeave = () => {
        setShowTooltip(false)
    }

    console.log('Rendering PO:', po);
    // Ensure po object has safe defaults
    const getRobustName = (val) => {
        if (!val || val === 'null' || val === 'None' || String(val).trim() === '') {
            return 'Desconhecido';
        }
        let strVal = String(val);
        if (strVal.includes('Fornecedor')) {
            strVal = strVal.replace(/Fornecedor/g, 'Cliente');
        }
        if (strVal.includes('fornecedor')) {
            strVal = strVal.replace(/fornecedor/g, 'cliente');
        }
        return strVal;
    };

    const safepo = {
        po_number: po?.po_number || 'N/A',
        client_name: getRobustName(po?.client_name || po?.supplier_name),
        vendor_name: getRobustName(po?.vendor_name || po?.supplier_name || po?.client_name),
        supplier_name: getRobustName(po?.supplier_name || po?.client_name),
        status: po?.status || 'pending',
        total_value: po?.total_value || 0,
        expected_delivery_date: po?.data_limite || po?.expected_delivery_date || null,
        delivery_date: po?.delivery_date || null,
        data_limite: po?.data_limite || null,
        items_count: po?.items_count || 0,
        priority: po?.priority || 'normal',
        ...po
    }

    const isReplacement = safepo.is_replacement || safepo.extra_metadata?.is_replacement || false
    // UAT-FIX-2: Manual exchange/return card detection [9.3]
    const isExchangeReturn = (
        safepo.items?.[0]?.extra_metadata?.is_exchange_return ||
        safepo.extra_metadata?.is_exchange_return ||
        (safepo.po_number || '').startsWith('TR-')
    ) || false

    const marginInfo = useMemo(() => {
        if (safepo.margin_percentage === '***' || safepo.margin_global === '***') {
            return {
                status: 'OK',
                margin: '***',
                badgeColor: 'gray',
                formattedMargin: '***',
                breakdown: null
            };
        }
        return calculatePOMargins(safepo)
    }, [safepo.items, safepo.total_value, safepo.payment_terms, safepo.margin_percentage, safepo.margin_global])

    const getStatusColor = (status) => {
        const colors = {
            pending: 'bg-yellow-100 text-yellow-800 border-yellow-200',
            approved: 'bg-green-100 text-green-800 border-green-200',
            rejected: 'bg-red-100 text-red-800 border-red-200',
            in_transit: 'bg-blue-100 text-blue-800 border-blue-200',
            delivered: 'bg-purple-100 text-purple-800 border-purple-200',
        }
        return colors[status] || 'bg-gray-100 text-gray-800 border-gray-200'
    }

    const getStatusIcon = (status) => {
        const icons = {
            pending: Clock,
            approved: CheckCircle,
            rejected: AlertCircle,
            in_transit: Package,
            delivered: CheckCircle,
        }
        const Icon = icons[status] || Clock
        return <Icon className="w-4 h-4" />
    }

    // Calculate SLA status based on deadline
    const getSLAStatus = () => {
        if (!safepo.expected_delivery_date) return 'green'

        const deadline = new Date(safepo.expected_delivery_date)
        const today = new Date()
        const daysUntilDeadline = Math.ceil((deadline - today) / (1000 * 60 * 60 * 24))

        // If already delivered, return green
        if (safepo.status === 'delivered') return 'green'

        // Red: overdue or less than 3 days
        if (daysUntilDeadline < 3) return 'red'

        // Orange: 3-7 days
        if (daysUntilDeadline < 7) return 'orange'

        // Green: more than 7 days
        return 'green'
    }

    const getSLABorderColor = (slaStatus) => {
        const colors = {
            green: 'border-l-green-500',
            orange: 'border-l-orange-500',
            red: 'border-l-red-500',
        }
        return colors[slaStatus] || 'border-l-gray-300'
    }

    const formatCurrency = (value) => {
        return new Intl.NumberFormat('pt-BR', {
            style: 'currency',
            currency: 'BRL',
        }).format(value || 0)
    }

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

    // Get strategic indicators from metadata
    const getStrategicIndicators = () => {
        const indicators = []
        const metadata = safepo.extra_metadata || {}

        const isPersonalized = metadata.is_personalized || metadata.is_urgent || safepo.priority === 'high' || (safepo.items && safepo.items.some(it => it.is_personalized))
        if (isPersonalized) {
            indicators.push({
                label: 'Personalizado',
                key: 'is_personalized',
                icon: Zap,
                color: 'red',
                tooltip: 'Personalizado - Pedido Customizado'
            })
        }

        const isNewClient = metadata.is_new_client || safepo.is_new_client || metadata.is_first_order || false
        if (isNewClient) {
            indicators.push({
                label: 'Cliente Novo',
                key: 'is_new_client',
                icon: Star,
                color: 'amber',
                tooltip: 'Cliente Novo - Garantir qualidade premium'
            })
        }

        if (metadata.is_export || safepo.is_export) {
            indicators.push({
                label: 'Exportação',
                key: 'is_export',
                icon: Globe,
                color: 'blue',
                tooltip: 'Pedido de exportação - Documentação internacional'
            })
        }

        const isReplacement = safepo.is_replacement || metadata.is_replacement || false
        if (isReplacement) {
            indicators.push({
                label: 'Troca/Reposição',
                key: 'is_replacement',
                icon: RefreshCw,
                color: 'cyan',
                tooltip: 'Troca/Reposição - SLA Prioritário (50%)'
            })
        }

        return indicators
    }

    const strategicIndicators = getStrategicIndicators()
    const slaStatus = getSLAStatus()

    // Calculate SLA elapsed percentage for premium progress indicator on card
    const slaPercent = useMemo(() => {
        if (!safepo.created_at || (!safepo.expected_delivery_date && !safepo.data_limite)) return null
        const start = new Date(safepo.created_at).getTime()
        const originalEnd = new Date(safepo.expected_delivery_date || safepo.data_limite).getTime()
        const now = new Date().getTime()
        if (originalEnd <= start) return 100
        
        let totalSlaDuration = originalEnd - start
        if (isReplacement) {
            totalSlaDuration = totalSlaDuration * 0.5
        }
        
        const percent = ((now - start) / totalSlaDuration) * 100
        return Math.max(0, Math.min(100, percent))
    }, [safepo.created_at, safepo.expected_delivery_date, safepo.data_limite, isReplacement])

    // Check if this PO is waiting for partition decision.
    // FIX [§2]: Only trigger when status_macro is strictly 'WAITING_COMMERCIAL_PARTITION'.
    // Previously, the loose `safepo.partition_reason` fallback caused child POs (which
    // inherit partition_reason from the parent) to display the badge even after they were
    // approved and routed to the PCP column — this was the spurious "Aguardando aprovação
    // da partição" label that appeared in the wrong column.
    const isWaitingPartition = safepo.status_macro === 'WAITING_COMMERCIAL_PARTITION'

    if (compactView) {
        return (
            <div
                onClick={() => onCardClick?.(safepo)}
                className={`${safepo.status_macro === 'WAITING_MATERIAL' ? 'bg-purple-50 border-purple-300 ring-2 ring-purple-300' : 'bg-white border-gray-200'} rounded-lg shadow-sm border ${safepo.sla_paused_at ? 'ring-2 ring-gray-300 ring-offset-1 border-gray-300 shadow-gray-250' : ''} border-l-4 ${getSLABorderColor(slaStatus)} p-3 hover:shadow-md transition-all cursor-pointer`}
            >
                <div className="flex items-center justify-between mb-2">
                    <h3 className="font-semibold text-gray-900 text-sm">
                        PO #{safepo.po_number}
                    </h3>
                    <div className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${getStatusColor(safepo.status)}`}>
                        {getStatusIcon(safepo.status)}
                    </div>
                </div>

                {safepo.sla_paused_at && (
                    <div className="mb-2">
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-extrabold bg-gray-100 text-gray-700 border border-gray-300 animate-pulse">
                            ⏸️ SLA PAUSADO (AGUARDANDO INSUMO)
                        </span>
                    </div>
                )}

                {safepo.status_macro === 'WAITING_MATERIAL' && (
                    <div className="mb-2">
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-bold bg-purple-100 text-purple-800 border border-purple-300 animate-pulse">
                            📦 AGUARDANDO INSUMO
                        </span>
                    </div>
                )}

                {safepo.extra_metadata?.credit_reproved === true && (safepo.status_macro === 'SUBMITTED' || safepo.status === 'Comercial') && (
                    <div className="mb-2">
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-extrabold bg-red-100 text-red-800 border border-red-300 animate-pulse">
                            🚫 CRÉDITO REPROVADO
                        </span>
                    </div>
                )}

                {safepo.status_macro === 'SHIPPING' && (
                    <div className="mb-2">
                        {(safepo.partition_metadata?.current_phase === 'FASE_A' || safepo.extra_metadata?.current_phase === 'FASE_A') ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-bold bg-amber-50 text-amber-800 border border-amber-200 animate-pulse" title="FASE A: FRETE">
                                🚛 FASE A: FRETE
                            </span>
                        ) : (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-bold bg-blue-50 text-blue-800 border border-blue-200" title="FASE B: DESPACHO">
                                📦 FASE B: DESPACHO
                            </span>
                        )}
                    </div>
                )}

                {/* FF-HARDENING-013 Issue A: Red badge for CANCELLED status */}
                {safepo.status_macro === 'CANCELLED' && (
                    <div className="mb-2">
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-extrabold bg-red-100 text-red-800 border border-red-400">
                            ❌ CANCELADO
                        </span>
                    </div>
                )}

                {isReplacement && (
                    <div className="mb-2">
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[9px] font-bold bg-cyan-100 text-cyan-800 border border-cyan-300">
                            🔄 TROCA/REPOSIÇÃO
                        </span>
                    </div>
                )}

                {/* UAT-FIX-2: Exchange/Return card badge (compact) */}
                {isExchangeReturn && (
                    <div className="mb-2">
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-extrabold bg-orange-100 text-orange-800 border border-orange-400">
                            🔄 TROCA/DEVOLUÇÃO
                        </span>
                    </div>
                )}

                <p className="font-bold text-gray-800 mb-2" style={{ fontSize: '12px' }}>
                    Cliente: {safepo.client_name}
                </p>
                <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-gray-900">
                        Vl.Pedido: {formatCurrency(safepo.total_value)}
                    </span>
                    <span className="text-gray-500 font-medium flex items-center gap-1" title="Prazo interno de segurança (2 dias de margem sobre o ONET)">
                        <Calendar className="w-3.5 h-3.5 text-gray-400" />
                        Dt.Entrega Estimada: {formatDate(safepo.expected_delivery_date)}
                    </span>
                </div>

                {/* Mini SLA progress bar in compact view */}
                {slaPercent !== null && (
                    <div className="mt-2" title={isReplacement ? '🔥 SLA DE TROCA ATIVO' : 'Progresso de SLA'}>
                        <div className="w-full bg-gray-150 rounded-full h-1 overflow-hidden border border-gray-200">
                            <div 
                                className={`h-full transition-all duration-500 ${isReplacement ? 'bg-cyan-500' : 'bg-emerald-500'}`} 
                                style={{ width: `${slaPercent}%` }}
                            />
                        </div>
                    </div>
                )}
            </div>
        )
    }

    return (
        <div
            onClick={() => onCardClick?.(safepo)}
            className={`${safepo.status_macro === 'WAITING_MATERIAL' ? 'bg-purple-50 border-purple-300 ring-2 ring-purple-300' : 'bg-white border-gray-200'} rounded-lg shadow-sm border ${safepo.sla_paused_at ? 'ring-2 ring-gray-300 ring-offset-1 border-gray-300 shadow-gray-250' : ''} border-l-4 ${getSLABorderColor(slaStatus)} p-4 hover:shadow-md transition-all cursor-pointer`}
        >
            {/* Gray Badge for Paused SLA */}
            {safepo.sla_paused_at && (
                <div className="mb-3 px-3 py-2 bg-gray-100 border border-gray-300 rounded-lg flex items-center gap-2 animate-pulse" title="⏸️ SLA PAUSADO (AGUARDANDO INSUMO)">
                    <span className="text-xs font-extrabold text-gray-600 flex items-center gap-1.5">
                        <span>⏸️</span> SLA PAUSADO (AGUARDANDO INSUMO)
                    </span>
                </div>
            )}

            {/* Purple Badge for Waiting Material */}
            {safepo.status_macro === 'WAITING_MATERIAL' && (
                <div className="mb-3 px-3 py-2 bg-purple-100 border border-purple-300 rounded-lg flex items-center gap-2 animate-pulse" title="📦 AGUARDANDO INSUMO">
                    <span className="text-xs font-extrabold text-purple-700 flex items-center gap-1.5 font-sans">
                        <span>📦</span> AGUARDANDO INSUMO
                    </span>
                </div>
            )}

            {/* Purple Badge for Partition Decision */}
            {isWaitingPartition && (
                <div className="mb-3 px-3 py-2 bg-purple-100 border border-purple-300 rounded-lg flex items-center gap-2">
                    <Split className="w-4 h-4 text-purple-700" />
                    <span className="text-xs font-semibold text-purple-700">
                        Aguardando Decisão de Partição
                    </span>
                </div>
            )}

            {/* Red Stamp for Credit Reproved */}
            {safepo.extra_metadata?.credit_reproved === true && (safepo.status_macro === 'SUBMITTED' || safepo.status === 'Comercial') && (
                <div className="mb-3 px-3 py-2 bg-red-100 border border-red-300 rounded-lg flex items-center gap-2 animate-pulse" title="🚫 CRÉDITO REPROVADO">
                    <span className="text-xs font-extrabold text-red-700 flex items-center gap-1.5">
                        <span>🚫</span> CRÉDITO REPROVADO
                    </span>
                </div>
            )}

            {/* Dual-Phase Badge for SHIPPING stage */}
            {safepo.status_macro === 'SHIPPING' && (
                (safepo.partition_metadata?.current_phase === 'FASE_A' || safepo.extra_metadata?.current_phase === 'FASE_A') ? (
                    <div className="mb-3 px-3 py-2 bg-amber-50 border border-amber-200 rounded-lg flex items-center gap-2" title="FASE A: FRETE">
                        <Tag className="w-4 h-4 text-amber-600 animate-pulse" />
                        <span className="text-xs font-bold text-yellow-850">
                            🚛 FASE A: FRETE
                        </span>
                    </div>
                ) : (
                    <div className="mb-3 px-3 py-2 bg-blue-50 border border-blue-200 rounded-lg flex items-center gap-2" title="FASE B: DESPACHO">
                        <Truck className="w-4 h-4 text-blue-600" />
                        <span className="text-xs font-bold text-blue-850">
                            📦 FASE B: DESPACHO
                        </span>
                    </div>
                )
            )}

            {/* FF-HARDENING-013 Issue A: Red badge for CANCELLED status (full view) */}
            {safepo.status_macro === 'CANCELLED' && (
                <div className="mb-3 px-3 py-2 bg-red-50 border-2 border-red-400 rounded-lg flex items-center gap-2">
                    <span className="text-xs font-extrabold text-red-700 flex items-center gap-1.5">
                        <span>❌</span> CANCELADO
                    </span>
                </div>
            )}

            {/* Cyan Badge for Replacement (Troca/Reposição) */}
            {isReplacement && (
                <div className="mb-3 px-3 py-2 bg-cyan-55 border border-cyan-300 rounded-lg flex items-center gap-2 animate-pulse" title="🔥 SLA DE TROCA ATIVO">
                    <RefreshCw className="w-4 h-4 text-cyan-600 animate-spin-slow" />
                    <span className="text-xs font-extrabold text-cyan-700">
                        🔥 SLA DE TROCA ATIVO
                    </span>
                </div>
            )}

            {/* UAT-FIX-2: Orange/Red Badge for Exchange/Return card (manual, TR-prefixed) */}
            {isExchangeReturn && (
                <div className="mb-3 px-3 py-2 bg-orange-50 border-2 border-orange-400 rounded-lg flex items-center gap-2" title="🔄 TROCA/DEVOLUÇÃO — SLA 50% do padrão">
                    <RefreshCw className="w-4 h-4 text-orange-600" />
                    <span className="text-xs font-extrabold text-orange-700">
                        🔄 TROCA/DEVOLUÇÃO
                    </span>
                    <span className="ml-auto text-[9px] font-bold text-orange-500 bg-orange-100 border border-orange-300 rounded px-1.5 py-0.5">
                        SLA 50%
                    </span>
                </div>
            )}

            {/* Header */}
            <div className="flex items-start justify-between mb-3">
                <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1.5">
                        <h3 className="font-semibold text-gray-900 text-sm">
                            PO #{safepo.po_number}
                        </h3>
                        {/* Strategic Indicators */}
                        {strategicIndicators.length > 0 && (
                            <div className="flex items-center gap-1">
                                {strategicIndicators.map((indicator) => {
                                    const IconComponent = indicator.icon
                                    return (
                                        <div
                                            key={indicator.key}
                                            className={`p-1 rounded-full bg-${indicator.color}-100 text-${indicator.color}-600`}
                                            title={indicator.tooltip}
                                        >
                                            <IconComponent className="w-3 h-3" />
                                        </div>
                                    )
                                })}
                            </div>
                        )}
                    </div>
                    <p className="font-bold text-gray-800 mb-1" style={{ fontSize: '12px' }}>
                        Cliente: {safepo.client_name}
                    </p>
                </div>
                <div className={`flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium border ${getStatusColor(safepo.status)}`}>
                    {getStatusIcon(safepo.status)}
                    <span className="capitalize">{(safepo.status || '').replace('_', ' ')}</span>
                </div>
            </div>

            {/* Details */}
            <div className="space-y-2">
                <div className="flex items-center gap-2 text-sm">
                    <DollarSign className="w-4 h-4 text-gray-400 flex-shrink-0" />
                    <span className="font-semibold text-gray-900">
                        Vl.Pedido: {formatCurrency(safepo.total_value)}
                    </span>
                </div>

                <div className="flex items-center gap-2 text-sm text-gray-600" title="Prazo interno de segurança (2 dias de margem sobre o ONET)">
                    <Calendar className="w-4 h-4 text-gray-400 flex-shrink-0" />
                    <span className="text-xs font-medium text-gray-700">
                        Dt.Entrega Estimada: {formatDate(safepo.expected_delivery_date)}
                    </span>
                </div>

                {safepo.items_count > 0 && (
                    <div className="flex items-center gap-2 text-sm text-gray-600">
                        <Package className="w-4 h-4 text-gray-400 flex-shrink-0" />
                        <span className="text-xs">
                            {safepo.items_count} {safepo.items_count === 1 ? 'item' : 'items'}
                        </span>
                    </div>
                )}
            </div>

            {/* Margin Indicator with Popover */}
            {isPrivileged && (
                <div className="mt-3 pt-3 border-t border-gray-100 flex items-center justify-between">
                    <span className="text-xs text-gray-500 font-medium">Margem Estimada:</span>
                    {marginInfo.status === 'PENDENTE_PCP' ? (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-gray-100 text-gray-800 border border-gray-300">
                            PENDENTE PCP
                        </span>
                    ) : (
                        <div className="inline-block">
                            <span 
                                ref={badgeRef}
                                onMouseEnter={handleMouseEnter}
                                onMouseLeave={handleMouseLeave}
                                className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold border cursor-help shadow-sm transition-all duration-250 hover:scale-105 ${
                                    marginInfo.badgeColor === 'green' ? 'bg-green-100 text-green-800 border-green-300' :
                                    marginInfo.badgeColor === 'yellow' ? 'bg-yellow-100 text-yellow-800 border-yellow-300' :
                                    marginInfo.badgeColor === 'orange' ? 'bg-orange-100 text-orange-850 border-orange-300' :
                                    'bg-red-100 text-red-800 border-red-300'
                                }`}
                            >
                                {marginInfo.formattedMargin}
                            </span>
                            
                             {/* Premium Popover "O Extrato" - floats independent of column overflow using fixed layout */}
                             {showTooltip && marginInfo.breakdown && (
                                 <div 
                                     style={{
                                         position: 'fixed',
                                         top: `${tooltipCoords.top}px`,
                                         left: `${tooltipCoords.left}px`,
                                         width: '320px',
                                         zIndex: 9999
                                     }}
                                     className="bg-slate-900 text-slate-100 p-4 rounded-xl shadow-2xl text-xs border border-slate-700 pointer-events-none animate-fade-in"
                                 >
                                     <h4 className="font-bold text-white mb-2 border-b border-slate-700 pb-1 flex items-center justify-between">
                                         <span>📊 Extrato de Margem PO</span>
                                     </h4>
                                     <div className="space-y-1 font-sans font-medium">
                                         <div className="flex justify-between py-1">
                                             <span className="text-slate-400">(+) Valor Bruto:</span>
                                             <span className="font-mono text-white">{formatCurrency(marginInfo.breakdown.gross)}</span>
                                         </div>
                                         <div className="flex justify-between text-amber-400 py-1">
                                             <span className="text-slate-400">(-) Ajuste VP (Prazo):</span>
                                             <span className="font-mono">-{formatCurrency(marginInfo.breakdown.vpDiscount)}</span>
                                         </div>
                                         <div className="flex justify-between border-t border-slate-800 pt-1 pb-1">
                                             <span className="text-slate-400 font-semibold">(=) Valor Presente (VP):</span>
                                             <span className="font-semibold font-mono text-white">{formatCurrency(marginInfo.breakdown.vp)}</span>
                                         </div>
                                         <div className="flex justify-between text-red-400 py-1">
                                             <span className="text-slate-400">(-) Impostos (22.25%):</span>
                                             <span className="font-mono">-{formatCurrency(marginInfo.breakdown.taxes)}</span>
                                         </div>
                                         {marginInfo.breakdown.commission > 0 && (
                                             <div className="flex justify-between text-red-400 py-1">
                                                 <span className="text-slate-400">(-) Comissão:</span>
                                                 <span className="font-mono">-{formatCurrency(marginInfo.breakdown.commission)}</span>
                                             </div>
                                         )}
                                         {marginInfo.breakdown.freight > 0 && (
                                             <div className="flex justify-between text-red-400 py-1">
                                                 <span className="text-slate-400">(-) Frete Total:</span>
                                                 <span className="font-mono">-{formatCurrency(marginInfo.breakdown.freight)}</span>
                                             </div>
                                         )}
                                         <div className="border-t border-slate-800 my-1"></div>
                                         <div className="flex justify-between text-emerald-400 font-bold py-1">
                                             <span className="text-slate-300">(=) Margem Absoluta:</span>
                                             <span className="font-mono text-white">{formatCurrency(marginInfo.breakdown.absoluteMargin)}</span>
                                         </div>
                                         <div className="flex justify-between text-slate-300 py-1">
                                             <span className="text-slate-400">(/) Custo Industrial:</span>
                                             <span className="font-mono text-white">{formatCurrency(marginInfo.breakdown.costs)}</span>
                                         </div>
                                         <div className="border-t border-slate-700 pt-1.5 flex justify-between items-center">
                                             <span className="font-bold text-white">Margem Final (%):</span>
                                            <span className={`font-mono text-sm font-bold ${
                                                marginInfo.badgeColor === 'green' ? 'text-green-400' :
                                                marginInfo.badgeColor === 'yellow' ? 'text-yellow-400' :
                                                marginInfo.badgeColor === 'orange' ? 'text-orange-400' :
                                                'text-red-400'
                                            }`}>
                                                {marginInfo.formattedMargin}
                                            </span>
                                        </div>
                                    </div>
                                 </div>
                             )}
                        </div>
                    )}
                </div>
            )}

            {/* SLA Progress Bar on Card */}
            {slaPercent !== null && (
                <div className="mt-3 pt-3 border-t border-gray-100" title={isReplacement ? '🔥 SLA DE TROCA ATIVO' : 'Progresso de SLA'}>
                    <div className="flex justify-between text-[10px] text-gray-500 font-semibold mb-1">
                        <span className={isReplacement ? 'text-cyan-700 font-extrabold animate-pulse' : ''}>
                            {isReplacement ? '🔥 SLA DE TROCA ATIVO' : 'SLA'}
                        </span>
                        <span className={isReplacement ? 'text-cyan-600 font-extrabold' : ''}>
                            {slaPercent.toFixed(0)}%
                        </span>
                    </div>
                    <div className="w-full bg-gray-100 rounded-full h-1.5 overflow-hidden border border-gray-250">
                        <div 
                            className={`h-full transition-all duration-500 ${isReplacement ? 'bg-cyan-500' : 'bg-emerald-500'}`} 
                            style={{ width: `${slaPercent}%` }}
                        />
                    </div>
                </div>
            )}

            {/* SLA Indicator */}
            {slaStatus !== 'green' && (
                <div className="mt-3 pt-3 border-t border-gray-100">
                    <div className={`flex items-center gap-1 text-xs ${slaStatus === 'red' ? 'text-red-600' : 'text-orange-600'}`}>
                        <AlertCircle className="w-3 h-3" />
                        <span className="font-medium">
                            {slaStatus === 'red' ? 'Urgent - Deadline approaching!' : 'Attention needed'}
                        </span>
                    </div>
                </div>
            )}

            {/* Priority Indicator */}
            {safepo.priority === 'high' && (
                <div className="mt-3 pt-3 border-t border-gray-100">
                    <div className="flex items-center gap-1 text-xs text-red-600">
                        <AlertCircle className="w-3 h-3" />
                        <span className="font-medium">High Priority</span>
                    </div>
                </div>
            )}
        </div>
    )
}

export default KanbanCard
