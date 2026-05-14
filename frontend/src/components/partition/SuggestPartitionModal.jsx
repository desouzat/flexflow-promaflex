import React, { useState } from 'react';
import { X, AlertTriangle } from 'lucide-react';

/**
 * Modal for PCP to suggest a partition
 * Allows PCP to provide technical reason for splitting a PO
 */
const SuggestPartitionModal = ({ isOpen, onClose, po, onSubmit }) => {
    const [reason, setReason] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState('');

    if (!isOpen || !po) return null;

    const handleSubmit = async (e) => {
        e.preventDefault();

        // Validate reason
        if (!reason || reason.trim().length < 10) {
            setError('O motivo deve ter no mínimo 10 caracteres');
            return;
        }

        setIsSubmitting(true);
        setError('');

        try {
            await onSubmit(po.id, reason.trim());
            setReason('');
            onClose();
        } catch (err) {
            setError(err.message || 'Erro ao sugerir partição');
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleClose = () => {
        if (!isSubmitting) {
            setReason('');
            setError('');
            onClose();
        }
    };

    return (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
                {/* Header */}
                <div className="flex items-center justify-between p-6 border-b border-gray-200">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-orange-100 rounded-lg">
                            <AlertTriangle className="w-6 h-6 text-orange-600" />
                        </div>
                        <div>
                            <h2 className="text-xl font-bold text-gray-900">
                                Sugerir Partição de Pedido
                            </h2>
                            <p className="text-sm text-gray-600">
                                PO: {po.po_number}
                            </p>
                        </div>
                    </div>
                    <button
                        onClick={handleClose}
                        disabled={isSubmitting}
                        className="p-2 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-50"
                    >
                        <X className="w-5 h-5 text-gray-500" />
                    </button>
                </div>

                {/* Content */}
                <form onSubmit={handleSubmit} className="p-6 space-y-6">
                    {/* Info Box */}
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                        <h3 className="font-semibold text-blue-900 mb-2">
                            O que é uma Partição?
                        </h3>
                        <p className="text-sm text-blue-800">
                            A partição permite dividir um pedido em duas remessas quando há impedimentos
                            técnicos para enviar todos os itens juntos. O time Comercial receberá sua
                            sugestão e decidirá quais itens enviar em cada remessa.
                        </p>
                    </div>

                    {/* PO Summary */}
                    <div className="bg-gray-50 rounded-lg p-4">
                        <h3 className="font-semibold text-gray-900 mb-3">
                            Resumo do Pedido
                        </h3>
                        <div className="grid grid-cols-2 gap-4 text-sm">
                            <div>
                                <span className="text-gray-600">Total de Itens:</span>
                                <span className="ml-2 font-semibold text-gray-900">
                                    {po.items_count || po.items?.length || 0}
                                </span>
                            </div>
                            <div>
                                <span className="text-gray-600">Valor Total:</span>
                                <span className="ml-2 font-semibold text-gray-900">
                                    R$ {(po.total_value || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                                </span>
                            </div>
                        </div>
                    </div>

                    {/* Reason Input */}
                    <div>
                        <label className="block text-sm font-semibold text-gray-900 mb-2">
                            Motivo Técnico da Partição *
                        </label>
                        <textarea
                            value={reason}
                            onChange={(e) => {
                                setReason(e.target.value);
                                setError('');
                            }}
                            placeholder="Descreva o motivo técnico que impede o envio conjunto dos itens (ex: falta de matéria-prima, problema de produção, prazo de entrega incompatível, etc.)"
                            rows={5}
                            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                            disabled={isSubmitting}
                            required
                            minLength={10}
                        />
                        <div className="flex items-center justify-between mt-2">
                            <p className="text-xs text-gray-500">
                                Mínimo 10 caracteres
                            </p>
                            <p className={`text-xs ${reason.length >= 10 ? 'text-green-600' : 'text-gray-400'}`}>
                                {reason.length} caracteres
                            </p>
                        </div>
                    </div>

                    {/* Error Message */}
                    {error && (
                        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                            <p className="text-sm text-red-800">{error}</p>
                        </div>
                    )}

                    {/* Warning */}
                    <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                        <p className="text-sm text-yellow-800">
                            <strong>Atenção:</strong> Ao sugerir a partição, o pedido será movido para o
                            status "Aguardando Partição" e o time Comercial será notificado para executar
                            a divisão dos itens.
                        </p>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center justify-end gap-3 pt-4 border-t border-gray-200">
                        <button
                            type="button"
                            onClick={handleClose}
                            disabled={isSubmitting}
                            className="px-6 py-2.5 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50"
                        >
                            Cancelar
                        </button>
                        <button
                            type="submit"
                            disabled={isSubmitting || reason.trim().length < 10}
                            className="px-6 py-2.5 bg-orange-600 text-white rounded-lg hover:bg-orange-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                        >
                            {isSubmitting ? (
                                <>
                                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                                    Enviando...
                                </>
                            ) : (
                                <>
                                    <AlertTriangle className="w-4 h-4" />
                                    Sugerir Partição
                                </>
                            )}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

export default SuggestPartitionModal;
