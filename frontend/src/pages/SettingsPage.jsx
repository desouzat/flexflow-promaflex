import React, { useState, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'
import { Shield, Settings, Mail, Save, Loader2, Clock, Calendar, Timer, AlertCircle, UserCheck } from 'lucide-react'
import api from '../utils/api'
import { showSuccess, showError, showLoading, dismissToast } from '../utils/toast'

const SettingsPage = () => {
    const { user, loading: authLoading } = useAuth()

    // --- Support Email State ---
    const [supportEmail, setSupportEmail] = useState('')
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)

    // --- SLA Config State (FF-HARDENING-010) ---
    const [slaTotalHours, setSlaTotalHours] = useState(240)
    const [slaAreaHours, setSlaAreaHours] = useState(24)
    const [slaStartHour, setSlaStartHour] = useState(8)
    const [slaEndHour, setSlaEndHour] = useState(18)
    const [slaWorkingDays, setSlaWorkingDays] = useState('Mon-Fri')
    const [slaLoading, setSlaLoading] = useState(true)
    const [slaSaving, setSlaSaving] = useState(false)

    // --- SLA Manager Email Delegation (FF-HARDENING-011) ---
    const [slaManagerEmail, setSlaManagerEmail] = useState('')
    const [slaManagerEmailInput, setSlaManagerEmailInput] = useState('')
    const [slaAccessLoading, setSlaAccessLoading] = useState(true)
    const [hasSlaAccess, setHasSlaAccess] = useState(false)
    const [slaManagerSaving, setSlaManagerSaving] = useState(false)

    const isAdmin = (user?.role || '').toLowerCase() === 'admin'
    const isPrivileged = ['admin', 'master'].includes((user?.role || '').toLowerCase())

    useEffect(() => {
        if (authLoading) return
        // Check SLA access for all logged-in users (admin, master, OR SLA manager delegate)
        fetchSlaAccess()
        // Only admin fetches support email
        if (isAdmin) {
            fetchSupportEmail()
        }
    }, [user, authLoading])

    // When we know hasSlaAccess, fetch SLA config
    useEffect(() => {
        if (!slaAccessLoading && hasSlaAccess) {
            fetchSlaConfig()
        }
    }, [slaAccessLoading, hasSlaAccess])

    const fetchSlaAccess = async () => {
        try {
            setSlaAccessLoading(true)
            const response = await api.get('/settings/sla-access')
            setHasSlaAccess(response.data.has_access)
            const mgr = response.data.sla_manager_email || ''
            setSlaManagerEmail(mgr)
            setSlaManagerEmailInput(mgr)
        } catch (error) {
            console.error('Failed to fetch SLA access:', error)
            // If 403, user has no access; that is fine
            setHasSlaAccess(isPrivileged)
        } finally {
            setSlaAccessLoading(false)
        }
    }

    const fetchSupportEmail = async () => {
        try {
            setLoading(true)
            const response = await api.get('/settings/support-email')
            setSupportEmail(response.data.support_email)
        } catch (error) {
            console.error('Failed to fetch settings:', error)
            showError('Erro ao carregar configurações de suporte.')
        } finally {
            setLoading(false)
        }
    }

    const fetchSlaConfig = async () => {
        try {
            setSlaLoading(true)
            const response = await api.get('/settings/sla-config')
            const data = response.data
            setSlaTotalHours(data.sla_total_hours)
            setSlaAreaHours(data.sla_area_hours)
            setSlaStartHour(data.sla_start_hour)
            setSlaEndHour(data.sla_end_hour)
            setSlaWorkingDays(data.sla_working_days)
            const mgr = data.sla_manager_email || ''
            setSlaManagerEmail(mgr)
            setSlaManagerEmailInput(mgr)
        } catch (error) {
            console.error('Failed to fetch SLA config:', error)
            showError('Erro ao carregar parâmetros de SLA.')
        } finally {
            setSlaLoading(false)
        }
    }

    const handleSaveEmail = async (e) => {
        e.preventDefault()
        if (!supportEmail.trim()) {
            showError('O e-mail de suporte não pode estar vazio.')
            return
        }
        setSaving(true)
        const toastId = showLoading('Salvando configurações...')
        try {
            const response = await api.post('/settings/support-email', { support_email: supportEmail })
            setSupportEmail(response.data.support_email)
            dismissToast(toastId)
            showSuccess('Configurações salvas com sucesso!')
        } catch (error) {
            dismissToast(toastId)
            showError(error.response?.data?.detail || 'Erro ao salvar configurações.')
        } finally {
            setSaving(false)
        }
    }

    const handleSaveSlaConfig = async (e) => {
        e.preventDefault()

        // Client-side validation
        if (slaStartHour >= slaEndHour) {
            showError('A hora de início do expediente deve ser menor que a hora de encerramento.')
            return
        }
        if (slaTotalHours < 1 || slaAreaHours < 1) {
            showError('Os limites de SLA devem ser maiores que zero.')
            return
        }

        setSlaSaving(true)
        const toastId = showLoading('Salvando parâmetros de SLA...')
        try {
            const payload = {
                sla_total_hours: parseInt(slaTotalHours, 10),
                sla_area_hours:  parseInt(slaAreaHours, 10),
                sla_start_hour:  parseInt(slaStartHour, 10),
                sla_end_hour:    parseInt(slaEndHour, 10),
                sla_working_days: slaWorkingDays,
            }
            // Admin can also save sla_manager_email inline
            if (isAdmin) {
                payload.sla_manager_email = slaManagerEmailInput.trim() || null
            }
            const response = await api.put('/settings/sla-config', payload)
            const d = response.data
            setSlaTotalHours(d.sla_total_hours)
            setSlaAreaHours(d.sla_area_hours)
            setSlaStartHour(d.sla_start_hour)
            setSlaEndHour(d.sla_end_hour)
            setSlaWorkingDays(d.sla_working_days)
            if (d.sla_manager_email !== undefined) {
                setSlaManagerEmail(d.sla_manager_email || '')
                setSlaManagerEmailInput(d.sla_manager_email || '')
            }
            dismissToast(toastId)
            showSuccess('Parâmetros de SLA atualizados com sucesso!')
        } catch (error) {
            dismissToast(toastId)
            showError(error.response?.data?.detail || 'Erro ao salvar parâmetros de SLA.')
        } finally {
            setSlaSaving(false)
        }
    }

    if (authLoading || slaAccessLoading) {
        return (
            <div className="h-full flex items-center justify-center bg-gray-50">
                <div className="w-12 h-12 border-4 border-primary-600 border-t-transparent rounded-full animate-spin" />
            </div>
        )
    }

    // Access gate: admin, master, OR SLA manager email delegate
    if (!hasSlaAccess && !isAdmin) {
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
                <div className="max-w-2xl mx-auto space-y-6">

                    {/* ── Support Email Card (admin only) ── */}
                    {isAdmin && (
                        <div className="bg-white rounded-xl shadow-md border border-gray-200 overflow-hidden">
                            <div className="p-6 border-b border-gray-200 bg-gray-50">
                                <h2 className="text-lg font-bold text-gray-800 flex items-center gap-2">
                                    <Mail className="w-5 h-5 text-gray-500" />
                                    Suporte &amp; Chamados
                                </h2>
                                <p className="text-xs text-gray-500 mt-1">
                                    Defina o endereço de destino para os problemas reportados pelos operadores do sistema.
                                </p>
                            </div>

                            {loading ? (
                                <div className="flex items-center justify-center h-32">
                                    <div className="w-8 h-8 border-4 border-primary-600 border-t-transparent rounded-full animate-spin" />
                                </div>
                            ) : (
                                <form onSubmit={handleSaveEmail} className="p-6 space-y-6">
                                    <div>
                                        <label className="block text-sm font-semibold text-gray-700 mb-2">
                                            E-mail de Suporte
                                        </label>
                                        <div className="relative rounded-lg shadow-sm">
                                            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                                <Mail className="h-5 w-5 text-gray-400" />
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
                            )}
                        </div>
                    )}

                    {/* ── SLA Parameters Card (admin + master + sla_manager_email delegate) ── */}
                    {/* FF-HARDENING-011 [Item 3]: visible PERMANENTLY when hasSlaAccess is true */}
                    {hasSlaAccess && (
                        <div className="bg-white rounded-xl shadow-md border border-gray-200 overflow-hidden">
                            <div className="p-6 border-b border-gray-200 bg-gradient-to-r from-indigo-50 to-blue-50">
                                <h2 className="text-lg font-bold text-gray-800 flex items-center gap-2">
                                    <Timer className="w-5 h-5 text-indigo-600" />
                                    Parâmetros de SLA Industrial
                                </h2>
                                <p className="text-xs text-gray-500 mt-1">
                                    Configure os limites e o calendário de horas úteis para o cálculo automático de SLA.
                                    Alterações têm efeito imediato no cronômetro de todos os pedidos ativos.
                                </p>
                            </div>

                            {slaLoading ? (
                                <div className="flex items-center justify-center h-48">
                                    <div className="w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" />
                                </div>
                            ) : (
                                <form onSubmit={handleSaveSlaConfig} className="p-6 space-y-6">
                                    {/* Informational notice */}
                                    <div className="flex items-start gap-3 p-3 bg-amber-50 border border-amber-200 rounded-lg">
                                        <AlertCircle className="w-4 h-4 text-amber-600 mt-0.5 flex-shrink-0" />
                                        <p className="text-xs text-amber-800">
                                            O SLA é calculado apenas dentro das <strong>horas úteis</strong> configuradas.
                                            Noites, fins de semana e dias fora do expediente não contam para o cronômetro.
                                        </p>
                                    </div>

                                    {/* SLA Limits */}
                                    <div>
                                        <h3 className="text-xs font-bold text-gray-600 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                                            <Clock className="w-3.5 h-3.5" /> Limites de Horas
                                        </h3>
                                        <div className="grid grid-cols-2 gap-4">
                                            <div>
                                                <label className="block text-sm font-semibold text-gray-700 mb-1">
                                                    SLA Total (horas)
                                                </label>
                                                <input
                                                    id="sla-total-hours"
                                                    type="number"
                                                    min="1"
                                                    max="9999"
                                                    value={slaTotalHours}
                                                    onChange={(e) => setSlaTotalHours(e.target.value)}
                                                    className="block w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-sm font-medium font-mono"
                                                />
                                                <p className="text-xs text-gray-400 mt-1">Prazo máximo total (padrão: 240h = 30 dias úteis de 8h)</p>
                                            </div>
                                            <div>
                                                <label className="block text-sm font-semibold text-gray-700 mb-1">
                                                    SLA por Área (horas)
                                                </label>
                                                <input
                                                    id="sla-area-hours"
                                                    type="number"
                                                    min="1"
                                                    max="9999"
                                                    value={slaAreaHours}
                                                    onChange={(e) => setSlaAreaHours(e.target.value)}
                                                    className="block w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-sm font-medium font-mono"
                                                />
                                                <p className="text-xs text-gray-400 mt-1">Prazo máximo por setor operacional (padrão: 24h)</p>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Business Hours */}
                                    <div>
                                        <h3 className="text-xs font-bold text-gray-600 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                                            <Calendar className="w-3.5 h-3.5" /> Expediente Industrial
                                        </h3>
                                        <div className="grid grid-cols-2 gap-4 mb-4">
                                            <div>
                                                <label className="block text-sm font-semibold text-gray-700 mb-1">
                                                    Início do Expediente (hora)
                                                </label>
                                                <input
                                                    id="sla-start-hour"
                                                    type="number"
                                                    min="0"
                                                    max="23"
                                                    value={slaStartHour}
                                                    onChange={(e) => setSlaStartHour(e.target.value)}
                                                    className="block w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-sm font-medium font-mono"
                                                />
                                                <p className="text-xs text-gray-400 mt-1">Ex: 8 = 08:00 (padrão)</p>
                                            </div>
                                            <div>
                                                <label className="block text-sm font-semibold text-gray-700 mb-1">
                                                    Encerramento do Expediente (hora)
                                                </label>
                                                <input
                                                    id="sla-end-hour"
                                                    type="number"
                                                    min="1"
                                                    max="24"
                                                    value={slaEndHour}
                                                    onChange={(e) => setSlaEndHour(e.target.value)}
                                                    className="block w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-sm font-medium font-mono"
                                                />
                                                <p className="text-xs text-gray-400 mt-1">Ex: 18 = 18:00 (padrão)</p>
                                            </div>
                                        </div>
                                        <div>
                                            <label className="block text-sm font-semibold text-gray-700 mb-1">
                                                Dias Úteis de Trabalho
                                            </label>
                                            <select
                                                id="sla-working-days"
                                                value={slaWorkingDays}
                                                onChange={(e) => setSlaWorkingDays(e.target.value)}
                                                className="block w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-sm font-medium"
                                            >
                                                <option value="Mon-Fri">Segunda a Sexta (Mon-Fri)</option>
                                                <option value="Mon-Sat">Segunda a Sábado (Mon-Sat)</option>
                                                <option value="Mon-Sun">Segunda a Domingo (Mon-Sun)</option>
                                                <option value="Mon,Wed,Fri">Seg, Qua, Sex (Mon,Wed,Fri)</option>
                                            </select>
                                            <p className="text-xs text-gray-400 mt-1">Sábados e Domingos não são contados como horas úteis no padrão Mon-Fri.</p>
                                        </div>
                                    </div>

                                    {/* Preview of computed daily hours */}
                                    <div className="flex items-center gap-2 p-3 bg-indigo-50 border border-indigo-200 rounded-lg">
                                        <Timer className="w-4 h-4 text-indigo-500 flex-shrink-0" />
                                        <p className="text-xs text-indigo-800">
                                            <strong>Horas úteis por dia:</strong>{' '}
                                            {Math.max(0, parseInt(slaEndHour, 10) - parseInt(slaStartHour, 10))}h
                                            {' '}({slaStartHour}:00 → {slaEndHour}:00).{' '}
                                            SLA total de <strong>{slaTotalHours}h</strong> ≈{' '}
                                            {(slaTotalHours / Math.max(1, parseInt(slaEndHour, 10) - parseInt(slaStartHour, 10))).toFixed(1)} dias úteis.
                                        </p>
                                    </div>

                                    {/* FF-HARDENING-011 [Item 3]: SLA Manager Email (admin only) */}
                                    {isAdmin && (
                                        <div>
                                            <h3 className="text-xs font-bold text-gray-600 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                                                <UserCheck className="w-3.5 h-3.5" /> Responsável pelo SLA (Delegação)
                                            </h3>
                                            <div>
                                                <label className="block text-sm font-semibold text-gray-700 mb-1">
                                                    E-mail do Responsável pelo SLA
                                                </label>
                                                <input
                                                    id="sla-manager-email"
                                                    type="email"
                                                    value={slaManagerEmailInput}
                                                    onChange={(e) => setSlaManagerEmailInput(e.target.value)}
                                                    placeholder="responsavel@empresa.com (deixe vazio para remover)"
                                                    className="block w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-sm font-medium"
                                                />
                                                <p className="text-xs text-gray-400 mt-1">
                                                    Quando definido, este usuário poderá acessar e editar os Parâmetros de SLA mesmo sem perfil admin/master.
                                                    Deixe em branco para remover a delegação.
                                                </p>
                                            </div>
                                        </div>
                                    )}

                                    <div className="flex items-center justify-end pt-4 border-t border-gray-200">
                                        <button
                                            type="submit"
                                            disabled={slaSaving}
                                            className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors shadow-sm disabled:bg-indigo-400 font-semibold text-sm cursor-pointer"
                                        >
                                            {slaSaving ? (
                                                <>
                                                    <Loader2 className="w-4 h-4 animate-spin" />
                                                    Salvando...
                                                </>
                                            ) : (
                                                <>
                                                    <Save className="w-4 h-4" />
                                                    Salvar Parâmetros de SLA
                                                </>
                                            )}
                                        </button>
                                    </div>
                                </form>
                            )}
                        </div>
                    )}

                </div>
            </div>
        </div>
    )
}

export default SettingsPage
