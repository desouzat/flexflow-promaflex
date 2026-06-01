import React, { useState } from 'react'
import { ChevronDown, ChevronRight, Edit2, Save, X, Paperclip } from 'lucide-react'

const KEY_TRANSLATIONS = {
    is_export: 'Exportação',
    is_replacement: 'Troca / Reposição',
    is_parted: 'Particionado',
    waiting_partition: 'Aguardando Partição',
    packaging_type: 'Tipo de Embalagem',
    data_programada: 'Data Programada',
    production_impediment: 'Impedimento de Produção',
    status_producao: 'Status de Produção',
    qtd_real_produzida: 'Qtd Real Produzida',
    perda_tecnica: 'Perda Técnica',
    numero_nfe: 'Número NF-e',
    chave_acesso: 'Chave de Acesso',
    transportadora: 'Transportadora',
    manual_commission_rate: 'Comissão Manual (%)',
    audit_comment: 'Comentário de Auditoria',
    client_name: 'Nome do Cliente',
    expected_delivery_date: 'Data de Entrega Prevista',
    endereco_conferido: 'Endereço Conferido',
    peso_validado: 'Peso Validado',
    etiquetas_impressas: 'Etiquetas Impressas',
    foto_carga_path: 'Foto da Carga (Anexo)',
    foto_canhoto_path: 'Canhoto / NF (Anexo)',
    freight_strategy: 'Estratégia de Frete',
    freight_ship_now: 'Enviar Frete Agora',
    freight_ship_later: 'Enviar Frete Depois',
    justification: 'Justificativa',
    reason: 'Motivo',
    priority_note: 'Nota Prioritária',
    ipi: 'IPI (%)',
    unit: 'Unidade',
    width: 'Largura',
    length: 'Comprimento',
    balance: 'Saldo',
    freight: 'Frete',
    Freight: 'Frete',
    salesperson: 'Vendedor',
    Salesperson: 'Vendedor',
    billing_date: 'Data Faturamento',
    'Billing Date': 'Data Faturamento',
    block_status: 'Bloqueio',
    'Block Status': 'Bloqueio',
    icms_percent: '% ICMS',
    'Icms Percent': '% ICMS',
    delivery_date: 'Data Entrega',
    'Delivery Date': 'Data Entrega',
    payment_terms: 'Condição Pagamento',
    'Payment Terms': 'Condição Pagamento',
    customization_notes: 'Descritivo Customização',
    'Customization Notes': 'Descritivo Customização',
    finance_justification: 'Parecer de Crédito',
    'Finance Justification': 'Parecer de Crédito',
    total_cost: 'Custo Total',
    'Total Cost': 'Custo Total',
    delay: 'Atraso (Dias)',
    Delay: 'Atraso (Dias)',
    shipping_cost: 'Custo de Envio',
    attachment_path: 'Foto do Item (Anexo)'
}

const humanizeKey = (key) => {
    return KEY_TRANSLATIONS[key] || key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

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
                    N/A
                </div>
            )
        }

        // Boolean
        if (typeof value === 'boolean') {
            return (
                <div style={{ marginLeft: `${indent}px` }} className="text-blue-650 font-bold">
                    {value ? 'Sim' : 'Não'}
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
            const isPath = (() => {
                const keyLower = String(key).toLowerCase();
                const valLower = String(value).toLowerCase();
                const hasPathKey = keyLower.includes('path') || keyLower.includes('foto') || keyLower.includes('anexo') || keyLower.includes('file') || keyLower.includes('url');
                const hasFileExtension = /\.(jpg|jpeg|png|gif|pdf|doc|docx|xls|xlsx|csv|txt|zip)$/i.test(valLower);
                const isUrlOrFilePath = valLower.startsWith('http') || valLower.startsWith('/') || valLower.startsWith('\\') || valLower.includes('/') || valLower.includes('\\');
                return hasPathKey || (hasFileExtension && isUrlOrFilePath);
            })();

            if (isPath) {
                return (
                    <div style={{ marginLeft: `${indent}px` }} className="flex items-center gap-1.5 mt-0.5">
                        <a 
                            href={`${(import.meta.env.VITE_API_URL || 'http://localhost:8000/api').replace(/\/api$/, '')}/api/uploads/download?path=${encodeURIComponent((value || '').replace(/^\//, ''))}`} 
                            download
                            className="inline-flex items-center justify-center p-2 bg-blue-50 border border-blue-200 hover:bg-blue-100 text-blue-600 hover:text-blue-850 rounded-lg transition-all shadow-xs"
                            title="Baixar anexo"
                        >
                            <Paperclip className="w-4 h-4" />
                        </a>
                    </div>
                )
            }

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
                                    <span className="text-gray-600 font-medium text-sm">{humanizeKey(objKey)}:</span>
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
                <h3 className="font-semibold text-gray-900 text-sm">Detalhe do Pedido</h3>
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
                        {Object.keys(metadata)
                            .filter((key) => {
                                const k = key.toLowerCase();
                                return ![
                                    'is_export',
                                    'is_first_order',
                                    'is_new_client',
                                    'is_replacement',
                                    'is_personalized',
                                    'is_urgent',
                                    'client_name',
                                    'apply_sla_reduction',
                                    'exportação',
                                    'is new client',
                                    'troca/reposição',
                                    'is personalized',
                                    'nome do cliente',
                                    'apply sla reduction',
                                    'description',
                                    'descrição',
                                    'descriçao',
                                    'attachment_filename',
                                    'cost_mp',
                                    'cost_updated_by',
                                    'cost_updated_at',
                                    'production_impediment'
                                ].includes(k);
                            })
                            .map((key) => (
                                <div key={key} className="border-b border-gray-100 pb-2 last:border-0">
                                    <div className="flex items-start gap-2">
                                        <span className="text-gray-700 font-semibold text-sm min-w-[140px]">
                                            {humanizeKey(key)}:
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

        </div>
    )
}

export default MetadataVisualizer
