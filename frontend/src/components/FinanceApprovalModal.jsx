/**
 * FinanceApprovalModal.jsx
 * ========================
 * Finance Approval Modal — UI Component
 *
 * Displays a line item's financial details and collects a written justification
 * before an Approve or Reject decision is submitted to the Finance API.
 *
 * State:
 *   - Props: item (staging item), onApprove(justification), onReject(justification), onClose
 *   - Local: justification (string), submitting (bool), error (string)
 *
 * Note (Hardening Step 2): This is the UI shell. API wiring will be completed
 * in Hardening Step 3 when the backend /api/import/finance-approval endpoint is ready.
 */

import React, { useState, useEffect, useRef } from 'react'
import {
    X,
    DollarSign,
    CheckCircle,
    XCircle,
    AlertTriangle,
    FileText,
    TrendingUp,
    TrendingDown,
    Minus,
    Loader2
} from 'lucide-react'

// ─── Constants ────────────────────────────────────────────────────────────────
const MIN_JUSTIFICATION_LENGTH = 20

// ─── Helper: Brazilian currency formatter ────────────────────────────────────
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

// ─── Helper: Margin indicator ────────────────────────────────────────────────
const getMarginIndicator = (unitValue, priceUnit) => {
    if (!unitValue || !priceUnit) return null
    const uv = parseFloat(unitValue)
    const pu = parseFloat(priceUnit)
    if (isNaN(uv) || isNaN(pu) || pu === 0) return null
    const margin = ((pu - uv) / pu) * 100
    return { value: margin.toFixed(1), isNegative: margin < 0, isLow: margin < 5 }
}

// ─── Sub-components ──────────────────────────────────────────────────────────

/** A single row in the financial details table */
const DetailRow = ({ label, value, highlight = false, testId }) => (
    <div
        className={`flex justify-between items-center py-2 border-b border-gray-700 last:border-b-0 ${highlight ? 'bg-yellow-500/5 rounded px-2' : ''}`}
        data-testid={testId}
    >
        <span className="text-sm text-gray-400">{label}</span>
        <span className={`text-sm font-semibold ${highlight ? 'text-yellow-300' : 'text-gray-100'}`}>
            {value}
        </span>
    </div>
)

/** Margin badge with traffic-light coloring */
const MarginBadge = ({ margin }) => {
    if (!margin) return null
    const { value, isNegative, isLow } = margin
    const color = isNegative
        ? 'bg-red-500/20 text-red-400 border-red-500/40'
        : isLow
            ? 'bg-yellow-500/20 text-yellow-400 border-yellow-500/40'
            : 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40'
    const Icon = isNegative ? TrendingDown : isLow ? Minus : TrendingUp

    return (
        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-xs font-bold ${color}`}>
            <Icon size={12} />
            {value}% margem
        </span>
    )
}

// ─── Main Component ───────────────────────────────────────────────────────────

/**
 * FinanceApprovalModal
 *
 * @param {object}   item           - The staging OrderItem being reviewed
 * @param {string}   poNumber       - The PO number (for context display)
 * @param {function} onApprove      - Called with (justification: string) on Approve
 * @param {function} onReject       - Called with (justification: string) on Reject
 * @param {function} onClose        - Called when the modal is closed without a decision
 * @param {boolean}  [submitting]   - If true, shows a loading spinner on action buttons
 */
const FinanceApprovalModal = ({
    item,
    poNumber,
    onApprove,
    onReject,
    onClose,
    submitting = false
}) => {
    const [justification, setJustification] = useState('')
    const [touched, setTouched] = useState(false)
    const [confirmAction, setConfirmAction] = useState(null) // 'approve' | 'reject' | null
    const textareaRef = useRef(null)

    // Auto-focus the textarea on open
    useEffect(() => {
        setTimeout(() => textareaRef.current?.focus(), 100)
    }, [])

    // Close on Escape key
    useEffect(() => {
        const handleKey = (e) => { if (e.key === 'Escape' && !submitting) onClose?.() }
        document.addEventListener('keydown', handleKey)
        return () => document.removeEventListener('keydown', handleKey)
    }, [submitting, onClose])

    if (!item) return null

    // ── Derived values ──────────────────────────────────────────────────────
    const justificationTrimmed = justification.trim()
    const justificationLength = justificationTrimmed.length
    const isJustificationValid = justificationLength >= MIN_JUSTIFICATION_LENGTH
    const charsRemaining = Math.max(0, MIN_JUSTIFICATION_LENGTH - justificationLength)
    const margin = getMarginIndicator(item.unit_value, item.price_unit)

    const canSubmit = isJustificationValid && !submitting

    // ── Handlers ────────────────────────────────────────────────────────────
    const handleApprove = () => {
        if (!canSubmit) return
        setConfirmAction('approve')
    }

    const handleReject = () => {
        if (!canSubmit) return
        setConfirmAction('reject')
    }

    const handleConfirm = () => {
        if (confirmAction === 'approve') onApprove?.(justificationTrimmed)
        if (confirmAction === 'reject') onReject?.(justificationTrimmed)
        setConfirmAction(null)
    }

    const handleCancelConfirm = () => setConfirmAction(null)

    // ── Render ──────────────────────────────────────────────────────────────
    return (
        /* Backdrop */
        <div
            id="finance-approval-modal-backdrop"
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
            style={{ background: 'rgba(0, 0, 0, 0.75)', backdropFilter: 'blur(4px)' }}
            onClick={(e) => { if (e.target === e.currentTarget && !submitting) onClose?.() }}
            role="dialog"
            aria-modal="true"
            aria-labelledby="finance-modal-title"
        >
            {/* Modal panel */}
            <div
                id="finance-approval-modal"
                className="relative w-full max-w-lg bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl overflow-hidden"
                style={{ boxShadow: '0 0 60px rgba(234, 179, 8, 0.15)' }}
            >
                {/* ── Header ── */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-gray-700"
                    style={{ background: 'linear-gradient(135deg, rgba(234,179,8,0.15) 0%, rgba(17,24,39,0) 60%)' }}>
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-yellow-500/20 rounded-lg border border-yellow-500/30">
                            <DollarSign size={20} className="text-yellow-400" />
                        </div>
                        <div>
                            <h2 id="finance-modal-title" className="text-base font-bold text-white leading-tight">
                                Aprovação Financeira
                            </h2>
                            <p className="text-xs text-gray-400 mt-0.5">
                                PO <span className="text-yellow-400 font-mono font-semibold">{poNumber}</span>
                            </p>
                        </div>
                    </div>
                    <button
                        id="finance-modal-close"
                        onClick={() => !submitting && onClose?.()}
                        disabled={submitting}
                        className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-gray-700 transition-colors disabled:opacity-40"
                        aria-label="Fechar modal"
                    >
                        <X size={18} />
                    </button>
                </div>

                {/* ── Item Details ── */}
                <div className="px-6 py-4 space-y-1">
                    <div className="flex items-start justify-between mb-3">
                        <div>
                            <p className="text-xs text-gray-500 uppercase tracking-wider mb-0.5">Item</p>
                            <p className="text-sm font-bold text-white font-mono">
                                {item.sku || item.description || 'N/A'}
                            </p>
                            {item.description && item.sku && (
                                <p className="text-xs text-gray-400 mt-0.5">{item.description}</p>
                            )}
                        </div>
                        {margin && <MarginBadge margin={margin} />}
                    </div>

                    <div className="bg-gray-800/60 rounded-xl p-4 border border-gray-700/50">
                        <DetailRow label="Quantidade" value={item.quantity ?? 'N/A'} testId="finance-qty" />
                        <DetailRow label="Unidade" value={item.unit || 'UN'} testId="finance-unit" />
                        <DetailRow
                            label="Valor Unitário"
                            value={formatCurrency(item.unit_value)}
                            highlight={!!item.unit_value}
                            testId="finance-unit-value"
                        />
                        <DetailRow
                            label="Preço Unitário"
                            value={formatCurrency(item.price_unit)}
                            testId="finance-price-unit"
                        />
                        <DetailRow
                            label="Total do Item"
                            value={formatCurrency(item.item_total_value)}
                            highlight={!!item.item_total_value}
                            testId="finance-total-value"
                        />
                        {item.payment_terms && (
                            <DetailRow label="Condição Pgto" value={String(item.payment_terms || '').replace(/\s*-\s*$/, '')} testId="finance-payment" />
                        )}
                    </div>

                    {/* Margin warning banner */}
                    {margin?.isNegative && (
                        <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/30 rounded-lg p-3 mt-2">
                            <AlertTriangle size={16} className="text-red-400 flex-shrink-0 mt-0.5" />
                            <p className="text-xs text-red-300">
                                <strong>Atenção:</strong> Margem negativa detectada. Este item está sendo vendido abaixo do custo.
                                Uma justificativa robusta é obrigatória.
                            </p>
                        </div>
                    )}
                </div>

                {/* ── Justification ── */}
                <div className="px-6 pb-4">
                    <div className="flex items-center justify-between mb-2">
                        <label
                            htmlFor="finance-justification"
                            className="flex items-center gap-2 text-sm font-semibold text-gray-300"
                        >
                            <FileText size={14} className="text-yellow-400" />
                            Justificativa <span className="text-red-400">*</span>
                        </label>
                        <span className={`text-xs ${isJustificationValid ? 'text-emerald-400' : touched ? 'text-red-400' : 'text-gray-500'}`}>
                            {isJustificationValid
                                ? `✓ ${justificationLength} chars`
                                : touched
                                    ? `Faltam ${charsRemaining} chars`
                                    : `Mín. ${MIN_JUSTIFICATION_LENGTH} chars`
                            }
                        </span>
                    </div>
                    <textarea
                        id="finance-justification"
                        ref={textareaRef}
                        value={justification}
                        onChange={(e) => { setJustification(e.target.value); setTouched(true) }}
                        onBlur={() => setTouched(true)}
                        disabled={submitting}
                        rows={3}
                        placeholder="Descreva o motivo da aprovação ou rejeição. Ex: 'Cliente estratégico com contrato anual garantido. Margem compensada pelo volume.'"
                        className={`
                            w-full px-3 py-2.5 bg-gray-800 border rounded-xl text-sm text-gray-100
                            placeholder-gray-600 resize-none outline-none transition-all
                            disabled:opacity-50 disabled:cursor-not-allowed
                            ${touched && !isJustificationValid
                                ? 'border-red-500/60 focus:border-red-400 focus:ring-1 focus:ring-red-400/30'
                                : isJustificationValid
                                    ? 'border-emerald-500/60 focus:border-emerald-400 focus:ring-1 focus:ring-emerald-400/30'
                                    : 'border-gray-600 focus:border-yellow-500/60 focus:ring-1 focus:ring-yellow-500/20'
                            }
                        `}
                        aria-describedby="finance-justification-hint"
                        aria-invalid={touched && !isJustificationValid}
                    />
                    {touched && !isJustificationValid && (
                        <p id="finance-justification-hint" className="mt-1 text-xs text-red-400">
                            A justificativa deve ter pelo menos {MIN_JUSTIFICATION_LENGTH} caracteres.
                        </p>
                    )}
                </div>

                {/* ── Confirmation overlay (inside modal) ── */}
                {confirmAction && (
                    <div className="absolute inset-0 bg-gray-900/95 flex flex-col items-center justify-center z-10 rounded-2xl p-8">
                        {confirmAction === 'approve'
                            ? <CheckCircle size={48} className="text-emerald-400 mb-4" />
                            : <XCircle size={48} className="text-red-400 mb-4" />
                        }
                        <p className="text-base font-bold text-white text-center mb-2">
                            {confirmAction === 'approve'
                                ? 'Confirmar Aprovação?'
                                : 'Confirmar Rejeição?'
                            }
                        </p>
                        <p className="text-xs text-gray-400 text-center mb-6 max-w-xs">
                            Esta ação será registrada no log de auditoria e não pode ser desfeita.
                        </p>
                        <div className="flex gap-3">
                            <button
                                id={`finance-confirm-${confirmAction}`}
                                onClick={handleConfirm}
                                className={`px-5 py-2 rounded-lg text-sm font-semibold text-white transition-all ${confirmAction === 'approve'
                                    ? 'bg-emerald-600 hover:bg-emerald-500 border border-emerald-500'
                                    : 'bg-red-600 hover:bg-red-500 border border-red-500'
                                }`}
                            >
                                {confirmAction === 'approve' ? 'Sim, Aprovar' : 'Sim, Rejeitar'}
                            </button>
                            <button
                                id="finance-cancel-confirm"
                                onClick={handleCancelConfirm}
                                className="px-5 py-2 rounded-lg text-sm font-semibold text-gray-300 bg-gray-700 hover:bg-gray-600 border border-gray-600 transition-all"
                            >
                                Cancelar
                            </button>
                        </div>
                    </div>
                )}

                {/* ── Action Buttons ── */}
                <div className="flex items-center gap-3 px-6 py-4 border-t border-gray-700 bg-gray-900/50">
                    <button
                        id="finance-reject-btn"
                        onClick={handleReject}
                        disabled={!canSubmit}
                        className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold
                            bg-red-500/15 text-red-400 border border-red-500/30
                            hover:bg-red-500/25 hover:border-red-400/60
                            disabled:opacity-40 disabled:cursor-not-allowed
                            transition-all duration-200 group"
                        aria-label="Rejeitar item"
                    >
                        {submitting
                            ? <Loader2 size={16} className="animate-spin" />
                            : <XCircle size={16} className="group-hover:scale-110 transition-transform" />
                        }
                        Rejeitar
                    </button>

                    <button
                        id="finance-approve-btn"
                        onClick={handleApprove}
                        disabled={!canSubmit}
                        className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold
                            bg-emerald-500/15 text-emerald-400 border border-emerald-500/30
                            hover:bg-emerald-500/25 hover:border-emerald-400/60
                            disabled:opacity-40 disabled:cursor-not-allowed
                            transition-all duration-200 group"
                        aria-label="Aprovar item"
                    >
                        {submitting
                            ? <Loader2 size={16} className="animate-spin" />
                            : <CheckCircle size={16} className="group-hover:scale-110 transition-transform" />
                        }
                        Aprovar
                    </button>
                </div>
            </div>
        </div>
    )
}

export default FinanceApprovalModal
