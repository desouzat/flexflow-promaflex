import React from 'react'
import {
    Calendar,
    DollarSign,
    Package,
    AlertCircle,
    CheckCircle,
    Clock
} from 'lucide-react'

const KanbanCard = ({ po, onCardClick }) => {
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

    return (
        <div
            onClick={() => onCardClick?.(po)}
            className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 hover:shadow-md transition-shadow cursor-pointer"
        >
            {/* Header */}
            <div className="flex items-start justify-between mb-3">
                <div className="flex-1">
                    <h3 className="font-semibold text-gray-900 text-sm mb-1">
                        PO #{po.po_number}
                    </h3>
                    <p className="text-xs text-gray-600">{po.supplier_name}</p>
                </div>
                <div className={`flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium border ${getStatusColor(po.status)}`}>
                    {getStatusIcon(po.status)}
                    <span className="capitalize">{po.status.replace('_', ' ')}</span>
                </div>
            </div>

            {/* Details */}
            <div className="space-y-2">
                <div className="flex items-center gap-2 text-sm">
                    <DollarSign className="w-4 h-4 text-gray-400 flex-shrink-0" />
                    <span className="font-medium text-gray-900">
                        {formatCurrency(po.total_value)}
                    </span>
                </div>

                <div className="flex items-center gap-2 text-sm text-gray-600">
                    <Calendar className="w-4 h-4 text-gray-400 flex-shrink-0" />
                    <span className="text-xs">
                        {formatDate(po.expected_delivery_date)}
                    </span>
                </div>

                {po.items_count && (
                    <div className="flex items-center gap-2 text-sm text-gray-600">
                        <Package className="w-4 h-4 text-gray-400 flex-shrink-0" />
                        <span className="text-xs">
                            {po.items_count} {po.items_count === 1 ? 'item' : 'items'}
                        </span>
                    </div>
                )}
            </div>

            {/* Priority Indicator */}
            {po.priority === 'high' && (
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
