import toast from 'react-hot-toast'

// Success toast
export const showSuccess = (message) => {
    toast.success(message, {
        duration: 3000,
        position: 'top-right',
        style: {
            background: '#10b981',
            color: '#fff',
            fontWeight: '500',
        },
        iconTheme: {
            primary: '#fff',
            secondary: '#10b981',
        },
    })
}

// Error toast
export const showError = (message) => {
    toast.error(message, {
        duration: 4000,
        position: 'top-right',
        style: {
            background: '#ef4444',
            color: '#fff',
            fontWeight: '500',
        },
        iconTheme: {
            primary: '#fff',
            secondary: '#ef4444',
        },
    })
}

// Info toast
export const showInfo = (message) => {
    toast(message, {
        duration: 3000,
        position: 'top-right',
        icon: 'ℹ️',
        style: {
            background: '#3b82f6',
            color: '#fff',
            fontWeight: '500',
        },
    })
}

// Loading toast
export const showLoading = (message) => {
    return toast.loading(message, {
        position: 'top-right',
        style: {
            background: '#6b7280',
            color: '#fff',
            fontWeight: '500',
        },
    })
}

// Dismiss toast
export const dismissToast = (toastId) => {
    toast.dismiss(toastId)
}

// Promise toast
export const showPromise = (promise, messages) => {
    return toast.promise(
        promise,
        {
            loading: messages.loading || 'Loading...',
            success: messages.success || 'Success!',
            error: messages.error || 'Error occurred',
        },
        {
            position: 'top-right',
            style: {
                fontWeight: '500',
            },
        }
    )
}
