import React, { useState } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useNotifications } from '../context/NotificationContext'
import {
    LayoutDashboard,
    Kanban,
    Upload,
    LogOut,
    Menu,
    X,
    User,
    DollarSign
} from 'lucide-react'

const Layout = () => {
    const [sidebarOpen, setSidebarOpen] = useState(true)
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
        { path: '/costs', icon: DollarSign, label: 'Custos (MASTER)', badge: 'costs', masterOnly: true },
    ]

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
                        // Hide MASTER-only items if user is not MASTER
                        if (item.masterOnly && user?.role !== 'MASTER') {
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
                        onClick={handleLogout}
                        className={`mt-3 w-full flex items-center gap-3 px-3 py-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors ${!sidebarOpen && 'justify-center'
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
        </div>
    )
}

export default Layout
