/**
 * FlexFlow - Help Modal Component
 * Modal de ajuda contextual "The Compass" para cada etapa do Kanban
 */

import React from 'react';
import { X, HelpCircle, CheckCircle, ArrowRight } from 'lucide-react';
import { getHelpForStatus } from '../config/helpConfig';

const HelpModal = ({ isOpen, onClose, status }) => {
    if (!isOpen) return null;

    const helpConfig = getHelpForStatus(status);

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4">
            <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
                {/* Header */}
                <div className="flex items-center justify-between p-6 border-b border-gray-200">
                    <div className="flex items-center gap-3">
                        <span className="text-3xl">{helpConfig.icon}</span>
                        <div>
                            <h2 className="text-2xl font-bold text-gray-900">
                                {helpConfig.title}
                            </h2>
                            <p className="text-sm text-gray-600 mt-1">
                                Sistema de Ajuda Contextual - The Compass
                            </p>
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
