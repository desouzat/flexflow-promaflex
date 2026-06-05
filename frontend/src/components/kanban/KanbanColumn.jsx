import React, { useState } from 'react'
import KanbanCard from './KanbanCard'
import { MoreVertical, HelpCircle } from 'lucide-react'
import HelpModal from '../HelpModal'

const KanbanColumn = ({ title, status, pos, onCardClick, onMoveCard, color = 'gray', compactView = false }) => {
    const [showHelp, setShowHelp] = useState(false)
    const colorClasses = {
        gray: 'bg-gray-100 border-gray-400',
        yellow: 'bg-yellow-50 border-yellow-400',
        green: 'bg-green-50 border-green-400',
        blue: 'bg-blue-50 border-blue-400',
        lightblue: 'bg-blue-50 border-blue-300',
        purple: 'bg-purple-50 border-purple-400',
        red: 'bg-red-50 border-red-400',
        orange: 'bg-orange-50 border-orange-400',
    }

    const headerColorClasses = {
        gray: 'bg-gray-200 text-gray-800',
        yellow: 'bg-yellow-100 text-yellow-800',
        green: 'bg-green-100 text-green-800',
        blue: 'bg-blue-100 text-blue-800',
        lightblue: 'bg-blue-100 text-blue-800',
        purple: 'bg-purple-100 text-purple-800',
        red: 'bg-red-100 text-red-800',
        orange: 'bg-orange-100 text-orange-800',
    }

    return (
        <div className="flex flex-col h-full min-w-[325px] max-w-[340px]">
            {/* Column Header */}
            <div className={`flex items-center justify-between px-4 py-3 rounded-t-lg ${headerColorClasses[color]}`}>
                <div className="flex items-center gap-2 overflow-hidden">
                    <h2 className="font-semibold text-sm tracking-tight whitespace-nowrap">{title}</h2>
                    <span className="px-2 py-0.5 bg-white bg-opacity-50 rounded-full text-xs font-medium flex-shrink-0">
                        {pos.length}
                    </span>
                </div>
                <div className="flex items-center gap-1">
                    <button
                        onClick={() => setShowHelp(true)}
                        className="p-1 hover:bg-white hover:bg-opacity-30 rounded transition-colors"
                        aria-label="Ajuda"
                        title="Ajuda Contextual"
                    >
                        <HelpCircle className="w-4 h-4" />
                    </button>
                    <button
                        className="p-1 hover:bg-white hover:bg-opacity-30 rounded transition-colors"
                        aria-label="Column options"
                    >
                        <MoreVertical className="w-4 h-4" />
                    </button>
                </div>
            </div>

            {/* Column Content */}
            <div className={`flex-1 p-3 border-2 border-t-0 rounded-b-lg ${colorClasses[color]} overflow-y-auto`}>
                <div className="space-y-3">
                    {pos.length === 0 ? (
                        <div className="text-center py-8 text-gray-500 text-sm">
                            Nenhum item nesta coluna
                        </div>
                    ) : (
                        pos.map((po) => (
                            <KanbanCard
                                key={po.id}
                                po={po}
                                onCardClick={onCardClick}
                                compactView={compactView}
                            />
                        ))
                    )}
                </div>
            </div>

            {/* Help Modal */}
            <HelpModal
                isOpen={showHelp}
                onClose={() => setShowHelp(false)}
                status={title}
            />
        </div>
    )
}

export default KanbanColumn
