#!/usr/bin/env python3
"""
Script to apply sprint fixes to ImportPage.jsx
"""

import re

# Read the original file
with open('frontend/src/pages/ImportPage.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update imports - add Lock, Unlock icons and useAuth
content = content.replace(
    "import { Upload, FileSpreadsheet, AlertCircle, CheckCircle, X, HelpCircle, Paperclip, Trash2, Cloud, ChevronLeft, ChevronRight, Globe, RefreshCw, DollarSign, CheckSquare, Square } from 'lucide-react'",
    "import { Upload, FileSpreadsheet, AlertCircle, CheckCircle, X, HelpCircle, Paperclip, Trash2, Cloud, ChevronLeft, ChevronRight, Globe, RefreshCw, DollarSign, CheckSquare, Square, Lock, Unlock } from 'lucide-react'"
)

content = content.replace(
    "import { useNotifications } from '../context/NotificationContext'",
    "import { useNotifications } from '../context/NotificationContext'\nimport { useAuth } from '../context/AuthContext'"
)

# 2. Add sendFinanceNotification function after STORAGE_KEY
storage_key_line = "const STORAGE_KEY = 'flexflow_staging_session'"
content = content.replace(
    storage_key_line,
    storage_key_line + """

// Mock function to send finance notification
const sendFinanceNotification = (poNumber, itemSku) => {
    console.log(`📧 EMAIL SENT TO FINANCE: PO [${poNumber}] - Item [${itemSku}] needs approval`)
    return true
}"""
)

# 3. Add finance modal state variables
content = content.replace(
    "const [showRestoreModal, setShowRestoreModal] = useState(false)",
    """const [showRestoreModal, setShowRestoreModal] = useState(false)
    const [showFinanceModal, setShowFinanceModal] = useState(false)
    const [selectedFinanceItem, setSelectedFinanceItem] = useState(null)
    const [financeJustification, setFinanceJustification] = useState('')"""
)

# 4. Add user from useAuth
content = content.replace(
    "const { refreshNotifications } = useNotifications()",
    """const { refreshNotifications } = useNotifications()
    const { user } = useAuth()"""
)

# 5. Add console logs to session persistence - Save
old_save = """    // Session persistence: Save to localStorage whenever stagingData changes
    useEffect(() => {
        if (stagingData) {
            try {
                localStorage.setItem(STORAGE_KEY, JSON.stringify({
                    stagingData,
                    selectedPOIndex,
                    currentPage,
                    timestamp: new Date().toISOString()
                }))
            } catch (error) {
                console.error('Failed to save session:', error)
            }
        } else {
            localStorage.removeItem(STORAGE_KEY)
        }
    }, [stagingData, selectedPOIndex, currentPage])"""

new_save = """    // Session persistence: Save to localStorage whenever stagingData changes
    useEffect(() => {
        if (stagingData) {
            try {
                console.log('💾 [Session] Saving session to localStorage:', {
                    timestamp: new Date().toISOString(),
                    selectedPOIndex,
                    currentPage,
                    totalPOs: stagingData.po_list?.length || 0
                })
                localStorage.setItem(STORAGE_KEY, JSON.stringify({
                    stagingData,
                    selectedPOIndex,
                    currentPage,
                    timestamp: new Date().toISOString()
                }))
                console.log('✅ [Session] Session saved successfully')
            } catch (error) {
                console.error('❌ [Session] Failed to save session:', error)
            }
        } else {
            console.log('🗑️ [Session] Removing session from localStorage')
            localStorage.removeItem(STORAGE_KEY)
        }
    }, [stagingData, selectedPOIndex, currentPage])"""

content = content.replace(old_save, new_save)

# 6. Add console logs to session restoration - Check
old_check = """    // Session restoration: Check for existing session on mount
    useEffect(() => {
        try {
            const savedSession = localStorage.getItem(STORAGE_KEY)
            if (savedSession) {
                const parsed = JSON.parse(savedSession)
                const sessionAge = Date.now() - new Date(parsed.timestamp).getTime()
                const maxAge = 24 * 60 * 60 * 1000 // 24 hours

                if (sessionAge < maxAge) {
                    setShowRestoreModal(true)
                } else {
                    localStorage.removeItem(STORAGE_KEY)
                }
            }
        } catch (error) {
            console.error('Failed to check for saved session:', error)
            localStorage.removeItem(STORAGE_KEY)
        }
    }, [])"""

new_check = """    // Session restoration: Check for existing session on mount
    useEffect(() => {
        console.log('🔍 [Session] Checking for saved session on mount...')
        try {
            const savedSession = localStorage.getItem(STORAGE_KEY)
            if (savedSession) {
                console.log('📦 [Session] Found saved session in localStorage')
                const parsed = JSON.parse(savedSession)
                const sessionAge = Date.now() - new Date(parsed.timestamp).getTime()
                const maxAge = 24 * 60 * 60 * 1000 // 24 hours
                
                console.log('⏰ [Session] Session age:', Math.floor(sessionAge / 1000 / 60), 'minutes')

                if (sessionAge < maxAge) {
                    console.log('✅ [Session] Session is valid, showing restore modal')
                    setShowRestoreModal(true)
                } else {
                    console.log('⏳ [Session] Session expired, removing from localStorage')
                    localStorage.removeItem(STORAGE_KEY)
                }
            } else {
                console.log('ℹ️ [Session] No saved session found')
            }
        } catch (error) {
            console.error('❌ [Session] Failed to check for saved session:', error)
            localStorage.removeItem(STORAGE_KEY)
        }
    }, [])"""

content = content.replace(old_check, new_check)

# 7. Add console logs to handleRestoreSession
old_restore = """    const handleRestoreSession = () => {
        try {
            const savedSession = localStorage.getItem(STORAGE_KEY)
            if (savedSession) {
                const parsed = JSON.parse(savedSession)
                setStagingData(parsed.stagingData)
                setSelectedPOIndex(parsed.selectedPOIndex || 0)
                setCurrentPage(parsed.currentPage || 1)
                showSuccess('Sessão restaurada com sucesso!')
            }
        } catch (error) {
            console.error('Failed to restore session:', error)
            showError('Erro ao restaurar sessão')
            localStorage.removeItem(STORAGE_KEY)
        }
        setShowRestoreModal(false)
    }"""

new_restore = """    const handleRestoreSession = () => {
        console.log('🔄 [Session] Restoring session...')
        try {
            const savedSession = localStorage.getItem(STORAGE_KEY)
            if (savedSession) {
                const parsed = JSON.parse(savedSession)
                console.log('📥 [Session] Loaded session data:', {
                    totalPOs: parsed.stagingData?.po_list?.length || 0,
                    selectedPOIndex: parsed.selectedPOIndex,
                    currentPage: parsed.currentPage
                })
                setStagingData(parsed.stagingData)
                setSelectedPOIndex(parsed.selectedPOIndex || 0)
                setCurrentPage(parsed.currentPage || 1)
                console.log('✅ [Session] Session restored successfully')
                showSuccess('Sessão restaurada com sucesso!')
            }
        } catch (error) {
            console.error('❌ [Session] Failed to restore session:', error)
            showError('Erro ao restaurar sessão')
            localStorage.removeItem(STORAGE_KEY)
        }
        setShowRestoreModal(false)
    }"""

content = content.replace(old_restore, new_restore)

# 8. Add console log to handleDiscardSession
old_discard = """    const handleDiscardSession = () => {
        localStorage.removeItem(STORAGE_KEY)
        setShowRestoreModal(false)
    }"""

new_discard = """    const handleDiscardSession = () => {
        console.log('🗑️ [Session] Discarding saved session')
        localStorage.removeItem(STORAGE_KEY)
        setShowRestoreModal(false)
    }"""

content = content.replace(old_discard, new_discard)

print("[OK] All changes applied successfully!")
print("Writing updated file...")

# Write the updated content
with open('frontend/src/pages/ImportPage.jsx', 'w', encoding='utf-8') as f:
    f.write(content)

print("[OK] File updated: frontend/src/pages/ImportPage.jsx")
print("\nNext steps:")
print("1. Apply price validation fixes")
print("2. Add finance gate fields to item structure")
print("3. Update validation logic")
print("4. Add finance gate UI and modal")
