import React, { useState, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'
import { Shield, Settings, Mail, Save, Loader2 } from 'lucide-react'
import api from '../utils/api'
import { showSuccess, showError, showLoading, dismissToast } from '../utils/toast'

const SettingsPage = () => {
    const { user, loading: authLoading } = useAuth()
    const [supportEmail, setSupportEmail] = useState('')
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)

    useEffect(() => {
        if (!authLoading && (user?.role || '').toLowerCase() === 'admin') {
            fetchSettings()
        }
    }, [user, authLoading])

    const fetchSettings = async () => {
        try {
            setLoading(true)
            const response = await api.get('/settings/support-email')
            setSupportEmail(response.data.support_email)
        } catch (error) {
            console.error('Failed to fetch settings:', error)
            showError('Erro ao carregar configurações.')
        } finally {
            setLoading(false)
        }
    }

    const handleSave = async (e) => {
        e.preventDefault()
        if (!supportEmail.trim()) {
            showError('O e-mail de suporte não pode estar vazio.')
            return
        }

        setSaving(true)
        const toastId = showLoading('Salvando configurações...')

        try {
            const response = await api.post('/settings/support-email', {
                support_email: supportEmail
            })
            setSupportEmail(response.data.support_email)
            dismissToast(toastId)
            showSuccess('Configurações salvas com sucesso!')
        } catch (error) {
            dismissToast(toastId)
            console.error('Failed to save settings:', error)
            showError(error.response?.data?.detail || 'Erro ao salvar configurações.')
        } finally {
            setSaving(false)
        }
    }

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
                <div className="text-center p-8 bg-white rounded-lg shadow-md max-w-md">
                    <Shield className="w-16 h-16 text-red-500 mx-auto mb-4" />
                    <h2 className="text-2xl font-bold text-gray-900 mb-2">Acesso Negado</h2>
                    <p className="text-gray-650">Você não possui o nível de permissão necessário (Administrador) para gerenciar as configurações do sistema.</p>
                </div>
            </div>
        )
    }

    return (
        <div className="h-full flex flex-col bg-gray-50">
            {/* Header */}
            <div className="bg-white border-b border-gray-200 px-6 py-4 shadow-sm">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-primary-50 rounded-lg">
                        <Settings className="w-6 h-6 text-primary-600" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-gray-900">Configurações do Sistema</h1>
                        <p className="text-sm text-gray-500 mt-0.5">
                            Gerencie os parâmetros globais e e-mails de atendimento
                        </p>
                    </div>
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 p-6 overflow-auto">
                <div className="max-w-2xl mx-auto">
                    {loading ? (
                        <div className="flex items-center justify-center h-64">
                            <div className="w-12 h-12 border-4 border-primary-600 border-t-transparent rounded-full animate-spin" />
                        </div>
                    ) : (
                        <div className="bg-white rounded-xl shadow-md border border-gray-200 overflow-hidden">
                            <div className="p-6 border-b border-gray-200 bg-gray-50">
                                <h2 className="text-lg font-bold text-gray-800 flex items-center gap-2">
                                    <Mail className="w-5 h-5 text-gray-500" />
                                    Suporte & Chamados
                                </h2>
                                <p className="text-xs text-gray-500 mt-1">
                                    Defina o endereço de destino para os problemas reportados pelos operadores do sistema.
                                </p>
                            </div>
                            
                            <form onSubmit={handleSave} className="p-6 space-y-6">
                                <div>
                                    <label className="block text-sm font-semibold text-gray-700 mb-2">
                                        E-mail de Suporte
                                    </label>
                                    <div className="relative rounded-lg shadow-sm">
                                        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                            <Mail className="h-5 h-5 text-gray-400" />
                                        </div>
                                        <input
                                            type="email"
                                            value={supportEmail}
                                            onChange={(e) => setSupportEmail(e.target.value)}
                                            placeholder="exemplo@empresa.com"
                                            className="block w-full pl-10 pr-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm font-medium"
                                            required
                                        />
                                    </div>
                                    <p className="text-xs text-gray-400 mt-2">
                                        Todas as mensagens e logs do simulador serão direcionados para este e-mail.
                                    </p>
                                </div>

                                <div className="flex items-center justify-end pt-4 border-t border-gray-200">
                                    <button
                                        type="submit"
                                        disabled={saving}
                                        className="flex items-center gap-2 px-5 py-2.5 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors shadow-sm disabled:bg-primary-400 font-semibold text-sm cursor-pointer"
                                    >
                                        {saving ? (
                                            <>
                                                <Loader2 className="w-4 h-4 animate-spin" />
                                                Salvando...
                                            </>
                                        ) : (
                                            <>
                                                <Save className="w-4 h-4" />
                                                Salvar Configurações
                                            </>
                                        )}
                                    </button>
                                </div>
                            </form>
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}

export default SettingsPage
