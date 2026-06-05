import React, { useState, useEffect } from 'react'
import { 
    BarChart3, 
    TrendingUp, 
    Package, 
    DollarSign, 
    Clock, 
    AlertTriangle, 
    ShieldAlert, 
    Calendar,
    Users as UsersIcon,
    Lock
} from 'lucide-react'
import {
    BarChart,
    Bar,
    PieChart,
    Pie,
    Cell,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer,
} from 'recharts'
import api from '../utils/api'
import { showError } from '../utils/toast'
import { useAuth } from '../context/AuthContext'

const DashboardPage = () => {
    const { user } = useAuth()
    const [loading, setLoading] = useState(true)
    const [kpiData, setKpiData] = useState(null)

    useEffect(() => {
        fetchCelsoKpis()
    }, [])

    const fetchCelsoKpis = async () => {
        try {
            setLoading(true)
            const response = await api.get('/dashboard/celso-kpis')
            setKpiData(response.data)
        } catch (error) {
            console.error('Erro ao carregar KPIs do Celso:', error)
            showError('Falha ao carregar indicadores do dashboard')
        } finally {
            setLoading(false)
        }
    }

    const formatCurrency = (value) => {
        if (value === '***') return '***'
        const num = parseFloat(value)
        if (isNaN(num)) return value
        return new Intl.NumberFormat('pt-BR', {
            style: 'currency',
            currency: 'BRL',
        }).format(num)
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center h-full">
                <div className="text-center">
                    <div className="w-16 h-16 border-4 border-primary-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                    <p className="text-gray-650 font-medium">Carregando painel de KPIs...</p>
                </div>
            </div>
        )
    }

    // Default fallbacks if backend returns empty/null
    const portfolio = kpiData?.portfolio_by_unit || { "Indústria": 0, "Construção Civil": 0, "Varejo": 0, "Outros": 0 }
    const margin = kpiData?.margin_by_unit || {
        "Indústria": { "total_margin": 0, "margin_percentage": 0 },
        "Construção Civil": { "total_margin": 0, "margin_percentage": 0 },
        "Varejo": { "total_margin": 0, "margin_percentage": 0 },
        "Outros": { "total_margin": 0, "margin_percentage": 0 }
    }
    const billing = kpiData?.billing_status || { "current_month": 0, "next_month": 0 }
    const readyNotBilled = kpiData?.ready_not_billed?.ready_not_billed_total ?? 0
    const ageingDays = kpiData?.ageing?.average_ageing_days ?? 0.0
    const salesRank = kpiData?.sales_ranking || []
    const alerts = kpiData?.alerts || { total_alerts: 0, details: [] }
    const generatedAt = kpiData?.generated_at ?? 'N/A'

    // Check if margins are masked
    const isMarginMasked = Object.values(margin).some(m => m.total_margin === '***')

    // Data transformation for Recharts
    const portfolioChartData = Object.keys(portfolio).map(key => ({
        name: key,
        value: portfolio[key]
    }))

    const marginChartData = isMarginMasked 
        ? [] 
        : Object.keys(margin).map(key => ({
            name: key,
            'Margem Absoluta': parseFloat(margin[key].total_margin || 0),
            'Margem %': parseFloat(margin[key].margin_percentage || 0)
        }))

    const billingChartData = [
        { name: 'Mês Atual', Valor: billing.current_month },
        { name: 'Próximo Mês', Valor: billing.next_month }
    ]

    const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6']

    return (
        <div className="h-full flex flex-col bg-gray-50">
            {/* Header */}
            <div className="bg-white border-b border-gray-200 px-6 py-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
                        <BarChart3 className="w-7 h-7 text-primary-600" />
                        Dashboard de Negócios (KPIs)
                    </h1>
                    <p className="text-sm text-gray-600 mt-0.5">
                        Métricas de portfólio, margens, faturamento e alertas operacionais
                    </p>
                </div>
                <div className="flex items-center gap-1.5 text-xs text-gray-500 bg-gray-100 px-3 py-1.5 rounded-lg border border-gray-200 self-start sm:self-center">
                    <Calendar className="w-4 h-4 text-gray-400" />
                    <span>Gerado em: <strong>{generatedAt}</strong></span>
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 p-6 overflow-auto space-y-6">
                {/* Stats Row */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div className="card shadow-xs hover:shadow-md transition-all duration-300">
                        <div className="flex items-center justify-between mb-3">
                            <div className="bg-blue-500 p-3 rounded-lg text-white">
                                <Package className="w-6 h-6" />
                            </div>
                            <span className="text-xs font-semibold text-blue-600 bg-blue-50 px-2.5 py-1 rounded-full border border-blue-200">
                                Expedição
                            </span>
                        </div>
                        <h3 className="text-2xl font-extrabold text-gray-900 mb-1">
                            {formatCurrency(readyNotBilled)}
                        </h3>
                        <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">Pronto / Não Faturado</p>
                    </div>

                    <div className="card shadow-xs hover:shadow-md transition-all duration-300">
                        <div className="flex items-center justify-between mb-3">
                            <div className="bg-indigo-500 p-3 rounded-lg text-white">
                                <Clock className="w-6 h-6" />
                            </div>
                            <span className="text-xs font-semibold text-indigo-600 bg-indigo-50 px-2.5 py-1 rounded-full border border-indigo-200">
                                Média Histórica
                            </span>
                        </div>
                        <h3 className="text-2xl font-extrabold text-gray-900 mb-1">
                            {ageingDays} <span className="text-sm text-gray-500 font-bold">dias</span>
                        </h3>
                        <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">Ageing (Faturamento ➔ Entrega)</p>
                    </div>

                    <div className="card shadow-xs hover:shadow-md transition-all duration-300">
                        <div className="flex items-center justify-between mb-3">
                            <div className="bg-red-500 p-3 rounded-lg text-white">
                                <AlertTriangle className="w-6 h-6" />
                            </div>
                            <span className="text-xs font-semibold text-red-600 bg-red-50 px-2.5 py-1 rounded-full border border-red-200">
                                Atenção Requerida
                            </span>
                        </div>
                        <h3 className="text-2xl font-extrabold text-gray-900 mb-1">
                            {alerts.total_alerts}
                        </h3>
                        <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">Alertas de SLA / Produção</p>
                    </div>
                </div>

                {/* Charts Grid */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* Portfolio by Unit */}
                    <div className="card">
                        <h3 className="text-base font-bold text-gray-900 mb-4 flex items-center gap-2 border-b border-gray-100 pb-2">
                            <span>💼</span> Portfólio por Unidade de Negócio (Faturamento Total)
                        </h3>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-center">
                            <div className="h-64">
                                <ResponsiveContainer width="100%" height="100%">
                                    <PieChart>
                                        <Pie
                                            data={portfolioChartData}
                                            cx="50%"
                                            cy="50%"
                                            labelLine={false}
                                            outerRadius={80}
                                            fill="#8884d8"
                                            dataKey="value"
                                        >
                                            {portfolioChartData.map((entry, index) => (
                                                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                            ))}
                                        </Pie>
                                        <Tooltip formatter={(value) => formatCurrency(value)} />
                                    </PieChart>
                                </ResponsiveContainer>
                            </div>
                            <div className="space-y-2.5">
                                {portfolioChartData.map((item, idx) => (
                                    <div key={idx} className="flex justify-between items-center bg-gray-50 p-2.5 rounded-lg border border-gray-200">
                                        <div className="flex items-center gap-2">
                                            <div className="w-3.5 h-3.5 rounded-full" style={{ backgroundColor: COLORS[idx % COLORS.length] }} />
                                            <span className="text-xs font-bold text-gray-700">{item.name}</span>
                                        </div>
                                        <span className="text-xs font-mono font-bold text-gray-950">{formatCurrency(item.value)}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>

                    {/* Margin by Unit */}
                    <div className="card">
                        <h3 className="text-base font-bold text-gray-900 mb-4 flex items-center gap-2 border-b border-gray-100 pb-2">
                            <span>📊</span> Margem de Contribuição por Unidade
                        </h3>
                        {isMarginMasked ? (
                            <div className="h-64 flex flex-col items-center justify-center bg-gray-50 border border-dashed border-gray-300 rounded-lg p-6 text-center">
                                <div className="flex items-center gap-2 text-amber-600 mb-2">
                                    <Lock className="w-5 h-5 animate-pulse" />
                                    <h4 className="font-bold text-gray-800 text-sm">Acesso restrito à diretoria</h4>
                                </div>
                                <p className="text-xs text-gray-500 mt-1 max-w-xs">
                                    Informações financeiras confidenciais. Apenas usuários com perfil de diretoria possuem acesso a estas métricas.
                                </p>
                            </div>
                        ) : (
                            <div className="h-64">
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={marginChartData}>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                                        <XAxis dataKey="name" tick={{ fill: '#4b5563', fontSize: 11, fontWeight: 'bold' }} />
                                        <YAxis tick={{ fill: '#6b7280', fontSize: 10 }} />
                                        <Tooltip formatter={(value, name) => name === 'Margem %' ? `${value}%` : formatCurrency(value)} />
                                        <Legend />
                                        <Bar dataKey="Margem Absoluta" fill="#10b981" name="Margem Absoluta" />
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        )}
                    </div>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Billing Status */}
                    <div className="card lg:col-span-1">
                        <h3 className="text-base font-bold text-gray-900 mb-4 flex items-center gap-2 border-b border-gray-100 pb-2">
                            <span>📅</span> Status de Faturamento
                        </h3>
                        <div className="h-56">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={billingChartData}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                                    <XAxis dataKey="name" tick={{ fill: '#4b5563', fontSize: 11, fontWeight: 'bold' }} />
                                    <YAxis tick={{ fill: '#6b7280', fontSize: 10 }} />
                                    <Tooltip formatter={(value) => formatCurrency(value)} />
                                    <Bar dataKey="Valor" fill="#f59e0b" name="Faturamento Previsto">
                                        <Cell fill="#f59e0b" />
                                        <Cell fill="#8b5cf6" />
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                        <div className="grid grid-cols-2 gap-4 mt-2">
                            <div className="bg-amber-50 border border-amber-200 rounded-lg p-2.5 text-center">
                                <span className="text-[10px] text-amber-700 font-bold uppercase tracking-wider block">Mês Atual</span>
                                <span className="text-sm font-mono font-bold text-amber-950">{formatCurrency(billing.current_month)}</span>
                            </div>
                            <div className="bg-purple-50 border border-purple-200 rounded-lg p-2.5 text-center">
                                <span className="text-[10px] text-purple-700 font-bold uppercase tracking-wider block">Próximo Mês</span>
                                <span className="text-sm font-mono font-bold text-purple-950">{formatCurrency(billing.next_month)}</span>
                            </div>
                        </div>
                    </div>

                    {/* Sales Ranking Table */}
                    <div className="card lg:col-span-2">
                        <h3 className="text-base font-bold text-gray-900 mb-4 flex items-center gap-2 border-b border-gray-100 pb-2">
                            <UsersIcon className="w-5 h-5 text-gray-500" />
                            Ranking de Vendas por Vendedor
                        </h3>
                        <div className="overflow-auto max-h-[268px] border border-gray-200 rounded-lg">
                            <table className="w-full text-xs text-left">
                                <thead className="bg-gray-100 text-gray-700 uppercase sticky top-0">
                                    <tr>
                                        <th className="py-2.5 px-4 font-bold">Posição</th>
                                        <th className="py-2.5 px-4 font-bold">Vendedor</th>
                                        <th className="py-2.5 px-4 text-right font-bold">Valor Total Vendido</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {salesRank.length === 0 ? (
                                        <tr>
                                            <td colSpan={3} className="py-8 text-center text-gray-500 italic">
                                                Nenhum dado de vendas disponível
                                            </td>
                                        </tr>
                                    ) : (
                                        salesRank.map((rank, index) => (
                                            <tr key={index} className="border-b border-gray-100 hover:bg-gray-50 transition-colors">
                                                <td className="py-2 px-4 font-bold text-gray-500">
                                                    #{index + 1}
                                                </td>
                                                <td className="py-2 px-4 font-semibold text-gray-800">
                                                    {rank.salesperson}
                                                </td>
                                                <td className="py-2 px-4 text-right font-mono font-bold text-green-700">
                                                    {formatCurrency(rank.total_value)}
                                                </td>
                                            </tr>
                                        ))
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                {/* Alerts List */}
                <div className="card">
                    <h3 className="text-base font-bold text-gray-900 mb-4 flex items-center gap-2 border-b border-gray-100 pb-2">
                        <AlertTriangle className="w-5 h-5 text-red-500" />
                        Alertas Ativos (Estoque / SLA de Entrega)
                    </h3>
                    <div className="overflow-auto max-h-[300px] border border-gray-200 rounded-lg">
                        <table className="w-full text-xs text-left">
                            <thead className="bg-gray-100 text-gray-700 uppercase sticky top-0">
                                <tr>
                                    <th className="py-2.5 px-4 font-bold">Pedido</th>
                                    <th className="py-2.5 px-4 font-bold">Cliente</th>
                                    <th className="py-2.5 px-4 font-bold">Tipo de Alerta</th>
                                    <th className="py-2.5 px-4 font-bold">Descrição da Pendência</th>
                                    <th className="py-2.5 px-4 font-bold text-center">Entrega Programada</th>
                                    <th className="py-2.5 px-4 text-center font-bold">Atraso</th>
                                </tr>
                            </thead>
                            <tbody>
                                {alerts.details.length === 0 ? (
                                    <tr>
                                        <td colSpan={6} className="py-8 text-center text-green-600 font-bold bg-green-50">
                                            ✓ Todos os prazos em dia. Nenhum gargalo operacional detectado!
                                        </td>
                                    </tr>
                                ) : (
                                    alerts.details.map((alert, index) => (
                                        <tr key={index} className="border-b border-gray-100 hover:bg-red-50/30 transition-colors">
                                            <td className="py-2.5 px-4 font-bold text-gray-900">
                                                {alert.po_number}
                                            </td>
                                            <td className="py-2.5 px-4 font-semibold text-gray-700">
                                                {alert.client_name}
                                            </td>
                                            <td className="py-2.5 px-4">
                                                <span className={`inline-flex items-center px-2 py-0.5 rounded-full font-bold uppercase ${
                                                    alert.alert_type === 'SLA_BREACH' 
                                                        ? 'bg-red-100 text-red-800 border border-red-200' 
                                                        : 'bg-orange-100 text-orange-800 border border-orange-200'
                                                }`}>
                                                    {alert.alert_type === 'SLA_BREACH' ? 'SLA Vencido' : 'Atraso PCP'}
                                                </span>
                                            </td>
                                            <td className="py-2.5 px-4 font-medium text-gray-800">
                                                {alert.message}
                                            </td>
                                            <td className="py-2.5 px-4 text-center font-semibold text-gray-800">
                                                {alert.expected_delivery_date}
                                            </td>
                                            <td className="py-2.5 px-4 text-center font-bold font-mono text-red-600">
                                                {alert.days_past} dias
                                            </td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    )
}

export default DashboardPage
