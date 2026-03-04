import importLogo from '../assets/inbox.svg';
import folderLogo from '../assets/folder.svg';

export default function CalculatePage() {

    const handleImport = () => {

    }

    const handleExport = () => {

    }

    const handleCalculate = () => {

    }

    return (
            <div className="w-screen mx-auto py-10">
                <h1 className="text-4xl">
                    Find Your Inflation <br/> with ease
                </h1>
                <p className="max-w-2xl mx-auto py-10">
                    Upload your CSV of past purchases to
                    calculate your personal inflation rate, 
                    then download the updated file with your results.
                </p>   
                <div className="w-1/2 mx-auto border-4 rounded-lg border-dashed border-[#00C3D0] p-4">
                    <div className="flex flex-col justify-center">
                        <div className="flex justify-between">
                            <div className='flex space-x-4'>
                                <img src={importLogo} alt='inbox' height={50} width={50}/>
                                <span className='text-2xl font-bold py-4'>
                                    Import/Export Data
                                </span>
                            </div>
                            <button onClick={handleImport} className='bg-[#33B4A8] text-2xl rounded-xl text-white font-bold px-20'>
                                Import CSV
                            </button>
                            <button onClick={handleExport} className='bg-[#33B4A8] text-2xl rounded-xl text-white font-bold px-20'>
                                Export CSV
                            </button>
                        </div>
                        <div className='bg-white bg-opacity-35 flex flex-col max-w-7xl border-4 rounded-lg border-dashed border-[#00C3D0] p-4 my-10'>
                            <div className='flex space-x-4 justify-center my-8'>
                                <img src={folderLogo} alt='folder'/>
                                <span className='py-4 text-2xl font-bold'>
                                    Drag & drop CSV file here
                                </span>
                            </div>
                            <div>
                                <span className='text-gray-700'> 
                                    or use the import button above
                                </span>
                            </div>
                        </div>
                        
                    </div>
                </div>
                <button onClick={handleCalculate} className='inline-block my-10 bg-[#33B4A8] text-2xl rounded-xl text-white font-bold px-20 py-4'>
                    Calculate my results
                </button>
            </div>
    )
}