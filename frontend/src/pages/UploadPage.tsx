import {useState } from 'react';
import importLogo from '../assets/inbox.svg';
import UploadFile from '../components/UploadFile';

export default function UploadPage() {
    const [ isImporting, setIsImporting ] = useState(false);

    const handleImport = () => {
        setIsImporting(true);
    };

    const handleExport = () => {

    };

    const handleCalculate = () => {
        // check if the user uploaded the file
        // see if the results is ready
        // have the user navigate to the results
    };
url /
    return (
            <div className="w-screen mx-auto py-10">
                <h1 className="text-4xl">
                    // content comes from API.
                </h1>
                <p className="max-w-2xl mx-auto py-10">
// content comes from API
                </p>   
                <div className="w-1/2 mx-auto border-4 rounded-lg border-dashed border-[#00C3D0] p-4">
                    <div className="flex flex-col justify-center">
                        <div className="flex justify-between">
                            <div className='flex space-x-4'>
                                <img src={importLogo} alt='inbox' height={50} width={50}/>
                                <span className='text-2xl font-bold py-4'>
// may come from API or come from the protocol of the API                                    Import/Export Data
                                </span>
                            </div>
                            <button onClick={handleImport} className='bg-[#33B4A8] text-2xl rounded-xl text-white font-bold px-20'>
//  will come from API                               Import CSV
                            </button>
                            <button onClick={handleExport} className='bg-[#33B4A8] text-2xl rounded-xl text-white font-bold px-20'>
// will come API                                Export CSV
                            </button>
                        </div>
                        <div className='bg-white bg-opacity-35 flex flex-col max-w-7xl border-4 rounded-lg border-dashed border-[#00C3D0] p-4 my-10'>
                            <UploadFile 
                                isImporting={isImporting}
                                onImportComplete={() => setIsImporting(false)}    
                            />
                        </div>
                    </div>
                </div>
                <button onClick={handleCalculate} className='inline-block my-10 bg-[#33B4A8] text-2xl rounded-xl text-white font-bold px-20 py-4'>
// will come from the API                    Calculate my results
                </button>
            </div>
    )
}