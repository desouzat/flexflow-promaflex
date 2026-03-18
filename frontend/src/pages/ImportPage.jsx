import React, { useState, useRef } from 'react'
import { Upload, FileSpreadsheet, AlertCircle, CheckCircle, X } from 'lucide-react'
import api from '../utils/api'
import { showSuccess, showError, showLoading, dismissToast } from '../utils/toast'
import { useNotifications } from '../context/NotificationContext'

const ImportPage = () => {
    const [selectedFile, setSelectedFile] = useState(null)
    const [uploading, setUploading] = useState(false)
    const [uploadResult, setUploadResult] = useState(null)
    const fileInputRef = useRef(null)
    const { refreshNotifications } = useNotifications()

    const handleFileSelect = (e) => {
        const file = e.target.files?.[0]
        if (file) {
            // Validate file type
            const validTypes = [
                'application/vnd.ms-excel',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            ]
            if (!validTypes.includes(file.type) && !file.name.match(/\.(xlsx|xls)$/)) {
                showError('Please select a valid Excel file (.xlsx or .xls)')
                return
            }

            // Validate file size (10MB)
            if (file.size > 10 * 1024 * 1024) {
                showError('File size must be less than 10MB')
                return
            }

            setSelectedFile(file)
            setUploadResult(null)
        }
    }

    const handleUpload = async () => {
        if (!selectedFile) {
            showError('Please select a file first')
            return
        }

        const formData = new FormData()
        formData.append('file', selectedFile)

        setUploading(true)
        const toastId = showLoading('Uploading and processing file...')

        try {
            const response = await api.post('/import/upload', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
            })

            dismissToast(toastId)
            setUploadResult(response.data)

            if (response.data.success_count > 0) {
                showSuccess(
                    `Successfully imported ${response.data.success_count} purchase order(s)`
                )
                refreshNotifications()
            }

            if (response.data.error_count > 0) {
                showError(
                    `${response.data.error_count} row(s) failed to import. Check details below.`
                )
            }

            // Clear file selection
            setSelectedFile(null)
            if (fileInputRef.current) {
                fileInputRef.current.value = ''
            }
        } catch (error) {
            dismissToast(toastId)
            console.error('Upload error:', error)
            showError(
                error.response?.data?.detail || 'Failed to upload file. Please try again.'
            )
        } finally {
            setUploading(false)
        }
    }

    const handleDragOver = (e) => {
        e.preventDefault()
        e.stopPropagation()
    }

    const handleDrop = (e) => {
        e.preventDefault()
        e.stopPropagation()

        const file = e.dataTransfer.files?.[0]
        if (file) {
            // Create a synthetic event for handleFileSelect
            const syntheticEvent = {
                target: {
                    files: [file]
                }
            }
            handleFileSelect(syntheticEvent)
        }
    }

    return (
        <div className="h-full flex flex-col">
            {/* Header */}
            <div className="bg-white border-b border-gray-200 px-6 py-4">
                <h1 className="text-2xl font-bold text-gray-900">Import Purchase Orders</h1>
                <p className="text-sm text-gray-600 mt-1">
                    Upload Excel files to import purchase orders
                </p>
            </div>

            {/* Content */}
            <div className="flex-1 p-6 overflow-auto">
                <div className="max-w-4xl mx-auto">
                    {/* Upload Area */}
                    <div className="card mb-6">
                        <div
                            onDragOver={handleDragOver}
                            onDrop={handleDrop}
                            onClick={() => fileInputRef.current?.click()}
                            className="border-2 border-dashed border-gray-300 rounded-lg p-12 text-center hover:border-primary-500 transition-colors cursor-pointer"
                        >
                            <Upload className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                            <h3 className="text-lg font-semibold text-gray-900 mb-2">
                                Drop your Excel file here
                            </h3>
                            <p className="text-sm text-gray-600 mb-4">
                                or click to browse
                            </p>
                            <input
                                ref={fileInputRef}
                                type="file"
                                accept=".xlsx,.xls"
                                onChange={handleFileSelect}
                                className="hidden"
                            />
                            {selectedFile ? (
                                <div className="inline-flex items-center gap-2 px-4 py-2 bg-primary-50 text-primary-700 rounded-lg">
                                    <FileSpreadsheet className="w-5 h-5" />
                                    <span className="font-medium">{selectedFile.name}</span>
                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation()
                                            setSelectedFile(null)
                                            if (fileInputRef.current) {
                                                fileInputRef.current.value = ''
                                            }
                                        }}
                                        className="ml-2 text-primary-600 hover:text-primary-800"
                                    >
                                        <X className="w-4 h-4" />
                                    </button>
                                </div>
                            ) : (
                                <button className="btn-primary" onClick={(e) => e.stopPropagation()}>
                                    Select File
                                </button>
                            )}
                        </div>

                        {selectedFile && (
                            <div className="mt-4 flex justify-end">
                                <button
                                    onClick={handleUpload}
                                    disabled={uploading}
                                    className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    {uploading ? (
                                        <>
                                            <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin mr-2" />
                                            Uploading...
                                        </>
                                    ) : (
                                        <>
                                            <Upload className="w-5 h-5 mr-2" />
                                            Upload and Import
                                        </>
                                    )}
                                </button>
                            </div>
                        )}
                    </div>

                    {/* Upload Result */}
                    {uploadResult && (
                        <div className="card mb-6">
                            <h3 className="text-lg font-semibold text-gray-900 mb-4">
                                Import Results
                            </h3>
                            <div className="space-y-3">
                                <div className="flex items-center justify-between p-3 bg-green-50 rounded-lg">
                                    <div className="flex items-center gap-2">
                                        <CheckCircle className="w-5 h-5 text-green-600" />
                                        <span className="text-sm font-medium text-green-900">
                                            Successfully Imported
                                        </span>
                                    </div>
                                    <span className="text-lg font-bold text-green-600">
                                        {uploadResult.success_count}
                                    </span>
                                </div>

                                {uploadResult.error_count > 0 && (
                                    <div className="flex items-center justify-between p-3 bg-red-50 rounded-lg">
                                        <div className="flex items-center gap-2">
                                            <AlertCircle className="w-5 h-5 text-red-600" />
                                            <span className="text-sm font-medium text-red-900">
                                                Failed to Import
                                            </span>
                                        </div>
                                        <span className="text-lg font-bold text-red-600">
                                            {uploadResult.error_count}
                                        </span>
                                    </div>
                                )}

                                {uploadResult.errors && uploadResult.errors.length > 0 && (
                                    <div className="mt-4">
                                        <h4 className="text-sm font-semibold text-gray-900 mb-2">
                                            Error Details:
                                        </h4>
                                        <div className="space-y-2 max-h-60 overflow-y-auto">
                                            {uploadResult.errors.map((error, index) => (
                                                <div
                                                    key={index}
                                                    className="text-xs text-red-700 bg-red-50 p-2 rounded"
                                                >
                                                    Row {error.row}: {error.message}
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}

                    {/* Instructions */}
                    <div className="card">
                        <div className="flex items-start gap-3 mb-4">
                            <FileSpreadsheet className="w-6 h-6 text-primary-600 flex-shrink-0" />
                            <div>
                                <h3 className="font-semibold text-gray-900 mb-2">
                                    File Requirements
                                </h3>
                                <ul className="text-sm text-gray-600 space-y-1 list-disc list-inside">
                                    <li>Excel format (.xlsx, .xls)</li>
                                    <li>Maximum file size: 10MB</li>
                                    <li>Required columns: PO Number, Supplier, Total Value, Delivery Date</li>
                                </ul>
                            </div>
                        </div>

                        <div className="flex items-start gap-3 pt-4 border-t border-gray-200">
                            <AlertCircle className="w-6 h-6 text-yellow-600 flex-shrink-0" />
                            <div>
                                <h3 className="font-semibold text-gray-900 mb-2">
                                    Important Notes
                                </h3>
                                <ul className="text-sm text-gray-600 space-y-1 list-disc list-inside">
                                    <li>Duplicate PO numbers will be skipped</li>
                                    <li>Invalid data will be reported after upload</li>
                                    <li>All dates should be in YYYY-MM-DD format</li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}

export default ImportPage
