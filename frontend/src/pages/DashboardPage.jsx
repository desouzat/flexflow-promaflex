import React, { useState, useEffect } from 'react'
import { BarChart3, TrendingUp, Package, DollarSign, Clock } from 'lucide-react'
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

const DashboardPage = () => {
    const [loading, setLoading] = useState(true)
    const [dashboardData, setDashboardData] = useState(null)

    useEffect(() => {
        fetchDashboardData()
    }, [])

    const fetchDashboardData = async () => {
        try {
            setLoading(true)
            const response = await api.get('/dashboard/metrics')
            const data = response.data

            // Transform backend data to frontend format
            const transformedData = {
                total_pos: data.margin?.po_count || 0,
                total_value: parseFloat(data.margin?.total_value || 0),
                total_margin: parseFloat(data.margin?.total_margin || 0),
                pending_approval: data.items_by_area?.by_area?.find(a => a.area === 'Comercial')?.count || 0,
                delivered: data.items_by_area?.by_area?.find(a => a.area === 'Concluído')?.count || 0,
                area_distribution: data.items_by_area?.by_area?.map(area => ({
                    area: area.area,
                    count: area.count,
                    value: 0 // Backend doesn't provide value per area yet
                })) || [],
                margin_by_category: [], // Not yet implemented in backend
                average_lead_time: data.lead_time?.average_lead_time_days || 0,
            }

            setDashboardData(transformedData)
        } catch (error) {
            console.error('Erro ao carregar dados do dashboard:', error)
            showError('Falha ao carregar dados do dashboard')
            // Set mock data for demo
            setDashboardData(getMockData())
        } finally {
            setLoading(false)
        }
    }

    const getMockData = () => ({
        total_pos: 45,
        total_value: 1250000.50,
        pending_approval: 8,
        delivered: 28,
        area_distribution: [
            { area: 'IT', count: 15, value: 450000 },
            { area: 'Operations', count: 12, value: 380000 },
            { area: 'Marketing', count: 8, value: 220000 },
            { area: 'HR', count: 6, value: 120000 },
            { area: 'Finance', count: 4, value: 80000 },
        ],
        margin_by_category: [
            { category: 'Hardware', margin: 15.5, value: 350000 },
            { category: 'Software', margin: 25.3, value: 280000 },
            { category: 'Services', margin: 18.7, value: 420000 },
            { category: 'Supplies', margin: 12.2, value: 200000 },
        ],
        average_lead_time: 12.5,
    })

    if (loading) {
        return (
            <div className="flex items-center justify-center h-full">
                <div className="text-center">
                    <div className="w-16 h-16 border-4 border-primary-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                    <p className="text-gray-600">Carregando dashboard...</p>
                </div>
            </div>
        )
    }

    const data = dashboardData || getMockData()

    const stats = [
        {
            label: 'Total de Pedidos',
            value: (data?.total_pos ?? 0).toString(),
            icon: Package,
            color: 'bg-blue-500',
            change: `${data?.total_pos ?? 0} POs`,
        },
        {
            label: 'Valor Total',
            value: new Intl.NumberFormat('pt-BR', {
                style: 'currency',
                currency: 'BRL',
            }).format(data?.total_value ?? 0),
            icon: DollarSign,
            color: 'bg-green-500',
            change: 'Margem: ' + new Intl.NumberFormat('pt-BR', {
                style: 'currency',
                currency: 'BRL',
            }).format(data?.total_margin ?? 0),
        },
        {
            label: 'Em Comercial',
            value: (data?.pending_approval ?? 0).toString(),
            icon: TrendingUp,
            color: 'bg-yellow-500',
            change: `${data?.pending_approval ?? 0} itens`,
        },
        {
            label: 'Concluídos',
            value: (data?.delivered ?? 0).toString(),
            icon: BarChart3,
            color: 'bg-purple-500',
            change: `${data?.delivered ?? 0} itens`,
        },
    ]

    const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']

    const formatCurrency = (value) => {
        return new Intl.NumberFormat('pt-BR', {
            style: 'currency',
            currency: 'BRL',
            minimumFractionDigits: 0,
        }).format(value)
    }

    return (
        <div className="h-full flex flex-col">
            {/* Header */}
            <div className="bg-white border-b border-gray-200 px-6 py-4">
                <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
                <p className="text-sm text-gray-600 mt-1">
                    Visão geral das métricas de pedidos
                </p>
            </div>

            {/* Content */}
            <div className="flex-1 p-6 overflow-auto">
                {/* Stats Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
                    {stats.map((stat, index) => (
                        <div key={index} className="card">
                            <div className="flex items-center justify-between mb-4">
                                <div className={`${stat.color} p-3 rounded-lg`}>
                                    <stat.icon className="w-6 h-6 text-white" />
                                </div>
                                <span className="text-sm font-medium text-green-600">
                                    {stat.change}
                                </span>
                            </div>
                            <h3 className="text-2xl font-bold text-gray-900 mb-1">
                                {stat.value}
                            </h3>
                            <p className="text-sm text-gray-600">{stat.label}</p>
                        </div>
                    ))}
                </div>

                {/* Charts Grid */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
                    {/* Area Distribution Bar Chart */}
                    <div className="card">
                        <h3 className="text-lg font-semibold text-gray-900 mb-4">
                            Distribuição por Área
                        </h3>
                        <ResponsiveContainer width="100%" height={300}>
                            <BarChart data={data?.area_distribution ?? []}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                                <XAxis
                                    dataKey="area"
                                    tick={{ fill: '#6b7280', fontSize: 12 }}
                                />
                                <YAxis tick={{ fill: '#6b7280', fontSize: 12 }} />
                                <Tooltip
                                    contentStyle={{
                                        backgroundColor: '#fff',
                                        border: '1px solid #e5e7eb',
                                        borderRadius: '8px',
                                    }}
                                    formatter={(value, name) => {
                                        if (name === 'value') return formatCurrency(value)
                                        return value
                                    }}
                                />
                                <Legend />
                                <Bar dataKey="count" fill="#3b82f6" name="Quantidade" />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>

                    {/* Margin by Category Pie Chart */}
                    <div className="card">
                        <h3 className="text-lg font-semibold text-gray-900 mb-4">
                            Margem Média por Categoria
                        </h3>
                        <ResponsiveContainer width="100%" height={300}>
                            <PieChart>
                                <Pie
                                    data={data?.margin_by_category ?? []}
                                    cx="50%"
                                    cy="50%"
                                    labelLine={false}
                                    label={({ category, margin }) =>
                                        `${category}: ${margin}%`
                                    }
                                    outerRadius={100}
                                    fill="#8884d8"
                                    dataKey="margin"
                                >
                                    {(data?.margin_by_category ?? []).map((entry, index) => (
                                        <Cell
                                            key={`cell-${index}`}
                                            fill={COLORS[index % COLORS.length]}
                                        />
                                    ))}
                                </Pie>
                                <Tooltip
                                    formatter={(value) => `${value}%`}
                                    contentStyle={{
                                        backgroundColor: '#fff',
                                        border: '1px solid #e5e7eb',
                                        borderRadius: '8px',
                                    }}
                                />
                            </PieChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                {/* Lead Time Indicator */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    <div className="card lg:col-span-1">
                        <div className="flex items-center gap-4">
                            <div className="bg-indigo-500 p-4 rounded-lg">
                                <Clock className="w-8 h-8 text-white" />
                            </div>
                            <div>
                                <p className="text-sm text-gray-600 mb-1">
                                    Lead Time Médio
                                </p>
                                <h3 className="text-3xl font-bold text-gray-900">
                                    {data?.average_lead_time ?? 0}
                                    <span className="text-lg text-gray-600 ml-1">dias</span>
                                </h3>
                            </div>
                        </div>
                        <div className="mt-4 pt-4 border-t border-gray-100">
                            <p className="text-xs text-gray-500">
                                Tempo médio desde a criação até a entrega
                            </p>
                        </div>
                    </div>

                    {/* Additional Metrics */}
                    <div className="card lg:col-span-2">
                        <h3 className="text-lg font-semibold text-gray-900 mb-4">
                            Resumo de Valores por Área
                        </h3>
                        <div className="space-y-3">
                            {(data?.area_distribution ?? []).map((area, index) => (
                                <div key={index} className="flex items-center justify-between">
                                    <div className="flex items-center gap-3">
                                        <div
                                            className="w-3 h-3 rounded-full"
                                            style={{ backgroundColor: COLORS[index % COLORS.length] }}
                                        />
                                        <span className="text-sm font-medium text-gray-700">
                                            {area.area}
                                        </span>
                                    </div>
                                    <div className="flex items-center gap-4">
                                        <span className="text-sm text-gray-600">
                                            {area.count} POs
                                        </span>
                                        <span className="text-sm font-semibold text-gray-900">
                                            {formatCurrency(area.value)}
                                        </span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}

export default DashboardPage
