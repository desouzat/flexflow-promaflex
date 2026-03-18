import React from 'react'
import { Upload, FileSpreadsheet, AlertCircle } from 'lucide-react'

const ImportPage = () => {
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
            <div className="flex-1 p-6">
                <div className="max-w-4xl mx-auto">
                    {/* Upload Area */}
                    <div className="card mb-6">
                        <div className="border-2 border-dashed border-gray-300 rounded-lg p-12 text-center hover:border-primary-500 transition-colors cursor-pointer">
                            <Upload className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                            <h3 className="text-lg font-semibold text-gray-900 mb-2">
                                Drop your Excel file here
                            </h3>
                            <p className="text-sm text-gray-600 mb-4">
                                or click to browse
                            </p>
                            <button className="btn-primary">
                                Select File
                            </button>
                        </div>
                    </div>

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
