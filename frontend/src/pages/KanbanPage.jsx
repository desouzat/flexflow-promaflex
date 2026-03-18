import React, { useState, useEffect } from 'react'
import KanbanColumn from '../components/kanban/KanbanColumn'
import api from '../utils/api'
import { RefreshCw, Filter, Search } from 'lucide-react'

const KanbanPage = () => {
    const [pos, setPOs] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const [searchTerm, setSearchTerm] = useState('')

    const columns = [
        { status: 'pending', title: 'Pending', color: 'yellow' },
        { status: 'approved', title: 'Approved', color: 'green' },
        { status: 'in_transit', title: 'In Transit', color: 'blue' },
        { status: 'delivered', title: 'Delivered', color: 'purple' },
        { status: 'rejected', title: 'Rejected', color: 'red' },
    ]

    const fetchPOs = async () => {
        try {
            setLoading(true)
            setError(null)
            const response = await api.get('/kanban/pos')
            setPOs(response.data)
        } catch (err) {
            setError(err.response?.data?.detail || 'Failed to load purchase orders')
            console.error('Error fetching POs:', err)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchPOs()
    }, [])

    const handleCardClick = (po) => {
        console.log('PO clicked:', po)
        // TODO: Open modal with PO details
    }

    const filterPOs = (status) => {
        return pos.filter((po) => {
            const matchesStatus = po.status === status
            const matchesSearch = searchTerm
                ? po.po_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
                po.supplier_name.toLowerCase().includes(searchTerm.toLowerCase())
                : true
            return matchesStatus && matchesSearch
        })
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center h-full">
                <div className="text-center">
                    <div className="w-16 h-16 border-4 border-primary-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                    <p className="text-gray-600">Loading purchase orders...</p>
                </div>
            </div>
        )
    }

    if (error) {
        return (
            <div className="flex items-center justify-center h-full">
                <div className="text-center max-w-md">
                    <div className="text-red-600 text-5xl mb-4">⚠️</div>
                    <h2 className="text-xl font-semibold text-gray-900 mb-2">Error Loading Data</h2>
                    <p className="text-gray-600 mb-4">{error}</p>
                    <button onClick={fetchPOs} className="btn-primary">
                        Try Again
                    </button>
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
                        <h1 className="text-2xl font-bold text-gray-900">Kanban Board</h1>
                        <p className="text-sm text-gray-600 mt-1">
                            Manage and track purchase orders
                        </p>
                    </div>
                    <div className="flex items-center gap-3">
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                            <input
                                type="text"
                                placeholder="Search POs..."
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                                className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                            />
                        </div>
                        <button
                            onClick={fetchPOs}
                            className="btn-secondary flex items-center gap-2"
                            aria-label="Refresh"
                        >
                            <RefreshCw className="w-5 h-5" />
                            Refresh
                        </button>
                        <button className="btn-secondary flex items-center gap-2">
                            <Filter className="w-5 h-5" />
                            Filter
                        </button>
                    </div>
                </div>
            </div>

            {/* Kanban Board */}
            <div className="flex-1 overflow-x-auto overflow-y-hidden p-6">
                <div className="flex gap-4 h-full">
                    {columns.map((column) => (
                        <KanbanColumn
                            key={column.status}
                            title={column.title}
                            status={column.status}
                            pos={filterPOs(column.status)}
                            onCardClick={handleCardClick}
                            color={column.color}
                        />
                    ))}
                </div>
            </div>
        </div>
    )
}

export default KanbanPage
