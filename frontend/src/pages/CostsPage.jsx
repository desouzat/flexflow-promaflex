import React, { useState, useEffect } from 'react'
import { Plus, Edit2, Trash2, Save, X, DollarSign, Package, TrendingUp, Search } from 'lucide-react'
import api from '../utils/api'
import { showSuccess, showError } from '../utils/toast'
import ErrorBoundary from '../components/ErrorBoundary'

/**
 * CostsPage - Página de Gerenciamento de Custos
 * 
 * Apenas usuários MASTER podem acessar esta página.
 * Permite CRUD completo de custos de materiais.
 */
const CostsPage = () => {
    const [materials, setMaterials] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const [searchTerm, setSearchTerm] = useState('')
    const [isCreating, setIsCreating] = useState(false)
    const [editingId, setEditingId] = useState(null)
    const [formData, setFormData] = useState({
        sku: '',
        nome: '',
        custo_mp_kg: '',
        rendimento: '',
        indice_impostos: '22.25'
    })

    useEffect(() => {
        fetchMaterials()
    }, [])

    const fetchMaterials = async () => {
        try {
            setLoading(true)
            setError(null)
            const response = await api.get('/costs/materials')
            setMaterials(response.data)
        } catch (err) {
            const errorMsg = err.response?.data?.detail || 'Falha ao carregar custos'
            setError(errorMsg)

            // Se for 403, usuário não é MASTER
            if (err.response?.status === 403) {
                showError('Acesso negado: Apenas usuários MASTER podem gerenciar custos')
            } else {
                showError(errorMsg)
            }
        } finally {
            setLoading(false)
        }
    }

    const handleCreate = async () => {
        try {
            await api.post('/costs/materials', {
                sku: formData.sku,
                nome: formData.nome,
                custo_mp_kg: parseFloat(formData.custo_mp_kg),
                rendimento: parseFloat(formData.rendimento),
                indice_impostos: parseFloat(formData.indice_impostos)
            })
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
            await api.put(`/costs/materials/${sku}`, {
                nome: formData.nome,
                custo_mp_kg: parseFloat(formData.custo_mp_kg),
                rendimento: parseFloat(formData.rendimento),
                indice_impostos: parseFloat(formData.indice_impostos)
            })
            showSuccess('Material atualizado com sucesso')
            setEditingId(null)
            resetForm()
            fetchMaterials()
        } catch (err) {
            const errorMsg = err.response?.data?.detail || 'Falha ao atualizar material'
            showError(errorMsg)
        }
    }

    const handleDelete = async (sku) => {
        if (!window.confirm(`Tem certeza que deseja deletar o material ${sku}?`)) {
            return
        }

        try {
            await api.delete(`/costs/materials/${sku}`)
            showSuccess('Material deletado com sucesso')
            fetchMaterials()
        } catch (err) {
            const errorMsg = err.response?.data?.detail || 'Falha ao deletar material'
            showError(errorMsg)
        }
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

    const cancelEdit = () => {
        setEditingId(null)
        setIsCreating(false)
        resetForm()
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

    const filteredMaterials = materials.filter((material) => {
        const search = searchTerm.toLowerCase()
        return (
            material.sku.toLowerCase().includes(search) ||
            material.nome.toLowerCase().includes(search)
        )
    })

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
                    <p className="text-gray-600">Carregando custos...</p>
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
                    <div className="flex items-center justify-between">
                        <div>
                            <h1 className="text-2xl font-bold text-gray-900">Gerenciamento de Custos</h1>
                            <p className="text-sm text-gray-600 mt-1">
                                {materials.length} {materials.length === 1 ? 'material cadastrado' : 'materiais cadastrados'}
                            </p>
                        </div>
                        <div className="flex items-center gap-3">
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
                                onClick={() => setIsCreating(true)}
                                className="btn-primary flex items-center gap-2"
                            >
                                <Plus className="w-5 h-5" />
                                Novo Material
                            </button>
                        </div>
                    </div>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-auto p-6">
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
                                                            onClick={() => handleDelete(material.sku)}
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
                </div>
            </div>
        </ErrorBoundary>
    )
}

export default CostsPage
