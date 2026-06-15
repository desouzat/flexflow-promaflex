import React, { useState, useEffect } from 'react'
import { Users, Plus, Trash2, Edit2, Shield, Mail, User as UserIcon, AlertCircle } from 'lucide-react'
import api from '../utils/api'
import { showSuccess, showError, showLoading, dismissToast } from '../utils/toast'
import { useAuth } from '../context/AuthContext'

const UsersPage = () => {
    const { user, loading: authLoading } = useAuth()
    const [users, setUsers] = useState([])
    const [loading, setLoading] = useState(true)
    const [showModal, setShowModal] = useState(false)
    const [editingUser, setEditingUser] = useState(null)
    const [formData, setFormData] = useState({
        username: '',
        email: '',
        password: '',
        role: 'user',
        area: '',
        is_sla_manager: false,  // FF-HARDENING-011
    })

    useEffect(() => {
        let attempts = 0
        let intervalId = null

        const checkAndLoad = () => {
            const token = localStorage.getItem('token')
            const isAdmin = user && (user.role || '').toLowerCase() === 'admin'
            
            if (token && isAdmin) {
                loadUsers()
                return true
            }
            return false
        }

        if (!authLoading) {
            const success = checkAndLoad()
            if (!success) {
                // Retry every 100ms up to 10 times to wait for token/role sync
                intervalId = setInterval(() => {
                    attempts++
                    const done = checkAndLoad()
                    if (done || attempts >= 10) {
                        clearInterval(intervalId)
                    }
                }, 100)
            }
        }

        return () => {
            if (intervalId) clearInterval(intervalId)
        }
    }, [user, authLoading])

    const loadUsers = async () => {
        const token = localStorage.getItem('token')
        if (!token) {
            console.warn('[UsersPage] Fetch cancelled: no token present in localStorage')
            return
        }
        setLoading(true)
        try {
            const response = await api.get('/users')
            setUsers(response.data)
        } catch (error) {
            console.error('Failed to load users:', error)
            showError(error.response?.data?.detail || 'Erro ao carregar usuários')
        } finally {
            setLoading(false)
        }
    }

    const handleEditClick = (u) => {
        setEditingUser(u)
        setFormData({
            username: u.username,
            email: u.email,
            password: '', // Not used/edited in PUT
            role: u.role,
            area: u.area === 'N/A' ? '' : (u.area || ''),
            is_sla_manager: Boolean(u.is_sla_manager),  // FF-HARDENING-011
        })
        setShowModal(true)
    }

    const handleCloseModal = () => {
        setFormData({
            username: '',
            email: '',
            password: '',
            role: 'user',
            area: '',
            is_sla_manager: false,  // FF-HARDENING-011
        })
        setEditingUser(null)
        setShowModal(false)
    }

    const handleSubmit = async (e) => {
        e.preventDefault()

        // Validation
        if (!editingUser) {
            if (!formData.username || !formData.email || !formData.password || !formData.area) {
                showError('Preencha todos os campos obrigatórios')
                return
            }
        } else {
            if (!formData.role || !formData.area) {
                showError('Preencha todos os campos obrigatórios')
                return
            }
        }

        const toastId = showLoading(editingUser ? 'Atualizando usuário...' : 'Criando usuário...')

        try {
            if (editingUser) {
                const payload = {
                    role: formData.role,
                    area: formData.area,
                    // FF-HARDENING-011: include is_sla_manager in PUT (only relevant for master)
                    is_sla_manager: formData.role === 'master' ? Boolean(formData.is_sla_manager) : false,
                }
                if (formData.password) {
                    payload.password = formData.password
                }
                await api.put(`/users/${editingUser.id}`, payload)
                dismissToast(toastId)
                showSuccess('Usuário atualizado com sucesso!')
            } else {
                await api.post('/users', formData)
                dismissToast(toastId)
                showSuccess('Usuário criado com sucesso!')
            }

            handleCloseModal()
            loadUsers()
        } catch (error) {
            dismissToast(toastId)
            showError(error.response?.data?.detail || 'Erro ao salvar usuário')
        }
    }

    const handleDelete = async (userId, username) => {
        if (!window.confirm(`Tem certeza que deseja excluir o usuário "${username}"?`)) {
            return
        }

        const toastId = showLoading('Excluindo usuário...')

        try {
            await api.delete(`/users/${userId}`)
            dismissToast(toastId)
            showSuccess('Usuário excluído com sucesso!')
            loadUsers()
        } catch (error) {
            dismissToast(toastId)
            showError(error.response?.data?.detail || 'Erro ao excluir usuário')
        }
    }

    const getRoleBadge = (role) => {
        const badges = {
            master: 'bg-purple-100 text-purple-800',
            admin: 'bg-blue-100 text-blue-800',
            operator: 'bg-cyan-100 text-cyan-800',
            user: 'bg-gray-100 text-gray-800'
        }
        return badges[role] || badges.user
    }

    const getRoleLabel = (role) => {
        const labels = {
            master: 'MASTER',
            admin: 'LÍDER',
            operator: 'OPERADOR',
            user: 'USUÁRIO'
        }
        return labels[role] || role.toUpperCase()
    }

    // Check if user has permission
    if (authLoading) {
        return (
            <div className="h-full flex items-center justify-center bg-gray-50">
                <div className="w-12 h-12 border-4 border-primary-600 border-t-transparent rounded-full animate-spin" />
            </div>
        )
    }

    if ((user?.role || '').toLowerCase() !== 'admin') {
        return (
            <div className="h-full flex items-center justify-center bg-gray-50">
                <div className="text-center">
                    <Shield className="w-16 h-16 text-red-500 mx-auto mb-4" />
                    <h2 className="text-2xl font-bold text-gray-900 mb-2">Acesso Negado</h2>
                    <p className="text-gray-600">Você não tem permissão para acessar esta página.</p>
                </div>
            </div>
        )
    }

    return (
        <div className="h-full flex flex-col">
            {/* Header */}
            <div className="bg-white border-b border-gray-200 px-6 py-4">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold text-gray-900">Gestão de Usuários</h1>
                        <p className="text-sm text-gray-600 mt-1">
                            Gerenciar usuários e permissões do sistema
                        </p>
                    </div>
                    <button
                        onClick={() => {
                            setEditingUser(null)
                            setShowModal(true)
                        }}
                        className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
                    >
                        <Plus className="w-5 h-5" />
                        <span className="font-medium">Novo Usuário</span>
                    </button>
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 p-6 overflow-auto">
                <div className="max-w-6xl mx-auto">
                    {loading ? (
                        <div className="flex items-center justify-center h-64">
                            <div className="w-12 h-12 border-4 border-primary-600 border-t-transparent rounded-full animate-spin" />
                        </div>
                    ) : users.length === 0 ? (
                        <div className="card text-center py-12">
                            <Users className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                            <h3 className="text-lg font-semibold text-gray-900 mb-2">
                                Nenhum usuário encontrado
                            </h3>
                            <p className="text-gray-600 mb-4">
                                Comece adicionando o primeiro usuário da equipe
                             </p>
                            <button
                                onClick={() => {
                                    setEditingUser(null)
                                    setShowModal(true)
                                }}
                                className="btn-primary"
                            >
                                <Plus className="w-5 h-5 mr-2" />
                                Adicionar Usuário
                            </button>
                        </div>
                    ) : (
                        <div className="card">
                            <div className="overflow-x-auto">
                                <table className="w-full">
                                    <thead>
                                        <tr className="border-b border-gray-200">
                                            <th className="text-left py-3 px-4 font-semibold text-gray-700">Usuário</th>
                                            <th className="text-left py-3 px-4 font-semibold text-gray-700">Email</th>
                                            <th className="text-left py-3 px-4 font-semibold text-gray-700">Função</th>
                                            <th className="text-left py-3 px-4 font-semibold text-gray-700">Área</th>
                                            <th className="text-left py-3 px-4 font-semibold text-gray-700">Criado em</th>
                                            <th className="text-right py-3 px-4 font-semibold text-gray-700">Ações</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {users.map((u) => (
                                            <tr key={u.id} className="border-b border-gray-100 hover:bg-gray-50">
                                                <td className="py-3 px-4">
                                                    <div className="flex items-center gap-3">
                                                        <div className="w-10 h-10 bg-primary-100 rounded-full flex items-center justify-center">
                                                            <UserIcon className="w-5 h-5 text-primary-600" />
                                                        </div>
                                                        <div>
                                                            <span className="font-medium text-gray-900">{u.username}</span>
                                                            {/* FF-HARDENING-011: show SLA manager badge */}
                                                            {u.is_sla_manager && (
                                                                <span className="ml-2 text-[10px] bg-indigo-100 text-indigo-700 border border-indigo-200 rounded-full px-2 py-0.5 font-semibold">SLA</span>
                                                            )}
                                                        </div>
                                                    </div>
                                                </td>
                                                <td className="py-3 px-4">
                                                    <div className="flex items-center gap-2 text-gray-600">
                                                        <Mail className="w-4 h-4" />
                                                        <span>{u.email}</span>
                                                    </div>
                                                </td>
                                                <td className="py-3 px-4">
                                                    <span className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm font-medium ${getRoleBadge(u.role)}`}>
                                                        <Shield className="w-4 h-4" />
                                                        {getRoleLabel(u.role)}
                                                    </span>
                                                </td>
                                                <td className="py-3 px-4 text-gray-600">{u.area}</td>
                                                <td className="py-3 px-4 text-gray-600">
                                                    {u.created_at ? new Date(u.created_at).toLocaleDateString('pt-BR') : 'N/A'}
                                                </td>
                                                <td className="py-3 px-4 text-right flex justify-end gap-1">
                                                    <button
                                                        onClick={() => handleEditClick(u)}
                                                        className="p-2 text-primary-600 hover:bg-primary-50 rounded-lg transition-colors"
                                                        title="Editar usuário"
                                                    >
                                                        <Edit2 className="w-5 h-5" />
                                                    </button>
                                                    <button
                                                        onClick={() => handleDelete(u.id, u.username)}
                                                        className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                                                        title="Excluir usuário"
                                                        disabled={u.email === user.email}
                                                    >
                                                        <Trash2 className="w-5 h-5" />
                                                    </button>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* Add/Edit User Modal */}
            {showModal && (
                <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
                    <div className="bg-white rounded-lg shadow-xl max-w-md w-full">
                        <div className="p-6">
                            <h3 className="text-xl font-bold text-gray-900 mb-4">
                                {editingUser ? 'Editar Usuário' : 'Novo Usuário'}
                            </h3>

                            <form onSubmit={handleSubmit} className="space-y-4">
                                {editingUser ? (
                                    <div className="space-y-3">
                                        <div className="bg-gray-50 p-3 rounded-lg border border-gray-150 space-y-2">
                                            <div>
                                                <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block">Usuário</span>
                                                <p className="text-sm font-bold text-gray-800">{editingUser.username}</p>
                                            </div>
                                            <div>
                                                <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block">Email</span>
                                                <p className="text-sm text-gray-700">{editingUser.email}</p>
                                            </div>
                                        </div>
                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                                Nova Senha (opcional)
                                            </label>
                                            <input
                                                type="password"
                                                value={formData.password}
                                                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                                                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                                                placeholder="Deixe em branco para manter"
                                            />
                                        </div>
                                    </div>
                                ) : (
                                    <>
                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                                Nome de Usuário *
                                            </label>
                                            <input
                                                type="text"
                                                value={formData.username}
                                                onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                                                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                                                placeholder="joao.silva"
                                                required
                                            />
                                        </div>

                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                                Email *
                                            </label>
                                            <input
                                                type="email"
                                                value={formData.email}
                                                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                                                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                                                placeholder="joao.silva@empresa.com"
                                                required
                                            />
                                        </div>

                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                                Senha *
                                            </label>
                                            <input
                                                type="password"
                                                value={formData.password}
                                                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                                                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                                                placeholder="••••••••"
                                                required
                                            />
                                        </div>
                                    </>
                                )}

                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        Função *
                                    </label>
                                    <select
                                        value={formData.role}
                                        onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                                        required
                                    >
                                        <option value="operator">OPERADOR</option>
                                        <option value="admin">LÍDER</option>
                                        <option value="master">MASTER</option>
                                    </select>
                                    <p className="mt-1 text-xs text-gray-500">
                                        OPERADOR: PCP/Expedição/Comercial básico | LÍDER: Gerência | MASTER: Admin Total
                                    </p>
                                </div>

                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        Área *
                                    </label>
                                    <select
                                        value={formData.area}
                                        onChange={(e) => setFormData({ ...formData, area: e.target.value })}
                                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                                        required
                                    >
                                        <option value="">Selecione...</option>
                                        <option value="Comercial">Comercial</option>
                                        <option value="PCP">PCP</option>
                                        <option value="Produção">Produção</option>
                                        <option value="Embalagem">Embalagem</option>
                                        <option value="Expedição">Expedição</option>
                                        <option value="Financeiro">Financeiro</option>
                                        <option value="Management">Management</option>
                                    </select>
                                </div>

                                {/* FF-HARDENING-011: SLA Manager delegation checkbox — only for 'master' role in edit mode */}
                                {editingUser && formData.role === 'master' && (
                                    <div className="flex items-start gap-3 p-3 bg-indigo-50 border border-indigo-200 rounded-lg">
                                        <input
                                            id="chk-sla-manager"
                                            type="checkbox"
                                            checked={Boolean(formData.is_sla_manager)}
                                            onChange={(e) => setFormData({ ...formData, is_sla_manager: e.target.checked })}
                                            className="mt-0.5 h-4 w-4 rounded border-indigo-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                                        />
                                        <label htmlFor="chk-sla-manager" className="cursor-pointer">
                                            <span className="block text-sm font-semibold text-indigo-800">Liberar Config/SLA</span>
                                            <span className="block text-xs text-indigo-600 mt-0.5">
                                                Permite que este usuário acesse e edite os Parâmetros de SLA Industrial nas Configurações do Sistema,
                                                sem precisar de perfil admin.
                                            </span>
                                        </label>
                                    </div>
                                )}

                                <div className="flex items-center justify-end gap-3 pt-4">
                                    <button
                                        type="button"
                                        onClick={handleCloseModal}
                                        className="px-4 py-2 bg-gray-300 text-gray-700 rounded-lg hover:bg-gray-400 transition-colors"
                                    >
                                        Cancelar
                                    </button>
                                    <button
                                        type="submit"
                                        className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
                                    >
                                        {editingUser ? 'Salvar Alterações' : 'Criar Usuário'}
                                    </button>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}

export default UsersPage
