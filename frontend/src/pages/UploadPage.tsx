import { useState } from 'react';
import importLogo from '../assets/inbox.svg';
import UploadFile from '../components/UploadFile';

export default function UploadPage() {
    const [isImporting, setIsImporting] = useState(false);

    const handleExport = () => {
        // CSV export will be implemented separately.
    };

    const handleCalculate = () => {
        // PDF submission and report-status polling will be implemented next.
    };

    return (
        <div className="w-screen mx-auto py-10 text-center">
            <h1 className="text-4xl">
                Upload Your Statements
            </h1>

            <p className="max-w-2xl mx-auto py-6">
                Upload your PDF statements to start building your personal
                inflation index.
            </p>

            <div className="w-11/12 md:w-3/4 mx-auto border-4 rounded-lg border-dashed border-[#00C3D0] p-4">
                <div className="flex flex-col gap-6">
                    <div className="flex flex-wrap items-center justify-center gap-4">
                        <div className="flex items-center gap-4">
                            <img
                                src={importLogo}
                                alt=""
                                height={50}
                                width={50}
                            />
                            <span className="text-2xl font-bold">
                                Import Statements
                            </span>
                        </div>

                        <button
                            type="button"
                            onClick={() => setIsImporting(true)}
                            className="bg-[#33B4A8] rounded-xl text-white font-bold px-8 py-3"
                        >
                            Select PDFs
                        </button>

                        <button
                            type="button"
                            onClick={handleExport}
                            className="bg-[#33B4A8] rounded-xl text-white font-bold px-8 py-3"
                        >
                            Export CSV
                        </button>
                    </div>

                    <div className="bg-white/35 border-2 rounded-lg border-dashed border-[#00C3D0] p-4">
                        <UploadFile
                            isImporting={isImporting}
                            onImportComplete={() => setIsImporting(false)}
                        />
                    </div>
                </div>
            </div>

            <button
                type="button"
                onClick={handleCalculate}
                className="inline-block my-10 bg-[#33B4A8] rounded-xl text-white font-bold px-10 py-4"
            >
                Calculate My Results
            </button>
        </div>
    );
}
