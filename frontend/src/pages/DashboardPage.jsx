import React from 'react'
import { BarChart3, TrendingUp, Package, DollarSign } from 'lucide-react'

const DashboardPage = () => {
    const stats = [
        {
            label: 'Total POs',
            value: '0',
            icon: Package,
            color: 'bg-blue-500',
            change: '+0%',
        },
        {
            label: 'Total Value',
            value: 'R$ 0,00',
            icon: DollarSign,
            color: 'bg-green-500',
            change: '+0%',
        },
        {
            label: 'Pending Approval',
            value: '0',
            icon: TrendingUp,
            color: 'bg-yellow-500',
            change: '0',
        },
        {
            label: 'Delivered',
            value: '0',
            icon: BarChart3,
            color: 'bg-purple-500',
            change: '+0%',
        },
    ]

    return (
        <div className="h-full flex flex-col">
            {/* Header */}
            <div className="bg-white border-b border-gray-200 px-6 py-4">
                <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
                <p className="text-sm text-gray-600 mt-1">
                    Overview of purchase order metrics
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

                {/* Charts Placeholder */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <div className="card">
                        <h3 className="text-lg font-semibold text-gray-900 mb-4">
                            POs by Status
                        </h3>
                        <div className="h-64 flex items-center justify-center bg-gray-50 rounded-lg">
                            <p className="text-gray-500">Chart coming soon</p>
                        </div>
                    </div>

                    <div className="card">
                        <h3 className="text-lg font-semibold text-gray-900 mb-4">
                            Monthly Trends
                        </h3>
                        <div className="h-64 flex items-center justify-center bg-gray-50 rounded-lg">
                            <p className="text-gray-500">Chart coming soon</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}

export default DashboardPage
