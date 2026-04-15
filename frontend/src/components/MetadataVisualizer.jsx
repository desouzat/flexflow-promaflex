import React, { useState } from 'react'
import { ChevronDown, ChevronRight, Edit2, Save, X } from 'lucide-react'

/**
 * MetadataVisualizer Component
 * 
 * Exibe e permite edição de metadata JSONB de OrderItems.
 * Suporta estruturas aninhadas e diferentes tipos de dados.
 */
const MetadataVisualizer = ({ metadata, itemId, onUpdate, readOnly = false }) => {
    const [isEditing, setIsEditing] = useState(false)
    const [editedMetadata, setEditedMetadata] = useState(JSON.stringify(metadata || {}, null, 2))
    const [expandedKeys, setExpandedKeys] = useState(new Set())
    const [error, setError] = useState(null)

    const toggleExpand = (key) => {
        const newExpanded = new Set(expandedKeys)
        if (newExpanded.has(key)) {
            newExpanded.delete(key)
        } else {
            newExpanded.add(key)
        }
        setExpandedKeys(newExpanded)
    }

    const handleSave = async () => {
        try {
            const parsed = JSON.parse(editedMetadata)
            setError(null)

            if (onUpdate) {
                await onUpdate(itemId, parsed)
            }

            setIsEditing(false)
        } catch (err) {
            setError('JSON inválido: ' + err.message)
        }
    }

    const handleCancel = () => {
        setEditedMetadata(JSON.stringify(metadata || {}, null, 2))
        setError(null)
        setIsEditing(false)
    }

    const renderValue = (value, key, depth = 0) => {
        const indent = depth * 20

        // Null or undefined
        if (value === null || value === undefined) {
            return (
                <div style={{ marginLeft: `${indent}px` }} className="text-gray-400 italic">
                    null
                </div>
            )
        }

        // Boolean
        if (typeof value === 'boolean') {
            return (
                <div style={{ marginLeft: `${indent}px` }} className="text-blue-600 font-medium">
                    {value.toString()}
                </div>
            )
        }

        // Number
        if (typeof value === 'number') {
            return (
                <div style={{ marginLeft: `${indent}px` }} className="text-green-600 font-medium">
                    {value}
                </div>
            )
        }

        // String
        if (typeof value === 'string') {
            return (
                <div style={{ marginLeft: `${indent}px` }} className="text-gray-700">
                    "{value}"
                </div>
            )
        }

        // Array
        if (Array.isArray(value)) {
            const isExpanded = expandedKeys.has(key)
            return (
                <div style={{ marginLeft: `${indent}px` }}>
                    <button
                        onClick={() => toggleExpand(key)}
                        className="flex items-center gap-1 text-purple-600 hover:text-purple-800 font-medium"
                    >
                        {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                        Array [{value.length}]
                    </button>
                    {isExpanded && (
                        <div className="mt-1">
                            {value.map((item, index) => (
                                <div key={index} className="mb-1">
                                    <span className="text-gray-500 text-sm">[{index}]:</span>
                                    {renderValue(item, `${key}[${index}]`, depth + 1)}
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )
        }

        // Object
        if (typeof value === 'object') {
            const isExpanded = expandedKeys.has(key)
            const keys = Object.keys(value)

            return (
                <div style={{ marginLeft: `${indent}px` }}>
                    <button
                        onClick={() => toggleExpand(key)}
                        className="flex items-center gap-1 text-indigo-600 hover:text-indigo-800 font-medium"
                    >
                        {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                        Object {`{${keys.length}}`}
                    </button>
                    {isExpanded && (
                        <div className="mt-1 space-y-1">
                            {keys.map((objKey) => (
                                <div key={objKey}>
                                    <span className="text-gray-600 font-medium text-sm">{objKey}:</span>
                                    {renderValue(value[objKey], `${key}.${objKey}`, depth + 1)}
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )
        }

        return <div style={{ marginLeft: `${indent}px` }} className="text-gray-500">{String(value)}</div>
    }

    // Se não há metadata
    if (!metadata || Object.keys(metadata).length === 0) {
        return (
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                <p className="text-gray-500 text-sm italic">Nenhuma metadata disponível</p>
                {!readOnly && (
                    <button
                        onClick={() => setIsEditing(true)}
                        className="mt-2 text-primary-600 hover:text-primary-800 text-sm flex items-center gap-1"
                    >
                        <Edit2 className="w-4 h-4" />
                        Adicionar Metadata
                    </button>
                )}
            </div>
        )
    }

    return (
        <div className="bg-white border border-gray-200 rounded-lg">
            {/* Header */}
            <div className="flex items-center justify-between p-3 border-b border-gray-200 bg-gray-50">
                <h3 className="font-semibold text-gray-900 text-sm">Metadata Customizada</h3>
                {!readOnly && !isEditing && (
                    <button
                        onClick={() => setIsEditing(true)}
                        className="text-primary-600 hover:text-primary-800 flex items-center gap-1 text-sm"
                    >
                        <Edit2 className="w-4 h-4" />
                        Editar
                    </button>
                )}
            </div>

            {/* Content */}
            <div className="p-4">
                {isEditing ? (
                    <div>
                        <textarea
                            value={editedMetadata}
                            onChange={(e) => setEditedMetadata(e.target.value)}
                            className="w-full h-64 p-3 border border-gray-300 rounded-lg font-mono text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                            placeholder='{"key": "value"}'
                        />
                        {error && (
                            <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
                                {error}
                            </div>
                        )}
                        <div className="mt-3 flex gap-2">
                            <button
                                onClick={handleSave}
                                className="btn-primary flex items-center gap-1"
                            >
                                <Save className="w-4 h-4" />
                                Salvar
                            </button>
                            <button
                                onClick={handleCancel}
                                className="btn-secondary flex items-center gap-1"
                            >
                                <X className="w-4 h-4" />
                                Cancelar
                            </button>
                        </div>
                    </div>
                ) : (
                    <div className="space-y-2">
                        {Object.keys(metadata).map((key) => (
                            <div key={key} className="border-b border-gray-100 pb-2 last:border-0">
                                <div className="flex items-start gap-2">
                                    <span className="text-gray-700 font-semibold text-sm min-w-[120px]">
                                        {key}:
                                    </span>
                                    <div className="flex-1">
                                        {renderValue(metadata[key], key)}
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Footer - JSON View Toggle */}
            {!isEditing && (
                <div className="p-3 border-t border-gray-200 bg-gray-50">
                    <details className="text-sm">
                        <summary className="cursor-pointer text-gray-600 hover:text-gray-900 font-medium">
                            Ver JSON Completo
                        </summary>
                        <pre className="mt-2 p-3 bg-gray-900 text-green-400 rounded-lg overflow-x-auto text-xs">
                            {JSON.stringify(metadata, null, 2)}
                        </pre>
                    </details>
                </div>
            )}
        </div>
    )
}

export default MetadataVisualizer
