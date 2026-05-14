import React, { useState, useEffect } from 'react'
import { Plus, Edit2, Trash2, Save, X, DollarSign, Package, TrendingUp, Search, AlertTriangle, Percent } from 'lucide-react'
import api from '../utils/api'
import { showSuccess, showError } from '../utils/toast'
import ErrorBoundary from '../components/ErrorBoundary'

/**
 * CostsPage - Página de Gerenciamento de Custos
 * 
 * Apenas usuários MASTER podem acessar esta página.
 * Permite CRUD completo de custos de materiais e tabela de comissões.
 */
const CostsPage = () => {
    const [activeTab, setActiveTab] = useState('materials') // 'materials' or 'commissions'
    const [materials, setMaterials] = useState([])
    const [commissions, setCommissions] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const [searchTerm, setSearchTerm] = useState('')
    const [isCreating, setIsCreating] = useState(false)
    const [editingId, setEditingId] = useState(null)
    const [deleteConfirm, setDeleteConfirm] = useState(null)
    const [formData, setFormData] = useState({
        sku: '',
        nome: '',
        custo_mp_kg: '',
        rendimento: '',
        indice_impostos: '22.25'
    })
    const [commissionFormData, setCommissionFormData] = useState({
        min_margin: '',
        max_margin: '',
        commission_rate: '',
        has_alert: false
    })

    useEffect(() => {
        if (activeTab === 'materials') {
            fetchMaterials()
        } else if (activeTab === 'commissions') {
            fetchCommissions()
        }
    }, [activeTab])

    const fetchMaterials = async () => {
        try {
            setLoading(true)
            setError(null)
            const response = await api.get('/costs/materials')
            const data = response.data
            const materialsArray = Array.isArray(data) ? data : (data.items || [])
            setMaterials(materialsArray)
        } catch (err) {
            const errorMsg = err.response?.data?.detail || 'Falha ao carregar custos'
            setError(errorMsg)

            if (err.response?.status === 403) {
                showError('Acesso negado: Apenas usuários MASTER podem gerenciar custos')
            } else {
                showError(errorMsg)
            }
        } finally {
            setLoading(false)
        }
    }

    const fetchCommissions = async () => {
        try {
            setLoading(true)
            setError(null)
            // Mock data for now - will be replaced with actual API call
            const mockCommissions = [
                { id: '1', min_margin: 0.00, max_margin: 18.99, commission_rate: 0.00, has_alert: true, display_order: 1 },
                { id: '2', min_margin: 19.00, max_margin: 24.99, commission_rate: 2.00, has_alert: false, display_order: 2 },
                { id: '3', min_margin: 25.00, max_margin: 29.99, commission_rate: 2.25, has_alert: false, display_order: 3 },
                { id: '4', min_margin: 30.00, max_margin: 39.99, commission_rate: 2.50, has_alert: false, display_order: 4 },
                { id: '5', min_margin: 40.00, max_margin: 44.99, commission_rate: 3.50, has_alert: false, display_order: 5 },
                { id: '6', min_margin: 45.00, max_margin: 49.99, commission_rate: 4.00, has_alert: false, display_order: 6 },
                { id: '7', min_margin: 50.00, max_margin: 999.99, commission_rate: 4.50, has_alert: false, display_order: 7 },
            ]
            setCommissions(mockCommissions)
        } catch (err) {
            const errorMsg = err.response?.data?.detail || 'Falha ao carregar tabela de comissões'
            setError(errorMsg)
            showError(errorMsg)
        } finally {
            setLoading(false)
        }
    }

    const handleCreate = async () => {
        try {
            if (!formData.sku || !formData.nome || !formData.custo_mp_kg || !formData.rendimento) {
                showError('Por favor, preencha todos os campos obrigatórios')
                return
            }

            const payload = {
                sku: formData.sku.trim(),
                nome: formData.nome.trim(),
                custo_mp_kg: parseFloat(formData.custo_mp_kg),
                rendimento: parseFloat(formData.rendimento),
                indice_impostos: parseFloat(formData.indice_impostos || '22.25')
            }

            if (isNaN(payload.custo_mp_kg) || isNaN(payload.rendimento) || isNaN(payload.indice_impostos)) {
                showError('Por favor, insira valores numéricos válidos')
                return
            }

            await api.post('/costs/materials', payload)
            showSuccess('Material criado com sucesso')
            setIsCreating(false)
            resetForm()
            fetchMaterials()
        } catch (err) {
            const errorMsg = err.response?.data?.detail || 'Falha ao criar material'
            showError(errorMsg)
        }
    }

    const handleUpdate = async (sku) => {
        try {
            if (!formData.nome || !formData.custo_mp_kg || !formData.rendimento) {
                showError('Por favor, preencha todos os campos obrigatórios')
                return
            }

            const payload = {
                nome: formData.nome.trim(),
                custo_mp_kg: parseFloat(formData.custo_mp_kg),
                rendimento: parseFloat(formData.rendimento),
                indice_impostos: parseFloat(formData.indice_impostos || '22.25')
            }

            if (isNaN(payload.custo_mp_kg) || isNaN(payload.rendimento) || isNaN(payload.indice_impostos)) {
                showError('Por favor, insira valores numéricos válidos')
                return
            }

            await api.put(`/costs/materials/${sku}`, payload)
            showSuccess('Material atualizado com sucesso')
            setEditingId(null)
            resetForm()
            fetchMaterials()
        } catch (err) {
            const errorMsg = err.response?.data?.detail || 'Falha ao atualizar o material'
            showError(errorMsg)
        }
    }

    const handleDelete = async (sku) => {
        try {
            await api.delete(`/costs/materials/${sku}`)
            showSuccess('Material deletado com sucesso')
            setDeleteConfirm(null)
            fetchMaterials()
        } catch (err) {
            const errorMsg = err.response?.data?.detail || 'Falha ao deletar material'
            showError(errorMsg)
        }
    }

    const handleCommissionUpdate = async (id) => {
        try {
            // Mock update - will be replaced with actual API call
            showSuccess('Faixa de comissão atualizada com sucesso')
            setEditingId(null)
            resetCommissionForm()
            fetchCommissions()
        } catch (err) {
            showError('Falha ao atualizar faixa de comissão')
        }
    }

    const confirmDelete = (material) => {
        setDeleteConfirm({ sku: material.sku, nome: material.nome })
    }

    const cancelDelete = () => {
        setDeleteConfirm(null)
    }

    const startEdit = (material) => {
        setEditingId(material.sku)
        setFormData({
            sku: material.sku,
            nome: material.nome,
            custo_mp_kg: material.custo_mp_kg.toString(),
            rendimento: material.rendimento.toString(),
            indice_impostos: material.indice_impostos.toString()
        })
    }

    const startCommissionEdit = (commission) => {
        setEditingId(commission.id)
        setCommissionFormData({
            min_margin: commission.min_margin.toString(),
            max_margin: commission.max_margin.toString(),
            commission_rate: commission.commission_rate.toString(),
            has_alert: commission.has_alert
        })
    }

    const cancelEdit = () => {
        setEditingId(null)
        setIsCreating(false)
        resetForm()
        resetCommissionForm()
    }

    const resetForm = () => {
        setFormData({
            sku: '',
            nome: '',
            custo_mp_kg: '',
            rendimento: '',
            indice_impostos: '22.25'
        })
    }

    const resetCommissionForm = () => {
        setCommissionFormData({
            min_margin: '',
            max_margin: '',
            commission_rate: '',
            has_alert: false
        })
    }

    const filteredMaterials = Array.isArray(materials) ? materials.filter((material) => {
        const search = searchTerm.toLowerCase()
        return (
            material.sku.toLowerCase().includes(search) ||
            material.nome.toLowerCase().includes(search)
        )
    }) : []

    const calculateCostPerUnit = (material) => {
        const costPerKg = parseFloat(material.custo_mp_kg)
        const yield_kg = parseFloat(material.rendimento)
        const taxRate = parseFloat(material.indice_impostos) / 100

        const baseCost = costPerKg * yield_kg
        const totalCost = baseCost * (1 + taxRate)

        return totalCost.toFixed(2)
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center h-full">
                <div className="text-center">
                    <div className="w-16 h-16 border-4 border-primary-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                    <p className="text-gray-600">Carregando...</p>
                </div>
            </div>
        )
    }

    if (error && error.includes('Acesso negado')) {
        return (
            <div className="flex items-center justify-center h-full">
                <div className="text-center max-w-md">
                    <div className="text-red-600 text-5xl mb-4">🔒</div>
                    <h2 className="text-xl font-semibold text-gray-900 mb-2">Acesso Restrito</h2>
                    <p className="text-gray-600 mb-4">{error}</p>
                    <p className="text-sm text-gray-500">
                        Esta página é exclusiva para usuários com permissão MASTER.
                    </p>
                </div>
            </div>
        )
    }

    return (
        <ErrorBoundary>
            <div className="h-full flex flex-col">
                {/* Header */}
                <div className="bg-white border-b border-gray-200 px-6 py-4">
                    <div className="flex items-center justify-between mb-4">
                        <div>
                            <h1 className="text-2xl font-bold text-gray-900">Gerenciamento de Custos</h1>
                            <p className="text-sm text-gray-600 mt-1">
                                {activeTab === 'materials'
                                    ? `${materials.length} ${materials.length === 1 ? 'material cadastrado' : 'materiais cadastrados'}`
                                    : `${commissions.length} faixas de comissão configuradas`
                                }
                            </p>
                        </div>
                        <div className="flex items-center gap-3">
                            {activeTab === 'materials' && (
                                <>
                                    <div className="relative">
                                        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                                        <input
                                            type="text"
                                            placeholder="Buscar por SKU ou nome..."
                                            value={searchTerm}
                                            onChange={(e) => setSearchTerm(e.target.value)}
                                            className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                                        />
                                    </div>
                                    <button
                                        onClick={() => {
                                            setIsCreating(true)
                                            setEditingId(null)
                                            resetForm()
                                        }}
                                        className="btn-primary flex items-center gap-2"
                                    >
                                        <Plus className="w-5 h-5" />
                                        Novo Material
                                    </button>
                                </>
                            )}
                        </div>
                    </div>

                    {/* Tabs */}
                    <div className="flex gap-2 border-b border-gray-200">
                        <button
                            onClick={() => setActiveTab('materials')}
                            className={`px-4 py-2 font-medium text-sm transition-colors relative ${activeTab === 'materials'
                                ? 'text-primary-600 border-b-2 border-primary-600'
                                : 'text-gray-600 hover:text-gray-900'
                                }`}
                        >
                            <div className="flex items-center gap-2">
                                <Package className="w-4 h-4" />
                                Custos de Materiais
                            </div>
                        </button>
                        <button
                            onClick={() => setActiveTab('commissions')}
                            className={`px-4 py-2 font-medium text-sm transition-colors relative ${activeTab === 'commissions'
                                ? 'text-primary-600 border-b-2 border-primary-600'
                                : 'text-gray-600 hover:text-gray-900'
                                }`}
                        >
                            <div className="flex items-center gap-2">
                                <Percent className="w-4 h-4" />
                                Tabela de Comissões
                            </div>
                        </button>
                    </div>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-auto p-6">
                    {activeTab === 'materials' ? (
                        <>
                            {/* Create Form */}
                            {isCreating && (
                                <div className="bg-white border border-gray-200 rounded-lg p-6 mb-6 shadow-sm">
                                    <h3 className="text-lg font-semibold text-gray-900 mb-4">Novo Material</h3>
                                    <div className="grid grid-cols-2 gap-4">
                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                                SKU *
                                            </label>
                                            <input
                                                type="text"
                                                value={formData.sku}
                                                onChange={(e) => setFormData({ ...formData, sku: e.target.value })}
                                                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                                                placeholder="MAT-001"
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                                Nome *
                                            </label>
                                            <input
                                                type="text"
                                                value={formData.nome}
                                                onChange={(e) => setFormData({ ...formData, nome: e.target.value })}
                                                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                                                placeholder="Nome do material"
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                                Custo MP/kg (R$) *
                                            </label>
                                            <input
                                                type="number"
                                                step="0.01"
                                                value={formData.custo_mp_kg}
                                                onChange={(e) => setFormData({ ...formData, custo_mp_kg: e.target.value })}
                                                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                                                placeholder="15.50"
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                                Rendimento (kg/unidade) *
                                            </label>
                                            <input
                                                type="number"
                                                step="0.0001"
                                                value={formData.rendimento}
                                                onChange={(e) => setFormData({ ...formData, rendimento: e.target.value })}
                                                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                                                placeholder="0.5"
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                                Índice de Impostos (%) *
                                            </label>
                                            <input
                                                type="number"
                                                step="0.01"
                                                value={formData.indice_impostos}
                                                onChange={(e) => setFormData({ ...formData, indice_impostos: e.target.value })}
                                                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                                                placeholder="22.25"
                                            />
                                        </div>
                                    </div>
                                    <div className="mt-4 flex gap-2">
                                        <button onClick={handleCreate} className="btn-primary flex items-center gap-1">
                                            <Save className="w-4 h-4" />
                                            Salvar
                                        </button>
                                        <button onClick={cancelEdit} className="btn-secondary flex items-center gap-1">
                                            <X className="w-4 h-4" />
                                            Cancelar
                                        </button>
                                    </div>
                                </div>
                            )}

                            {/* Materials Table */}
                            <div className="bg-white border border-gray-200 rounded-lg overflow-hidden shadow-sm">
                                <table className="w-full">
                                    <thead className="bg-gray-50 border-b border-gray-200">
                                        <tr>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                SKU
                                            </th>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                Nome
                                            </th>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                Custo MP/kg
                                            </th>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                Rendimento
                                            </th>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                Impostos
                                            </th>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                Custo/Unidade
                                            </th>
                                            <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                Ações
                                            </th>
                                        </tr>
                                    </thead>
                                    <tbody className="bg-white divide-y divide-gray-200">
                                        {filteredMaterials.length === 0 ? (
                                            <tr>
                                                <td colSpan="7" className="px-6 py-8 text-center text-gray-500">
                                                    {searchTerm ? 'Nenhum material encontrado' : 'Nenhum material cadastrado'}
                                                </td>
                                            </tr>
                                        ) : (
                                            filteredMaterials.map((material) => (
                                                <tr key={material.sku} className="hover:bg-gray-50">
                                                    {editingId === material.sku ? (
                                                        <>
                                                            <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                                                                {material.sku}
                                                            </td>
                                                            <td className="px-6 py-4 whitespace-nowrap">
                                                                <input
                                                                    type="text"
                                                                    value={formData.nome}
                                                                    onChange={(e) => setFormData({ ...formData, nome: e.target.value })}
                                                                    className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
                                                                />
                                                            </td>
                                                            <td className="px-6 py-4 whitespace-nowrap">
                                                                <input
                                                                    type="number"
                                                                    step="0.01"
                                                                    value={formData.custo_mp_kg}
                                                                    onChange={(e) => setFormData({ ...formData, custo_mp_kg: e.target.value })}
                                                                    className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
                                                                />
                                                            </td>
                                                            <td className="px-6 py-4 whitespace-nowrap">
                                                                <input
                                                                    type="number"
                                                                    step="0.0001"
                                                                    value={formData.rendimento}
                                                                    onChange={(e) => setFormData({ ...formData, rendimento: e.target.value })}
                                                                    className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
                                                                />
                                                            </td>
                                                            <td className="px-6 py-4 whitespace-nowrap">
                                                                <input
                                                                    type="number"
                                                                    step="0.01"
                                                                    value={formData.indice_impostos}
                                                                    onChange={(e) => setFormData({ ...formData, indice_impostos: e.target.value })}
                                                                    className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
                                                                />
                                                            </td>
                                                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                                                R$ {calculateCostPerUnit(material)}
                                                            </td>
                                                            <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                                                <button
                                                                    onClick={() => handleUpdate(material.sku)}
                                                                    className="text-green-600 hover:text-green-900 mr-3"
                                                                >
                                                                    <Save className="w-4 h-4" />
                                                                </button>
                                                                <button
                                                                    onClick={cancelEdit}
                                                                    className="text-gray-600 hover:text-gray-900"
                                                                >
                                                                    <X className="w-4 h-4" />
                                                                </button>
                                                            </td>
                                                        </>
                                                    ) : (
                                                        <>
                                                            <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                                                                {material.sku}
                                                            </td>
                                                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                                                {material.nome}
                                                            </td>
                                                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                                                R$ {parseFloat(material.custo_mp_kg).toFixed(2)}
                                                            </td>
                                                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                                                {parseFloat(material.rendimento).toFixed(4)} kg
                                                            </td>
                                                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                                                {parseFloat(material.indice_impostos).toFixed(2)}%
                                                            </td>
                                                            <td className="px-6 py-4 whitespace-nowrap text-sm font-semibold text-green-600">
                                                                R$ {calculateCostPerUnit(material)}
                                                            </td>
                                                            <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                                                <button
                                                                    onClick={() => startEdit(material)}
                                                                    className="text-primary-600 hover:text-primary-900 mr-3"
                                                                >
                                                                    <Edit2 className="w-4 h-4" />
                                                                </button>
                                                                <button
                                                                    onClick={() => confirmDelete(material)}
                                                                    className="text-red-600 hover:text-red-900"
                                                                >
                                                                    <Trash2 className="w-4 h-4" />
                                                                </button>
                                                            </td>
                                                        </>
                                                    )}
                                                </tr>
                                            ))
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        </>
                    ) : (
                        /* Commission Table */
                        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden shadow-sm">
                            <div className="p-6 border-b border-gray-200 bg-blue-50">
                                <div className="flex items-start gap-3">
                                    <TrendingUp className="w-6 h-6 text-blue-600 flex-shrink-0 mt-1" />
                                    <div>
                                        <h3 className="text-lg font-semibold text-gray-900 mb-1">
                                            Escada de Comissões
                                        </h3>
                                        <p className="text-sm text-gray-600">
                                            Configure as faixas de margem e suas respectivas taxas de comissão.
                                            <br />
                                            <span className="font-medium text-blue-700">Exceção CSN:</span> Cliente CSN sempre recebe taxa fixa de 1.5%, independente da margem.
                                        </p>
                                    </div>
                                </div>
                            </div>

                            <table className="w-full">
                                <thead className="bg-gray-50 border-b border-gray-200">
                                    <tr>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                            Margem Mínima (%)
                                        </th>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                            Margem Máxima (%)
                                        </th>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                            Taxa de Comissão (%)
                                        </th>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                            Alerta
                                        </th>
                                        <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                                            Ações
                                        </th>
                                    </tr>
                                </thead>
                                <tbody className="bg-white divide-y divide-gray-200">
                                    {commissions.map((commission) => (
                                        <tr key={commission.id} className={`hover:bg-gray-50 ${commission.has_alert ? 'bg-red-50' : ''}`}>
                                            {editingId === commission.id ? (
                                                <>
                                                    <td className="px-6 py-4 whitespace-nowrap">
                                                        <input
                                                            type="number"
                                                            step="0.01"
                                                            value={commissionFormData.min_margin}
                                                            onChange={(e) => setCommissionFormData({ ...commissionFormData, min_margin: e.target.value })}
                                                            className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
                                                        />
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap">
                                                        <input
                                                            type="number"
                                                            step="0.01"
                                                            value={commissionFormData.max_margin}
                                                            onChange={(e) => setCommissionFormData({ ...commissionFormData, max_margin: e.target.value })}
                                                            className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
                                                        />
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap">
                                                        <input
                                                            type="number"
                                                            step="0.01"
                                                            value={commissionFormData.commission_rate}
                                                            onChange={(e) => setCommissionFormData({ ...commissionFormData, commission_rate: e.target.value })}
                                                            className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
                                                        />
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap">
                                                        <input
                                                            type="checkbox"
                                                            checked={commissionFormData.has_alert}
                                                            onChange={(e) => setCommissionFormData({ ...commissionFormData, has_alert: e.target.checked })}
                                                            className="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                                                        />
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                                        <button
                                                            onClick={() => handleCommissionUpdate(commission.id)}
                                                            className="text-green-600 hover:text-green-900 mr-3"
                                                        >
                                                            <Save className="w-4 h-4" />
                                                        </button>
                                                        <button
                                                            onClick={cancelEdit}
                                                            className="text-gray-600 hover:text-gray-900"
                                                        >
                                                            <X className="w-4 h-4" />
                                                        </button>
                                                    </td>
                                                </>
                                            ) : (
                                                <>
                                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                                        {commission.min_margin.toFixed(2)}%
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                                        {commission.max_margin.toFixed(2)}%
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap text-sm font-semibold text-green-600">
                                                        {commission.commission_rate.toFixed(2)}%
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                                                        {commission.has_alert ? (
                                                            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                                                                <AlertTriangle className="w-3 h-3 mr-1" />
                                                                Alerta
                                                            </span>
                                                        ) : (
                                                            <span className="text-gray-400">—</span>
                                                        )}
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                                        <button
                                                            onClick={() => startCommissionEdit(commission)}
                                                            className="text-primary-600 hover:text-primary-900"
                                                        >
                                                            <Edit2 className="w-4 h-4" />
                                                        </button>
                                                    </td>
                                                </>
                                            )}
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>

                {/* Delete Confirmation Modal */}
                {deleteConfirm && (
                    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
                        <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
                            <div className="flex items-center gap-3 mb-4">
                                <div className="flex-shrink-0 w-12 h-12 rounded-full bg-red-100 flex items-center justify-center">
                                    <AlertTriangle className="w-6 h-6 text-red-600" />
                                </div>
                                <div>
                                    <h3 className="text-lg font-semibold text-gray-900">
                                        Confirmar Exclusão
                                    </h3>
                                    <p className="text-sm text-gray-600">
                                        Esta ação não pode ser desfeita
                                    </p>
                                </div>
                            </div>
                            <div className="mb-6">
                                <p className="text-gray-700">
                                    Tem certeza que deseja deletar o material{' '}
                                    <span className="font-semibold">{deleteConfirm.sku}</span>
                                    {' - '}
                                    <span className="font-semibold">{deleteConfirm.nome}</span>?
                                </p>
                            </div>
                            <div className="flex gap-3 justify-end">
                                <button
                                    onClick={cancelDelete}
                                    className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
                                >
                                    Cancelar
                                </button>
                                <button
                                    onClick={() => handleDelete(deleteConfirm.sku)}
                                    className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors flex items-center gap-2"
                                >
                                    <Trash2 className="w-4 h-4" />
                                    Deletar Material
                                </button>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </ErrorBoundary>
    )
}

export default CostsPage
