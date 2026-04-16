import React from 'react'
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
    Zap
} from 'lucide-react'
import { STRATEGIC_INDICATORS } from '../../config/helpConfig'

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
        return new Date(dateString).toLocaleDateString('pt-BR')
    }

    // Get strategic indicators from metadata
    const getStrategicIndicators = () => {
        const indicators = []
        const metadata = safepo.extra_metadata || {}

        if (metadata.is_export) {
            indicators.push({
                key: 'is_export',
                icon: Globe,
                ...STRATEGIC_INDICATORS.is_export
            })
        }

        if (metadata.is_first_order) {
            indicators.push({
                key: 'is_first_order',
                icon: Star,
                ...STRATEGIC_INDICATORS.is_first_order
            })
        }

        if (metadata.is_replacement) {
            indicators.push({
                key: 'is_replacement',
                icon: RefreshCw,
                ...STRATEGIC_INDICATORS.is_replacement
            })
        }

        if (metadata.is_urgent || safepo.priority === 'high') {
            indicators.push({
                key: 'is_urgent',
                icon: Zap,
                ...STRATEGIC_INDICATORS.is_urgent
            })
        }

        return indicators
    }

    const strategicIndicators = getStrategicIndicators()
    const slaStatus = getSLAStatus()

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
