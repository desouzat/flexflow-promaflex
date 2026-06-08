import React, { useState } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useNotifications } from '../context/NotificationContext'
import api from '../utils/api'
import { showSuccess, showError, showLoading, dismissToast } from '../utils/toast'
import {
    LayoutDashboard,
    Kanban,
    Upload,
    LogOut,
    Menu,
    X,
    User,
    DollarSign,
    Users,
    AlertCircle,
    Settings
} from 'lucide-react'

const Layout = () => {
    const [sidebarOpen, setSidebarOpen] = useState(true)
    const [showReportModal, setShowReportModal] = useState(false)
    const [reportDescription, setReportDescription] = useState('')
    const [reportAttachment, setReportAttachment] = useState(null)
    const [showSuccessModal, setShowSuccessModal] = useState(false)
    const [successTicketId, setSuccessTicketId] = useState('')
    const { user, logout } = useAuth()
    const { badges } = useNotifications()
    const navigate = useNavigate()

    const handleLogout = () => {
        logout()
        navigate('/login')
    }

    const navItems = [
        { path: '/kanban', icon: Kanban, label: 'Kanban Board', badge: 'kanban' },
        { path: '/import', icon: Upload, label: 'Import POs', badge: 'import' },
        { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard', badge: 'dashboard' },
        { path: '/costs', icon: DollarSign, label: 'Gerenciar Custos', badge: 'costs', adminOnly: true },
        { path: '/users', icon: Users, label: 'Gestão de Usuários', badge: 'users', strictAdminOnly: true },
        { path: '/settings', icon: Settings, label: 'Configurações', badge: 'settings', strictAdminOnly: true },
    ]

    const handleReportProblem = async () => {
        if (!reportDescription.trim()) {
            showError('Por favor, descreva o problema')
            return
        }

        const toastId = showLoading('Enviando chamado...')

        try {
            const formData = new FormData()
            formData.append('description', reportDescription)
            if (reportAttachment) {
                formData.append('attachment', reportAttachment)
            }

            const response = await api.post('/support/ticket', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data'
                }
            })

            dismissToast(toastId)
            
            const ticketId = response.data.ticket_id
            setSuccessTicketId(ticketId)
            setShowSuccessModal(true)
            showSuccess(`Chamado registrado! Guarde seu ID: ${ticketId}`)

            setReportDescription('')
            setReportAttachment(null)
            setShowReportModal(false)
        } catch (error) {
            dismissToast(toastId)
            console.error('Failed to report problem:', error)
            showError(error.response?.data?.detail || 'Erro ao reportar problema')
        }
    }

    return (
        <div className="flex h-screen bg-gray-50">
            {/* Sidebar */}
            <aside
                className={`${sidebarOpen ? 'w-64' : 'w-20'
                    } bg-white border-r border-gray-200 transition-all duration-300 flex flex-col`}
            >
                {/* Sidebar Header */}
                <div className="h-16 flex items-center justify-between px-4 border-b border-gray-200">
                    {sidebarOpen && (
                        <h1 className="text-xl font-bold text-primary-600">FlexFlow</h1>
                    )}
                    <button
                        onClick={() => setSidebarOpen(!sidebarOpen)}
                        className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
                        aria-label={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}
                    >
                        {sidebarOpen ? (
                            <X className="w-5 h-5 text-gray-600" />
                        ) : (
                            <Menu className="w-5 h-5 text-gray-600" />
                        )}
                    </button>
                </div>

                {/* Navigation */}
                <nav className="flex-1 px-3 py-4 space-y-1">
                    {navItems.map((item) => {
                        // Hide strictAdminOnly items if user is not admin
                        if (item.strictAdminOnly && (user?.role || '').toLowerCase() !== 'admin') {
                            return null
                        }

                        // Hide admin-only items if user is not admin or master
                        if (item.adminOnly && (user?.role || '').toLowerCase() !== 'admin' && (user?.role || '').toLowerCase() !== 'master') {
                            return null
                        }

                        // Hide master-only items if user is not master
                        if (item.masterOnly && (user?.role || '').toLowerCase() !== 'master') {
                            return null
                        }

                        return (
                            <NavLink
                                key={item.path}
                                to={item.path}
                                className={({ isActive }) =>
                                    `flex items-center gap-3 px-3 py-3 rounded-lg transition-colors relative ${isActive
                                        ? 'bg-primary-50 text-primary-700'
                                        : 'text-gray-700 hover:bg-gray-100'
                                    }`
                                }
                            >
                                <item.icon className="w-5 h-5 flex-shrink-0" />
                                {sidebarOpen && (
                                    <span className="font-medium flex-1">{item.label}</span>
                                )}
                                {badges[item.badge] > 0 && (
                                    <span className={`${sidebarOpen ? '' : 'absolute -top-1 -right-1'} flex items-center justify-center min-w-[20px] h-5 px-1.5 text-xs font-bold text-white bg-red-500 rounded-full`}>
                                        {badges[item.badge] > 99 ? '99+' : badges[item.badge]}
                                    </span>
                                )}
                            </NavLink>
                        )
                    })}
                </nav>

                {/* User Section */}
                <div className="border-t border-gray-200 p-4">
                    <div className={`flex items-center gap-3 ${!sidebarOpen && 'justify-center'}`}>
                        <div className="w-10 h-10 bg-primary-100 rounded-full flex items-center justify-center flex-shrink-0">
                            <User className="w-5 h-5 text-primary-600" />
                        </div>
                        {sidebarOpen && (
                            <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium text-gray-900 truncate">
                                    {user?.username || 'User'}
                                </p>
                                <p className="text-xs text-gray-500 truncate">
                                    {user?.email || 'user@example.com'}
                                </p>
                            </div>
                        )}
                    </div>
                    <button
                        onClick={() => setShowReportModal(true)}
                        className={`mt-3 w-full flex items-center gap-3 px-3 py-2 text-orange-600 hover:bg-orange-50 rounded-lg transition-colors ${!sidebarOpen && 'justify-center'
                            }`}
                        title="Reportar Problema"
                    >
                        <AlertCircle className="w-5 h-5 flex-shrink-0" />
                        {sidebarOpen && <span className="font-medium">Reportar Problema</span>}
                    </button>
                    <button
                        onClick={handleLogout}
                        className={`mt-2 w-full flex items-center gap-3 px-3 py-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors ${!sidebarOpen && 'justify-center'
                            }`}
                        aria-label="Logout"
                    >
                        <LogOut className="w-5 h-5 flex-shrink-0" />
                        {sidebarOpen && <span className="font-medium">Logout</span>}
                    </button>
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 overflow-auto">
                <div className="h-full">
                    <Outlet />
                </div>
            </main>

            {/* Report Problem Modal */}
            {showReportModal && (
                <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
                    <div className="bg-white rounded-lg shadow-xl max-w-md w-full">
                        <div className="p-6">
                            <div className="flex items-center gap-3 mb-4">
                                <AlertCircle className="w-6 h-6 text-orange-600" />
                                <h3 className="text-xl font-bold text-gray-900">Reportar Problema</h3>
                            </div>

                            <p className="text-sm text-gray-600 mb-4">
                                Descreva o problema encontrado. Nossa equipe será notificada imediatamente.
                            </p>

                            <textarea
                                value={reportDescription}
                                onChange={(e) => setReportDescription(e.target.value)}
                                placeholder="Descreva o problema em detalhes..."
                                rows={5}
                                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent mb-4"
                            />

                            {/* Attachment Input */}
                            <div className="mb-4 text-left">
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Anexo (opcional, PDF/JPG/PNG, máx 5MB)
                                </label>
                                <input
                                    type="file"
                                    accept=".pdf,.jpg,.jpeg,.png"
                                    onChange={(e) => setReportAttachment(e.target.files[0] || null)}
                                    className="w-full text-sm text-gray-550 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-orange-50 file:text-orange-700 hover:file:bg-orange-100 cursor-pointer border border-gray-300 rounded-lg p-1"
                                />
                                {reportAttachment && (
                                    <p className="text-xs text-green-600 mt-1 font-medium">
                                        ✓ Arquivo selecionado: {reportAttachment.name}
                                    </p>
                                )}
                            </div>

                            <div className="flex items-center justify-end gap-3">
                                <button
                                    onClick={() => {
                                        setShowReportModal(false)
                                        setReportDescription('')
                                        setReportAttachment(null)
                                    }}
                                    className="px-4 py-2 bg-gray-300 text-gray-700 rounded-lg hover:bg-gray-400 transition-colors"
                                >
                                    Cancelar
                                </button>
                                <button
                                    onClick={handleReportProblem}
                                    className="px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 transition-colors"
                                >
                                    Enviar Relatório
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Success Ticket Modal */}
            {showSuccessModal && (
                <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
                    <div className="bg-white rounded-lg shadow-xl max-w-sm w-full p-6 text-center">
                        <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                            <span className="text-green-600 text-2xl font-bold">✓</span>
                        </div>
                        <h3 className="text-xl font-bold text-gray-900 mb-2">Chamado Registrado!</h3>
                        <p className="text-sm text-gray-600 mb-4">
                            Seu chamado foi registrado com sucesso.
                        </p>
                        <div className="bg-gray-100 rounded-lg p-3 mb-6 font-mono font-bold text-lg text-primary-700 tracking-wider">
                            {successTicketId}
                        </div>
                        <p className="text-xs text-gray-500 mb-6 font-medium">
                            Guarde seu ID para acompanhamento do problema.
                        </p>
                        <button
                            onClick={() => {
                                setShowSuccessModal(false)
                                setSuccessTicketId('')
                            }}
                            className="w-full py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-semibold"
                        >
                            Fechar
                        </button>
                    </div>
                </div>
            )}
        </div>
    )
}

export default Layout
