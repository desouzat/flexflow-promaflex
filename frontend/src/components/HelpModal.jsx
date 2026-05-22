/**
 * FlexFlow - Help Modal Component
 * Modal de ajuda contextual "The Compass" para cada etapa do Kanban
 */

import React, { useEffect } from 'react';
import { X, HelpCircle, CheckCircle, ArrowRight } from 'lucide-react';
import { getHelpForStatus } from '../config/helpConfig';

const HelpModal = ({ isOpen, onClose, status }) => {
    // Add escape key handler
    useEffect(() => {
        if (!isOpen) return;

        const handleEscape = (e) => {
            if (e.key === 'Escape') {
                onClose();
            }
        };

        document.addEventListener('keydown', handleEscape);
        return () => document.removeEventListener('keydown', handleEscape);
    }, [isOpen, onClose]);

    if (!isOpen) return null;

    const helpConfig = getHelpForStatus(status);

    const handleBackdropClick = (e) => {
        if (e.target === e.currentTarget) {
            onClose();
        }
    };

    return (
        <div
            className="fixed inset-0 z-[60] flex items-center justify-center bg-black bg-opacity-50 p-4"
            onClick={handleBackdropClick}
        >
            <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
                {/* Header */}
                <div className="flex items-center justify-between p-6 border-b border-gray-200">
                    <div className="flex items-center gap-3">
                        <span className="text-3xl">{helpConfig.icon}</span>
                        <div>
                            <h2 className="text-2xl font-bold text-gray-900">
                                Mesa de Conferência - Sistema de Ajuda Contextual - FlexFlow
                            </h2>
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        className="text-gray-400 hover:text-gray-600 transition-colors"
                        aria-label="Fechar"
                    >
                        <X size={24} />
                    </button>
                </div>

                {/* Content */}
                <div className="p-6 space-y-6">
                    {/* Description */}
                    <div>
                        <h3 className="text-lg font-semibold text-gray-900 mb-2">
                            📖 Descrição
                        </h3>
                        <p className="text-gray-700 leading-relaxed">
                            {helpConfig.description}
                        </p>
                    </div>

                    {/* Rules */}
                    {helpConfig.rules && helpConfig.rules.length > 0 && (
                        <div>
                            <h3 className="text-lg font-semibold text-gray-900 mb-3">
                                📋 Regras e Diretrizes
                            </h3>
                            <ul className="space-y-2">
                                {helpConfig.rules.map((rule, index) => (
                                    <li key={index} className="flex items-start gap-3">
                                        <CheckCircle className="text-green-500 flex-shrink-0 mt-0.5" size={20} />
                                        <span className="text-gray-700">{rule}</span>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}

                    {/* Required Fields */}
                    {helpConfig.requiredFields && helpConfig.requiredFields.length > 0 && (
                        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                            <h3 className="text-lg font-semibold text-yellow-900 mb-3 flex items-center gap-2">
                                <span>⚠️</span>
                                Campos Obrigatórios
                            </h3>
                            <ul className="space-y-1">
                                {helpConfig.requiredFields.map((field, index) => (
                                    <li key={index} className="text-yellow-800 ml-6">
                                        • {field}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}

                    {/* Next Steps */}
                    {helpConfig.nextSteps && helpConfig.nextSteps.length > 0 && (
                        <div>
                            <h3 className="text-lg font-semibold text-gray-900 mb-3">
                                🎯 Próximos Passos
                            </h3>
                            <ul className="space-y-2">
                                {helpConfig.nextSteps.map((step, index) => (
                                    <li key={index} className="flex items-start gap-3">
                                        <ArrowRight className="text-blue-500 flex-shrink-0 mt-0.5" size={20} />
                                        <span className="text-gray-700">{step}</span>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}

                    {/* Glossário / Dicionário de Termos */}
                    <div className="border-t border-gray-150 pt-6">
                        <h3 className="text-lg font-semibold text-gray-900 mb-3 flex items-center gap-2">
                            <span>📚</span> Dicionário de Conceitos & Margem
                        </h3>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="bg-sky-50 border border-sky-200 rounded-lg p-4">
                                <h4 className="font-semibold text-sky-950 mb-1 flex items-center gap-1.5">
                                    <span className="text-sky-600">🔍</span> PENDENTE PCP
                                </h4>
                                <p className="text-sm text-sky-850 leading-relaxed">
                                    Indica que o custo industrial do SKU ainda não foi validado pelo PCP; a margem será calculada após o vínculo técnico.
                                </p>
                            </div>
                            <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-4">
                                <h4 className="font-semibold text-indigo-950 mb-1 flex items-center gap-1.5">
                                    <span className="text-indigo-600">📊</span> Manual de Margem
                                </h4>
                                <p className="text-sm text-indigo-850 leading-relaxed">
                                    Frete e Custos Adicionais informados no cabeçalho (Header Freight/Costs) são rateados proporcionalmente entre todos os itens do pedido com base no seu valor relativo, impactando diretamente a composição de suas margens individuais.
                                </p>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Footer */}
                <div className="flex items-center justify-between p-6 border-t border-gray-200 bg-gray-50">
                    <div className="flex items-center gap-2 text-sm text-gray-600">
                        <HelpCircle size={16} />
                        <span>Precisa de mais ajuda? Contate o suporte.</span>
                    </div>
                    <button
                        onClick={onClose}
                        className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
                    >
                        Entendi
                    </button>
                </div>
            </div>
        </div>
    );
};

export default HelpModal;
