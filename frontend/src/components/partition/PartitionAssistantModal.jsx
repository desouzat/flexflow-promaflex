import React, { useState, useMemo } from 'react';
import { X, Package, TruckIcon, Calculator, AlertCircle, CheckCircle2 } from 'lucide-react';

/**
 * Partition Assistant Modal for Commercial users
 * Allows selection of items for immediate vs later shipment
 * Includes freight management with 3 strategies
 */
const PartitionAssistantModal = ({ isOpen, onClose, po, onExecute }) => {
    const [selectedItems, setSelectedItems] = useState(new Set());
    const [freightStrategy, setFreightStrategy] = useState('PROPORTIONAL');
    const [manualFreightNow, setManualFreightNow] = useState('');
    const [manualFreightLater, setManualFreightLater] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState('');

    if (!isOpen || !po) return null;

    const items = po.items || [];
    const totalShippingCost = parseFloat(po.shipping_cost || 0);

    // Calculate values for selected and unselected items
    const calculations = useMemo(() => {
        let shipNowValue = 0;
        let shipLaterValue = 0;
        let shipNowCount = 0;
        let shipLaterCount = 0;

        items.forEach(item => {
            const itemValue = parseFloat(item.price || 0) * (item.quantity || 0);
            if (selectedItems.has(item.id)) {
                shipNowValue += itemValue;
                shipNowCount++;
            } else {
                shipLaterValue += itemValue;
                shipLaterCount++;
            }
        });

        const totalValue = shipNowValue + shipLaterValue;
        const proportion = totalValue > 0 ? shipNowValue / totalValue : 0;

        // Calculate freight based on strategy
        let freightNow = 0;
        let freightLater = 0;

        if (freightStrategy === 'PROPORTIONAL') {
            freightNow = totalShippingCost * proportion;
            freightLater = totalShippingCost - freightNow;
        } else if (freightStrategy === 'FULL_ON_FIRST') {
            freightNow = totalShippingCost;
            freightLater = 0;
        } else if (freightStrategy === 'MANUAL') {
            freightNow = parseFloat(manualFreightNow || 0);
            freightLater = parseFloat(manualFreightLater || 0);
        }

        return {
            shipNowValue,
            shipLaterValue,
            shipNowCount,
            shipLaterCount,
            totalValue,
            proportion,
            freightNow,
            freightLater
        };
    }, [selectedItems, items, freightStrategy, manualFreightNow, manualFreightLater, totalShippingCost]);

    const toggleItem = (itemId) => {
        const newSelected = new Set(selectedItems);
        if (newSelected.has(itemId)) {
            newSelected.delete(itemId);
        } else {
            newSelected.add(itemId);
        }
        setSelectedItems(newSelected);
        setError('');
    };

    const handleSubmit = async (e) => {
        e.preventDefault();

        // Validation
        if (selectedItems.size === 0) {
            setError('Selecione pelo menos um item para enviar agora');
            return;
        }

        if (selectedItems.size >= items.length) {
            setError('Deve deixar pelo menos um item para enviar depois');
            return;
        }

        if (freightStrategy === 'MANUAL') {
            if (!manualFreightNow || parseFloat(manualFreightNow) < 0) {
                setError('Informe o valor do frete para envio imediato');
                return;
            }
            if (!manualFreightLater || parseFloat(manualFreightLater) < 0) {
                setError('Informe o valor do frete para envio posterior');
                return;
            }
        }

        setIsSubmitting(true);
        setError('');

        try {
            await onExecute({
                po_id: po.id,
                items_ship_now: Array.from(selectedItems),
                freight_strategy: freightStrategy,
                freight_ship_now: freightStrategy === 'MANUAL' ? parseFloat(manualFreightNow) : null,
                freight_ship_later: freightStrategy === 'MANUAL' ? parseFloat(manualFreightLater) : null
            });

            // Reset state
            setSelectedItems(new Set());
            setFreightStrategy('PROPORTIONAL');
            setManualFreightNow('');
            setManualFreightLater('');
            onClose();
        } catch (err) {
            setError(err.message || 'Erro ao executar partição');
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleClose = () => {
        if (!isSubmitting) {
            setSelectedItems(new Set());
            setFreightStrategy('PROPORTIONAL');
            setManualFreightNow('');
            setManualFreightLater('');
            setError('');
            onClose();
        }
    };

    return (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-lg shadow-xl max-w-6xl w-full max-h-[90vh] overflow-y-auto">
                {/* Header */}
                <div className="flex items-center justify-between p-6 border-b border-gray-200 sticky top-0 bg-white z-10">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-blue-100 rounded-lg">
                            <Package className="w-6 h-6 text-blue-600" />
                        </div>
                        <div>
                            <h2 className="text-xl font-bold text-gray-900">
                                Assistente de Partição
                            </h2>
                            <p className="text-sm text-gray-600">
                                PO: {po.po_number} • {items.length} itens
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

                <form onSubmit={handleSubmit} className="p-6 space-y-6">
                    {/* Partition Reason */}
                    {po.partition_reason && (
                        <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
                            <h3 className="font-semibold text-orange-900 mb-2 flex items-center gap-2">
                                <AlertCircle className="w-5 h-5" />
                                Motivo da Partição (PCP)
                            </h3>
                            <p className="text-sm text-orange-800">{po.partition_reason}</p>
                        </div>
                    )}

                    {/* Item Selection */}
                    <div>
                        <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                            <Package className="w-5 h-5" />
                            Seleção de Itens
                        </h3>
                        <p className="text-sm text-gray-600 mb-4">
                            Selecione os itens que serão enviados <strong>agora</strong>. Os demais serão enviados <strong>posteriormente</strong>.
                        </p>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {items.map(item => {
                                const isSelected = selectedItems.has(item.id);
                                const itemTotal = parseFloat(item.price || 0) * (item.quantity || 0);

                                return (
                                    <div
                                        key={item.id}
                                        onClick={() => toggleItem(item.id)}
                                        className={`p-4 border-2 rounded-lg cursor-pointer transition-all ${isSelected
                                                ? 'border-green-500 bg-green-50'
                                                : 'border-gray-200 bg-white hover:border-gray-300'
                                            }`}
                                    >
                                        <div className="flex items-start justify-between">
                                            <div className="flex-1">
                                                <div className="flex items-center gap-2 mb-2">
                                                    <div className={`w-5 h-5 rounded border-2 flex items-center justify-center ${isSelected
                                                            ? 'border-green-500 bg-green-500'
                                                            : 'border-gray-300'
                                                        }`}>
                                                        {isSelected && <CheckCircle2 className="w-4 h-4 text-white" />}
                                                    </div>
                                                    <span className="font-semibold text-gray-900">{item.sku}</span>
                                                </div>
                                                <div className="text-sm text-gray-600 space-y-1 ml-7">
                                                    <div>Qtd: {item.quantity}</div>
                                                    <div>Preço: R$ {parseFloat(item.price || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</div>
                                                    <div className="font-semibold text-gray-900">
                                                        Total: R$ {itemTotal.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                                                    </div>
                                                </div>
                                            </div>
                                            <div className={`px-3 py-1 rounded-full text-xs font-semibold ${isSelected
                                                    ? 'bg-green-100 text-green-800'
                                                    : 'bg-gray-100 text-gray-600'
                                                }`}>
                                                {isSelected ? 'Enviar Agora' : 'Enviar Depois'}
                                            </div>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    {/* Summary */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {/* Ship Now */}
                        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                            <h4 className="font-semibold text-green-900 mb-3">📦 Envio Imediato</h4>
                            <div className="space-y-2 text-sm">
                                <div className="flex justify-between">
                                    <span className="text-green-700">Itens:</span>
                                    <span className="font-semibold text-green-900">{calculations.shipNowCount}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-green-700">Valor:</span>
                                    <span className="font-semibold text-green-900">
                                        R$ {calculations.shipNowValue.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                                    </span>
                                </div>
                                <div className="flex justify-between pt-2 border-t border-green-300">
                                    <span className="text-green-700">Frete:</span>
                                    <span className="font-semibold text-green-900">
                                        R$ {calculations.freightNow.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                                    </span>
                                </div>
                            </div>
                        </div>

                        {/* Ship Later */}
                        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                            <h4 className="font-semibold text-blue-900 mb-3">📅 Envio Posterior</h4>
                            <div className="space-y-2 text-sm">
                                <div className="flex justify-between">
                                    <span className="text-blue-700">Itens:</span>
                                    <span className="font-semibold text-blue-900">{calculations.shipLaterCount}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-blue-700">Valor:</span>
                                    <span className="font-semibold text-blue-900">
                                        R$ {calculations.shipLaterValue.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                                    </span>
                                </div>
                                <div className="flex justify-between pt-2 border-t border-blue-300">
                                    <span className="text-blue-700">Frete:</span>
                                    <span className="font-semibold text-blue-900">
                                        R$ {calculations.freightLater.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                                    </span>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Freight Management */}
                    <div>
                        <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                            <TruckIcon className="w-5 h-5" />
                            Gestão de Frete
                        </h3>
                        <p className="text-sm text-gray-600 mb-4">
                            Frete Original: R$ {totalShippingCost.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                        </p>

                        <div className="space-y-3">
                            {/* Proportional */}
                            <label className={`flex items-start gap-3 p-4 border-2 rounded-lg cursor-pointer transition-all ${freightStrategy === 'PROPORTIONAL'
                                    ? 'border-blue-500 bg-blue-50'
                                    : 'border-gray-200 hover:border-gray-300'
                                }`}>
                                <input
                                    type="radio"
                                    name="freightStrategy"
                                    value="PROPORTIONAL"
                                    checked={freightStrategy === 'PROPORTIONAL'}
                                    onChange={(e) => setFreightStrategy(e.target.value)}
                                    className="mt-1"
                                />
                                <div className="flex-1">
                                    <div className="font-semibold text-gray-900">Proporcional ao Valor</div>
                                    <div className="text-sm text-gray-600">
                                        Frete dividido proporcionalmente ao valor dos itens em cada remessa
                                    </div>
                                    {freightStrategy === 'PROPORTIONAL' && (
                                        <div className="mt-2 text-sm text-blue-700">
                                            {(calculations.proportion * 100).toFixed(1)}% no envio imediato, {((1 - calculations.proportion) * 100).toFixed(1)}% no envio posterior
                                        </div>
                                    )}
                                </div>
                            </label>

                            {/* Full on First */}
                            <label className={`flex items-start gap-3 p-4 border-2 rounded-lg cursor-pointer transition-all ${freightStrategy === 'FULL_ON_FIRST'
                                    ? 'border-blue-500 bg-blue-50'
                                    : 'border-gray-200 hover:border-gray-300'
                                }`}>
                                <input
                                    type="radio"
                                    name="freightStrategy"
                                    value="FULL_ON_FIRST"
                                    checked={freightStrategy === 'FULL_ON_FIRST'}
                                    onChange={(e) => setFreightStrategy(e.target.value)}
                                    className="mt-1"
                                />
                                <div className="flex-1">
                                    <div className="font-semibold text-gray-900">Frete Total no Primeiro Envio</div>
                                    <div className="text-sm text-gray-600">
                                        Todo o frete cobrado no envio imediato, sem frete no envio posterior
                                    </div>
                                </div>
                            </label>

                            {/* Manual */}
                            <label className={`flex items-start gap-3 p-4 border-2 rounded-lg cursor-pointer transition-all ${freightStrategy === 'MANUAL'
                                    ? 'border-blue-500 bg-blue-50'
                                    : 'border-gray-200 hover:border-gray-300'
                                }`}>
                                <input
                                    type="radio"
                                    name="freightStrategy"
                                    value="MANUAL"
                                    checked={freightStrategy === 'MANUAL'}
                                    onChange={(e) => setFreightStrategy(e.target.value)}
                                    className="mt-1"
                                />
                                <div className="flex-1">
                                    <div className="font-semibold text-gray-900">Valores Manuais</div>
                                    <div className="text-sm text-gray-600 mb-3">
                                        Defina manualmente o valor do frete para cada remessa
                                    </div>
                                    {freightStrategy === 'MANUAL' && (
                                        <div className="grid grid-cols-2 gap-3">
                                            <div>
                                                <label className="block text-xs font-medium text-gray-700 mb-1">
                                                    Frete Envio Imediato
                                                </label>
                                                <input
                                                    type="number"
                                                    step="0.01"
                                                    min="0"
                                                    value={manualFreightNow}
                                                    onChange={(e) => setManualFreightNow(e.target.value)}
                                                    placeholder="0.00"
                                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-xs font-medium text-gray-700 mb-1">
                                                    Frete Envio Posterior
                                                </label>
                                                <input
                                                    type="number"
                                                    step="0.01"
                                                    min="0"
                                                    value={manualFreightLater}
                                                    onChange={(e) => setManualFreightLater(e.target.value)}
                                                    placeholder="0.00"
                                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                                />
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </label>
                        </div>
                    </div>

                    {/* Error Message */}
                    {error && (
                        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                            <p className="text-sm text-red-800">{error}</p>
                        </div>
                    )}

                    {/* Info */}
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                        <p className="text-sm text-blue-800">
                            <strong>Resultado:</strong> Serão criados dois novos pedidos (PO Mãe e PO Filho) com os itens
                            selecionados. Ambos retornarão ao status "Comercial" para aprovação. O sistema recalculará
                            automaticamente as margens e valores presentes.
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
                            disabled={isSubmitting || selectedItems.size === 0 || selectedItems.size >= items.length}
                            className="px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                        >
                            {isSubmitting ? (
                                <>
                                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                                    Executando...
                                </>
                            ) : (
                                <>
                                    <Calculator className="w-4 h-4" />
                                    Executar Partição
                                </>
                            )}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

export default PartitionAssistantModal;
