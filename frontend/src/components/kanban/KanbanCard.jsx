import React, { useMemo } from 'react'
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
    Split
} from 'lucide-react'
import { STRATEGIC_INDICATORS } from '../../config/helpConfig'
import { calculatePOMargins } from '../../utils/marginCalculator'

const KanbanCard = ({ po, onCardClick, compactView = false }) => {
    // Ensure po object has safe defaults
    const safepo = {
        po_number: po?.po_number || 'N/A',
        supplier_name: po?.supplier_name || 'Unknown Supplier',
        status: po?.status || 'pending',
        total_value: po?.total_value || 0,
        expected_delivery_date: po?.expected_delivery_date || null,
        items_count: po?.items_count || 0,
        priority: po?.priority || 'normal',
        ...po
    }

    const marginInfo = useMemo(() => {
        return calculatePOMargins(safepo)
    }, [safepo.items, safepo.total_value, safepo.payment_terms])

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
        if (/^\d{4}-\d{2}-\d{2}$/.test(dateString)) {
            const [year, month, day] = dateString.split('-')
            return `${day}/${month}/${year}`
        }
        return new Date(dateString).toLocaleDateString('pt-BR')
    }

    // Get strategic indicators from metadata
    const getStrategicIndicators = () => {
        const indicators = []
        const metadata = safepo.extra_metadata || {}

        if (metadata.is_export) {
            indicators.push({
                ...STRATEGIC_INDICATORS.is_export,
                key: 'is_export',
                icon: Globe
            })
        }

        if (metadata.is_first_order) {
            indicators.push({
                ...STRATEGIC_INDICATORS.is_first_order,
                key: 'is_first_order',
                icon: Star
            })
        }

        if (metadata.is_replacement) {
            indicators.push({
                ...STRATEGIC_INDICATORS.is_replacement,
                key: 'is_replacement',
                icon: RefreshCw
            })
        }

        if (metadata.is_urgent || safepo.priority === 'high') {
            indicators.push({
                ...STRATEGIC_INDICATORS.is_urgent,
                key: 'is_urgent',
                icon: Zap
            })
        }

        return indicators
    }

    const strategicIndicators = getStrategicIndicators()
    const slaStatus = getSLAStatus()

    // Check if this PO is waiting for partition decision
    const isWaitingPartition = safepo.extra_metadata?.waiting_partition ||
        safepo.status_macro === 'WAITING_COMMERCIAL_PARTITION' ||
        safepo.partition_reason

    if (compactView) {
        return (
            <div
                onClick={() => onCardClick?.(safepo)}
                className={`bg-white rounded-lg shadow-sm border border-gray-200 border-l-4 ${getSLABorderColor(slaStatus)} p-3 hover:shadow-md transition-shadow cursor-pointer`}
            >
                <div className="flex items-center justify-between mb-2">
                    <h3 className="font-semibold text-gray-900 text-sm">
                        PO #{safepo.po_number}
                    </h3>
                    <div className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${getStatusColor(safepo.status)}`}>
                        {getStatusIcon(safepo.status)}
                    </div>
                </div>
                <p className="text-xs text-gray-600 mb-2">{safepo.supplier_name}</p>
                <div className="flex items-center justify-between text-xs">
                    <span className="font-medium text-gray-900">
                        {formatCurrency(safepo.total_value)}
                    </span>
                    <span className="text-gray-500">
                        {formatDate(safepo.expected_delivery_date)}
                    </span>
                </div>
            </div>
        )
    }

    return (
        <div
            onClick={() => onCardClick?.(safepo)}
            className={`bg-white rounded-lg shadow-sm border border-gray-200 border-l-4 ${getSLABorderColor(slaStatus)} p-4 hover:shadow-md transition-shadow cursor-pointer`}
        >
            {/* Purple Badge for Partition Decision */}
            {isWaitingPartition && (
                <div className="mb-3 px-3 py-2 bg-purple-100 border border-purple-300 rounded-lg flex items-center gap-2">
                    <Split className="w-4 h-4 text-purple-700" />
                    <span className="text-xs font-semibold text-purple-700">
                        Aguardando Decisão de Partição
                    </span>
                </div>
            )}

            {/* Header */}
            <div className="flex items-start justify-between mb-3">
                <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
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
                    <p className="text-xs text-gray-600">{safepo.supplier_name}</p>
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
                    <span className="font-medium text-gray-900">
                        {formatCurrency(safepo.total_value)}
                    </span>
                </div>

                <div className="flex items-center gap-2 text-sm text-gray-600">
                    <Calendar className="w-4 h-4 text-gray-400 flex-shrink-0" />
                    <span className="text-xs">
                        {formatDate(safepo.expected_delivery_date)}
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
            <div className="mt-3 pt-3 border-t border-gray-100 flex items-center justify-between">
                <span className="text-xs text-gray-500 font-medium">Margem Estimada:</span>
                {marginInfo.status === 'PENDENTE_PCP' ? (
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-gray-100 text-gray-800 border border-gray-300">
                        PENDENTE PCP
                    </span>
                ) : (
                    <div className="relative group inline-block">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold border cursor-help shadow-sm transition-all duration-250 hover:scale-105 ${
                            marginInfo.badgeColor === 'green' ? 'bg-green-100 text-green-800 border-green-300' :
                            marginInfo.badgeColor === 'yellow' ? 'bg-yellow-100 text-yellow-800 border-yellow-300' :
                            marginInfo.badgeColor === 'orange' ? 'bg-orange-100 text-orange-800 border-orange-300' :
                            'bg-red-100 text-red-800 border-red-300'
                        }`}>
                            {marginInfo.formattedMargin}
                        </span>
                        
                        {/* Premium Popover "O Extrato" */}
                        <div className="absolute z-50 hidden group-hover:block bg-slate-900 text-slate-100 p-4 rounded-xl shadow-2xl w-80 text-xs border border-slate-700 -top-2 right-full mr-3 pointer-events-none animate-fade-in">
                            <h4 className="font-bold text-white mb-2 border-b border-slate-700 pb-1 flex items-center justify-between">
                                <span>📊 Extrato de Margem PO</span>
                                <span className="text-[10px] text-slate-400 font-normal">Fórmula Celso</span>
                            </h4>
                            <div className="space-y-1.5 font-sans font-medium">
                                <div className="flex justify-between">
                                    <span className="text-slate-400">(+) Valor Bruto:</span>
                                    <span className="font-mono text-white">{formatCurrency(marginInfo.breakdown.gross)}</span>
                                </div>
                                <div className="flex justify-between text-amber-400">
                                    <span className="text-slate-400">(-) Ajuste VP (Prazo):</span>
                                    <span className="font-mono">-{formatCurrency(marginInfo.breakdown.vpDiscount)}</span>
                                </div>
                                <div className="flex justify-between border-t border-slate-800 pt-0.5">
                                    <span className="text-slate-400 font-semibold">(=) Valor Presente (VP):</span>
                                    <span className="font-semibold font-mono text-white">{formatCurrency(marginInfo.breakdown.vp)}</span>
                                </div>
                                <div className="flex justify-between text-red-400">
                                    <span className="text-slate-400">(-) Impostos (22.25%):</span>
                                    <span className="font-mono">-{formatCurrency(marginInfo.breakdown.taxes)}</span>
                                </div>
                                {marginInfo.breakdown.commission > 0 && (
                                    <div className="flex justify-between text-red-400">
                                        <span className="text-slate-400">(-) Comissão:</span>
                                        <span className="font-mono">-{formatCurrency(marginInfo.breakdown.commission)}</span>
                                    </div>
                                )}
                                {marginInfo.breakdown.freight > 0 && (
                                    <div className="flex justify-between text-red-400">
                                        <span className="text-slate-400">(-) Frete Total:</span>
                                        <span className="font-mono">-{formatCurrency(marginInfo.breakdown.freight)}</span>
                                    </div>
                                )}
                                <div className="border-t border-slate-800 my-1"></div>
                                <div className="flex justify-between text-emerald-400 font-bold">
                                    <span className="text-slate-300">(=) Margem Absoluta:</span>
                                    <span className="font-mono text-white">{formatCurrency(marginInfo.breakdown.absoluteMargin)}</span>
                                </div>
                                <div className="flex justify-between text-slate-300">
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
                    </div>
                )}
            </div>

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
